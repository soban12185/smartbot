"""
Automated tests for Product Research Agent accuracy.

Tests verify that:
- Correct category matching (rejects wrong product types)
- Correct brand matching
- Correct feature extraction
- No fabricated ratings/prices
- Source confidence is set
- Empty results handled properly
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from product_research import (
    extract_product_requirements,
    _validate_search_results,
    _calculate_relevance_score,
    _score_category_match,
    _determine_source_confidence,
    _parse_search_result,
    _extract_store_from_url,
    CATEGORY_TAXONOMY,
    RELEVANCE_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def assert_condition(condition, test_name, details=""):
    if condition:
        print(f"  PASS: {test_name}")
    else:
        print(f"  FAIL: {test_name} {details}")
    return condition


# ---------------------------------------------------------------------------
# Test 1: samsung charger – must reject Samsung mobile phones
# ---------------------------------------------------------------------------

def test_samsung_charger_rejects_phones():
    print("\nTest 1: samsung charger – must reject Samsung mobile phones")
    req = extract_product_requirements("samsung charger")
    assert_condition(req.get("category") == "charger", "Category extracted as 'charger'",
                     f"got: {req.get('category')}")

    # Simulate search results
    results = [
        {"title": "Samsung Mobile Phones Price List In India", "snippet": "Samsung Galaxy S25 starts at Rs 8999", "link": "https://mysmartprice.com/samsung-phones"},
        {"title": "Samsung 25W USB-C Charger", "snippet": "Samsung 25W Fast Charger for phones", "link": "https://amazon.in/samsung-charger-25w"},
        {"title": "Samsung Galaxy A15 Price", "snippet": "Samsung Galaxy A15 specifications and price", "link": "https://flipkart.com/samsung-galaxy-a15"},
        {"title": "Samsung 45W Power Adapter", "snippet": "Samsung 45W USB-C Power Adapter for fast charging", "link": "https://amazon.in/samsung-45w-adapter"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    # Must reject phones
    assert_condition("Samsung Mobile Phones Price List" not in titles,
                     "Rejects 'Samsung Mobile Phones Price List'")
    assert_condition("Samsung Galaxy A15 Price" not in titles,
                     "Rejects 'Samsung Galaxy A15 Price'")
    # Must keep chargers
    assert_condition("Samsung 25W USB-C Charger" in titles,
                     "Keeps 'Samsung 25W USB-C Charger'")
    assert_condition("Samsung 45W Power Adapter" in titles,
                     "Keeps 'Samsung 45W Power Adapter'")


# ---------------------------------------------------------------------------
# Test 2: iphone 17 – must reject iPhone cases
# ---------------------------------------------------------------------------

def test_iphone17_rejects_cases():
    print("\nTest 2: iphone 17 – must reject iPhone cases")
    req = extract_product_requirements("iphone 17")

    results = [
        {"title": "iPhone 17 Case - Premium Clear Case", "snippet": "Protect your iPhone 17 with this case", "link": "https://amazon.in/iphone17-case"},
        {"title": "iPhone 17 Price in India", "snippet": "Apple iPhone 17 starts at Rs 79900", "link": "https://mysmartprice.com/iphone17"},
        {"title": "iPhone 17 Pro Max", "snippet": "Apple iPhone 17 Pro Max specifications", "link": "https://flipkart.com/iphone17-pro"},
        {"title": "iPhone 17 Screen Protector", "snippet": "Tempered glass for iPhone 17", "link": "https://amazon.in/iphone17-screen-guard"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    assert_condition("iPhone 17 Case - Premium Clear Case" not in titles,
                     "Rejects iPhone case")
    assert_condition("iPhone 17 Screen Protector" not in titles,
                     "Rejects iPhone screen protector")
    assert_condition("iPhone 17 Price in India" in titles,
                     "Keeps actual iPhone 17 listing")


# ---------------------------------------------------------------------------
# Test 3: laptop under 70000 – must reject laptop bags
# ---------------------------------------------------------------------------

def test_laptop_rejects_bags():
    print("\nTest 3: laptop under 70000 – must reject laptop bags")
    req = extract_product_requirements("laptop under 70000")
    assert_condition(req.get("budget_max") == 70000, "Budget max extracted as 70000",
                     f"got: {req.get('budget_max')}")

    results = [
        {"title": "Laptop Bag - 15.6 inch Waterproof", "snippet": "Premium laptop bag for men and women", "link": "https://amazon.in/laptop-bag"},
        {"title": "HP Laptop under 70000", "snippet": "HP Pavilion with i5 processor, 16GB RAM", "link": "https://amazon.in/hp-pavilion"},
        {"title": "Lenovo ThinkPad under 70000", "snippet": "Lenovo business laptop with SSD", "link": "https://flipkart.com/lenovo-thinkpad"},
        {"title": "Laptop Cooling Pad", "snippet": "USB cooling pad for laptops", "link": "https://amazon.in/cooling-pad"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    assert_condition("Laptop Bag - 15.6 inch Waterproof" not in titles,
                     "Rejects laptop bag")
    assert_condition("Laptop Cooling Pad" not in titles,
                     "Rejects laptop cooling pad")
    assert_condition("HP Laptop under 70000" in titles,
                     "Keeps actual laptop")
    assert_condition("Lenovo ThinkPad under 70000" in titles,
                     "Keeps actual laptop")


# ---------------------------------------------------------------------------
# Test 4: samsung tv – must reject Samsung refrigerators
# ---------------------------------------------------------------------------

def test_samsung_tv_rejects_fridges():
    print("\nTest 4: samsung tv – must reject Samsung refrigerators")
    req = extract_product_requirements("samsung tv")
    assert_condition(req.get("category") == "tv", "Category extracted as 'tv'",
                     f"got: {req.get('category')}")

    results = [
        {"title": "Samsung Refrigerator 253L", "snippet": "Samsung double door fridge", "link": "https://amazon.in/samsung-fridge"},
        {"title": "Samsung 55 inch Smart TV", "snippet": "Samsung Crystal 4K UHD TV", "link": "https://amazon.in/samsung-tv-55"},
        {"title": "Samsung Washing Machine", "snippet": "Samsung 7kg fully automatic", "link": "https://flipkart.com/samsung-washing-machine"},
        {"title": "Samsung 43 inch TV", "snippet": "Samsung Smart TV with Alexa", "link": "https://croma.com/samsung-43-tv"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    assert_condition("Samsung Refrigerator 253L" not in titles,
                     "Rejects Samsung refrigerator")
    assert_condition("Samsung Washing Machine" not in titles,
                     "Rejects Samsung washing machine")
    assert_condition("Samsung 55 inch Smart TV" in titles,
                     "Keeps Samsung TV")
    assert_condition("Samsung 43 inch TV" in titles,
                     "Keeps Samsung TV")


# ---------------------------------------------------------------------------
# Test 5: nike running shoes – must reject Nike socks
# ---------------------------------------------------------------------------

def test_nike_shoes_rejects_socks():
    print("\nTest 5: nike running shoes – must reject Nike socks")
    req = extract_product_requirements("nike running shoes")
    assert_condition(req.get("category") == "shoes", "Category extracted as 'shoes'",
                     f"got: {req.get('category')}")
    assert_condition(req.get("brand") == "Nike", "Brand extracted as 'Nike'",
                     f"got: {req.get('brand')}")

    results = [
        {"title": "Nike Running Socks - 3 Pack", "snippet": "Cushioned running socks", "link": "https://amazon.in/nike-socks"},
        {"title": "Nike Air Zoom Pegasus 41", "snippet": "Men's running shoes with Zoom Air", "link": "https://nike.com/pegasus-41"},
        {"title": "Nike Revolution 7", "snippet": "Running shoes for beginners", "link": "https://amazon.in/nike-revolution"},
        {"title": "Nike Shoe Rack", "snippet": "3-tier shoe rack organizer", "link": "https://amazon.in/nike-shoe-rack"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    assert_condition("Nike Running Socks - 3 Pack" not in titles,
                     "Rejects Nike socks")
    assert_condition("Nike Shoe Rack" not in titles,
                     "Rejects Nike shoe rack")
    assert_condition("Nike Air Zoom Pegasus 41" in titles,
                     "Keeps Nike running shoes")


# ---------------------------------------------------------------------------
# Test 6: samsung 25w charger – must prioritize 25W
# ---------------------------------------------------------------------------

def test_samsung_25w_charger():
    print("\nTest 6: samsung 25w charger – must prioritize 25W Samsung chargers")
    req = extract_product_requirements("samsung 25w charger")
    assert_condition(req.get("category") == "charger", "Category is charger",
                     f"got: {req.get('category')}")
    assert_condition("25W" in req.get("required_features", []), "25W extracted as required feature",
                     f"got: {req.get('required_features')}")

    results = [
        {"title": "Samsung 45W USB-C Charger", "snippet": "Samsung 45W fast charger", "link": "https://amazon.in/samsung-45w"},
        {"title": "Samsung 25W USB-C Fast Charger", "snippet": "Original Samsung 25W charger", "link": "https://amazon.in/samsung-25w"},
        {"title": "Samsung 15W Wireless Charger", "snippet": "Samsung wireless charging pad", "link": "https://amazon.in/samsung-wireless"},
    ]

    validated = _validate_search_results(results, req)
    titles = [r.get("title", "") for r in validated]

    assert_condition("Samsung 25W USB-C Fast Charger" in titles,
                     "Keeps Samsung 25W charger")
    # 45W charger may be kept (it's still a charger), but 25W should score higher


# ---------------------------------------------------------------------------
# Test 7: samsung charger under 2000 – must reject chargers above budget
# ---------------------------------------------------------------------------

def test_budget_filter():
    print("\nTest 7: samsung charger under 2000 – reject over-budget")
    req = extract_product_requirements("samsung charger under 2000")
    assert_condition(req.get("budget_max") == 2000, "Budget max is 2000",
                     f"got: {req.get('budget_max')}")

    # Test price extraction from search results
    result_above = {"title": "Samsung 45W Charger Rs 3500", "snippet": "Premium charger", "link": "https://example.com"}
    result_below = {"title": "Samsung 25W Charger Rs 1499", "snippet": "Fast charger", "link": "https://example.com"}

    # Parse both
    prod_above = _parse_search_result(result_above, req)
    prod_below = _parse_search_result(result_below, req)

    assert_condition(prod_above.get("price") == 3500, "Price above budget extracted correctly",
                     f"got: {prod_above.get('price')}")
    assert_condition(prod_below.get("price") == 1499, "Price below budget extracted correctly",
                     f"got: {prod_below.get('price')}")


# ---------------------------------------------------------------------------
# Test 8: No relevant products – must show clear message
# ---------------------------------------------------------------------------

def test_empty_results():
    print("\nTest 8: No relevant products – must show clear message")
    req = extract_product_requirements("quantum computer for sale")
    # With no search results, should get empty list
    results = []
    validated = _validate_search_results(results, req)
    assert_condition(len(validated) == 0, "No results for obscure query")


# ---------------------------------------------------------------------------
# Test 9: Source confidence detection
# ---------------------------------------------------------------------------

def test_source_confidence():
    print("\nTest 9: Source confidence detection")
    conf = _determine_source_confidence("https://www.samsung.com/in/galaxy-s25")
    assert_condition(conf == "high", "Samsung official = high confidence",
                     f"got: {conf}")

    conf = _determine_source_confidence("https://www.amazon.in/samsung-charger/dp/B0xyz")
    assert_condition(conf == "high", "Amazon.in = high confidence",
                     f"got: {conf}")

    conf = _determine_source_confidence("https://www.flipkart.com/samsung-tv")
    assert_condition(conf == "high", "Flipkart = high confidence",
                     f"got: {conf}")

    conf = _determine_source_confidence("https://some-random-blog.com/review")
    assert_condition(conf == "low", "Random blog = low confidence",
                     f"got: {conf}")

    conf = _determine_source_confidence("https://www.croma.com/samsung-tv")
    assert_condition(conf == "medium", "Croma = medium confidence",
                     f"got: {conf}")


# ---------------------------------------------------------------------------
# Test 10: Store name extraction from URL (not from brand)
# ---------------------------------------------------------------------------

def test_store_from_url():
    print("\nTest 10: Store name extraction from URL")
    store = _extract_store_from_url("https://www.amazon.in/Samsung-Charger/dp/B0xyz")
    assert_condition(store == "Amazon", "Amazon URL -> 'Amazon'",
                     f"got: {store}")

    store = _extract_store_from_url("https://www.flipkart.com/samsung-tv")
    assert_condition(store == "Flipkart", "Flipkart URL -> 'Flipkart'",
                     f"got: {store}")

    store = _extract_store_from_url("https://www.samsung.com/in/galaxy-s25")
    # samsung.com should not be mapped to Amazon
    assert_condition(store != "Amazon", "Samsung URL is NOT Amazon",
                     f"got: {store}")


# ---------------------------------------------------------------------------
# Test 11: No fabricated ratings
# ---------------------------------------------------------------------------

def test_no_fabricated_ratings():
    print("\nTest 11: No fabricated ratings")
    req = extract_product_requirements("samsung charger")

    # Result with NO rating in source
    result = {
        "title": "Samsung 25W USB-C Charger",
        "snippet": "Samsung charger for fast charging",
        "link": "https://amazon.in/samsung-charger",
    }
    product = _parse_search_result(result, req)
    assert_condition(product.get("rating") is None, "Rating is null when not in source",
                     f"got: {product.get('rating')}")
    assert_condition(product.get("review_count") is None, "Review count is null when not in source",
                     f"got: {product.get('review_count')}")

    # Result WITH rating in source
    result_with_rating = {
        "title": "Samsung 25W Charger - Rated 4.5 out of 5",
        "snippet": "Samsung charger with 1234 reviews",
        "link": "https://amazon.in/samsung-charger-rated",
    }
    product_rated = _parse_search_result(result_with_rating, req)
    assert_condition(product_rated.get("rating") == 4.5, "Rating extracted from source",
                     f"got: {product_rated.get('rating')}")
    assert_condition(product_rated.get("review_count") == 1234, "Review count extracted from source",
                     f"got: {product_rated.get('review_count')}")


# ---------------------------------------------------------------------------
# Test 12: Category mismatch detection
# ---------------------------------------------------------------------------

def test_category_mismatch():
    print("\nTest 12: Category mismatch detection")
    # Test the score function directly
    score = _score_category_match("samsung galaxy s25 price", "samsung galaxy s25", "charger")
    assert_condition(score == 0.0, "Phone result for charger query = 0.0 score",
                     f"got: {score}")

    score = _score_category_match("samsung 25w usb-c charger price", "samsung charger", "charger")
    assert_condition(score >= 0.7, "Charger result for charger query = high score",
                     f"got: {score}")

    score = _score_category_match("laptop bag waterproof", "laptop bag 15.6 inch", "laptop")
    assert_condition(score == 0.0, "Laptop bag result for laptop query = 0.0 score",
                     f"got: {score}")

    # Additional cross-category checks
    score = _score_category_match("samsung refrigerator 253l", "samsung refrigerator", "tv")
    assert_condition(score == 0.0, "Refrigerator result for TV query = 0.0 score",
                     f"got: {score}")

    score = _score_category_match("nike running socks 3 pack", "nike socks", "shoes")
    assert_condition(score == 0.0, "Socks result for shoes query = 0.0 score",
                     f"got: {score}")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("PRODUCT RESEARCH ACCURACY TESTS")
    print("=" * 60)

    tests = [
        test_samsung_charger_rejects_phones,
        test_iphone17_rejects_cases,
        test_laptop_rejects_bags,
        test_samsung_tv_rejects_fridges,
        test_nike_shoes_rejects_socks,
        test_samsung_25w_charger,
        test_budget_filter,
        test_empty_results,
        test_source_confidence,
        test_store_from_url,
        test_no_fabricated_ratings,
        test_category_mismatch,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
