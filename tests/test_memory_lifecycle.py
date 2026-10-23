"""
Memory lifecycle tests for SmartBot.

These tests verify the FULL end-to-end memory flow:

  1. Explicit fact:  "my name is soban" -> stored -> "what is my name?" -> Soban
  2. Preference:     "I like blue"      -> stored -> "what color do I like?" -> blue
  3. Namespace isolation: User A's name must NOT leak to User B
  4. New thread:     long-term memory persists when the same user starts a new thread
  5. DB unavailable: chat continues normally without crashing

Unit tests use a FakeLongTermMemory that mirrors the real PostgreSQL-backed
architecture (same extract_facts/build_context semantics keyed by session_id).

Live integration tests (skipped without real GROQ/SERPER keys + DATABASE_URI)
exercise the real Postgres-backed LongTermMemory through the real /api/chat
endpoint.
"""
import os
import re
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mirror tests/test_api.py: set test keys BEFORE importing main, mock Neo4j
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("SERPER_API_KEY", "test_key")
os.environ.setdefault("JINA_API_KEY", "test_key")

with patch("main.Neo4jGraph", autospec=True):
    import main
    from main import app

from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Fake LongTermMemory replicating the real PostgreSQL-backed semantics
# ---------------------------------------------------------------------------

class FakeLongTermMemory:
    """
    In-memory stand-in for memory_system.LongTermMemory. It implements the same
    contract (extract_facts, build_context, search, get, put) keyed by
    session_id, so tests exercise the real extraction/retrieval/injection code
    in main.py without requiring a database.
    """

    def __init__(self):
        self.storage = {}          # session_id -> {key: value}
        self.conversations = {}    # session_id -> [(query, response)]

    def put(self, session_id, key, value):
        self.storage.setdefault(session_id, {})[key] = value

    def get(self, session_id, key):
        return self.storage.get(session_id, {}).get(key)

    def delete(self, session_id, key):
        self.storage.get(session_id, {}).pop(key, None)

    def list_keys(self, session_id):
        return list(self.storage.get(session_id, {}).keys())

    def search(self, session_id, text):
        results = []
        for key, value in self.storage.get(session_id, {}).items():
            if text.lower() in str(value).lower():
                results.append({"key": key, "value": value})
        return results[:5]

    def save_conversation(self, session_id, query, response):
        self.conversations.setdefault(session_id, []).append((query, response))

    def get_recent_conversations(self, session_id, limit=10):
        return [
            {"query": q, "response": r}
            for q, r in list(self.conversations.get(session_id, []))[-limit:]
        ]

    def build_context(self, session_id, query):
        parts = []

        prefs = self.get(session_id, "preferences")
        if prefs:
            parts.append(f"User Preferences: {prefs}")

        facts = self.get(session_id, "facts")
        if facts and isinstance(facts, list):
            parts.append("Known Facts:\n" + "\n".join(f"- {f}" for f in facts[-10:]))

        hits = self.search(session_id, query)
        if hits:
            parts.append(f"Relevant Past: {hits[:3]}")

        recent = self.get_recent_conversations(session_id, 3)
        if recent:
            convos = "\n".join(
                f"User: {r['query']}\nBot: {r['response'][:200]}"
                for r in reversed(recent)
            )
            parts.append(f"Recent Conversation:\n{convos}")

        if not parts:
            return ""
        return "\n\n--- Long-Term Memory ---\n" + "\n\n".join(parts)

    def extract_facts(self, session_id, query, response):
        self.save_conversation(session_id, query, response)
        existing = self.get(session_id, "facts") or []
        interaction = f"{query[:100]} -> {response[:100]}"
        existing.append(interaction)
        existing = existing[-50:]
        self.put(session_id, "facts", existing)

    def clear_all(self, session_id):
        self.storage.pop(session_id, None)
        self.conversations.pop(session_id, None)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def fake_ltm():
    return FakeLongTermMemory()


def _fake_llm_invoke(inputs, config):
    """Stand-in for chat_graph.invoke that recalls facts FROM the injected context.

    It only answers from the LTM block that main.py injects into the prompt
    (the section before 'User Question:'). This is a semantic Q&A double, NOT a
    hardcoded answer: if the memory block contains 'my name is X' the fake
    recalls X; if it contains 'I like Y' it recalls Y; otherwise it politely
    says it does not know.
    """
    content = inputs["messages"][-1].content
    low = content.lower()

    if "user question:" in content:
        ctx = content.split("user question:", 1)[0]
    else:
        ctx = content

    name_match = re.search(r"my name is\s+([a-z0-9]+)", ctx.lower())
    if name_match and "what is my name" in low:
        name = name_match.group(1).capitalize()
        return {"messages": [AIMessage(content=f"Your name is {name}.")]}

    color_match = re.search(r"i like\s+([a-z]+)", ctx.lower())
    if color_match and ("what color" in low or "favorite color" in low):
        return {"messages": [AIMessage(content=f"You like {color_match.group(1)}.")]}

    if "what is my name" in low:
        return {"messages": [AIMessage(content="I don't know your name.")]}
    if "color" in low:
        return {"messages": [AIMessage(content="I don't know your favorite color.")]}
    return {"messages": [AIMessage(content="Okay, noted.")]}


# ---------------------------------------------------------------------------
# Hermetic /api/chat lifecycle tests
# ---------------------------------------------------------------------------

class TestMemoryLifecycle:
    def _chat(self, client, fake_ltm, query, session_id, thread_id=None):
        body = {"query": query, "session_id": session_id}
        if thread_id is not None:
            body["thread_id"] = thread_id
        with patch("main.detect_product_intent", return_value={"is_product": False}), \
             patch("main.ltm", fake_ltm), \
             patch.object(main.chat_graph, "invoke", side_effect=_fake_llm_invoke):
            return client.post("/api/chat", json=body)

    def test_name_fact_survives_and_is_retrievable(self, client, fake_ltm):
        r1 = self._chat(client, fake_ltm, "my name is soban", "user_a")
        assert r1.status_code == 200

        facts = fake_ltm.get("user_a", "facts")
        assert facts, "memory must be written after the first message"
        assert any("my name is soban" in f for f in facts), facts
        convos = fake_ltm.get_recent_conversations("user_a", 3)
        assert convos and convos[-1]["query"] == "my name is soban"

        ctx = fake_ltm.build_context("user_a", "what is my name?")
        assert "my name is soban" in ctx, "retrieved memory must reach the prompt"

        r2 = self._chat(client, fake_ltm, "what is my name?", "user_a")
        assert r2.status_code == 200
        assert "Soban" in r2.get_json()["response"]

    def test_preference_color(self, client, fake_ltm):
        self._chat(client, fake_ltm, "I like blue", "user_a")
        facts = fake_ltm.get("user_a", "facts")
        assert facts and any("i like blue" in f.lower() for f in facts), facts

        r2 = self._chat(client, fake_ltm, "what color do I like?", "user_a")
        assert r2.status_code == 200
        assert "blue" in r2.get_json()["response"].lower()

    def test_namespace_isolation_between_users(self, client, fake_ltm):
        self._chat(client, fake_ltm, "my name is soban", "user_a")
        r_b = self._chat(client, fake_ltm, "what is my name?", "user_b")
        assert r_b.status_code == 200
        assert "your name is soban" not in r_b.get_json()["response"].lower()
        assert "soban" not in fake_ltm.build_context("user_b", "what is my name?")

    def test_new_thread_keeps_long_term_memory(self, client, fake_ltm):
        self._chat(client, fake_ltm, "my name is soban", "user_a", thread_id="thread_1")

        facts = fake_ltm.get("user_a", "facts")
        assert facts

        r2 = self._chat(client, fake_ltm, "what is my name?", "user_a", thread_id="thread_2")
        assert r2.status_code == 200
        assert "Soban" in r2.get_json()["response"]
        assert len(fake_ltm.get("user_a", "facts")) >= 2

    def test_chat_continues_when_database_unavailable(self, client, fake_ltm):
        class BrokenMemory:
            def build_context(self, *a, **kw):
                raise RuntimeError("database unreachable")

            def extract_facts(self, *a, **kw):
                raise RuntimeError("database unreachable")

        with patch("main.detect_product_intent", return_value={"is_product": False}), \
             patch("main.ltm", BrokenMemory()), \
             patch.object(main.chat_graph, "invoke", return_value={"messages": [AIMessage(content="still works")]}):
            response = client.post("/api/chat", json={"query": "hello", "session_id": "user_a"})
        assert response.status_code == 200
        assert response.get_json()["response"] == "still works"


# ---------------------------------------------------------------------------
# Unit tests: database URI resolves correctly after .env is loaded
# ---------------------------------------------------------------------------

class TestDatabaseURIConfig:
    def test_memory_system_resolves_database_uri_from_env(self):
        """Regression: DATABASE_URI must be the configured value, not the import-time localhost default."""
        import memory_system
        from dotenv import load_dotenv
        load_dotenv()

        configured = os.environ.get("DATABASE_URI")
        if configured:
            assert memory_system._resolve_database_uri() == configured
        else:
            assert "localhost" in memory_system._resolve_database_uri()


# ---------------------------------------------------------------------------
# Live integration tests (require real keys; verify real Postgres persistence)
# ---------------------------------------------------------------------------

def _live_available() -> bool:
    real_keys = (os.environ.get("GROQ_API_KEY") and os.environ.get("SERPER_API_KEY"))
    return bool(real_keys) and bool(os.environ.get("DATABASE_URI"))


live_marker = pytest.mark.skipif(not _live_available(), reason="requires live Groq/Serper/DB keys")


@live_marker
class TestLiveMemoryPersistence:
    def _chat_retry(self, client, body, tries=3, wait=20):
        """POST /api/chat with bounded retries for transient Groq/DB errors."""
        import time
        for attempt in range(1, tries + 1):
            resp = client.post("/api/chat", json=body)
            data = resp.get_json() or {}
            if resp.status_code == 200 and data.get("response"):
                return resp
            if attempt < tries:
                time.sleep(wait)
        return resp

    def test_live_name_roundtrip(self, client):
        import uuid
        session_id = f"live_mem_{uuid.uuid4().hex[:8]}"

        try:
            r1 = self._chat_retry(
                client, {"query": "my name is soban", "session_id": session_id}
            )
            assert r1.status_code == 200, r1.get_json()

            from memory_system import ltm
            facts = ltm.get(session_id, "facts")
            assert facts, "live write to Postgres failed"
            assert any("my name is soban" in f for f in facts), facts

            r2 = self._chat_retry(
                client, {"query": "what is my name?", "session_id": session_id}
            )
            assert r2.status_code == 200, r2.get_json()
            response = r2.get_json()["response"].lower()
            assert "soban" in response, f"real LLM did not recall the name: {response}"
        finally:
            from memory_system import ltm
            ltm.clear_all(session_id)