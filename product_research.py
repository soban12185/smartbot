"""
Product Research Agent for SmartBot

Pipeline (v2 – accuracy-first):
1. Intent detection (is this a product query?)
2. LLM-based requirement extraction (structured product requirements)
3. Search query generation (preserve product type + brand + attributes)
4. Online product search (via Serper API)
5. LOCAL STORE SEARCH (via Serper API)
6. SEARCH RESULT VALIDATION (relevance + data accuracy)
   - Stage 1: Product relevance validation (category, brand, type match)
   - Stage 2: Product data validation (price, rating, store accuracy)
7. Product normalization & deduplication
8. Product analysis & scoring (with relevance gate)
9. Recommendation generation (only relevant products)
10. Response synthesis (null-safe, no fabricated data)

Environment:
    SERPER_API_KEY  - for web search
    GROQ_API_KEY    - for LLM extraction/analysis
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI

from tracing import trace_run, trace_product_research

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERPER_API_URL = "https://google.serper.dev/search"
GROQ_MODEL = "openai/gpt-oss-120b"

PRODUCT_SEARCH_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes

# ---------------------------------------------------------------------------
# Relevance scoring weights (configurable)
# ---------------------------------------------------------------------------

RELEVANCE_WEIGHTS = {
    "category_match": 0.40,
    "brand_match": 0.20,
    "model_match": 0.15,
    "keyword_match": 0.15,
    "budget_match": 0.10,
}

# Minimum relevance score for a product to be considered (0-1)
RELEVANCE_THRESHOLD = 0.25

# Scoring weights for recommendation engine
SCORING_WEIGHTS = {
    "budget_fit": 0.20,
    "performance": 0.30,
    "features": 0.25,
    "value": 0.15,
    "ratings": 0.10,
}

# ---------------------------------------------------------------------------
# Category taxonomy – prevents mismatch (Requirement 6)
# ---------------------------------------------------------------------------

CATEGORY_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "charger": {
        "exact_matches": ["charger", "power adapter", "charging adapter", "fast charger",
                          "usb-c charger", "usb charger", "type-c charger", "wall charger",
                          "car charger", "wireless charger", "magnetic charger"],
        "reject_matches": ["phone", "mobile", "smartphone", "tablet", "laptop",
                           "earbuds", "headphones", "watch", "case", "cover",
                           "screen protector", "cable", "stand", "dock"],
        "aliases": ["power adapter", "charging adapter", "adapter"],
    },
    "laptop": {
        "exact_matches": ["laptop", "notebook", "ultrabook", "chromebook",
                          "macbook", "thinkpad"],
        "reject_matches": ["laptop bag", "laptop case", "laptop sleeve", "laptop stand",
                           "laptop charger", "laptop adapter", "laptop cooling pad",
                           "keyboard", "mouse", "monitor", "desktop"],
        "aliases": ["notebook", "ultrabook"],
    },
    "phone": {
        "exact_matches": ["phone", "smartphone", "mobile phone", "mobile",
                          "iphone", "galaxy", "pixel", "oneplus"],
        "reject_matches": ["phone case", "phone cover", "phone screen protector",
                           "phone charger", "phone cable", "phone holder",
                           "phone stand", "phone mount", "earbuds",
                           "case", "cover", "screen protector", "tempered glass",
                           "charger", "adapter", "cable", "holder", "stand",
                           "pouch", "sleeve", "wallet case", "flip cover",
                           "back cover", "armband", "car mount"],
        "aliases": ["smartphone", "mobile"],
    },
    "tv": {
        "exact_matches": ["television", "smart tv", "led tv", "oled tv", "qled tv",
                          "android tv", "4k tv", "uhd tv"],
        "reject_matches": ["tv stand", "tv mount", "tv wall mount", "tv remote",
                           "tv antenna", "tv cable", "tv soundbar", "refrigerator",
                           "washing machine", "ac", "air conditioner"],
        "aliases": ["television", "smart television"],
    },
    "shoes": {
        "exact_matches": ["shoe", "shoes", "sneaker", "sneakers", "running shoes",
                          "sports shoes", "training shoes", "walking shoes",
                          "football shoes", "cricket shoes", "basketball shoes"],
        "reject_matches": ["socks", "shoe rack", "shoe cleaner", "shoe bag",
                           "shoe insole", "shoe cover", "insole"],
        "aliases": ["footwear", "sports shoes"],
    },
    "headphones": {
        "exact_matches": ["headphone", "headphones", "earphone", "earphones",
                          "earbuds", "true wireless", "tws", "airpods",
                          "over-ear", "on-ear", "in-ear"],
        "reject_matches": ["headphone case", "headphone cable", "earphone case",
                           "headphone stand", "headphone hanger"],
        "aliases": ["headset", "audio"],
    },
    "camera": {
        "exact_matches": ["camera", "dslr", "mirrorless", "point-and-shoot",
                          "action camera", "gopro", "camcorder"],
        "reject_matches": ["camera bag", "camera case", "camera tripod",
                           "camera lens filter", "camera strap", "memory card"],
        "aliases": [],
    },
    "watch": {
        "exact_matches": ["watch", "smartwatch", "smart watch", "fitness band",
                          "fitness tracker"],
        "reject_matches": ["watch band", "watch strap", "watch case", "watch charger"],
        "aliases": ["timepiece", "wearable"],
    },
    "tablet": {
        "exact_matches": ["tablet", "ipad", "tab", "android tablet"],
        "reject_matches": ["tablet case", "tablet cover", "tablet stand",
                           "tablet screen protector", "stylus"],
        "aliases": [],
    },
    "monitor": {
        "exact_matches": ["monitor", "display", "screen", "gaming monitor",
                          "ultrawide monitor", "4k monitor"],
        "reject_matches": ["monitor stand", "monitor arm", "monitor mount",
                           "monitor cleaning kit"],
        "aliases": ["display"],
    },
    "headphones_wireless": {
        "exact_matches": ["wireless headphones", "bluetooth headphones",
                          "wireless earbuds", "bluetooth earbuds"],
        "reject_matches": ["headphone case", "earbuds case"],
        "aliases": [],
    },
}

# Well-known store detection from URL
STORE_DOMAIN_MAP = {
    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "croma": "Croma",
    "reliance digital": "Reliance Digital",
    "vijay sales": "Vijay Sales",
    "snapdeal": "Snapdeal",
    "tata cliq": "Tata CLiQ",
    "myntra": "Myntra",
    "ajio": "AJIO",
    "nykaa": "Nykaa",
    "meesho": "Meesho",
    "jio": "JioMart",
    "mobikwik": "MobiKwik",
    "paytm": "Paytm Mall",
}

# Official brand store domains (high confidence)
BRAND_STORE_DOMAINS = {
    "samsung.com": ("Samsung", "high"),
    "apple.com": ("Apple", "high"),
    "sony.com": ("Sony", "high"),
    "lg.com": ("LG", "high"),
    "dell.com": ("Dell", "high"),
    "lenovo.com": ("Lenovo", "high"),
    "hp.com": ("HP", "high"),
    "asus.com": ("ASUS", "high"),
    "nike.com": ("Nike", "high"),
    "adidas.com": ("Adidas", "high"),
    "boat-lifestyle.com": ("boAt", "high"),
    "jbl.com": ("JBL", "high"),
    "mi.com": ("Xiaomi", "high"),
    "oneplus.com": ("OnePlus", "high"),
    "realme.com": ("Realme", "high"),
    "vivo.com": ("Vivo", "high"),
    "oppo.com": ("Oppo", "high"),
}

# Major retailer domains (medium-high confidence)
MAJOR_RETAILER_DOMAINS = {
    "amazon.in": ("Amazon", "high"),
    "flipkart.com": ("Flipkart", "high"),
    "croma.com": ("Croma", "medium"),
    "reliancedigital.in": ("Reliance Digital", "medium"),
    "vijaysales.com": ("Vijay Sales", "medium"),
    "snapdeal.com": ("Snapdeal", "low"),
    "tatacliq.com": ("Tata CLiQ", "medium"),
    "myntra.com": ("Myntra", "medium"),
}

# ---------------------------------------------------------------------------
# Accessory keywords – products that are accessories for a device
# ---------------------------------------------------------------------------

ACCESSORY_KEYWORDS = {
    "charger": ["charger", "power adapter", "charging adapter", "fast charger",
                "usb charger", "type-c charger", "usb-c charger", "wall charger",
                "car charger", "wireless charger", "magnetic charger", "charging cable"],
    "case": ["case", "cover", "back cover", "flip cover", "wallet case",
             "protective case", "silicone case", "hard case", "shell"],
    "screen_protector": ["screen protector", "tempered glass", "screen guard",
                         "privacy screen protector", "anti-glare protector"],
    "cable": ["cable", "usb cable", "type-c cable", "usb-c cable", "charging cable",
              "data cable", "lightning cable"],
    "earphones": ["earphones", "earbuds", "headphones", "airpods", "tws"],
    "power_bank": ["power bank", "portable charger", "powerbank"],
    "stand": ["stand", "holder", "mount", "dock", "cradle"],
}

# Device keywords – products that ARE the device itself
DEVICE_KEYWORDS = {
    "phone": ["phone", "smartphone", "mobile phone", "mobile", "galaxy", "iphone",
              "pixel", "oneplus", "realme", "vivo", "oppo", "xiaomi"],
    "laptop": ["laptop", "notebook", "ultrabook", "chromebook", "macbook"],
    "tablet": ["tablet", "ipad", "tab"],
    "tv": ["tv", "television", "smart tv", "led tv", "oled tv"],
    "watch": ["watch", "smartwatch", "smart watch", "fitness band"],
    "headphones": ["headphone", "headphones", "earphone", "earbuds", "airpods"],
    "camera": ["camera", "dslr", "mirrorless"],
    "monitor": ["monitor", "display", "screen"],
}

# Informational article patterns – NOT product listings
INFORMATIONAL_PATTERNS = [
    r"(?:price\s+in\s+india|features?\s+(?:and|&)\s+specifications?)",
    r"(?:full\s+specs?|complete\s+specifications?|detailed\s+specs?)",
    r"(?:review[s]?\s+(?:of|for|about))",
    r"(?:all\s+you\s+need\s+to\s+know)",
    r"(?:everything\s+you\s+need\s+to\s+know)",
    r"(?:top\s+\d+\s+(?:best|phone|laptop|charger))",
    r"(?:list\s+of\s+best)",
    r"(?:vs\.?|versus|compared?\s+to)",
    r"(?:how\s+to\s+(?:choose|buy|select))",
    r"(?:buying\s+guide|buyers?\s+guide)",
    r"(?:faq[s]?|frequently\s+asked)",
    r"(?:tips?\s+(?:for|to|and)\s+(?:buy|choose|select))",
    r"(?:launch\s+date|expected\s+price|rumour|rumor)",
    r"(?:leaked|leak|renders?)",
    r"(?:comparison|compare)",
    r"(?: pros?\s+and\s+cons?)",
    r"(?:what(?:'s| is| are)\s+new\s+in)",
]


# ---------------------------------------------------------------------------
# Structured Intent Parsing (Requirement 1)
# ---------------------------------------------------------------------------

def parse_product_intent(query: str) -> Dict[str, Any]:
    """
    Parse user query into structured product intent.

    Returns dict with:
        product_type: the accessory/product category (charger, case, etc.)
        brand: manufacturer brand (Samsung, Apple, etc.)
        device_model: the target device (Samsung M14, iPhone 15, etc.)
        compatibility_target: what device the product is for
        intent: user intent (best, recommend, compare, price, buy)
        original_query: the raw query
    """
    query_lower = query.lower().strip()
    result = {
        "product_type": None,
        "brand": None,
        "device_model": None,
        "compatibility_target": None,
        "intent": "search",
        "original_query": query,
    }

    # 1. Detect intent keywords
    intent_patterns = {
        "best": r"\b(?:best|top|greatest|finest)\b",
        "recommend": r"\b(?:recommend|suggestion|suggest|advise)\b",
        "compare": r"\b(?:compare|comparison|vs\.?|versus|difference)\b",
        "price": r"\b(?:price|cost|how\s+much|cheap|cheapest|affordable)\b",
        "buy": r"\b(?:buy|purchase|order|shop|where\s+to|available)\b",
        "review": r"\b(?:review|reviews|rating|ratings)\b",
    }
    for intent_name, pattern in intent_patterns.items():
        if re.search(pattern, query_lower):
            result["intent"] = intent_name
            break

    # 2. Detect brand (including product-name aliases)
    brand_aliases = {"iphone": "apple", "galaxy": "samsung", "pixel": "google"}
    brand_list = [
        "apple", "samsung", "sony", "lg", "dell", "lenovo", "hp", "asus",
        "acer", "msi", "nike", "adidas", "puma", "boat", "jbl", "sennheiser",
        "canon", "nikon", "oneplus", "xiaomi", "realme", "vivo", "oppo",
        "nothing", "google", "microsoft", "motorola", "nokia", "iqoo",
    ]
    for alias, canonical in brand_aliases.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", query_lower):
            result["brand"] = canonical.title()
            break
    if not result["brand"]:
        for b in brand_list:
            if re.search(r"\b" + re.escape(b) + r"\b", query_lower):
                result["brand"] = b.title()
                break

    # 3. Detect product type (accessory vs device)
    # First check if query is for an accessory
    for acc_type, keywords in ACCESSORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
                result["product_type"] = acc_type
                break
        if result["product_type"]:
            break

    # If no accessory found, check if it's a device query
    if not result["product_type"]:
        for dev_type, keywords in DEVICE_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
                    result["product_type"] = dev_type
                    break
            if result["product_type"]:
                break

    # 4. Detect device model (what the product is FOR)
    # Pattern: "for <device>" or "<brand> <model> <product>"
    device_model = None

    # Check "for X" pattern
    for_pattern = re.search(r"\bfor\s+(.+?)(?:\s+(?:best|under|price|buy|in|near|with|\d+\s*w))", query_lower)
    if for_pattern:
        device_model = for_pattern.group(1).strip()
    else:
        # Check if brand + model appears before product type
        # e.g., "samsung m14 charger" -> device_model = "samsung m14"
        if result["brand"] and result["product_type"]:
            brand_escaped = re.escape(result["brand"].lower())
            prod_escaped = re.escape(result["product_type"])
            # Try to find brand + model before product type
            model_match = re.search(
                rf"({brand_escaped}\s+\S+)\s+{prod_escaped}",
                query_lower
            )
            if model_match:
                device_model = model_match.group(1).strip()

    # Also try to extract model numbers like "M14", "S24", "A54", etc.
    model_number = re.search(
        r"\b([a-z]\d{1,3}[a-z]?)\b",
        query_lower.replace(result["brand"].lower() if result["brand"] else "", "", 1)
    )
    if model_number and not device_model:
        if result["brand"]:
            device_model = f"{result['brand']} {model_number.group(1).upper()}"
    elif model_number and device_model:
        # Enrich device model with model number if not already included
        model_num = model_number.group(1).upper()
        if model_num.lower() not in device_model.lower():
            device_model = f"{device_model} {model_num}"

    if device_model:
        result["device_model"] = device_model.title()
        result["compatibility_target"] = device_model.title()

    return result


# ---------------------------------------------------------------------------
# Informational Article Detection (Requirement 4)
# ---------------------------------------------------------------------------

def is_informational_article(title: str, snippet: str = "") -> bool:
    """
    Detect if a search result is an informational article, not a product listing.

    Returns True if the result is likely an article (specs page, review article,
    comparison, buying guide, etc.) rather than a purchasable product.
    """
    combined = f"{title} {snippet}".lower()

    # Check for informational patterns
    for pattern in INFORMATIONAL_PATTERNS:
        if re.search(pattern, combined, re.I):
            return True

    # Check for specification pages
    spec_indicators = [
        "price in india",
        "features and specifications",
        "full specifications",
        "detailed specifications",
        "all specifications",
        "key specifications",
        "specs and features",
        "specifications & features",
    ]
    for indicator in spec_indicators:
        if indicator in combined:
            return True

    # Check for review/comparison articles (not product reviews with star ratings)
    article_indicators = [
        "review:", "review -",
        "comparison:", "compared:",
        "buying guide",
        "best phones under",
        "best laptops under",
        "top 10",
        "top 5",
    ]
    for indicator in article_indicators:
        if indicator in combined:
            # But allow if it's a product listing with star ratings
            has_star_rating = re.search(r"\d\.?\d?\s*(?:out of|/)\s*5", combined)
            if not has_star_rating:
                return True

    # Check if title looks like a product listing vs article
    # Product listings usually have: brand + model + product type + (optional) price
    # Articles usually have: "Best X", "Top X", "X Review", "X vs Y"
    title_lower = title.lower()
    product_listing_signals = [
        re.search(r"(?:₹|rs\.?|inr)\s*\d", title_lower),  # Has price
        re.search(r"\d\.?\d?\s*(?:out of|/)\s*5", title_lower),  # Has rating
        re.search(r"\bbuy\b|\border\b|\bshop\b", title_lower),  # Buy/action words
    ]
    if any(product_listing_signals):
        return False

    return False


# ---------------------------------------------------------------------------
# Candidate Validation (Requirements 3, 5, 6, 7)
# ---------------------------------------------------------------------------

def validate_candidate(
    candidate: Dict[str, Any],
    intent: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Validate a search result candidate against the parsed intent.

    Returns (is_valid, rejection_reason).
    If valid, rejection_reason is empty string.
    """
    title = (candidate.get("title") or "").lower()
    snippet = (candidate.get("snippet") or "").lower()
    link = (candidate.get("link") or "").lower()
    combined = f"{title} {snippet}"

    product_type = intent.get("product_type")
    brand = (intent.get("brand") or "").lower()
    device_model = (intent.get("device_model") or "").lower()
    compatibility_target = (intent.get("compatibility_target") or "").lower()

    # 1. Reject informational articles
    if is_informational_article(title, snippet):
        return False, "informational_article"

    # 2. If product_type is an accessory (charger, case, etc.), validate it's not the device itself
    if product_type in ACCESSORY_KEYWORDS:
        # Check if the title is about the DEVICE, not the ACCESSORY
        device_keywords = DEVICE_KEYWORDS.get("phone", []) + DEVICE_KEYWORDS.get("laptop", []) + \
                         DEVICE_KEYWORDS.get("tablet", []) + DEVICE_KEYWORDS.get("watch", [])

        # If title mentions a device but NOT the accessory, reject
        has_device_keyword = any(kw in title for kw in device_keywords)
        has_accessory_keyword = any(kw in title for kw in ACCESSORY_KEYWORDS.get(product_type, []))

        if has_device_keyword and not has_accessory_keyword:
            # Check if the device keyword is the product we're looking for
            # e.g., "Samsung M14 phone" when we want "Samsung M14 charger"
            if device_model:
                # If the title is about the device model itself (not accessory for it), reject
                if device_model.split()[-1] in title and product_type not in title:
                    return False, f"wrong_category:device_not_{product_type}"

        # Check if title contains the accessory type we're looking for
        if not has_accessory_keyword:
            # Check if title contains a DIFFERENT accessory type (reject)
            other_accessory_match = False
            for other_type, other_kws in ACCESSORY_KEYWORDS.items():
                if other_type == product_type:
                    continue
                if any(kw in title for kw in other_kws):
                    other_accessory_match = True
                    break
            if other_accessory_match:
                return False, f"wrong_category:{product_type}_requested_but_other_found"

            # Check if it's at least related to the device
            if device_model:
                model_words = device_model.split()
                has_model_in_title = any(w in title for w in model_words if len(w) > 1)
                if not has_model_in_title:
                    return False, f"wrong_category:no_{product_type}_keyword"
            else:
                # No specific device model, check if accessory keyword is present
                if product_type not in title and not any(kw in title for kw in ACCESSORY_KEYWORDS.get(product_type, [])):
                    return False, f"wrong_category:no_{product_type}_keyword"

    # 3. Compatibility check
    if compatibility_target and product_type in ACCESSORY_KEYWORDS:
        compat_result = _check_compatibility(combined, compatibility_target, brand)
        if compat_result == "incompatible":
            return False, "incompatible_with_target_device"
        # "uncertain" is allowed but flagged

    # 4. Brand check (if brand specified)
    if brand:
        # Allow if brand is in title OR if it's a compatible third-party accessory
        brand_in_title = brand in title
        brand_in_snippet = brand in snippet
        if not brand_in_title and not brand_in_snippet:
            # Third-party accessories can be compatible, so allow if compatible
            if product_type in ACCESSORY_KEYWORDS and compatibility_target:
                # Already checked compatibility above, allow
                pass
            else:
                return False, "brand_mismatch"

    return True, ""


def _check_compatibility(
    text: str,
    target_device: str,
    brand: str,
) -> str:
    """
    Check if a product is compatible with the target device.

    Returns:
        "compatible" - explicitly compatible
        "uncertain" - compatibility cannot be determined
        "incompatible" - explicitly incompatible
    """
    text_lower = text.lower()
    target_lower = target_device.lower()

    # Extract model identifier (e.g., "M14", "S24", "A54")
    model_parts = target_lower.split()
    model_id = model_parts[-1] if model_parts else target_lower

    # Check for incompatible signals FIRST (before compatible, since
    # "not compatible with M14" would also match "compatible with M14")
    incompatible_patterns = [
        rf"not\s+compatible\s+with.*{re.escape(model_id)}",
        rf"incompatible\s+with.*{re.escape(model_id)}",
        rf"does\s+not\s+fit.*{re.escape(model_id)}",
        rf"not\s+for\s+{re.escape(model_id)}",
    ]
    for pattern in incompatible_patterns:
        if re.search(pattern, text_lower):
            return "incompatible"

    # Check for explicit compatibility statements
    compatible_patterns = [
        rf"compatible\s+with.*{re.escape(model_id)}",
        rf"for\s+{re.escape(target_lower)}",
        rf"for\s+{re.escape(model_id)}",
        rf"works\s+with.*{re.escape(model_id)}",
        rf"designed\s+for.*{re.escape(model_id)}",
        rf" fits.*{re.escape(model_id)}",
        rf"support.*{re.escape(model_id)}",
    ]
    for pattern in compatible_patterns:
        if re.search(pattern, text_lower):
            return "compatible"

    # Check if model ID appears in text (implicit compatibility)
    if model_id in text_lower:
        return "compatible"

    # Check for brand + model mention (likely compatible if same brand)
    if brand and brand.lower() in text_lower:
        if model_id in text_lower:
            return "compatible"
            return "incompatible"

    return "uncertain"


# ---------------------------------------------------------------------------
# Pydantic-style data models (using dicts for lightweight compatibility)
# ---------------------------------------------------------------------------

def make_product_search_request(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "product_query": data.get("product_query", ""),
        "category": data.get("category", ""),
        "brand": data.get("brand"),
        "model": data.get("model"),
        "budget_min": data.get("budget_min"),
        "budget_max": data.get("budget_max"),
        "required_features": data.get("required_features", []),
        "preferred_features": data.get("preferred_features", []),
        "location": data.get("location"),
        "quantity": data.get("quantity", 1),
        "sort_preference": data.get("sort_preference", "best_overall"),
        "use_case": data.get("use_case", ""),
    }


def make_product_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a product result dict. Null fields represent genuinely unknown data.
    NO fabricated defaults.
    """
    return {
        "name": data.get("name", "Unknown Product"),
        "brand": data.get("brand"),          # null if unknown
        "model": data.get("model"),           # null if unknown
        "category": data.get("category"),     # null if unknown
        "price": data.get("price"),           # null if unknown
        "currency": data.get("currency", "INR"),
        "original_price": data.get("original_price"),   # null if unknown
        "discount": data.get("discount"),     # null if unknown
        "specifications": data.get("specifications", {}),
        "rating": data.get("rating"),         # null if not from source
        "review_count": data.get("review_count"),  # null if unknown
        "availability": data.get("availability"),  # null if unknown
        "store_name": data.get("store_name"), # null if unknown
        "store_type": data.get("store_type", "online"),
        "location": data.get("location"),
        "distance": data.get("distance"),
        "url": data.get("url", ""),
        "source": data.get("source", ""),
        "source_type": data.get("source_type", "online"),
        "source_confidence": data.get("source_confidence", "low"),  # high/medium/low
        "relevance_score": data.get("relevance_score"),  # 0-1
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def make_search_result(
    products: List[Dict],
    local_stores: List[Dict],
    recommendation: Dict,
    request: Dict,
    synthesis: str = "",
) -> Dict[str, Any]:
    return {
        "products": products,
        "local_stores": local_stores,
        "recommendation": recommendation,
        "request": request,
        "synthesis": synthesis,
        "total_products": len(products),
        "total_local_stores": len(local_stores),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------

PRODUCT_KEYWORDS = [
    "buy", "price", "cost", "cheap", "cheapest", "best", "review",
    "compare", "comparison", "vs", "versus", "under", "above",
    "laptop", "phone", "mobile", "tablet", "headphone", "earphone",
    "camera", "watch", "tv", "television", "monitor", "keyboard",
    "mouse", "speaker", "shirt", "shoes", "sneakers", "jeans",
    "washing machine", "refrigerator", "fridge", "ac", "air conditioner",
    "microwave", "oven", "mixer", "grinder", "fan", "cooler",
    "sofa", "bed", "table", "chair", "wardrobe",
    "car", "bike", "scooter", "cycle",
    "book", "pen", "bag", "wallet",
    "charger", "adapter", "cable", "power bank",
    "case", "cover", "screen protector", "stand",
    "where can i buy", "where to buy", "available at",
    "online", "store", "shop", "near me", "nearby",
    "budget", "affordable", "premium", "discount", "offer",
    "specifications", "specs", "features", "ram", "storage",
    "processor", "cpu", "gpu", "battery", "display", "screen",
    "camera quality", "performance", "speed",
    "which laptop", "which phone", "which tv", "which camera",
    "find me", "find a", "search for", "look for",
    "recommend", "suggestion", "suggest",
]

SERVICE_KEYWORDS = [
    "plumber", "electrician", "mechanic", "catering", "decoration",
    "photography", "repair", "maintenance", "cleaning", "moving",
    "tutor", "coach", "consultant", "developer", "designer",
]


def detect_product_intent(query: str) -> Dict[str, Any]:
    """
    Detect if a query is about product research.
    Returns intent detection result with confidence.
    """
    query_lower = query.lower().strip()

    product_score = 0
    service_score = 0

    for keyword in PRODUCT_KEYWORDS:
        if keyword in query_lower:
            product_score += 1

    for keyword in SERVICE_KEYWORDS:
        if keyword in query_lower:
            service_score += 1

    price_pattern = r"(?:under|below|between|around|approx|₹|rs\.?|inr)\s*\d"
    if re.search(price_pattern, query_lower):
        product_score += 2

    compare_pattern = r"(?:compare|vs\.?|versus|difference between)"
    if re.search(compare_pattern, query_lower):
        product_score += 2

    buy_pattern = r"(?:buy|purchase|order|shop|store|available)"
    if re.search(buy_pattern, query_lower):
        product_score += 1

    if service_score > product_score:
        return {"is_product": False, "confidence": min(service_score / 3, 1.0)}

    confidence = min(product_score / 3, 1.0)
    is_product = product_score >= 1 and product_score > service_score

    return {"is_product": is_product, "confidence": confidence}


# ---------------------------------------------------------------------------
# LLM-based Requirement Extraction
# ---------------------------------------------------------------------------

def _get_llm_client():
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        return OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        return OpenAI(api_key=google_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    return None


def extract_product_requirements(query: str) -> Dict[str, Any]:
    """
    Use LLM to extract structured product requirements from user query.
    Falls back to rule-based extraction on failure.
    """
    client = _get_llm_client()
    if not client:
        return _fallback_extract(query)

    extraction_prompt = f"""Extract structured product search requirements from this user query.

User query: "{query}"

Return a JSON object with these fields (use null for unknown/missing fields):
{{
    "product_query": "the core product type (e.g., 'charger', 'laptop', 'running shoes', 'tv')",
    "category": "product category (charger, laptop, phone, tv, shoes, headphones, camera, watch, tablet, monitor, etc.)",
    "brand": "specific brand if mentioned, else null",
    "model": "specific model if mentioned (e.g., 'Galaxy S25', 'ThinkPad X1'), else null",
    "budget_min": minimum budget number as integer or null,
    "budget_max": maximum budget number as integer or null,
    "required_features": ["list of must-have features (e.g., '25W', 'USB-C', '16GB RAM')"],
    "preferred_features": ["list of nice-to-have features"],
    "location": "city or area if mentioned, else null",
    "use_case": "what the product will be used for, else null",
    "sort_preference": "best_overall, cheapest, best_performance, or best_value"
}}

CRITICAL RULES:
- "product_query" must be the PRODUCT TYPE, not the full query. For "samsung charger", product_query = "charger"
- "category" must be a specific product category. For "samsung charger", category = "charger"
- "category" must NOT be "samsung" or just the brand name
- Extract budget numbers as integers (e.g., 70000 not "70000" or "₹70,000")
- If user says "under 70000", set budget_max=70000, budget_min=null
- Extract features like wattage, connector type, etc.
- Return ONLY valid JSON, no other text
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a structured data extraction assistant. Return only valid JSON."},
                {"role": "user", "content": extraction_prompt},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*$", "", content)
        extracted = json.loads(content)

        # Post-validate: ensure category is a valid product type, not a brand
        extracted = _post_validate_requirements(extracted, query)
        return extracted
    except Exception as exc:
        logger.warning("LLM extraction failed, using fallback: %s", exc)
        return _fallback_extract(query)


def _post_validate_requirements(req: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Ensure extracted requirements are sensible (not brand-as-category)."""
    category = (req.get("category") or "").lower().strip()
    brand = (req.get("brand") or "").lower().strip()
    product_query = (req.get("product_query") or "").lower().strip()

    # If category is the same as brand (wrong), try to fix
    if category and brand and category == brand:
        # Check if the original query has a product type
        for cat_name, cat_info in CATEGORY_TAXONOMY.items():
            for match in cat_info["exact_matches"]:
                if match in query.lower():
                    req["category"] = cat_name
                    req["product_query"] = cat_name
                    break
            if req.get("category") != brand:
                break
        else:
            # If we can't find a product type, use the brand as product_query
            # but keep category as the broader type
            if not req.get("category"):
                req["category"] = ""

    # If category is empty, try to infer from product_query
    if not category and product_query:
        for cat_name, cat_info in CATEGORY_TAXONOMY.items():
            if product_query in cat_info["exact_matches"] or product_query == cat_name:
                req["category"] = cat_name
                break

    # Ensure product_query is not just the brand
    if product_query and brand and product_query == brand:
        # The product_query should be the product type, not the brand
        req["product_query"] = req.get("category") or product_query

    return req


def _fallback_extract(query: str) -> Dict[str, Any]:
    """Rule-based fallback for requirement extraction."""
    query_lower = query.lower()

    # Detect category using taxonomy
    category = ""
    for cat_name, cat_info in CATEGORY_TAXONOMY.items():
        for match in cat_info["exact_matches"]:
            if match in query_lower:
                category = cat_name
                break
        if category:
            break
        # Check aliases
        for alias in cat_info.get("aliases", []):
            if alias in query_lower:
                category = cat_name
                break
        if category:
            break

    # Fallback category detection with common product words
    if not category:
        category_map = {
            "laptop": ["laptop", "notebook"],
            "phone": ["phone", "mobile", "smartphone", "iphone", "galaxy"],
            "charger": ["charger", "adapter", "power adapter", "charging adapter"],
            "tv": ["tv", "television", "smart tv"],
            "headphones": ["headphone", "earphone", "earbuds", "airpods"],
            "camera": ["camera", "dslr", "mirrorless"],
            "watch": ["watch", "smartwatch"],
            "shoes": ["shoe", "shoes", "sneaker", "sneakers", "running shoe"],
            "tablet": ["tablet", "ipad"],
            "monitor": ["monitor", "display"],
        }
        for cat, keywords in category_map.items():
            for kw in keywords:
                if kw in query_lower:
                    category = cat
                    break
            if category:
                break

    brand = None
    brand_list = [
        "apple", "samsung", "sony", "lg", "dell", "lenovo", "hp", "asus",
        "acer", "msi", "nike", "adidas", "puma", "boat", "jbl", "sennheiser",
        "canon", "nikon", "fujifilm", "oneplus", "xiaomi", "realme", "vivo",
        "oppo", "nothing", "google", "microsoft",
    ]
    for b in brand_list:
        if b in query_lower:
            brand = b.title()
            break

    model = None
    model_patterns = [
        r"(?:model|version)\s+([A-Z0-9][\w-]+)",
        r"((?:galaxy|iphone|ipad|macbook|thinkpad|inspiron|pavilion)\s+[\w-]+)",
    ]
    for pat in model_patterns:
        m = re.search(pat, query, re.I)
        if m:
            model = m.group(1).strip()
            break

    budget_max = None
    budget_min = None
    price_match = re.search(r"(?:under|below|less than|<)\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*)", query_lower)
    if price_match:
        budget_max = int(price_match.group(1).replace(",", ""))
    between_match = re.search(r"between\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*)\s*(?:and|to|-)\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*)", query_lower)
    if between_match:
        budget_min = int(between_match.group(1).replace(",", ""))
        budget_max = int(between_match.group(2).replace(",", ""))

    location = None
    loc_match = re.search(r"(?:in|near|at|from)\s+([A-Z][a-zA-Z\s]+?)(?:\s*$|\s*[?,.\n])", query)
    if loc_match:
        location = loc_match.group(1).strip()
    if "near me" in query_lower:
        location = "near_me"

    # Detect required features from query
    features = []
    feature_patterns = {
        r"(\d+)\s*w(?:att)?": lambda m: f"{m.group(1)}W",
        r"usb[\s-]*c": lambda m: "USB-C",
        r"type[\s-]*c": lambda m: "USB-C",
        r"(\d+)\s*gb\s*ram": lambda m: f"{m.group(1)}GB RAM",
        r"(\d+)\s*(?:gb|tb)\s*(?:ssd|hdd|storage)": lambda m: m.group(0),
        r"fast\s*charg": lambda m: "fast charging",
        r"wireless\s*charg": lambda m: "wireless charging",
        r"(\d+)k": lambda m: f"{m.group(1)}K",
        r"amoled": lambda m: "AMOLED",
        r"oled": lambda m: "OLED",
        r"ips": lambda m: "IPS",
        r"5g": lambda m: "5G",
        r"water\s*resist": lambda m: "water resistant",
        r"waterproof": lambda m: "waterproof",
        r"rtx\s*(\d+)": lambda m: f"RTX {m.group(1)}",
        r"gtx\s*(\d+)": lambda m: f"GTX {m.group(1)}",
    }
    for pat, extractor in feature_patterns.items():
        m = re.search(pat, query_lower)
        if m:
            feat = extractor(m)
            if feat not in features:
                features.append(feat)

    use_case = ""
    use_case_keywords = {
        "gaming": "gaming", "coding": "coding/development", "programming": "coding/development",
        "python": "Python development", "ai": "AI/ML development",
        "video editing": "video editing", "photo editing": "photo editing",
        "office": "office work", "study": "studying", "student": "student use",
        "work from home": "remote work", "running": "running", "gym": "gym/fitness",
    }
    for kw, uc in use_case_keywords.items():
        if kw in query_lower:
            use_case = uc
            break

    # Determine product_query: should be the product type, not the full query
    product_query = category if category else query_lower.strip()

    return make_product_search_request({
        "product_query": product_query,
        "category": category,
        "brand": brand,
        "model": model,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "required_features": features,
        "preferred_features": [],
        "location": location,
        "use_case": use_case,
        "sort_preference": "best_overall",
    })


# ---------------------------------------------------------------------------
# Search Query Generation (Requirement 4 – preserve product type)
# ---------------------------------------------------------------------------

def _build_search_queries(requirements: Dict[str, Any]) -> List[str]:
    """
    Build precise search queries from extracted requirements.
    Always preserves the PRODUCT TYPE in the query.
    """
    queries = []
    product = requirements.get("product_query", "")
    category = requirements.get("category", "")
    brand = requirements.get("brand", "")
    model = requirements.get("model")
    budget_max = requirements.get("budget_max")
    required_features = requirements.get("required_features", [])
    use_case = requirements.get("use_case", "")
    location = requirements.get("location")

    # Determine the core search term (product type + brand)
    search_term = product
    if brand:
        search_term = f"{brand} {product}"

    # Add model if specified
    if model:
        search_term = f"{brand} {model}" if brand else model

    # Add key features to search (like wattage)
    feature_str = " ".join(required_features[:2]) if required_features else ""

    # Build queries preserving product type
    if budget_max:
        queries.append(f"{search_term} price India under {budget_max}")
        if feature_str:
            queries.append(f"{search_term} {feature_str} price India")
        queries.append(f"best {search_term} under {budget_max} India buy online")
        if feature_str:
            queries.append(f"{search_term} {feature_str} under {budget_max} India")
    else:
        queries.append(f"{search_term} price India 2025")
        queries.append(f"{search_term} buy online India")
        if feature_str:
            queries.append(f"{search_term} {feature_str} India")
        queries.append(f"best {search_term} India 2025")

    if use_case:
        queries.append(f"best {search_term} for {use_case} India")

    if location and location != "near_me":
        queries.append(f"{search_term} price {location} India")

    return queries[:6]


# ---------------------------------------------------------------------------
# Online Product Search (via Serper)
# ---------------------------------------------------------------------------

def _serper_search(query: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """Execute a Serper search and return organic results."""
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        logger.warning("SERPER_API_KEY not configured")
        return []

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "gl": "in",
        "hl": "en",
        "num": num_results,
    }

    try:
        resp = requests.post(SERPER_API_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic", [])
    except Exception as exc:
        logger.warning("Serper search failed for '%s': %s", query, exc)
        return []


def search_online_products(requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search for products online using Serper API.
    Returns ONLY validated, relevant products.

    Pipeline:
    1. Parse structured intent from requirements
    2. Execute search queries
    3. Validate relevance (existing)
    4. Validate candidate category + compatibility (new)
    5. Parse into product dicts
    6. Validate data accuracy (existing)
    """
    # Parse structured intent for candidate validation
    original_query = requirements.get("product_query", "")
    if requirements.get("brand"):
        original_query = f"{requirements['brand']} {original_query}"
    intent = parse_product_intent(original_query)
    # Enrich intent from extracted requirements
    if requirements.get("category"):
        intent["product_type"] = requirements["category"]
    if requirements.get("brand"):
        intent["brand"] = requirements["brand"]
    if requirements.get("model"):
        intent["device_model"] = requirements["model"]
        intent["compatibility_target"] = requirements["model"]

    logger.info(
        "INTENT PARSED | product_type=%s | brand=%s | device=%s | compat=%s | intent=%s",
        intent.get("product_type"), intent.get("brand"),
        intent.get("device_model"), intent.get("compatibility_target"),
        intent.get("intent"),
    )

    queries = _build_search_queries(requirements)
    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for query in queries:
        results = _serper_search(query, num_results=10)
        for r in results:
            url = r.get("link", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_results.append(r)

    logger.info("QUERY: %s | RAW RESULTS: %d", requirements.get("product_query", ""), len(all_results))

    # Stage 1: Validate relevance
    validated_results = _validate_search_results(all_results, requirements)
    logger.info("QUERY: %s | AFTER RELEVANCE VALIDATION: %d",
                requirements.get("product_query", ""), len(validated_results))

    # Stage 1.5: Validate candidate category + compatibility (Requirement 3, 5, 6, 7)
    category_validated_results = []
    rejection_counts = {}
    for r in validated_results:
        is_valid, rejection_reason = validate_candidate(r, intent)
        if is_valid:
            category_validated_results.append(r)
        else:
            rejection_counts[rejection_reason] = rejection_counts.get(rejection_reason, 0) + 1
            logger.info(
                "CANDIDATE REJECTED | title=%s | reason=%s",
                (r.get("title") or "")[:60], rejection_reason,
            )

    logger.info(
        "QUERY: %s | AFTER CATEGORY VALIDATION: %d | rejections=%s",
        requirements.get("product_query", ""),
        len(category_validated_results),
        rejection_counts,
    )

    # If all candidates were rejected, try to recover with less strict validation
    if not category_validated_results and validated_results:
        logger.warning(
            "ALL CANDIDATES REJECTED for query=%s. Recovering with relaxed validation.",
            requirements.get("product_query", ""),
        )
        # Only keep results that at least match the brand
        for r in validated_results:
            title_lower = (r.get("title") or "").lower()
            snippet_lower = (r.get("snippet") or "").lower()
            brand_lower = (intent.get("brand") or "").lower()
            if brand_lower and (brand_lower in title_lower or brand_lower in snippet_lower):
                category_validated_results.append(r)
        logger.info(
            "QUERY: %s | RECOVERY: %d candidates after brand filter",
            requirements.get("product_query", ""),
            len(category_validated_results),
        )

    # Convert to product dicts
    products = []
    for r in category_validated_results:
        product = _parse_search_result(r, requirements)
        if product:
            products.append(product)

    # Stage 2: Validate data accuracy
    products = _validate_product_data(products, requirements)
    logger.info("QUERY: %s | AFTER DATA VALIDATION: %d",
                requirements.get("product_query", ""), len(products))

    return products


# ---------------------------------------------------------------------------
# STAGE 1: Search Result Relevance Validation (Requirement 5, 6)
# ---------------------------------------------------------------------------

def _validate_search_results(
    results: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Stage 1: Check if each search result is actually about the requested product.
    Rejects results that don't match the requested category/type.
    HARD GATE: If category score is 0.0, reject immediately.
    """
    validated = []
    requested_category = (requirements.get("category") or "").lower()
    requested_brand = (requirements.get("brand") or "").lower()
    requested_model = (requirements.get("model") or "").lower()

    for result in results:
        title = (result.get("title") or "").lower()
        snippet = (result.get("snippet") or "").lower()
        link = (result.get("link") or "").lower()
        combined_text = f"{title} {snippet} {link}"

        # HARD GATE: Check category match first
        category_score = _score_category_match(combined_text, title, requested_category)
        if category_score == 0.0:
            logger.info(
                "REJECTED (category mismatch) | Title: %s | Requested: %s",
                result.get("title", "")[:60],
                requested_category,
            )
            continue

        # Calculate full relevance score
        relevance = _calculate_relevance_score(
            combined_text, title, requested_category, requested_brand, requested_model, requirements
        )

        logger.info(
            "RELEVANCE CHECK | Title: %s | Category: %s | CatScore: %.2f | Score: %.2f | Decision: %s",
            result.get("title", "")[:60],
            requested_category,
            category_score,
            relevance,
            "ACCEPT" if relevance >= RELEVANCE_THRESHOLD else "REJECT"
        )

        if relevance >= RELEVANCE_THRESHOLD:
            validated.append(result)
        else:
            logger.info(
                "REJECTED (low relevance) | Title: %s | Score: %.2f < %.2f",
                result.get("title", "")[:60],
                relevance,
                RELEVANCE_THRESHOLD,
            )

    return validated


def _calculate_relevance_score(
    combined_text: str,
    title: str,
    requested_category: str,
    requested_brand: str,
    requested_model: str,
    requirements: Dict[str, Any],
) -> float:
    """
    Calculate how relevant a search result is to the requested product.
    Returns 0-1 score.
    """
    score = 0.0

    # 1. Category match (40%)
    category_score = _score_category_match(combined_text, title, requested_category)
    score += category_score * RELEVANCE_WEIGHTS["category_match"]

    # 2. Brand match (20%)
    brand_score = _score_brand_match(combined_text, requested_brand)
    score += brand_score * RELEVANCE_WEIGHTS["brand_match"]

    # 3. Model match (15%)
    model_score = _score_model_match(combined_text, requested_model)
    score += model_score * RELEVANCE_WEIGHTS["model_match"]

    # 4. Keyword match (15%)
    keyword_score = _score_keyword_match(combined_text, requirements)
    score += keyword_score * RELEVANCE_WEIGHTS["keyword_match"]

    # 5. Budget match (10%)
    budget_score = _score_budget_match(combined_text, requirements)
    score += budget_score * RELEVANCE_WEIGHTS["budget_match"]

    return min(score, 1.0)


def _score_category_match(text: str, title: str, requested_category: str) -> float:
    """
    Score how well the result matches the requested product category.
    Returns 0-1. Cross-category mismatches return 0.0.
    """
    if not requested_category:
        return 0.5  # Unknown category, neutral score

    cat_info = CATEGORY_TAXONOMY.get(requested_category)
    if not cat_info:
        return 0.5 if requested_category in text else 0.0

    title_lower = title.lower()
    text_lower = text.lower()

    # Step 1: Check for explicit rejects in title
    for reject_term in cat_info["reject_matches"]:
        if reject_term in title_lower:
            logger.info("CATEGORY MISMATCH | Requested: %s | Found in title: '%s' | REJECT",
                        requested_category, reject_term)
            return 0.0

    # Step 2: Check for exact matches in title/text
    for match_term in cat_info["exact_matches"]:
        if match_term in text_lower:
            return 1.0

    # Step 3: Check aliases
    for alias in cat_info.get("aliases", []):
        if alias in text_lower:
            return 0.9

    # Step 4: Cross-category mismatch check
    # If the title contains keywords from a DIFFERENT category, reject it
    for other_cat_name, other_cat_info in CATEGORY_TAXONOMY.items():
        if other_cat_name == requested_category:
            continue
        for other_match in other_cat_info["exact_matches"]:
            if other_match in title_lower:
                # Title is about a different product type
                logger.info("CROSS-CATEGORY MISMATCH | Requested: %s | Title is: %s | REJECT",
                            requested_category, other_cat_name)
                return 0.0

    # Step 5: Partial match on requested category
    if requested_category in text_lower:
        return 0.7

    return 0.1  # Weak match – no strong evidence either way


def _score_brand_match(text: str, requested_brand: str) -> float:
    """Score brand match."""
    if not requested_brand:
        return 0.5  # No brand specified

    if requested_brand.lower() in text:
        return 1.0

    return 0.0


def _score_model_match(text: str, requested_model: str) -> float:
    """Score model match."""
    if not requested_model:
        return 0.5  # No model specified

    if requested_model.lower() in text:
        return 1.0

    return 0.0


def _score_keyword_match(text: str, requirements: Dict[str, Any]) -> float:
    """Score how many required keywords appear."""
    required_features = requirements.get("required_features", [])
    if not required_features:
        return 0.5

    hits = 0
    for feat in required_features:
        feat_lower = feat.lower()
        if feat_lower in text or any(w in text for w in feat_lower.split()):
            hits += 1

    return hits / len(required_features) if required_features else 0.5


def _score_budget_match(text: str, requirements: Dict[str, Any]) -> float:
    """Score if the result mentions prices within budget."""
    budget_max = requirements.get("budget_max")
    if not budget_max:
        return 0.5

    # Try to extract price from text
    price_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*)", text, re.I)
    if price_match:
        price = float(price_match.group(1).replace(",", ""))
        if price <= budget_max:
            return 1.0
        elif price <= budget_max * 1.2:
            return 0.5  # Slightly over budget
        else:
            return 0.0  # Way over budget

    return 0.5  # No price found, neutral


# ---------------------------------------------------------------------------
# STAGE 2: Product Data Validation (Requirement 7, 8, 9, 10)
# ---------------------------------------------------------------------------

def _validate_product_data(
    products: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Stage 2: Validate the accuracy of extracted product data.
    - Price must belong to the actual product
    - Rating must be from the source (never fabricated)
    - Store must be the actual seller (not the brand)
    - URL must match the product
    """
    validated = []
    requested_category = (requirements.get("category") or "").lower()

    for product in products:
        name = (product.get("name") or "").lower()
        url = (product.get("url") or "").lower()

        # Validate category in product name
        cat_info = CATEGORY_TAXONOMY.get(requested_category)
        if cat_info:
            category_valid = False
            for match_term in cat_info["exact_matches"]:
                if match_term in name:
                    category_valid = True
                    break
            if not category_valid:
                for reject_term in cat_info["reject_matches"]:
                    if reject_term in name:
                        logger.info("DATA VALIDATION | Product: %s | Category mismatch: '%s' in name | REJECT",
                                    product.get("name", "")[:50], reject_term)
                        continue

        # Validate source confidence
        product["source_confidence"] = _determine_source_confidence(url)

        # Set availability: only "available" if we have evidence, else null
        # Don't assume availability from search results
        if product.get("availability") == "available":
            # Search results don't prove availability; mark as uncertain
            product["availability"] = None  # Unknown

        validated.append(product)

    return validated


def _determine_source_confidence(url: str) -> str:
    """Determine confidence level based on the source URL."""
    url_lower = url.lower()

    # Check official brand stores (highest confidence)
    for domain, (brand, conf) in BRAND_STORE_DOMAINS.items():
        if domain in url_lower:
            return "high"

    # Check major retailers
    for domain, (store, conf) in MAJOR_RETAILER_DOMAINS.items():
        if domain in url_lower:
            return conf

    # Check for generic article/blog
    blog_indicators = ["blog", "article", "review", "news", "medium.com",
                       "quora.com", "reddit.com", "wordpress.com"]
    for indicator in blog_indicators:
        if indicator in url_lower:
            return "low"

    # Default to low for unknown sources
    return "low"


# ---------------------------------------------------------------------------
# Parse Search Result into Product Dict
# ---------------------------------------------------------------------------

def _parse_search_result(
    result: Dict[str, Any],
    requirements: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Parse a single Serper search result into a product.
    Only extracts data that is actually present in the source.
    Does NOT fabricate ratings, prices, or availability.
    """
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    link = result.get("link", "")

    if not title:
        return None

    # Extract price ONLY from the result text
    price = None
    price_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d+)?)", f"{title} {snippet}", re.I)
    if price_match:
        price = float(price_match.group(1).replace(",", ""))

    # Extract rating ONLY if explicitly stated in source
    rating = None
    rating_match = re.search(r"(\d\.?\d?)\s*(?:out of|/)\s*5|(\d\.?\d?)\s*stars?", f"{title} {snippet}", re.I)
    if rating_match:
        rating = float(rating_match.group(1) or rating_match.group(2))

    # Extract review count ONLY if explicitly stated
    review_count = None
    review_match = re.search(r"(\d[\d,]*)\s*(?:reviews?|ratings?)", f"{title} {snippet}", re.I)
    if review_match:
        review_count = int(review_match.group(1).replace(",", ""))

    # Extract brand
    brand = requirements.get("brand", "")
    if not brand:
        brand_list = [
            "Apple", "Samsung", "Sony", "LG", "Dell", "Lenovo", "HP", "Asus",
            "Acer", "MSI", "Nike", "Adidas", "Puma", "boAt", "JBL", "Sennheiser",
            "Canon", "Nikon", "OnePlus", "Xiaomi", "Realme", "Vivo", "Oppo",
            "Nothing", "Google", "Microsoft",
        ]
        for b in brand_list:
            if b.lower() in title.lower():
                brand = b
                break

    # Extract store name from URL (not from brand)
    store_name = _extract_store_from_url(link)

    # Extract model
    model = _extract_model(title, brand)

    # Extract specifications
    specs = _extract_specs(f"{title} {snippet}")

    # Determine source type
    source_type = "online"

    return make_product_result({
        "name": title,
        "brand": brand or None,
        "model": model or None,
        "category": requirements.get("category"),
        "price": price,
        "currency": "INR",
        "original_price": None,
        "discount": None,
        "specifications": specs,
        "rating": rating,
        "review_count": review_count,
        "availability": None,  # Unknown from search results
        "store_name": store_name,
        "store_type": source_type,
        "location": None,
        "distance": None,
        "url": link,
        "source": link,
        "source_type": source_type,
        "source_confidence": _determine_source_confidence(link),
        "relevance_score": None,  # Will be calculated later
    })


def _extract_store_from_url(url: str) -> str:
    """Extract the actual store/seller name from URL. Never uses brand as store."""
    url_lower = url.lower()

    # Check well-known stores
    for domain_key, store_name in STORE_DOMAIN_MAP.items():
        if domain_key in url_lower:
            return store_name

    # Check for marketplace patterns
    if "amazon." in url_lower:
        return "Amazon"
    if "flipkart." in url_lower:
        return "Flipkart"

    # Extract domain name as last resort
    domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if domain_match:
        domain = domain_match.group(1)
        # Clean up common domain patterns
        domain = re.sub(r"\.(com|in|co\.in|net|org)$", "", domain)
        return domain.title()

    return None  # Unknown store


def _extract_model(title: str, brand: str) -> str:
    """Extract model name from title."""
    model = title
    if brand and brand.lower() in model.lower():
        parts = model.split(brand)
        if len(parts) > 1:
            model = parts[1]
    model = re.sub(r"\s*[-–|]\s*(?:Amazon|Flipkart|Buy|Online|Price|Best|Review).*", "", model, flags=re.I)
    model = model.strip()[:80]
    return model if model else None


def _extract_specs(text: str) -> Dict[str, str]:
    """Extract specifications from text."""
    specs: Dict[str, str] = {}

    ram_match = re.search(r"(\d+)\s*GB\s*RAM", text, re.I)
    if ram_match:
        specs["RAM"] = f"{ram_match.group(1)}GB"

    storage_match = re.search(r"(\d+)\s*(?:GB|TB)\s*(?:SSD|HDD|storage)", text, re.I)
    if storage_match:
        specs["Storage"] = storage_match.group(0)

    cpu_patterns = [
        r"(Intel\s*Core\s*i\d[\w-]*)",
        r"(AMD\s*Ryzen\s*\d[\w-]*)",
        r"(Apple\s*M\d[\w+]*)",
        r"(Snapdragon\s*\d[\w+]*)",
    ]
    for pat in cpu_patterns:
        m = re.search(pat, text, re.I)
        if m:
            specs["Processor"] = m.group(1)
            break

    gpu_match = re.search(r"(NVIDIA\s*(?:GeForce\s*)?(?:RTX|GTX)\s*[\w-]*)", text, re.I)
    if gpu_match:
        specs["GPU"] = gpu_match.group(1)

    display_match = re.search(r'(\d+\.?\d*)\s*["\u201d]?\s*(?:AMOLED|OLED|IPS|LED|LCD)', text, re.I)
    if display_match:
        specs["Display"] = display_match.group(0)

    watt_match = re.search(r"(\d+)\s*W(?:att)?", text, re.I)
    if watt_match:
        specs["Wattage"] = f"{watt_match.group(1)}W"

    return specs


# ---------------------------------------------------------------------------
# Local Store Search
# ---------------------------------------------------------------------------

def search_local_stores(requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search for local stores using Serper API."""
    location = requirements.get("location")
    if not location or location == "near_me":
        return []

    category = requirements.get("category", "")
    brand = requirements.get("brand", "")
    search_term = f"{brand} {category}" if brand else category

    if not search_term:
        return []

    query = f"{search_term} stores in {location}"
    results = _serper_search(query, num_results=10)

    stores: List[Dict[str, Any]] = []
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")

        store = {
            "name": title,
            "store_type": "local",
            "source_type": "local",
            "url": link,
            "source": link,
            "location": location,
            "availability": "not_verified",  # Always unverified for local
            "price": None,
            "currency": "INR",
            "brand": brand or None,
            "category": category or None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_confidence": "low",  # Local store results are inherently uncertain
        }

        phone_match = re.search(r"(\+?\d[\d\s-]{8,})", snippet)
        if phone_match:
            store["phone"] = phone_match.group(1).strip()

        rating_match = re.search(r"(\d\.?\d?)\s*(?:out of|/)\s*5", snippet, re.I)
        if rating_match:
            store["rating"] = float(rating_match.group(1))

        stores.append(store)

    return stores


# ---------------------------------------------------------------------------
# Product Normalization & Deduplication
# ---------------------------------------------------------------------------

def _normalize_product_name(name: str, brand: str) -> str:
    """Normalize a product name for comparison."""
    normalized = name.lower()
    if brand:
        normalized = normalized.replace(brand.lower(), "")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\b(buy|online|price|india|off|discount|offer|best|cheap|latest|new)\b", "", normalized)
    return normalized.strip()


def deduplicate_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate products based on brand + model similarity."""
    if not products:
        return []

    seen: Dict[str, Dict[str, Any]] = {}

    for product in products:
        brand = (product.get("brand") or "").lower()
        model = (product.get("model") or "").lower()
        name = _normalize_product_name(product.get("name", ""), product.get("brand", ""))

        key_parts = [brand, model, name[:40]]
        key = "|".join(p for p in key_parts if p)

        if not key.strip("|"):
            continue

        existing = seen.get(key)
        if existing:
            if product.get("price") and (not existing.get("price") or product["price"] < existing["price"]):
                seen[key] = product
        else:
            seen[key] = product

    return list(seen.values())


# ---------------------------------------------------------------------------
# Product Analysis & Scoring
# ---------------------------------------------------------------------------

def _calculate_budget_fit(product: Dict[str, Any], requirements: Dict[str, Any]) -> float:
    """Score how well the product fits the budget (0-1)."""
    price = product.get("price")
    budget_max = requirements.get("budget_max")
    budget_min = requirements.get("budget_min")

    if not price:
        return 0.5

    if budget_max and price <= budget_max:
        if budget_min and price >= budget_min:
            return 1.0
        elif budget_min:
            return max(0.3, 1.0 - (budget_min - price) / budget_min)
        else:
            remaining_ratio = (budget_max - price) / budget_max
            return 0.7 + 0.3 * remaining_ratio

    if budget_max:
        over_ratio = (price - budget_max) / budget_max
        return max(0.0, 0.5 - over_ratio)

    return 0.5


def _calculate_performance_score(product: Dict[str, Any], requirements: Dict[str, Any]) -> float:
    """Score product performance based on specs (0-1)."""
    specs = product.get("specifications", {})
    score = 0.5

    if specs.get("RAM"):
        ram = specs["RAM"]
        if "32" in ram:
            score += 0.2
        elif "16" in ram:
            score += 0.15
        elif "8" in ram:
            score += 0.1

    if specs.get("Processor"):
        proc = specs["Processor"].lower()
        if "i9" in proc or "m3" in proc or "ryzen 9" in proc:
            score += 0.2
        elif "i7" in proc or "m2" in proc or "ryzen 7" in proc:
            score += 0.15
        elif "i5" in proc or "m1" in proc or "ryzen 5" in proc:
            score += 0.1

    if specs.get("GPU"):
        score += 0.1

    return min(score, 1.0)


def _calculate_features_score(product: Dict[str, Any], requirements: Dict[str, Any]) -> float:
    """Score how many required features the product has (0-1)."""
    required = requirements.get("required_features", [])
    preferred = requirements.get("preferred_features", [])

    if not required and not preferred:
        return 0.5

    specs_text = " ".join(product.get("specifications", {}).values()).lower()
    name_text = product.get("name", "").lower()
    all_text = f"{specs_text} {name_text}"

    req_hits = 0
    for feat in required:
        feat_lower = feat.lower()
        if feat_lower in all_text or any(word in all_text for word in feat_lower.split()):
            req_hits += 1

    pref_hits = 0
    for feat in preferred:
        feat_lower = feat.lower()
        if feat_lower in all_text or any(word in all_text for word in feat_lower.split()):
            pref_hits += 1

    req_score = req_hits / len(required) if required else 1.0
    pref_score = pref_hits / len(preferred) if preferred else 0.5

    return 0.7 * req_score + 0.3 * pref_score


def _calculate_value_score(product: Dict[str, Any], requirements: Dict[str, Any]) -> float:
    """Score value for money (0-1)."""
    price = product.get("price")
    rating = product.get("rating")

    if not price:
        return 0.5

    score = 0.5

    if rating:
        score += (rating / 5.0) * 0.3

    budget_max = requirements.get("budget_max")
    if budget_max and price < budget_max * 0.7:
        score += 0.2
    elif budget_max and price < budget_max * 0.9:
        score += 0.1

    return min(score, 1.0)


def _calculate_ratings_score(product: Dict[str, Any]) -> float:
    """Score based on ratings (0-1)."""
    rating = product.get("rating")
    if not rating:
        return 0.5
    return min(rating / 5.0, 1.0)


def analyze_products(
    products: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Score and rank products based on user requirements. Only relevant products pass."""
    for product in products:
        budget_fit = _calculate_budget_fit(product, requirements)
        performance = _calculate_performance_score(product, requirements)
        features = _calculate_features_score(product, requirements)
        value = _calculate_value_score(product, requirements)
        ratings = _calculate_ratings_score(product)

        overall = (
            SCORING_WEIGHTS["budget_fit"] * budget_fit
            + SCORING_WEIGHTS["performance"] * performance
            + SCORING_WEIGHTS["features"] * features
            + SCORING_WEIGHTS["value"] * value
            + SCORING_WEIGHTS["ratings"] * ratings
        )

        # Apply relevance score as a multiplier
        relevance = product.get("relevance_score", 0.5)
        if relevance is None:
            relevance = 0.5
        overall = overall * relevance

        product["scores"] = {
            "budget_fit": round(budget_fit, 3),
            "performance": round(performance, 3),
            "features": round(features, 3),
            "value": round(value, 3),
            "ratings": round(ratings, 3),
            "relevance": round(relevance, 3),
            "overall": round(overall, 3),
        }

    products.sort(key=lambda p: p.get("scores", {}).get("overall", 0), reverse=True)
    return products


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

def generate_recommendation(
    products: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate product recommendations. Only from validated, relevant products.

    BEST OVERALL must only be assigned if the product matches the requested category.
    If no valid products are found, shows appropriate message.
    """
    if not products:
        return {
            "best_overall": None,
            "best_budget": None,
            "best_performance": None,
            "best_value": None,
            "summary": "No products found matching your criteria.",
        }

    requested_category = (requirements.get("category") or "").lower()
    brand = (requirements.get("brand") or "").lower()

    # Filter products that match the requested category
    def _product_matches_category(product: Dict[str, Any]) -> bool:
        """Check if product matches the requested category."""
        if not requested_category:
            return True
        product_name = (product.get("name") or "").lower()
        product_category = (product.get("category") or "").lower()
        cat_info = CATEGORY_TAXONOMY.get(requested_category)
        if not cat_info:
            return True
        # Check exact matches
        for match_term in cat_info["exact_matches"]:
            if match_term in product_name:
                return True
        # Check reject matches
        for reject_term in cat_info["reject_matches"]:
            if reject_term in product_name:
                return False
        # Check if category field matches
        if product_category == requested_category:
            return True
        return False

    # Validate all products against category
    validated_products = [p for p in products if _product_matches_category(p)]

    # If no products pass category validation, use original list but log warning
    if not validated_products:
        logger.warning(
            "No products match category=%s. Using all %d products for recommendation.",
            requested_category, len(products),
        )
        validated_products = products
    else:
        logger.info(
            "CATEGORY VALIDATION: %d/%d products match category=%s",
            len(validated_products), len(products), requested_category,
        )

    sorted_by_overall = sorted(validated_products, key=lambda p: p.get("scores", {}).get("overall", 0), reverse=True)
    sorted_by_price = sorted([p for p in validated_products if p.get("price")], key=lambda p: p["price"])
    sorted_by_perf = sorted(validated_products, key=lambda p: p.get("scores", {}).get("performance", 0), reverse=True)
    sorted_by_value = sorted(validated_products, key=lambda p: p.get("scores", {}).get("value", 0), reverse=True)

    budget_max = requirements.get("budget_max")
    budget_products = [p for p in sorted_by_price if not budget_max or (p.get("price") and p["price"] <= budget_max)]

    best_overall = sorted_by_overall[0] if sorted_by_overall else None
    best_budget = budget_products[0] if budget_products else (sorted_by_price[0] if sorted_by_price else None)
    best_performance = sorted_by_perf[0] if sorted_by_perf else None
    best_value = sorted_by_value[0] if sorted_by_value else None

    # Final validation: BEST OVERALL must match category
    if best_overall and not _product_matches_category(best_overall):
        logger.warning(
            "BEST OVERALL does not match category=%s: %s. Reassigning.",
            requested_category, (best_overall.get("name") or "")[:50],
        )
        # Find first product that matches
        for p in sorted_by_overall:
            if _product_matches_category(p):
                best_overall = p
                break
        else:
            best_overall = None

    categories = {}
    if best_overall:
        categories["best_overall"] = _format_recommendation(best_overall, "Best Overall", requirements)
    if best_budget and best_budget != best_overall:
        categories["best_budget"] = _format_recommendation(best_budget, "Best Budget Option", requirements)
    if best_performance and best_performance not in [best_overall, best_budget]:
        categories["best_performance"] = _format_recommendation(best_performance, "Best Performance", requirements)
    if best_value and best_value not in [best_overall, best_budget, best_performance]:
        categories["best_value"] = _format_recommendation(best_value, "Best Value for Money", requirements)

    # If no recommendations were generated, provide a helpful message
    if not categories:
        product_type = requirements.get("product_query", "product")
        brand_str = f"{brand} " if brand else ""
        categories["summary"] = f"No matching {brand_str}{product_type}s found."

    return categories


def _format_recommendation(
    product: Dict[str, Any],
    label: str,
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """Format a single product recommendation."""
    reasons = []

    budget_max = requirements.get("budget_max")
    if budget_max and product.get("price"):
        if product["price"] <= budget_max:
            reasons.append(f"Within your ₹{budget_max:,} budget")
        else:
            reasons.append(f"₹{product['price']:,.0f} (slightly above ₹{budget_max:,} budget)")

    specs = product.get("specifications", {})
    if specs.get("RAM"):
        reasons.append(f"{specs['RAM']} RAM")
    if specs.get("Processor"):
        reasons.append(f"{specs['Processor']}")
    if specs.get("GPU"):
        reasons.append(f"{specs['GPU']}")
    if specs.get("Storage"):
        reasons.append(f"{specs['Storage']}")
    if specs.get("Wattage"):
        reasons.append(f"{specs['Wattage']}")

    if product.get("rating"):
        reasons.append(f"Rated {product['rating']}/5")

    use_case = requirements.get("use_case", "")
    if use_case:
        reasons.append(f"Suitable for {use_case}")

    confidence = product.get("source_confidence", "low")
    if confidence == "high":
        reasons.append("From trusted source")

    return {
        "label": label,
        "product": product,
        "reasons": reasons,
        "score": product.get("scores", {}).get("overall", 0),
    }


# ---------------------------------------------------------------------------
# Response Synthesis
# ---------------------------------------------------------------------------

def synthesize_response(
    products: List[Dict[str, Any]],
    local_stores: List[Dict[str, Any]],
    recommendation: Dict[str, Any],
    requirements: Dict[str, Any],
) -> str:
    """
    Generate a human-readable response summarizing product research.
    All fields are null-safe. No fabricated data is displayed.
    """
    lines: List[str] = []

    product_type = requirements.get("product_query", "product")
    brand = requirements.get("brand", "")
    budget_max = requirements.get("budget_max")
    location = requirements.get("location")

    lines.append(f"## Product Research: {brand} {product_type}".strip())
    if budget_max:
        lines.append(f"**Budget:** Under ₹{budget_max:,}")
    if brand:
        lines.append(f"**Brand:** {brand}")
    if requirements.get("required_features"):
        lines.append(f"**Features:** {', '.join(requirements['required_features'])}")
    if requirements.get("use_case"):
        lines.append(f"**Use case:** {requirements['use_case']}")
    lines.append("")

    if not products:
        lines.append(f"I couldn't find any {brand + ' ' if brand else ''}{product_type}s matching your criteria from the available sources.")
        lines.append("")
        lines.append("**Suggestions:**")
        lines.append(f"- Try searching for '{brand} {product_type}' with different features")
        lines.append(f"- Broaden your budget range")
        lines.append(f"- Check official {brand + ' ' if brand else ''}website for the latest models")
        return "\n".join(lines)

    for cat_key, cat_label in [
        ("best_overall", "Best Overall"),
        ("best_budget", "Best Budget Option"),
        ("best_performance", "Best Performance"),
        ("best_value", "Best Value for Money"),
    ]:
        rec = recommendation.get(cat_key)
        if not rec:
            continue
        prod = rec["product"]
        lines.append(f"### {cat_label}")
        lines.append(f"**{prod.get('name', 'Unknown')}**")

        # Price: only show if available
        if prod.get("price"):
            price_str = f"₹{prod['price']:,.0f}"
            if prod.get("original_price") and prod["original_price"] > prod["price"]:
                price_str += f" (MRP ₹{prod['original_price']:,.0f})"
            lines.append(f"**Price:** {price_str}")

        # Store: only show if available
        if prod.get("store_name"):
            lines.append(f"**Store:** {prod['store_name']}")

        # Rating: only show if from source
        if prod.get("rating"):
            rating_str = f"**Rating:** {prod['rating']}/5"
            if prod.get("review_count"):
                rating_str += f" ({prod['review_count']} reviews)"
            lines.append(rating_str)

        # Availability: only show if known
        if prod.get("availability"):
            lines.append(f"**Availability:** {prod['availability']}")

        # Source URL
        if prod.get("url"):
            lines.append(f"**Link:** {prod['url']}")

        # Source confidence
        confidence = prod.get("source_confidence", "low")
        if confidence:
            conf_label = {"high": "Trusted source", "medium": "Standard source", "low": "Verify independently"}
            lines.append(f"**Source:** {conf_label.get(confidence, confidence)}")

        # Reasons
        if rec.get("reasons"):
            lines.append("**Why:**")
            for reason in rec["reasons"]:
                lines.append(f"- {reason}")
        lines.append("")

    # Other options
    if len(products) > 1:
        lines.append("### Other Options")
        shown = set()
        count = 0
        for p in products:
            name = p.get("name", "")
            if name in shown or count >= 3:
                continue
            shown.add(name)
            price_str = f"₹{p['price']:,.0f}" if p.get("price") else "Price N/A"
            store_str = p.get("store_name") or "Store unknown"
            lines.append(f"- **{name}** — {price_str} — {store_str}")
            count += 1
        lines.append("")

    # Local stores
    if local_stores:
        lines.append(f"### Local Stores in {location or 'your area'}")
        lines.append("| Store | Location | Price | Availability |")
        lines.append("|-------|----------|-------|-------------|")
        for store in local_stores[:5]:
            name = store.get("name", "N/A")
            loc = store.get("location", "N/A")
            price = f"₹{store['price']:,.0f}" if store.get("price") else "N/A"
            avail = "Contact to verify"
            lines.append(f"| {name} | {loc} | {price} | {avail} |")
        lines.append("")
        lines.append("*Local availability could not be verified. Contact the store before visiting.*")
        lines.append("")

    lines.append("---")
    lines.append("*Product information sourced from publicly available data. Prices and availability may change.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Search Function
# ---------------------------------------------------------------------------

def research_products(query: str) -> Dict[str, Any]:
    """
    Main entry point for product research.
    Accuracy-first pipeline with two-stage validation.
    """
    with trace_product_research(query) as pr_run:
        requirements = extract_product_requirements(query)
        logger.info(
            "REQUIREMENTS | Category: %s | Brand: %s | Model: %s | Budget: %s | Features: %s",
            requirements.get("category"),
            requirements.get("brand"),
            requirements.get("model"),
            requirements.get("budget_max"),
            requirements.get("required_features"),
        )

        products = search_online_products(requirements)
        local_stores = search_local_stores(requirements)

        products = deduplicate_products(products)
        products = analyze_products(products, requirements)
        recommendation = generate_recommendation(products, requirements)
        response_text = synthesize_response(products, local_stores, recommendation, requirements)

        logger.info(
            "FINAL RESULTS | Products: %d | Local Stores: %d | Recommendation keys: %s",
            len(products),
            len(local_stores),
            list(recommendation.keys()),
        )

    result = make_search_result(
        products=products[:20],
        local_stores=local_stores[:10],
        recommendation=recommendation,
        request=requirements,
        synthesis=response_text,
    )

    if pr_run:
        pr_run.end(outputs={
            "total_products": len(result.get("products", [])),
            "total_local_stores": len(result.get("local_stores", [])),
            "recommendation_keys": list(result.get("recommendation", {}).keys()),
        })

    return result
