"""Regression tests for the Service Finder root-cause fix.

These tests are deterministic: Serper HTTP calls are mocked. They cover the
original T. Nagar failure, location aliases, optional-field handling, provider
failures, parsing failures, deduplication, nearby classification, category
coverage, and the public Flask response shape.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import service_finder
from services.service_finder import (
    CATEGORY_RELEVANCE_TERMS,
    CATEGORY_SEARCH_TERMS,
    _deduplicate,
    _extract_candidate,
    _is_relevant_candidate,
    _location_relevance,
    normalize_location,
    parse_user_request,
    search_services,
)


def _service_result(title, snippet, link, position=1):
    return {
        "title": title,
        "snippet": snippet,
        "link": link,
        "position": position,
    }


def _load_app():
    """Import the Flask app without attempting a real Neo4j connection."""
    if "main" in sys.modules:
        return sys.modules["main"].app
    with patch("langchain_community.graphs.Neo4jGraph", autospec=True):
        import main
    return main.app


def _event_planner_rows():
    return [
        _service_result(
            "Popular Party Organisers in T Nagar, Chennai",
            "Directory of party organisers in T Nagar, Chennai",
            "https://www.justdial.com/Chennai/Party-Organisers-in-T-Nagar/nct-10355",
            1,
        ),
        _service_result(
            "Haritham Events: Wedding Planning, Decor & Catering in Chennai",
            (
                "End-to-end wedding planning, decor and event management. "
                "Trusted by families across Chennai. Location 24, Maharajapuram "
                "Santhanam Salai, T-Nagar - 600017."
            ),
            "https://www.harithamevents.com/",
            2,
        ),
        _service_result(
            "Thyagaraya Nagar Event Management Company",
            "We plan weddings and corporate events in Thyagaraya Nagar, Chennai.",
            "https://example-events.in/",
            3,
        ),
    ]


def _mock_serper_returning(rows, monkeypatch):
    calls = []

    def fake_search(query, num_results=10):
        calls.append(query)
        return list(rows)

    monkeypatch.setattr(service_finder, "_serper_search", fake_search)
    monkeypatch.setenv("SERPER_API_KEY", "test_key")
    return calls


class TestOriginalBug:
    def test_event_planner_in_chennai_t_nagar_now_finds_real_results(self, monkeypatch):
        calls = _mock_serper_returning(_event_planner_rows(), monkeypatch)

        result = search_services("chennai t nagar", "Event Planner", "")

        assert result["success"] is True
        assert result["count"] == len(result["results"]) >= 1
        assert any("Haritham" in r["name"] for r in result["results"])
        assert all("justdial" not in (r.get("source_url") or "") for r in result["results"])
        assert result["query"]["normalized_location"] == "t nagar, chennai"
        assert result["query"]["search_location"] == "T Nagar Chennai"
        # Primary query is targeted and the fallback is bounded.
        assert calls[0] == "event planners in T Nagar Chennai"
        assert len(calls) <= 3

    def test_realistic_t_nagar_result_was_previously_rejected_as_location_mismatch(self):
        candidate = _extract_candidate(
            _service_result(
                "Top Event Planners in T. Nagar, Chennai",
                "Event planning and management services in T Nagar, Chennai.",
                "https://example-event.com/",
                1,
            )
        )
        valid, reason = _is_relevant_candidate(
            candidate, "event planner", "chennai t nagar"
        )
        assert valid is True, reason


class TestLocationNormalization:
    @pytest.mark.parametrize("value", [
        "chennai t nagar",
        "T Nagar, Chennai",
        "T. Nagar Chennai",
        "T Nagar, Chennai, Tamil Nadu",
        "Thyagaraya Nagar, Chennai",
    ])
    def test_equivalent_spellings_share_profile(self, value):
        profile = normalize_location(value)
        assert profile["city"] == "chennai"
        assert profile["area"] == "t nagar"
        assert profile["search_location"] == "T Nagar Chennai"

    def test_city_only_input_does_not_become_a_fake_area(self):
        profile = normalize_location("Bangalore")
        assert profile["city"] == "bengaluru"
        assert profile["area"] is None
        assert profile["search_location"] == "Bangalore"

    def test_parse_keeps_original_for_display_and_normalized_for_search(self):
        parsed = parse_user_request("T. Nagar Chennai", "Event Planner")
        assert parsed["location"] == "T. Nagar Chennai"
        assert parsed["normalized_location"] == "t nagar, chennai"
        assert "T Nagar Chennai" in parsed["search_queries"][0]

    def test_nearby_area_is_not_labeled_exact(self):
        profile = normalize_location("chennai t nagar")
        candidate = _extract_candidate(
            _service_result(
                "Adyar Wedding Planners",
                "Wedding planning company serving Adyar, Chennai.",
                "https://adyar-events.example/",
            )
        )
        assert _location_relevance(candidate, profile) == "nearby"

    def test_city_wide_result_is_not_labeled_exact(self):
        profile = normalize_location("chennai t nagar")
        candidate = _extract_candidate(
            _service_result(
                "Chennai Event Planners",
                "Leading event management company serving Chennai.",
                "https://chennai-events.example/",
            )
        )
        assert _location_relevance(candidate, profile) == "city"


class TestOptionalFields:
    def test_relevant_result_without_phone_is_kept(self, monkeypatch):
        _mock_serper_returning([
            _service_result(
                "T Nagar Event Planners",
                "Event planning services in T Nagar, Chennai.",
                "https://t-nagar-events.example/",
            )
        ], monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        assert result["count"] == 1
        assert "phone" not in result["results"][0]

    def test_relevant_result_without_rating_is_kept(self, monkeypatch):
        _mock_serper_returning([
            _service_result(
                "T Nagar Event Planners",
                "Event planning services in T Nagar, Chennai.",
                "https://t-nagar-events.example/",
            )
        ], monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        assert result["count"] == 1
        assert "rating" not in result["results"][0]

    def test_incomplete_address_is_not_fabricated(self, monkeypatch):
        _mock_serper_returning([
            _service_result(
                "T Nagar Event Planners",
                "Event planning services in T Nagar, Chennai.",
                "https://t-nagar-events.example/",
            )
        ], monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        assert result["count"] == 1
        assert "address" not in result["results"][0]

    def test_structured_address_is_preserved_when_supplied(self):
        candidate = _extract_candidate({
            "title": "T Nagar Event Planners",
            "snippet": "Event planning services in T Nagar, Chennai.",
            "link": "https://t-nagar-events.example/",
            "address": "12, Some Street, T Nagar, Chennai - 600017",
        })
        assert candidate["address"] == "12, Some Street, T Nagar, Chennai - 600017"


class TestRelevance:
    def test_mix_of_relevant_and_unrelated_results(self, monkeypatch):
        rows = _event_planner_rows() + [
            _service_result(
                "Buy Samsung Phone Online",
                "Best price on Samsung phones",
                "https://www.amazon.com/samsung",
                4,
            ),
            _service_result(
                "Mumbai Event Planners",
                "Event planning company in Mumbai",
                "https://mumbai-events.example/",
                5,
            ),
        ]
        _mock_serper_returning(rows, monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        names = " ".join(r["name"].lower() for r in result["results"])
        assert "samsung" not in names
        assert "mumbai" not in names
        assert result["diagnostics"]["rejected"] >= 2

    @pytest.mark.parametrize("category", sorted(CATEGORY_SEARCH_TERMS))
    def test_every_supported_category_can_validate_a_relevant_business(self, category):
        term = CATEGORY_RELEVANCE_TERMS[category][0]
        candidate = {
            "name": "Local Provider",
            "description": f"Professional {term} services in T Nagar, Chennai.",
            "website": "https://provider.example/",
            "source_url": "https://provider.example/",
            "domain": "provider.example",
        }
        valid, reason = _is_relevant_candidate(candidate, category, "T Nagar, Chennai")
        assert valid is True, reason


class TestProviderFailures:
    def test_empty_organic_results_is_a_genuine_empty_search(self, monkeypatch):
        _mock_serper_returning([], monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is True
        assert result["count"] == 0
        assert result["empty_reason"] == "no_provider_results"
        assert "No web results" in result["message"]

    def test_http_error_is_not_reported_as_empty(self, monkeypatch):
        response = MagicMock()
        response.status_code = 500

        def fail(query, num_results=10):
            raise requests.exceptions.HTTPError(response=response)

        monkeypatch.setattr(service_finder, "_serper_search", fail)
        monkeypatch.setenv("SERPER_API_KEY", "test_key")

        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "provider_unavailable"
        assert result["results"] == []
        assert result["count"] == 0

    def test_timeout_is_reported(self, monkeypatch):
        def fail(query, num_results=10):
            raise requests.exceptions.Timeout()

        monkeypatch.setattr(service_finder, "_serper_search", fail)
        monkeypatch.setenv("SERPER_API_KEY", "test_key")

        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "provider_timeout"

    def test_missing_api_key_is_reported(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "missing_api_key"

    def test_malformed_json_is_reported(self, monkeypatch):
        response = MagicMock()
        response.status_code = 200

        def raise_value_error():
            raise ValueError("not json")

        response.json.side_effect = raise_value_error
        response.raise_for_status.return_value = None
        monkeypatch.setattr(service_finder.requests, "post", lambda *args, **kwargs: response)
        monkeypatch.setenv("SERPER_API_KEY", "test_key")

        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "malformed_provider_response"

    def test_unexpected_organic_shape_is_reported(self, monkeypatch):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"organic": {"not": "a list"}}
        monkeypatch.setattr(service_finder.requests, "post", lambda *args, **kwargs: response)
        monkeypatch.setenv("SERPER_API_KEY", "test_key")

        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "malformed_provider_response"

    def test_one_bad_candidate_does_not_discard_valid_candidates(self, monkeypatch):
        rows = _event_planner_rows()
        real_extract = service_finder._extract_candidate

        def flaky_extract(row):
            if "Broken" in str(row.get("title", "")):
                raise ValueError("unparseable result")
            return real_extract(row)

        rows.insert(1, _service_result(
            "Broken Result", "unparseable", "https://broken.example/", 2
        ))
        _mock_serper_returning(rows, monkeypatch)
        monkeypatch.setattr(service_finder, "_extract_candidate", flaky_extract)

        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is True
        assert result["count"] >= 1
        assert result["diagnostics"]["parse_failures"] == 1

    def test_all_unparseable_candidates_are_a_parse_failure(self, monkeypatch):
        _mock_serper_returning([
            _service_result("Broken", "x", "https://broken.example/")
        ], monkeypatch)
        monkeypatch.setattr(
            service_finder, "_extract_candidate",
            MagicMock(side_effect=ValueError("bad")),
        )
        result = search_services("chennai t nagar", "event planner")
        assert result["success"] is False
        assert result["error_code"] == "candidate_parse_error"


class TestDeduplication:
    def test_distinct_businesses_on_shared_domain_are_kept(self, monkeypatch):
        _mock_serper_returning([
            _service_result(
                "Alpha Events",
                "Event planning in T Nagar, Chennai.",
                "https://shared.example/alpha",
                1,
            ),
            _service_result(
                "Beta Events",
                "Event management in T Nagar, Chennai.",
                "https://shared.example/beta",
                2,
            ),
        ], monkeypatch)
        result = search_services("chennai t nagar", "event planner")
        assert result["count"] == 2

    def test_duplicate_pages_of_same_business_are_removed(self):
        candidates = [
            {"name": "Royal Catering Services", "domain": "royalcatering.com",
             "source_url": "https://royalcatering.com/", "website": "https://royalcatering.com/"},
            {"name": "Royal Catering Services", "domain": "royalcatering.com",
             "source_url": "https://www.royalcatering.com/about", "website": "https://www.royalcatering.com/about"},
        ]
        assert len(_deduplicate(candidates)) == 1


class TestApiContract:
    def test_service_endpoint_returns_expected_shape(self):
        pytest.importorskip("flask")
        os.environ.setdefault("GROQ_API_KEY", "test_key")
        os.environ.setdefault("SERPER_API_KEY", "test_key")
        os.environ.setdefault("JINA_API_KEY", "test_key")
        app = _load_app()

        app.config["TESTING"] = True
        with patch.object(service_finder, "_serper_search", return_value=_event_planner_rows()), \
             patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}), \
             app.test_client() as client:
            response = client.post(
                "/api/services/search",
                json={
                    "location": "T Nagar, Chennai",
                    "service_category": "Event Planner",
                    "special_requirements": "",
                },
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["count"] == len(data["results"]) >= 1
        assert data["source"] == "Web Search"
        assert data["query"]["location"] == "T Nagar, Chennai"
        assert data["query"]["normalized_location"] == "t nagar, chennai"
        assert data["query"]["service_category"] == "event planner"
        for result in data["results"]:
            assert result["name"]
            assert result["source_url"]

    def test_langsmith_failure_does_not_break_service_endpoint(self):
        pytest.importorskip("flask")
        os.environ.setdefault("GROQ_API_KEY", "test_key")
        os.environ.setdefault("SERPER_API_KEY", "test_key")
        os.environ.setdefault("JINA_API_KEY", "test_key")
        app = _load_app()

        app.config["TESTING"] = True
        with patch("tracing._get_client", side_effect=RuntimeError("langsmith down")), \
             patch.object(service_finder, "_serper_search", return_value=_event_planner_rows()), \
             patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}), \
             app.test_client() as client:
            response = client.post(
                "/api/services/search",
                json={"location": "T Nagar, Chennai", "service_category": "Event Planner"},
            )

        assert response.status_code == 200
        assert response.get_json()["success"] is True
