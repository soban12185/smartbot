"""Tests for Flask API endpoints."""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing app
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("SERPER_API_KEY", "test_key")
os.environ.setdefault("JINA_API_KEY", "test_key")

# Mock Neo4j before importing main
with patch("main.Neo4jGraph") as mock_neo4j:
    mock_neo4j.return_value = MagicMock()
    from main import app


@pytest.fixture
def client():
    """Create a test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestChatEndpoint:
    """Test /api/chat."""

    def test_chat_missing_query(self, client):
        response = client.post("/api/chat", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_chat_empty_query(self, client):
        response = client.post("/api/chat", json={"query": ""})
        assert response.status_code == 400

    def test_chat_valid_query(self, client):
        response = client.post("/api/chat", json={"query": "hello", "session_id": "test_session"})
        assert response.status_code == 200
        data = response.get_json()
        assert "response" in data
        assert "run_id" in data


class TestSearchEndpoint:
    """Test /api/search."""

    def test_search_missing_query(self, client):
        response = client.post("/api/search", json={})
        assert response.status_code == 400

    def test_search_empty_query(self, client):
        response = client.post("/api/search", json={"query": ""})
        assert response.status_code == 400


class TestPDFEndpoints:
    """Test /api/pdf/*."""

    def test_pdf_summary_no_file(self, client):
        response = client.post("/api/pdf/summary")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_pdf_summary_non_pdf(self, client):
        import io
        data = {"file": (io.BytesIO(b"not a pdf"), "test.txt")}
        response = client.post(
            "/api/pdf/summary",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_pdf_ask_missing_question(self, client):
        response = client.post("/api/pdf/ask", json={"doc_id": "abc"})
        assert response.status_code == 400

    def test_pdf_ask_missing_doc_id(self, client):
        response = client.post("/api/pdf/ask", json={"question": "what?"})
        assert response.status_code == 400


class TestMemoryEndpoints:
    """Test /api/memory/*."""

    def test_get_facts(self, client):
        response = client.get("/api/memory/facts?session_id=test")
        assert response.status_code == 200
        data = response.get_json()
        assert "facts" in data

    def test_get_history(self, client):
        response = client.get("/api/memory/history?session_id=test")
        assert response.status_code == 200
        data = response.get_json()
        assert "history" in data

    def test_clear_memory(self, client):
        response = client.post("/api/memory/clear", json={"session_id": "test"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "cleared"


class TestServiceEndpoints:
    """Test /api/services/*."""

    def test_service_lookup_missing_query(self, client):
        response = client.post("/api/services/lookup", json={})
        assert response.status_code == 400

    def test_service_lookup_unknown_type(self, client):
        response = client.post("/api/services/lookup", json={"query": "plumbing"})
        assert response.status_code == 404

    def test_service_lookup_catering(self, client):
        response = client.post("/api/services/lookup", json={"query": "catering"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["service_type"] == "catering"
        assert len(data["services"]) > 0

    def test_book_missing_fields(self, client):
        response = client.post("/api/services/book", json={})
        assert response.status_code == 400

    def test_book_invalid_key(self, client):
        response = client.post("/api/services/book", json={
            "service_name": "test",
            "user_name": "test",
            "api_key": "invalid",
        })
        assert response.status_code == 401


class TestEventEndpoint:
    """Test /api/event/plan."""

    def test_event_plan_missing_fields(self, client):
        response = client.post("/api/event/plan", json={})
        assert response.status_code == 400

    def test_event_plan_dummy(self, client):
        response = client.post("/api/event/plan", json={
            "event_type": "wedding",
            "date": "2025-01-01",
            "location": "Chennai",
            "exactlocation": "Adyar",
            "guest_count": 100,
            "total_budget": 500000,
            "special_requirements": "",
            "use_dummy": True,
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "response" in data


class TestFeedbackEndpoint:
    """Test /api/feedback."""

    def test_feedback_missing_fields(self, client):
        response = client.post("/api/feedback", json={})
        assert response.status_code == 400


class TestLangSmithStatus:
    """Test /api/langsmith/status."""

    def test_langsmith_status(self, client):
        response = client.get("/api/langsmith/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "tracing_enabled" in data
        assert "project" in data
