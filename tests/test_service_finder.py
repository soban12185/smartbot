"""Tests for the service finder module (Serper web search based)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from services.service_finder import (
    parse_user_request,
    _build_search_queries,
    _is_relevant_candidate,
    _deduplicate,
    _rank_candidates,
    _extract_candidate,
    _extract_phone,
    _extract_rating,
    search_services,
    CATEGORY_SEARCH_TERMS,
)


# ---------------------------------------------------------------------------
# Input Parsing Tests
# ---------------------------------------------------------------------------

class TestParseUserRequest:
    """Test structured request parsing."""

    def test_catering_in_bangalore(self):
        result = parse_user_request("Bangalore", "catering", "vegetarian catering for 100 people")
        assert result["location"] == "Bangalore"
        assert result["service_category"] == "catering"
        assert len(result["search_queries"]) >= 1
        assert any("bangalore" in q.lower() for q in result["search_queries"])

    def test_ac_repair_in_chennai(self):
        result = parse_user_request("Chennai", "ac repair", "split AC")
        assert result["location"] == "Chennai"
        assert result["service_category"] == "ac repair"
        assert any("chennai" in q.lower() for q in result["search_queries"])

    def test_photographer_in_coimbatore(self):
        result = parse_user_request("Coimbatore", "photographer", "wedding")
        assert result["location"] == "Coimbatore"
        assert result["service_category"] == "photographer"
        assert any("coimbatore" in q.lower() for q in result["search_queries"])

    def test_missing_location_raises(self):
        try:
            parse_user_request("", "catering")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "location" in str(e).lower()

    def test_missing_category_raises(self):
        try:
            parse_user_request("Bangalore", "")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "service category" in str(e).lower()

    def test_extracted_info_keywords(self):
        result = parse_user_request("Chennai", "catering", "vegetarian 100 people tomorrow evening")
        info = result["extracted_info"]
        assert "vegetarian" in info

    def test_category_lowercased(self):
        result = parse_user_request("Delhi", "PLUMBER")
        assert result["service_category"] == "plumber"

    def test_search_queries_limited_to_three(self):
        result = parse_user_request("Mumbai", "catering", "wedding reception for 200 people")
        assert len(result["search_queries"]) <= 3


# ---------------------------------------------------------------------------
# Search Query Generation Tests
# ---------------------------------------------------------------------------

class TestBuildSearchQueries:
    """Test that targeted search queries are generated."""

    def test_primary_query_contains_category_and_location(self):
        queries = _build_search_queries("catering", "Bangalore")
        assert len(queries) >= 1
        assert "bangalore" in queries[0].lower()
        assert "catering" in queries[0].lower()

    def test_requirements_add_second_query(self):
        queries = _build_search_queries("catering", "Bangalore", "vegetarian")
        assert len(queries) >= 2
        assert any("vegetarian" in q.lower() for q in queries)

    def test_max_three_queries(self):
        queries = _build_search_queries("catering", "Bangalore", "wedding reception for 200 people")
        assert len(queries) <= 3


# ---------------------------------------------------------------------------
# Candidate Extraction Tests
# ---------------------------------------------------------------------------

class TestExtractCandidate:
    """Test extraction of structured candidates from web results."""

    def test_extracts_name_and_description(self):
        result = {
            "title": "Royal Catering Services Bangalore",
            "snippet": "Best catering in Bangalore. Call +91-9876543210",
            "link": "https://royalcatering.com",
            "position": 1,
        }
        candidate = _extract_candidate(result)
        assert candidate["name"] == "Royal Catering Services Bangalore"
        assert "catering" in candidate["description"].lower()
        assert candidate["website"] == "https://royalcatering.com"
        assert candidate["phone"] == "+91-9876543210"

    def test_extracts_domain(self):
        result = {
            "title": "Test Service",
            "snippet": "Some description",
            "link": "https://www.example.com/service",
            "position": 1,
        }
        candidate = _extract_candidate(result)
        assert candidate["domain"] == "example.com"

    def test_extracts_rating(self):
        result = {
            "title": "Rated Business",
            "snippet": "Rated 4.5/5 stars for excellent service",
            "link": "https://example.com",
            "position": 1,
        }
        candidate = _extract_candidate(result)
        assert candidate["rating"] == 4.5

    def test_missing_optional_fields(self):
        result = {
            "title": "Simple Business",
            "snippet": "Just a description",
            "link": "https://example.com",
            "position": 1,
        }
        candidate = _extract_candidate(result)
        assert candidate["phone"] is None
        assert candidate["rating"] is None
        assert candidate["address"] is None


# ---------------------------------------------------------------------------
# Phone Extraction Tests
# ---------------------------------------------------------------------------

class TestExtractPhone:
    """Test phone number extraction from text."""

    def test_indian_format_with_country_code(self):
        assert _extract_phone("Call +91-9876543210 for booking") is not None

    def test_indian_format_local(self):
        assert _extract_phone("Phone: 044-23456789") is not None

    def test_no_phone(self):
        assert _extract_phone("No phone number here") is None


# ---------------------------------------------------------------------------
# Rating Extraction Tests
# ---------------------------------------------------------------------------

class TestExtractRating:
    """Test rating extraction from text."""

    def test_rating_with_stars(self):
        assert _extract_rating("Rated 4.5 stars") == 4.5

    def test_rating_with_slash(self):
        assert _extract_rating("4.2/5 rating") == 4.2

    def test_no_rating(self):
        assert _extract_rating("No rating mentioned") is None


# ---------------------------------------------------------------------------
# Candidate Validation Tests
# ---------------------------------------------------------------------------

class TestCandidateValidation:
    """Test that candidates are validated against service category."""

    def test_reject_article_url(self):
        candidate = {
            "name": "Top 10 Catering Services in Bangalore",
            "description": "List of best catering services",
            "website": "https://example.com/top-10-catering",
            "source_url": "https://example.com/top-10-catering",
            "domain": "example.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is False
        assert "reject_title" in reason or "reject_url" in reason

    def test_reject_news_url(self):
        candidate = {
            "name": "Bangalore News Today",
            "description": "Latest news from Bangalore",
            "website": "https://news.example.com/bangalore",
            "source_url": "https://news.example.com/bangalore",
            "domain": "news.example.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is False

    def test_accept_catering_service(self):
        candidate = {
            "name": "Royal Catering Services Bangalore",
            "description": "Professional catering services in Bangalore for events",
            "website": "https://royalcatering.com",
            "source_url": "https://royalcatering.com",
            "domain": "royalcatering.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is True
        assert reason == ""

    def test_reject_wrong_location(self):
        candidate = {
            "name": "Mumbai Catering Co",
            "description": "Best catering in Mumbai for weddings",
            "website": "https://mumbaicatering.com",
            "source_url": "https://mumbaicatering.com",
            "domain": "mumbaicatering.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is False
        assert "location" in reason

    def test_accept_plumber(self):
        candidate = {
            "name": "Quick Fix Plumbing Chennai",
            "description": "Professional plumber in Chennai for all repairs",
            "website": "https://quickfixplumbing.in",
            "source_url": "https://quickfixplumbing.in",
            "domain": "quickfixplumbing.in",
        }
        valid, reason = _is_relevant_candidate(candidate, "plumber", "Chennai")
        assert valid is True

    def test_reject_buy_electronics(self):
        candidate = {
            "name": "Buy Samsung Phone Online - Amazon",
            "description": "Best price for Samsung phones",
            "website": "https://amazon.com/samsung-phone",
            "source_url": "https://amazon.com/samsung-phone",
            "domain": "amazon.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is False

    def test_accept_with_location_in_domain(self):
        candidate = {
            "name": "Best Services",
            "description": "Great catering services",
            "website": "https://bangalorecatering.com",
            "source_url": "https://bangalorecatering.com",
            "domain": "bangalorecatering.com",
        }
        valid, reason = _is_relevant_candidate(candidate, "catering", "Bangalore")
        assert valid is True


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Test that duplicate businesses are removed."""

    def test_removes_same_domain(self):
        candidates = [
            {"name": "Catering A", "description": "Service A", "domain": "cateringa.com", "website": "https://cateringa.com"},
            {"name": "Catering A - Best", "description": "Service A details", "domain": "cateringa.com", "website": "https://cateringa.com"},
        ]
        result = _deduplicate(candidates)
        assert len(result) == 1

    def test_removes_similar_names(self):
        candidates = [
            {"name": "Royal Catering Services", "description": "A", "domain": "royalcatering.com", "website": "https://royalcatering.com"},
            {"name": "Royal Catering Services", "description": "B", "domain": "royalcatering.com", "website": "https://www.royalcatering.com/about"},
        ]
        result = _deduplicate(candidates)
        assert len(result) == 1

    def test_keeps_distinct_businesses(self):
        candidates = [
            {"name": "Catering A", "description": "A", "domain": "a.com", "website": "https://a.com"},
            {"name": "Catering B", "description": "B", "domain": "b.com", "website": "https://b.com"},
            {"name": "Catering C", "description": "C", "domain": "c.com", "website": "https://c.com"},
        ]
        result = _deduplicate(candidates)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Ranking Tests
# ---------------------------------------------------------------------------

class TestRanking:
    """Test candidate ranking."""

    def test_rank_by_category_match(self):
        candidates = [
            {"name": "General Events", "description": "Event planning services", "domain": "a.com", "website": "https://a.com"},
            {"name": "Wedding Photography Studio", "description": "Professional wedding photographer in Bangalore", "domain": "b.com", "website": "https://b.com"},
        ]
        ranked = _rank_candidates(candidates, "wedding photographer")
        assert ranked[0]["name"] == "Wedding Photography Studio"

    def test_rank_with_requirements_match(self):
        candidates = [
            {"name": "General Catering", "description": "Catering services", "domain": "a.com", "website": "https://a.com"},
            {"name": "Veg Catering Bangalore", "description": "Vegetarian catering for events in Bangalore", "domain": "b.com", "website": "https://b.com"},
        ]
        ranked = _rank_candidates(candidates, "catering", "vegetarian")
        assert ranked[0]["name"] == "Veg Catering Bangalore"


# ---------------------------------------------------------------------------
# Search Integration Tests (mocked Serper API)
# ---------------------------------------------------------------------------

class TestSearchServices:
    """Test the main search_services function with mocked Serper API."""

    def test_missing_api_key(self):
        with patch("services.service_finder.os.environ", {}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is False
            assert "configured" in result["error"].lower()

    @patch("services.service_finder._serper_search")
    def test_no_results(self, mock_search):
        mock_search.return_value = []
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is True
            assert result["count"] == 0
            assert result["results"] == []

    @patch("services.service_finder._serper_search")
    def test_returns_validated_results(self, mock_search):
        mock_search.return_value = [
            {
                "title": "Royal Catering Bangalore",
                "snippet": "Best catering service in Bangalore. Phone: +91-9876543210",
                "link": "https://royalcatering.com",
                "position": 1,
            },
            {
                "title": "Bangalore Event Foods",
                "snippet": "Event catering in Indiranagar, Bangalore",
                "link": "https://bangaloreevents.com",
                "position": 2,
            },
            {
                "title": "Samsung Mobile Store",
                "snippet": "Buy Samsung phones online",
                "link": "https://samsung.com/bangalore",
                "position": 3,
            },
        ]
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is True
            assert result["count"] >= 1
            # Samsung store should be rejected
            assert all("samsung" not in r["name"].lower() for r in result["results"])

    @patch("services.service_finder._serper_search")
    def test_removes_duplicates(self, mock_search):
        mock_search.return_value = [
            {
                "title": "Same Catering Service",
                "snippet": "Catering in Bangalore",
                "link": "https://samecatering.com",
                "position": 1,
            },
            {
                "title": "Same Catering Service - Best",
                "snippet": "Best catering in Bangalore",
                "link": "https://samecatering.com/about",
                "position": 2,
            },
        ]
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["count"] == 1

    @patch("services.service_finder._serper_search")
    def test_api_timeout(self, mock_search):
        import requests as req
        mock_search.side_effect = req.exceptions.Timeout()
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    @patch("services.service_finder._serper_search")
    def test_api_403_error(self, mock_search):
        import requests as req
        resp = MagicMock()
        resp.status_code = 403
        mock_search.side_effect = req.exceptions.HTTPError(response=resp)
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is False
            assert "invalid" in result["error"].lower() or "quota" in result["error"].lower()

    @patch("services.service_finder._serper_search")
    def test_api_429_error(self, mock_search):
        import requests as req
        resp = MagicMock()
        resp.status_code = 429
        mock_search.side_effect = req.exceptions.HTTPError(response=resp)
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is False
            assert "too many" in result["error"].lower()

    def test_no_fake_businesses_in_output(self):
        """Verify that no hardcoded/mock business names appear."""
        fake_names = {"A1 Catering", "FoodZone", "EventDecor Pro", "FlowerArt",
                      "LensCraft", "WeddingFrames", "Premium Catering",
                      "Royal Decoration", "ProPhoto Studio"}
        with patch("services.service_finder._serper_search", return_value=[]):
            result = search_services("Chennai", "catering")
            for r in result["results"]:
                assert r["name"] not in fake_names

    @patch("services.service_finder._serper_search")
    def test_max_three_results(self, mock_search):
        mock_search.return_value = [
            {
                "title": f"Catering Service {i}",
                "snippet": f"Best catering in Bangalore area {i}",
                "link": f"https://catering{i}.com",
                "position": i,
            }
            for i in range(1, 8)
        ]
        result = search_services("Bangalore", "catering")
        assert result["count"] <= 3
        assert len(result["results"]) <= 3

    @patch("services.service_finder._serper_search")
    def test_no_fake_data_when_fields_missing(self, mock_search):
        """Verify that missing rating/address/phone are not fabricated."""
        mock_search.return_value = [
            {
                "title": "Simple Catering Bangalore",
                "snippet": "We provide catering services in Bangalore",
                "link": "https://simplecatering.com",
                "position": 1,
            },
        ]
        with patch.dict("os.environ", {"SERPER_API_KEY": "test_key"}):
            result = search_services("Bangalore", "catering")
            assert result["success"] is True
            if result["results"]:
                r = result["results"][0]
                # Phone should not be present if not in snippet
                assert "phone" not in r or r["phone"] is None
                # Rating should not be present if not in snippet
                assert "rating" not in r or r["rating"] is None


# ---------------------------------------------------------------------------
# Category Coverage Tests
# ---------------------------------------------------------------------------

class TestCategoryCoverage:
    """Test that all required categories have search terms."""

    def test_all_categories_have_terms(self):
        required = [
            "catering", "plumber", "electrician", "ac repair", "appliance repair",
            "photographer", "wedding photographer", "cleaning", "salon",
            "beauty service", "car repair", "bike repair", "home tutor",
            "pest control", "laundry", "event decorator", "event planner",
            "makeup artist",
        ]
        for cat in required:
            assert cat in CATEGORY_SEARCH_TERMS, f"Missing category: {cat}"
            assert len(CATEGORY_SEARCH_TERMS[cat]) > 0, f"Empty terms for: {cat}"


# ---------------------------------------------------------------------------
# Missing Input Tests
# ---------------------------------------------------------------------------

class TestMissingInput:
    """Test handling of missing required inputs."""

    def test_missing_location(self):
        result = search_services("", "catering")
        assert result["success"] is False
        assert "location" in result["error"].lower()

    def test_missing_category(self):
        result = search_services("Bangalore", "")
        assert result["success"] is False
        assert "service category" in result["error"].lower()
