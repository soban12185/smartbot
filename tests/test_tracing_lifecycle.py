"""
Tests for LangSmith trace lifecycle (finalization of manual runs and the
auto-tracing LangGraph root run).

Two layers:

1. Unit tests (no network): verify the manual `trace_run` wrapper finalizes
   exactly once, records errors, is a no-op when LangSmith is unavailable,
   and that the Flask endpoints finalize their manual runs (service_search
   now calls `run.end(...)` explicitly instead of relying on GC/`__del__`).

2. Live integration tests (require real GROQ_SERPER/LangSmith keys): perform
   a genuinely new chat request and a service_search request and confirm the
   NEW root runs ("LangGraph" and "service_search") arrive in LangSmith
   finalized (end_time set, status success) with no duplicate updates. These
   are skipped automatically when LangSmith/Groq keys are absent.
"""
import os
import sys
import time
import uuid as uuid_mod
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing the app (mirrors tests/test_api.py)
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("SERPER_API_KEY", "test_key")
os.environ.setdefault("JINA_API_KEY", "test_key")

# Mock Neo4j before importing main
with patch("main.Neo4jGraph", autospec=True):
    import main
    from main import app

from tracing import trace_run  # noqa: E402


class FakeLangSmithClient:
    """In-memory stand-in for langsmith.Client used by _TraceRun."""

    def __init__(self):
        self.created = []
        self.updated = []  # list of (run_id, kwargs)
        self.flushed = 0

    def create_run(self, **kwargs):
        self.created.append(kwargs)

    def update_run(self, run_id, **kwargs):
        self.updated.append((run_id, kwargs))

    def flush(self):
        self.flushed += 1


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Unit tests: manual trace_run lifecycle
# ---------------------------------------------------------------------------

class TestManualRunLifecycle:
    def test_manual_run_end_finalizes_exactly_once(self):
        fake = FakeLangSmithClient()
        with patch("tracing._get_client", return_value=fake):
            with trace_run("op_test", run_type="chain", inputs={"q": 1}) as run:
                run.add_outputs({"a": 1})
                run.end(outputs={"a": 2, "b": 3})

        assert len(fake.created) == 1
        assert len(fake.updated) == 1
        rid, upd = fake.updated[0]
        assert rid == fake.created[0]["id"]
        assert upd["end_time"] is not None
        assert upd["outputs"] == {"a": 2, "b": 3}
        assert "error" not in upd

    def test_manual_run_error_records_error_and_reraises(self):
        fake = FakeLangSmithClient()
        with patch("tracing._get_client", return_value=fake):
            with pytest.raises(RuntimeError, match="boom"):
                with trace_run("op_fail", inputs={}) as run:
                    raise RuntimeError("boom")

        assert len(fake.updated) == 1
        _, upd = fake.updated[0]
        assert upd["error"] == "boom"
        assert upd["end_time"] is not None

    def test_manual_run_end_is_idempotent(self):
        fake = FakeLangSmithClient()
        with patch("tracing._get_client", return_value=fake):
            with trace_run("op_idem", inputs={}) as run:
                run.end(outputs={"x": 1})
                run.end(outputs={"x": 2})

        assert len(fake.updated) == 1
        assert fake.updated[0][1]["outputs"] == {"x": 1}

    def test_trace_run_yields_none_when_langsmith_unavailable(self):
        with patch("tracing._get_client", return_value=None):
            with trace_run("op_disabled", inputs={}) as run:
                assert run is None

    def test_flush_langsmith_traces_uses_official_and_own_client(self):
        import tracing
        fake = FakeLangSmithClient()
        tracing._client = fake
        try:
            with patch("langchain_core.tracers.langchain.wait_for_all_tracers") as official:
                tracing.flush_langsmith_traces()
            official.assert_called_once()
            assert fake.flushed == 1
        finally:
            tracing._client = None


# ---------------------------------------------------------------------------
# Unit tests: Flask endpoints finalize their manual runs
# ---------------------------------------------------------------------------

class TestEndpointFinalization:
    def test_service_search_endpoint_finalizes_run(self, client):
        fake = FakeLangSmithClient()
        result = {"success": True, "count": 2, "services": [{"name": "S1"}, {"name": "S2"}]}
        with patch("tracing._get_client", return_value=fake), \
             patch("main.search_services", return_value=result):
            response = client.post(
                "/api/services/search",
                json={"location": "Hyderabad", "service_category": "catering"},
            )

        assert response.status_code == 200
        updates = [u for _, u in fake.updated]
        assert len(updates) == 1, "service_search run must be finalized exactly once"
        assert updates[0]["end_time"] is not None
        assert updates[0]["outputs"] == result
        assert "error" not in updates[0]

    def test_chat_endpoint_finalizes_manual_runs(self, client):
        import gc
        from langchain_core.messages import AIMessage

        fake = FakeLangSmithClient()

        with patch("tracing._get_client", return_value=fake), \
             patch("main.detect_product_intent", return_value={"is_product": False, "confidence": 0.0}), \
             patch("main.ltm.build_context", return_value=""), \
             patch("main.ltm.extract_facts", return_value=None), \
             patch.object(main.chat_graph, "invoke", return_value={"messages": [AIMessage(content="hello back")]}):
            response = client.post(
                "/api/chat", json={"query": "hello", "session_id": "unit_test_session"}
            )

        assert response.status_code == 200
        gc.collect()

        created_names = {c["name"] for c in fake.created}
        assert {"smartbot_chat", "langgraph_invoke"} <= created_names

        updated_map = dict(fake.updated)
        for c in fake.created:
            upd = updated_map.get(c["id"])
            assert upd is not None, f"run {c['name']} was never finalized"
            assert upd["end_time"] is not None, f"run {c['name']} is still pending"
            assert "error" not in upd

        chat_run = next(c for c in fake.created if c["name"] == "smartbot_chat")
        assert updated_map[chat_run["id"]]["outputs"]["response_length"] > 0


# ---------------------------------------------------------------------------
# Live integration tests (need real keys; verify NEW runs are finalized)
# ---------------------------------------------------------------------------

def _live_tracing_available() -> bool:
    return (
        bool(os.environ.get("GROQ_API_KEY"))
        and bool(os.environ.get("LANGSMITH_API_KEY"))
        and os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")
    )


_live = _live_tracing_available()

pytestmark_live = pytest.mark.skipif(not _live, reason="requires live Groq/Serper/LangSmith keys")


def _new_runs_since(t0):
    from langsmith import Client
    try:
        return list(Client().list_runs(project_name="smartbot", start_time=t0, limit=100))
    except Exception:
        return []


def _poll_until(predicate, timeout=15.0, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return predicate()


@pytestmark_live
class TestLiveFinalization:
    def test_new_chat_request_finalizes_langgraph_root(self, client):
        session_id = f"live_{uuid_mod.uuid4().hex[:8]}"
        t0 = datetime.now(timezone.utc)
        response = client.post(
            "/api/chat",
            json={"query": "Reply with exactly the single word: FINALCHECK", "session_id": session_id},
        )
        assert response.status_code == 200, response.get_json()

        runs = _poll_until(lambda: _new_runs_since(t0), timeout=15.0)
        langgraph_roots = [r for r in runs if r.name == "LangGraph" and r.parent_run_id is None]

        assert langgraph_roots, "NEW LangGraph root run not found (flush did not persist it)"
        assert len(langgraph_roots) == 1, "expected exactly one NEW LangGraph root run (no duplicates)"
        root = langgraph_roots[0]
        assert root.end_time is not None, "LangGraph root run is still PENDING"
        assert getattr(root, "status", None) == "success", root.status

        trace_id = root.trace_id
        children = [r for r in runs if r.trace_id == trace_id and r.id != root.id]
        for child in children:
            assert child.end_time is not None, f"child run {child.name} is still PENDING"
            assert getattr(child, "status", None) == "success", f"{child.name}: {child.status}"

    def test_new_service_search_finalizes_root(self, client):
        t0 = datetime.now(timezone.utc)
        response = client.post(
            "/api/services/search",
            json={"location": "Hyderabad", "service_category": "catering"},
        )
        assert response.status_code == 200, response.get_json()

        runs = _poll_until(lambda: _new_runs_since(t0), timeout=20.0)
        service_runs = [r for r in runs if r.name == "service_search" and r.parent_run_id is None]

        assert service_runs, "NEW service_search root run not found"
        assert len(service_runs) == 1, "expected exactly one NEW service_search root run (no duplicates)"
        root = service_runs[0]
        assert root.end_time is not None, "service_search run is still PENDING"
        assert getattr(root, "status", None) == "success", root.status