"""
LangSmith Tracing for SmartBot

Provides non-blocking tracing for:
- Chat requests (LangGraph workflow)
- RAG pipeline (PDF analysis + retrieval)
- Product research agent
- Service finder (Google Places API)
- LLM calls
- Tool calls

LangSmith is NEVER a hard dependency. If unavailable or misconfigured,
SmartBot continues to function normally.

Environment:
    LANGSMITH_TRACING=true/false
    LANGSMITH_API_KEY=your_key
    LANGSMITH_PROJECT=smartbot
"""

import datetime
import functools
import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangSmith client initialization (lazy, non-blocking)
# ---------------------------------------------------------------------------

_client = None
_client_initialized = False
_tracing_enabled = False


def _get_client():
    """
    Lazy-initialize LangSmith client.
    Returns None if LangSmith is not configured or unavailable.
    Never raises exceptions that would break SmartBot.
    """
    global _client, _client_initialized, _tracing_enabled

    if _client_initialized:
        return _client

    _client_initialized = True

    try:
        tracing_flag = os.environ.get("LANGSMITH_TRACING", "false").lower()
        api_key = os.environ.get("LANGSMITH_API_KEY", "")

        if tracing_flag not in ("true", "1", "yes") or not api_key:
            logger.info("LangSmith tracing is disabled (set LANGSMITH_TRACING=true to enable)")
            _tracing_enabled = False
            return None

        # Set environment variables for LangSmith SDK
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = api_key

        project = os.environ.get("LANGSMITH_PROJECT", "smartbot")
        os.environ["LANGSMITH_PROJECT"] = project

        from langsmith import Client
        _client = Client()
        _tracing_enabled = True
        logger.info("LangSmith client initialized (project: %s)", project)
        return _client

    except ImportError:
        logger.warning("langsmith package not installed. Run: pip install langsmith")
        _tracing_enabled = False
        return None
    except Exception as exc:
        logger.warning("Failed to initialize LangSmith client: %s", exc)
        _tracing_enabled = False
        return None


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    _get_client()
    return _tracing_enabled


def flush_langsmith_traces(timeout: float = 3.0) -> None:
    """
    Flush pending LangSmith runs using the OFFICIAL LangChain/LangSmith
    mechanism before a request completes.

    LangChain/LangGraph auto-tracing (LangChainTracer) persists run create
    and update operations on a background batching thread (langsmith
    Client.tracing_queue). On serverless deployments (e.g. Vercel) the
    process may be frozen immediately after the HTTP response is returned,
    so anything the background thread has not yet sent is lost and the root
    "LangGraph" run stays permanently PENDING. Flushing before responding
    guarantees the collection of these runs.

    This does NOT build a custom flush: it calls the official
    `langchain_core.tracers.langchain.wait_for_all_tracers()` (which flushes
    the shared cached client used by LangChainTracer) plus this module's own
    client. Both calls run in a bounded worker thread so a slow or absent
    LangSmith endpoint never blocks the request (non-blocking LangSmith).
    """
    targets: list = []

    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        targets.append(wait_for_all_tracers)
    except Exception:
        logger.debug("wait_for_all_tracers unavailable; skipping official flush")

    if _client is not None:
        client = _client
        targets.append(lambda: client.flush())

    if not targets:
        return

    def _run():
        for target in targets:
            try:
                target()
            except Exception:
                logger.debug("LangSmith flush skipped (non-blocking)")

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(timeout)


# ---------------------------------------------------------------------------
# Run trace wrapper
# ---------------------------------------------------------------------------

class _TraceRun:
    """
    Lightweight handle for a LangSmith run created via the manual
    create_run / update_run API.

    The langsmith Client.create_run() is write-only and returns None, so the
    run id must be generated locally and passed to create_run(id=...). This
    wrapper owns the run lifecycle: callers finalize with .end(outputs=...) or
    .add_outputs(...), and the run is committed to LangSmith exactly once via
    client.update_run().
    """

    def __init__(self, client: Any, run_id, name: str):
        self._client = client
        self._run_id = run_id
        self._name = name
        self.outputs: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.end_time: Optional[datetime.datetime] = None
        self._finalized = False

    @property
    def id(self):
        return self._run_id

    def end(self, outputs: Optional[Dict[str, Any]] = None):
        """Finalize the run with the given outputs (replaces accumulated ones)."""
        if outputs is not None:
            self.outputs = outputs
        self._finalize()

    def add_outputs(self, outputs: Optional[Dict[str, Any]] = None):
        """Accumulate outputs without finalizing the run yet."""
        if outputs:
            if not isinstance(outputs, dict):
                self.outputs["output"] = outputs
            else:
                self.outputs.update(outputs)

    def _finalize(self, error: Optional[Exception] = None):
        if self._finalized:
            return
        self._finalized = True
        self.end_time = datetime.datetime.now(datetime.timezone.utc)

        if error is not None:
            self.error = str(error)

        updates: Dict[str, Any] = {"end_time": self.end_time}
        if self.outputs:
            updates["outputs"] = self.outputs
        if self.error:
            updates["error"] = self.error

        try:
            self._client.update_run(run_id=self._run_id, **updates)
            if self.error:
                logger.debug(
                    "LangSmith trace ERROR: %s [%s]",
                    self._name, str(self._run_id)[:8],
                )
            else:
                logger.debug(
                    "LangSmith trace END: %s [%s]",
                    self._name, str(self._run_id)[:8],
                )
        except Exception as exc:
            logger.debug("LangSmith update_run failed (non-blocking): %s", exc)

    def __del__(self):
        # Safety net: finalize if the caller never called .end()/.add_outputs().
        if not self._finalized:
            try:
                self._finalize()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Run trace context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace_run(
    name: str,
    run_type: str = "chain",
    inputs: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Context manager for LangSmith tracing.

    Usage:
        with trace_run("my_operation", inputs={"query": q}) as run:
            result = do_something(q)
        if run:
            run.end(outputs={"result": result})

    or:
        with trace_run("my_operation", inputs={"query": q}) as run:
            result = do_something(q)
            if run:
                run.end(outputs={"result": result})

    If LangSmith is unavailable, yields None and the code still runs.
    Exceptions from the wrapped code are recorded on the run and re-raised.
    """
    client = _get_client()
    if not client:
        yield None
        return

    project = os.environ.get("LANGSMITH_PROJECT", "smartbot")
    run_id = uuid4()

    try:
        client.create_run(
            id=run_id,
            name=name,
            run_type=run_type,
            inputs=inputs or {},
            metadata=metadata or {},
            tags=tags or [],
            project_name=project,
        )
        logger.debug("LangSmith trace START: %s [%s]", name, str(run_id)[:8])
    except Exception as exc:
        logger.debug("LangSmith create_run failed (non-blocking): %s", exc)
        yield None
        return

    handle = _TraceRun(client, run_id, name)

    try:
        yield handle
    except Exception as exc:
        logger.debug("LangSmith trace ERROR: %s [%s]", name, str(run_id)[:8])
        handle._finalize(error=exc)
        raise


# ---------------------------------------------------------------------------
# Decorator for tracing function calls
# ---------------------------------------------------------------------------

def traced(
    name: Optional[str] = None,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
) -> Callable:
    """
    Decorator to trace a function call with LangSmith.

    Usage:
        @traced(name="my_function", tags=["rag"])
        def my_function(query: str):
            return result

    The decorated function always runs, even if LangSmith is unavailable.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            run_name = name or func.__name__
            client = _get_client()

            if not client:
                return func(*args, **kwargs)

            project = os.environ.get("LANGSMITH_PROJECT", "smartbot")

            # Build inputs dict
            run_inputs = {"args": str(args)[:500], "kwargs": str(kwargs)[:500]}
            run_id = uuid4()

            try:
                client.create_run(
                    id=run_id,
                    name=run_name,
                    run_type=run_type,
                    inputs=run_inputs,
                    metadata=metadata or {},
                    tags=tags or [],
                    project_name=project,
                )
                logger.debug("LangSmith trace START: %s [%s]", run_name, str(run_id)[:8])
            except Exception as exc:
                logger.debug("LangSmith create_run failed (non-blocking): %s", exc)
                return func(*args, **kwargs)

            start_time = time.time()
            error = None
            result = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                error = exc
                raise
            finally:
                elapsed = time.time() - start_time
                try:
                    outputs = {}
                    if result is not None:
                        # Safely serialize result
                        try:
                            import json
                            json.dumps(result)
                            outputs["result"] = result
                        except (TypeError, ValueError):
                            outputs["result"] = str(result)[:1000]

                    updates = {
                        "outputs": outputs,
                        "extra": {"elapsed_seconds": elapsed},
                        "end_time": datetime.datetime.now(datetime.timezone.utc),
                    }
                    if error:
                        updates["error"] = str(error)

                    client.update_run(run_id=run_id, **updates)
                    if error:
                        logger.debug(
                            "LangSmith trace ERROR: %s [%s]",
                            run_name, str(run_id)[:8],
                        )
                    else:
                        logger.debug(
                            "LangSmith trace END: %s [%s]",
                            run_name, str(run_id)[:8],
                        )
                except Exception:
                    pass

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Convenience functions for common tracing patterns
# ---------------------------------------------------------------------------

def trace_chat_request(
    query: str,
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace a chat request through SmartBot.
    Returns a context manager yielding the LangSmith run.
    """
    return trace_run(
        name="smartbot_chat",
        run_type="chain",
        inputs={"query": query, "session_id": session_id},
        metadata=metadata or {},
        tags=["chat", "production"],
    )


def trace_langgraph(
    query: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace LangGraph execution.
    """
    return trace_run(
        name="langgraph_invoke",
        run_type="chain",
        inputs={"query": query[:500]},
        metadata=metadata or {},
        tags=["langgraph", "production"],
    )


def trace_rag_retrieval(
    query: str,
    doc_id: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace RAG retrieval pipeline.
    """
    return trace_run(
        name="rag_retrieval",
        run_type="retriever",
        inputs={"query": query, "doc_id": doc_id},
        metadata=metadata or {},
        tags=["rag", "retrieval", "production"],
    )


def trace_rag_generation(
    query: str,
    context_length: int,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace RAG answer generation.
    """
    return trace_run(
        name="rag_generation",
        run_type="llm",
        inputs={"query": query, "context_length": context_length},
        metadata=metadata or {},
        tags=["rag", "generation", "production"],
    )


def trace_product_research(
    query: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace product research pipeline.
    """
    return trace_run(
        name="product_research",
        run_type="chain",
        inputs={"query": query},
        metadata=metadata or {},
        tags=["product_research", "production"],
    )


def trace_web_search(
    query: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace web search.
    """
    return trace_run(
        name="web_search",
        run_type="retriever",
        inputs={"query": query},
        metadata=metadata or {},
        tags=["search", "production"],
    )


def trace_event_plan(
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace event planning.
    """
    return trace_run(
        name="event_planning",
        run_type="chain",
        inputs={"event_type": event_type},
        metadata=metadata or {},
        tags=["event_planning", "production"],
    )


def trace_service_search(
    location: str,
    service_category: str,
    special_requirements: str = "",
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace service finder search via web search (Serper).

    Captures: location, service_category, special_requirements,
    number of candidates, validated/rejected counts, latency.
    """
    return trace_run(
        name="service_search",
        run_type="chain",
        inputs={
            "location": location,
            "service_category": service_category,
            "special_requirements": special_requirements,
        },
        metadata=metadata or {},
        tags=["service_finder", "serper", "production"],
    )


# ---------------------------------------------------------------------------
# Feedback helper
# ---------------------------------------------------------------------------

def submit_feedback(
    run_id: str,
    score: int,
    comment: Optional[str] = None,
) -> bool:
    """
    Submit user feedback for a LangSmith run.
    score: 1 (positive) or 0 (negative)
    Returns True if successful, False otherwise.
    """
    client = _get_client()
    if not client:
        return False

    try:
        client.create_feedback(
            run_id=run_id,
            key="user_feedback",
            score=score,
            comment=comment or ("positive" if score == 1 else "negative"),
        )
        return True
    except Exception as exc:
        logger.debug("Failed to submit feedback (non-blocking): %s", exc)
        return False


# ---------------------------------------------------------------------------
# LLM call tracing helper
# ---------------------------------------------------------------------------

def trace_llm_call(
    model: str,
    prompt_length: int,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace an individual LLM call.
    """
    return trace_run(
        name=f"llm_call_{model.replace('/', '_')}",
        run_type="llm",
        inputs={"model": model, "prompt_length": prompt_length},
        metadata=metadata or {},
        tags=["llm", "production"],
    )
