"""Tests for the product research module."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProductIntentDetection:
    """Test product intent detection."""

    def test_detect_product_query(self):
        from product_research import detect_product_intent
        result = detect_product_intent("best laptop under 50000")
        assert result["is_product"] is True
        assert result["confidence"] > 0.0

    def test_detect_non_product_query(self):
        from product_research import detect_product_intent
        result = detect_product_intent("what is the capital of France")
        assert result["is_product"] is False or result.get("confidence", 0) < 0.4

    def test_detect_empty_query(self):
        from product_research import detect_product_intent
        result = detect_product_intent("")
        assert result["is_product"] is False


class TestParseProductIntent:
    """Test structured intent parsing for product queries."""

    def test_samsung_m14_charger(self):
        from product_research import parse_product_intent
        result = parse_product_intent("samsung m14 charger best")
        assert result["product_type"] == "charger"
        assert result["brand"] == "Samsung"
        assert result["device_model"] is not None
        assert "m14" in result["device_model"].lower()
        assert result["intent"] == "best"

    def test_samsung_m14_case(self):
        from product_research import parse_product_intent
        result = parse_product_intent("samsung m14 case")
        assert result["product_type"] == "case"
        assert result["brand"] == "Samsung"
        assert result["device_model"] is not None
        assert "m14" in result["device_model"].lower()

    def test_samsung_m14_screen_protector(self):
        from product_research import parse_product_intent
        result = parse_product_intent("samsung m14 screen protector")
        assert result["product_type"] == "screen_protector"
        assert result["brand"] == "Samsung"
        assert result["device_model"] is not None
        assert "m14" in result["device_model"].lower()

    def test_samsung_m14_phone(self):
        from product_research import parse_product_intent
        result = parse_product_intent("samsung m14 phone")
        assert result["product_type"] == "phone"
        assert result["brand"] == "Samsung"
        assert result["device_model"] is not None
        assert "m14" in result["device_model"].lower()

    def test_best_charger_for_samsung_m14(self):
        from product_research import parse_product_intent
        result = parse_product_intent("best charger for samsung m14")
        assert result["product_type"] == "charger"
        assert result["brand"] == "Samsung"
        assert result["device_model"] is not None
        assert "m14" in result["device_model"].lower()
        assert result["intent"] == "best"

    def test_samsung_25w_charger(self):
        from product_research import parse_product_intent
        result = parse_product_intent("samsung 25w charger")
        assert result["product_type"] == "charger"
        assert result["brand"] == "Samsung"

    def test_iphone_case(self):
        from product_research import parse_product_intent
        result = parse_product_intent("iphone 15 pro max case")
        assert result["product_type"] == "case"
        assert result["brand"] == "Apple"

    def test_generic_charger(self):
        from product_research import parse_product_intent
        result = parse_product_intent("best usb-c charger")
        assert result["product_type"] == "charger"


class TestIsInformationalArticle:
    """Test informational article detection."""

    def test_specs_page(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Samsung M14: Price in India, Features and Specifications"
        ) is True

    def test_review_article(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Samsung M14 Review: Pros and Cons"
        ) is True

    def test_buying_guide(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Best Samsung Phones Under 15000 - Buying Guide"
        ) is True

    def test_comparison_article(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Samsung M14 vs M15: Which is Better?"
        ) is True

    def test_product_listing(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Samsung 25W USB-C Fast Charger - Buy Online at ₹1,499"
        ) is False

    def test_product_with_rating(self):
        from product_research import is_informational_article
        assert is_informational_article(
            "Samsung 25W USB-C Fast Charger 4.3 out of 5 stars"
        ) is False


class TestValidateCandidate:
    """Test candidate validation against intent."""

    def test_reject_phone_for_charger_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 charger best")
        candidate = {
            "title": "Samsung M14: Price in India, Features and Specifications",
            "snippet": "Samsung Galaxy M14 price in India starts from ₹11,999",
            "link": "https://example.com/samsung-m14",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is False
        assert "informational_article" in reason or "wrong_category" in reason

    def test_accept_charger_for_charger_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 charger best")
        candidate = {
            "title": "Samsung 25W USB-C Fast Charger for Galaxy M14",
            "snippet": "Buy Samsung 25W USB-C Fast Charger compatible with Galaxy M14",
            "link": "https://amazon.in/samsung-charger",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is True
        assert reason == ""

    def test_reject_case_for_charger_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 charger")
        candidate = {
            "title": "Samsung M14 Back Cover Case",
            "snippet": "Protective case for Samsung M14",
            "link": "https://example.com/samsung-m14-case",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is False
        assert "wrong_category" in reason

    def test_reject_screen_protector_for_charger_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 charger")
        candidate = {
            "title": "Samsung M14 Tempered Glass Screen Protector",
            "snippet": "Screen protector for Samsung Galaxy M14",
            "link": "https://example.com/samsung-m14-screen",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is False
        assert "wrong_category" in reason

    def test_accept_case_for_case_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 case")
        candidate = {
            "title": "Samsung M14 Protective Case Cover",
            "snippet": "Buy Samsung M14 case online",
            "link": "https://amazon.in/samsung-m14-case",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is True
        assert reason == ""

    def test_reject_article_for_case_query(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 case")
        candidate = {
            "title": "Best Samsung M14 Cases: Top 10 Picks",
            "snippet": "Here are the best cases for Samsung M14",
            "link": "https://example.com/best-cases",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is False
        assert "informational_article" in reason

    def test_third_party_compatible_charger(self):
        from product_research import validate_candidate, parse_product_intent
        intent = parse_product_intent("samsung m14 charger")
        candidate = {
            "title": "Ambrane 20W USB-C Fast Charger for Samsung Galaxy M14",
            "snippet": "Compatible with Samsung Galaxy M14, 20W fast charging",
            "link": "https://amazon.in/ambrane-charger",
        }
        is_valid, reason = validate_candidate(candidate, intent)
        assert is_valid is True
        assert reason == ""


class TestCheckCompatibility:
    """Test compatibility checking."""

    def test_compatible_charger(self):
        from product_research import _check_compatibility
        result = _check_compatibility(
            "Samsung 25W USB-C Fast Charger for Galaxy M14",
            "samsung m14",
            "Samsung",
        )
        assert result == "compatible"

    def test_compatible_with_for_keyword(self):
        from product_research import _check_compatibility
        result = _check_compatibility(
            "Fast Charger for Samsung Galaxy M14",
            "samsung m14",
            "Samsung",
        )
        assert result == "compatible"

    def test_uncertain_compatibility(self):
        from product_research import _check_compatibility
        result = _check_compatibility(
            "Universal USB-C Charger 20W",
            "samsung m14",
            "Samsung",
        )
        assert result in ("compatible", "uncertain")

    def test_incompatible_explicit(self):
        from product_research import _check_compatibility
        result = _check_compatibility(
            "Not compatible with Samsung M14",
            "samsung m14",
            "Samsung",
        )
        assert result == "incompatible"
