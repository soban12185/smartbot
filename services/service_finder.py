"""
Service Finder - real-time local service discovery via web search.

Uses the existing Google Serper web-search integration to find real local
service providers. No fake/static businesses. No Google Places API. No
additional API keys or billing required.

Design notes
------------
* The original user location is kept for display, while a normalized location
  profile is used for query generation and relevance matching.
* Relevance is split into category, geographic, and evidence dimensions so a
  missing phone number/rating/street address never causes a valid business to
  be discarded.
* Provider failures are reported as failures, never as an empty result set.
* Every response carries safe diagnostic counts so "Serper returned 0" can be
  distinguished from "Serper returned results but all were rejected".
"""

import html as html_lib
import logging
import os
import re
import time
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Serper configuration (reuses existing SERPER_API_KEY)
# ---------------------------------------------------------------------------

SERPER_API_URL = "https://google.serper.dev/search"
MAX_RESULTS_PER_QUERY = 10
MAX_RESULTS_RETURNED = 3
MAX_SERPER_QUERIES = 3


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


SERPER_TIMEOUT_SECONDS = _env_float("SERPER_TIMEOUT_SECONDS", 12.0)


class SerperError(Exception):
    """Base class for expected Serper failures."""


class SerperConfigError(SerperError):
    """Raised when the Serper API key is missing."""


class SerperResponseError(SerperError):
    """Raised when Serper returns malformed or unexpected JSON."""


# ---------------------------------------------------------------------------
# Service category -> search-term mappings
# ---------------------------------------------------------------------------

CATEGORY_SEARCH_TERMS: Dict[str, List[str]] = {
    "catering": ["catering service", "food catering", "event catering"],
    "plumber": ["plumber", "plumbing service", "plumbing repair"],
    "electrician": ["electrician", "electrical service", "electrical repair"],
    "ac repair": ["AC repair", "air conditioning repair", "HVAC repair"],
    "appliance repair": ["appliance repair", "home appliance service"],
    "photographer": ["photography studio", "photographer", "photo studio"],
    "wedding photographer": ["wedding photographer", "wedding photography"],
    "cleaning": ["cleaning service", "house cleaning", "home cleaning"],
    "salon": ["beauty salon", "hair salon", "salon"],
    "beauty service": ["beauty salon", "beauty service", "beauty parlor"],
    "car repair": ["car repair", "auto repair", "automobile service"],
    "bike repair": ["bike repair", "motorcycle repair", "two-wheeler service"],
    "home tutor": ["tuition center", "home tutor", "coaching center"],
    "pest control": ["pest control", "pest control service"],
    "laundry": ["laundry service", "dry cleaning", "laundry"],
    "event decorator": ["event decoration", "wedding decorator", "party decorator"],
    "event planner": ["event planners", "event management company", "party planners"],
    "makeup artist": ["makeup artist", "beauty makeup", "bridal makeup"],
}

# Terms used for *relevance* checks. These are intentionally a little broader
# than the search terms (planner/planning, salon/parlour, etc.) but still stay
# tied to the requested service intent.
CATEGORY_RELEVANCE_TERMS: Dict[str, List[str]] = {
    "catering": ["catering", "caterer", "food service", "event food"],
    "plumber": ["plumber", "plumbing"],
    "electrician": ["electrician", "electrical service", "electrical work", "electric work"],
    "ac repair": ["ac repair", "air conditioning", "air conditioner", "hvac", "ac service"],
    "appliance repair": ["appliance repair", "appliance service"],
    "photographer": ["photographer", "photography", "photo studio"],
    "wedding photographer": ["wedding photographer", "wedding photography"],
    "cleaning": ["cleaning", "cleaning service", "house cleaning", "home cleaning", "deep cleaning"],
    "salon": ["salon", "beauty salon", "hair salon", "beauty parlour", "beauty parlor"],
    "beauty service": ["beauty service", "beauty salon", "beauty parlour", "beauty parlor", "spa"],
    "car repair": ["car repair", "car service", "auto repair", "automobile service", "car garage"],
    "bike repair": ["bike repair", "bike service", "motorcycle repair", "two wheeler service", "two-wheeler service"],
    "home tutor": ["home tutor", "tutor", "tuition", "coaching"],
    "pest control": ["pest control", "pest control service"],
    "laundry": ["laundry", "dry cleaning", "laundry service"],
    "event decorator": ["event decorator", "event decoration", "wedding decorator", "party decorator", "decoration"],
    "event planner": [
        "event planner",
        "event planning",
        "event management",
        "event management company",
        "event organiser",
        "event organizer",
        "wedding planner",
        "wedding planning",
        "party planner",
        "party organiser",
        "party organizer",
        "surprise planner",
        "birthday planner",
        "event company",
        "event services",
    ],
    "makeup artist": ["makeup artist", "make up artist", "bridal makeup", "makeup"],
}

_CATEGORY_ALIASES: Dict[str, str] = {}
for _category in CATEGORY_SEARCH_TERMS:
    _CATEGORY_ALIASES[_category] = _category
    _CATEGORY_ALIASES[f"{_category}s"] = _category

_CATEGORY_ALIASES.update({
    "event planning": "event planner",
    "event management": "event planner",
    "event management company": "event planner",
    "event organizer": "event planner",
    "event organiser": "event planner",
    "party planner": "event planner",
    "planners": "event planner",
    "plumbing": "plumber",
    "electrical": "electrician",
    "air conditioning repair": "ac repair",
    "hvac repair": "ac repair",
    "photography": "photographer",
    "wedding photography": "wedding photographer",
    "house cleaning": "cleaning",
    "cleaning service": "cleaning",
    "hair salon": "salon",
    "beauty salon": "beauty service",
    "automobile repair": "car repair",
    "two wheeler repair": "bike repair",
    "tuition": "home tutor",
    "laundromat": "laundry",
    "decoration": "event decorator",
    "event decoration": "event decorator",
})

# Info words to extract from special requirements
INFO_KEYWORDS = [
    "vegetarian", "vegan", "non-veg", "halal", "jain",
    "wedding", "birthday", "corporate", "party", "reception",
    "100 people", "200 people", "50 people", "2000 people",
    "split ac", "window ac", "inverter ac",
    "ton", "tons", "ton ac",
    "tomorrow", "today", "this weekend", "next week",
    "budget", "cheap", "affordable", "premium",
    "home", "office", "commercial", "residential",
    "emergency", "urgent", "same day",
]

# URL patterns that indicate non-business results (articles, directories, etc.)
_REJECT_URL_PATTERNS = [
    r"wikipedia\.org",
    r"youtube\.com",
    r"reddit\.com",
    r"quora\.com",
    r"amazon\.com",
    r"flipkart\.com",
    r"news\.",
    r"timesofindia\.indiatimes\.com",
    r"ndtv\.com",
    r"hindustantimes\.com",
    r"\.gov\.in",
    # Listing/aggregator pages are not a single business.
    r"justdial\.com",
    r"sulekha\.com",
    r"weddingwire\.in",
    r"wedmegood\.com",
    r"leadzo\.co\.in",
    r"indiamart\.com",
    r"indianyellowpages\.com",
    r"yellowpages\.",
    r"yelp\.",
    r"urbancompany\.com",
    r"urbanclap\.com",
    # Documents / aggregator listing pages, not individual businesses.
    r"venuebookingz\.com",
    r"scribd\.com",
    r"slideshare\.net",
    r"issuu\.com",
    r"/blog/",
    r"\.pdf(?:$|\?)",
]

# Title keywords that indicate articles / non-business pages
_REJECT_TITLE_KEYWORDS = [
    "how to", "what is", "why ", "top 10", "top 20", "list of",
    "wiki", "wikipedia", "news", "article", "blog",
    "buy ", "price in india", "amazon", "flipkart",
    "samsung", "iphone", "mobile phone",
    "salary", "jobs in", "recruitment",
]


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

_LOCATION_GROUPS: List[Dict[str, Any]] = [
    # Cities (equivalent spellings / older names)
    {"kind": "city", "canonical": "chennai", "display": "Chennai", "state": "Tamil Nadu", "aliases": ["chennai", "madras"]},
    {"kind": "city", "canonical": "bengaluru", "display": "Bengaluru", "state": "Karnataka", "aliases": ["bengaluru", "bangalore"]},
    {"kind": "city", "canonical": "mumbai", "display": "Mumbai", "state": "Maharashtra", "aliases": ["mumbai", "bombay"]},
    {"kind": "city", "canonical": "kolkata", "display": "Kolkata", "state": "West Bengal", "aliases": ["kolkata", "calcutta"]},
    {"kind": "city", "canonical": "delhi", "display": "Delhi", "state": "Delhi", "aliases": ["delhi", "new delhi"]},
    {"kind": "city", "canonical": "hyderabad", "display": "Hyderabad", "state": "Telangana", "aliases": ["hyderabad"]},
    {"kind": "city", "canonical": "coimbatore", "display": "Coimbatore", "state": "Tamil Nadu", "aliases": ["coimbatore", "kovai"]},
    {"kind": "city", "canonical": "madurai", "display": "Madurai", "state": "Tamil Nadu", "aliases": ["madurai"]},
    {"kind": "city", "canonical": "pune", "display": "Pune", "state": "Maharashtra", "aliases": ["pune", "poona"]},
    {"kind": "city", "canonical": "mysuru", "display": "Mysuru", "state": "Karnataka", "aliases": ["mysuru", "mysore"]},
    {"kind": "city", "canonical": "kochi", "display": "Kochi", "state": "Kerala", "aliases": ["kochi", "cochin"]},
    {"kind": "city", "canonical": "thiruvananthapuram", "display": "Thiruvananthapuram", "state": "Kerala", "aliases": ["thiruvananthapuram", "trivandrum"]},
    {"kind": "city", "canonical": "ahmedabad", "display": "Ahmedabad", "state": "Gujarat", "aliases": ["ahmedabad"]},
    {"kind": "city", "canonical": "jaipur", "display": "Jaipur", "state": "Rajasthan", "aliases": ["jaipur"]},
    {"kind": "city", "canonical": "lucknow", "display": "Lucknow", "state": "Uttar Pradesh", "aliases": ["lucknow"]},
    {"kind": "city", "canonical": "chandigarh", "display": "Chandigarh", "state": "Chandigarh", "aliases": ["chandigarh"]},
    {"kind": "city", "canonical": "visakhapatnam", "display": "Visakhapatnam", "state": "Andhra Pradesh", "aliases": ["visakhapatnam", "vizag"]},
    {"kind": "city", "canonical": "trichy", "display": "Tiruchirappalli", "state": "Tamil Nadu", "aliases": ["trichy", "tiruchirappalli", "tiruchirapalli"]},
    {"kind": "city", "canonical": "salem", "display": "Salem", "state": "Tamil Nadu", "aliases": ["salem"]},
    {"kind": "city", "canonical": "erode", "display": "Erode", "state": "Tamil Nadu", "aliases": ["erode"]},
    {"kind": "city", "canonical": "tiruppur", "display": "Tiruppur", "state": "Tamil Nadu", "aliases": ["tiruppur", "tirupur"]},
    # Common localities with alternative spellings (extendable without changing
    # the matching algorithm).
    {"kind": "area", "canonical": "t nagar", "display": "T Nagar", "city": "chennai", "state": "Tamil Nadu",
     "aliases": ["t nagar", "t. nagar", "t.nagar", "t-nagar", "thyagaraya nagar", "thyagarayanagar"]},
    {"kind": "area", "canonical": "anna nagar", "display": "Anna Nagar", "city": "chennai", "state": "Tamil Nadu",
     "aliases": ["anna nagar"]},
    {"kind": "area", "canonical": "adyar", "display": "Adyar", "city": "chennai", "state": "Tamil Nadu", "aliases": ["adyar"]},
    {"kind": "area", "canonical": "mylapore", "display": "Mylapore", "city": "chennai", "state": "Tamil Nadu", "aliases": ["mylapore"]},
    {"kind": "area", "canonical": "velachery", "display": "Velachery", "city": "chennai", "state": "Tamil Nadu", "aliases": ["velachery"]},
    {"kind": "area", "canonical": "besant nagar", "display": "Besant Nagar", "city": "chennai", "state": "Tamil Nadu", "aliases": ["besant nagar"]},
    {"kind": "area", "canonical": "porur", "display": "Porur", "city": "chennai", "state": "Tamil Nadu", "aliases": ["porur"]},
    {"kind": "area", "canonical": "tambaram", "display": "Tambaram", "city": "chennai", "state": "Tamil Nadu", "aliases": ["tambaram"]},
    {"kind": "area", "canonical": "nanganallur", "display": "Nanganallur", "city": "chennai", "state": "Tamil Nadu", "aliases": ["nanganallur"]},
    {"kind": "area", "canonical": "guindy", "display": "Guindy", "city": "chennai", "state": "Tamil Nadu", "aliases": ["guindy"]},
    {"kind": "area", "canonical": "egmore", "display": "Egmore", "city": "chennai", "state": "Tamil Nadu", "aliases": ["egmore"]},
    {"kind": "area", "canonical": "kilpauk", "display": "Kilpauk", "city": "chennai", "state": "Tamil Nadu", "aliases": ["kilpauk"]},
    {"kind": "area", "canonical": "thiruvanmiyur", "display": "Thiruvanmiyur", "city": "chennai", "state": "Tamil Nadu", "aliases": ["thiruvanmiyur"]},
    {"kind": "area", "canonical": "koramangala", "display": "Koramangala", "city": "bengaluru", "state": "Karnataka", "aliases": ["koramangala"]},
    {"kind": "area", "canonical": "indiranagar", "display": "Indiranagar", "city": "bengaluru", "state": "Karnataka", "aliases": ["indiranagar", "indira nagar"]},
    {"kind": "area", "canonical": "whitefield", "display": "Whitefield", "city": "bengaluru", "state": "Karnataka", "aliases": ["whitefield"]},
    {"kind": "area", "canonical": "hsr layout", "display": "HSR Layout", "city": "bengaluru", "state": "Karnataka", "aliases": ["hsr layout", "hsr"]},
    {"kind": "area", "canonical": "jp nagar", "display": "JP Nagar", "city": "bengaluru", "state": "Karnataka", "aliases": ["jp nagar", "j p nagar"]},
    {"kind": "area", "canonical": "btm layout", "display": "BTM Layout", "city": "bengaluru", "state": "Karnataka", "aliases": ["btm layout", "btm"]},
    {"kind": "area", "canonical": "malleshwaram", "display": "Malleshwaram", "city": "bengaluru", "state": "Karnataka", "aliases": ["malleshwaram", "malleswaram"]},
    {"kind": "area", "canonical": "rs puram", "display": "RS Puram", "city": "coimbatore", "state": "Tamil Nadu", "aliases": ["rs puram", "r.s. puram", "r s puram"]},
    {"kind": "area", "canonical": "gandhipuram", "display": "Gandhipuram", "city": "coimbatore", "state": "Tamil Nadu", "aliases": ["gandhipuram"]},
    {"kind": "area", "canonical": "peelamedu", "display": "Peelamedu", "city": "coimbatore", "state": "Tamil Nadu", "aliases": ["peelamedu"]},
    {"kind": "area", "canonical": "saibaba colony", "display": "Saibaba Colony", "city": "coimbatore", "state": "Tamil Nadu", "aliases": ["saibaba colony", "sai baba colony"]},
    {"kind": "area", "canonical": "bandra", "display": "Bandra", "city": "mumbai", "state": "Maharashtra", "aliases": ["bandra"]},
    {"kind": "area", "canonical": "andheri", "display": "Andheri", "city": "mumbai", "state": "Maharashtra", "aliases": ["andheri"]},
    {"kind": "area", "canonical": "powai", "display": "Powai", "city": "mumbai", "state": "Maharashtra", "aliases": ["powai"]},
]

_STATE_NAMES = {
    "tamil nadu", "karnataka", "kerala", "telangana", "andhra pradesh",
    "maharashtra", "delhi", "gujarat", "rajasthan", "uttar pradesh",
    "west bengal", "madhya pradesh", "punjab", "haryana", "odisha",
}


def _normalize_for_matching(text: Any) -> str:
    """Lowercase and canonicalize punctuation/whitespace for matching."""
    value = html_lib.unescape(str(text or "")).lower()
    value = value.replace("&", " and ")
    # Periods/hyphens are common in locality spellings: T.Nagar, T-Nagar.
    value = re.sub(r"[._\-/\\|@,;:!?'\"()\[\]{}]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _title_location(value: str) -> str:
    if not value:
        return ""
    return " ".join(word.capitalize() for word in value.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _matches_alias(text: str, compact_text: str, alias: str) -> bool:
    """Match an alias with word boundaries or as a compact domain/path string."""
    if _contains_phrase(text, alias):
        return True
    compact_alias = alias.replace(" ", "")
    if len(compact_alias) >= 5 and compact_alias in compact_text:
        return True
    return False


def _matched_alias(text: str, compact_text: str, aliases: List[str]) -> Optional[str]:
    # Prefer the longest match so "anna nagar" wins over a shorter accidental one.
    for alias in sorted(aliases, key=len, reverse=True):
        normalized = _normalize_for_matching(alias)
        if _matches_alias(text, compact_text, normalized):
            return normalized
    return None


def normalize_category(service_category: str) -> str:
    """Normalize capitalization, whitespace, and simple plural forms."""
    category = _normalize_for_matching(service_category)
    if not category:
        return ""
    if category in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[category]
    if category.endswith("s") and category[:-1] in CATEGORY_SEARCH_TERMS:
        return category[:-1]
    return category


def normalize_location(location: str) -> Dict[str, Any]:
    """
    Build a location profile without replacing the user's meaning.

    The original value is preserved for display. The profile contains a
    canonical city/area and equivalent aliases used only for matching.
    """
    original = (location or "").strip()
    full_norm = _normalize_for_matching(original)
    compact = full_norm.replace(" ", "")
    raw_parts = [p.strip() for p in original.split(",") if p.strip()]
    norm_parts = [_normalize_for_matching(p) for p in raw_parts if _normalize_for_matching(p)]

    city: Optional[str] = None
    city_display: Optional[str] = None
    city_aliases: List[str] = []
    area: Optional[str] = None
    area_display: Optional[str] = None
    area_aliases: List[str] = []

    for group in _LOCATION_GROUPS:
        matched = _matched_alias(full_norm, compact, group["aliases"])
        if not matched:
            continue
        if group["kind"] == "city" and city is None:
            city = group["canonical"]
            city_display = _title_location(matched)
            city_aliases = sorted({_normalize_for_matching(a) for a in group["aliases"]})
        elif group["kind"] == "area" and area is None:
            area = group["canonical"]
            area_display = group["display"]
            area_aliases = sorted({_normalize_for_matching(a) for a in group["aliases"]})

    # Handle free-form "area, city" input not present in the alias tables.
    remaining_parts = [
        part for part in norm_parts
        if part not in (city, area) and part not in _STATE_NAMES
    ]
    if city is None and len(norm_parts) >= 2:
        city = norm_parts[-1]
        city_display = _title_location(city)
        city_aliases = [city]
        remaining_parts = [p for p in remaining_parts if p != city]

    if area is None and city is not None:
        # A city-only input (e.g. "Bangalore") must not become a fake area.
        extra_parts = [
            part for part in remaining_parts
            if part not in city_aliases and part != city
        ]
        if len(norm_parts) >= 2 and extra_parts:
            area = extra_parts[0]
            area_display = _title_location(area)
            area_aliases = [area]
    elif area is None and city is None and norm_parts:
        area = norm_parts[0]
        area_display = _title_location(area)
        area_aliases = [area]

    if area_display:
        search_location = f"{area_display} {city_display or ''}".strip()
    else:
        search_location = city_display or original

    normalized = ", ".join(part for part in (area, city) if part) or full_norm

    return {
        "original": original,
        "normalized": normalized,
        "display": original,
        "search_location": search_location or original,
        "city": city,
        "city_display": city_display,
        "city_aliases": city_aliases or ([city] if city else []),
        "area": area,
        "area_display": area_display,
        "area_aliases": area_aliases or ([area] if area else []),
    }


def _candidate_match_text(candidate: Dict[str, Any]) -> str:
    return _normalize_for_matching(" ".join(str(candidate.get(key) or "") for key in (
        "name", "description", "address", "domain", "website", "source_url",
    )))


def _location_relevance(candidate: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """
    Classify geographic relevance as exact / nearby / city / none.

    * exact  - the requested area (or city, for a city-only request) is present.
    * nearby - another known locality in the same city is present.
    * city   - only the broader city is present.
    * none   - no geographic evidence.
    """
    text = _candidate_match_text(candidate)
    compact = text.replace(" ", "")

    area_match = bool(profile.get("area_aliases")) and _matched_alias(
        text, compact, profile["area_aliases"]
    ) is not None
    city_match = bool(profile.get("city_aliases")) and _matched_alias(
        text, compact, profile["city_aliases"]
    ) is not None

    if area_match:
        return "exact"

    if city_match:
        if not profile.get("area"):
            return "exact"
        # Another known locality in the requested city is useful evidence, but
        # must not be mislabeled as the requested neighborhood.
        for group in _LOCATION_GROUPS:
            if group["kind"] != "area" or group.get("city") != profile.get("city"):
                continue
            if group["canonical"] == profile.get("area"):
                continue
            if _matched_alias(text, compact, group["aliases"]):
                return "nearby"
        return "city"

    # Area-only request (e.g. "Koramangala" with no city) or known nearby area
    # without the city name.
    if profile.get("city"):
        for group in _LOCATION_GROUPS:
            if group["kind"] != "area" or group.get("city") != profile["city"]:
                continue
            if group["canonical"] == profile.get("area"):
                continue
            if _matched_alias(text, compact, group["aliases"]):
                return "nearby"

    # Unknown free-form location: require the full phrase or a meaningful part.
    if not profile.get("city") and not profile.get("area"):
        for phrase in profile.get("fallback_phrases", []):
            if len(phrase) >= 3 and _matches_alias(text, compact, phrase):
                return "exact"

    return "none"


# ---------------------------------------------------------------------------
# Input parsing / query generation
# ---------------------------------------------------------------------------

def parse_user_request(
    location: str,
    service_category: str,
    special_requirements: str = "",
) -> Dict[str, Any]:
    """
    Parse and normalize the user's service search request.

    Returns a structured dict with:
        location, normalized_location, location_profile, service_category,
        search_queries, special_requirements, extracted_info
    """
    location = (location or "").strip()
    service_category = (service_category or "").strip()
    special_requirements = (special_requirements or "").strip()

    if not location:
        raise ValueError("Location is required. Please provide a city or area.")
    if not service_category:
        raise ValueError("Service category is required. Please specify the type of service.")

    profile = normalize_location(location)
    category = normalize_category(service_category)

    search_queries = _build_search_queries(category, location, special_requirements)

    extracted_info: List[str] = []
    if special_requirements:
        req_lower = special_requirements.lower()
        for kw in INFO_KEYWORDS:
            if kw in req_lower:
                extracted_info.append(kw)

    return {
        "location": location,
        "normalized_location": profile["normalized"],
        "location_profile": profile,
        "service_category": category,
        "search_queries": search_queries,
        "special_requirements": special_requirements,
        "extracted_info": extracted_info,
    }


def _build_search_queries(
    category: str,
    location: str,
    special_requirements: str = "",
) -> List[str]:
    """
    Generate 1-3 targeted Serper search queries.

    Terms stay tied to the requested service and location. Fallback queries are
    only used by the caller when the preceding search was insufficient.
    """
    category = normalize_category(category)
    profile = normalize_location(location)
    search_location = profile["search_location"] or (location or "").strip()
    terms = CATEGORY_SEARCH_TERMS.get(category, [category or "service"])

    queries: List[str] = []
    seen: set = set()

    def add(query: str) -> None:
        cleaned = re.sub(r"\s+", " ", query).strip()
        key = cleaned.lower()
        if cleaned and key not in seen and len(queries) < MAX_SERPER_QUERIES:
            seen.add(key)
            queries.append(cleaned)

    primary_term = terms[0] if terms else (category or "service")
    add(f"{primary_term} in {search_location}")

    if special_requirements:
        req_clean = re.sub(r"[^\w\s-]", " ", special_requirements)
        req_clean = re.sub(r"\s+", " ", req_clean).strip()[:60]
        if req_clean:
            add(f"{primary_term} {req_clean} in {search_location}")

    for term in terms[1:]:
        add(f"{term} in {search_location}")

    return queries[:MAX_SERPER_QUERIES]


# ---------------------------------------------------------------------------
# Serper search
# ---------------------------------------------------------------------------

def _serper_search(query: str, num_results: int = MAX_RESULTS_PER_QUERY) -> List[Dict[str, Any]]:
    """
    Execute a Serper web search and return organic results.

    Empty organic results are a successful result. HTTP, timeout, network, and
    malformed-response failures raise so the caller can distinguish them from a
    genuine empty search.
    """
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        logger.warning("SERPER_API_KEY not configured")
        raise SerperConfigError("SERPER_API_KEY is not configured")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "gl": "in",
        "hl": "en",
        "num": min(max(int(num_results), 1), MAX_RESULTS_PER_QUERY),
    }

    try:
        resp = requests.post(
            SERPER_API_URL,
            headers=headers,
            json=payload,
            timeout=SERPER_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        logger.warning("Serper search timed out for query: %s", query)
        raise
    except requests.exceptions.RequestException as exc:
        logger.warning("Serper request failed for query '%s': %s", query, type(exc).__name__)
        raise

    logger.info("SERVICE_FINDER | serper_status=%s | query=%s", resp.status_code, query)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.warning("Serper HTTP error %s for query: %s", resp.status_code, query)
        raise

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("Serper returned non-JSON for query '%s'", query)
        raise SerperResponseError("Serper returned non-JSON") from exc

    if not isinstance(data, dict):
        raise SerperResponseError("Serper returned an unexpected JSON shape")

    organic = data.get("organic", [])
    if organic is None:
        organic = []
    if not isinstance(organic, list):
        raise SerperResponseError("Serper 'organic' field is not a list")

    results = [item for item in organic if isinstance(item, dict)]
    logger.info(
        "SERVICE_FINDER | serper_results=%d | malformed_results=%d | query=%s",
        len(results), len(organic) - len(results), query,
    )
    return results


# ---------------------------------------------------------------------------
# Candidate extraction from web results
# ---------------------------------------------------------------------------

_PHONE_PATTERN = re.compile(
    r"(?:\+91[\s\-]?\d{5}[\s\-]?\d{5}|"  # +91 XXXXX XXXXX
    r"\+91[\s\-]?\d{4}[\s\-]?\d{6}|"       # +91 XXXX XXXXXX
    r"0\d{2,4}[\s\-]?\d{6,8}|"             # 0XXX XXXXXX
    r"\d{5}[\s\-]?\d{5}|"                  # XXXXX XXXXX
    r"\d{4}[\s\-]?\d{6})"                  # XXXX XXXXXX
)

_RATING_PATTERN = re.compile(
    r"(?:rated?\s+)?(\d\.\d)\s*(?:/5|out of 5|★|stars?|rating)|"
    r"(\d\.\d)\s*(?:★|stars?)"
)


def _extract_phone(text: str) -> Optional[str]:
    """Extract an Indian phone number from text, if present."""
    match = _PHONE_PATTERN.search(text or "")
    return match.group(0).strip() if match else None


def _extract_rating(text: str) -> Optional[float]:
    """Extract a numeric rating from text, if present."""
    match = _RATING_PATTERN.search(text or "")
    if match:
        try:
            val = float(match.group(1) or match.group(2))
            if 1.0 <= val <= 5.0:
                return val
        except (ValueError, TypeError):
            pass
    return None


def _extract_address(text: str) -> Optional[str]:
    """
    Best-effort address extraction from snippet text.

    Only returns content explicitly marked as an address/location or text that
    contains a street number and comma-separated locality. Never invents a
    street address when the source does not contain one.
    """
    if not text:
        return None

    explicit = re.search(
        r"(?:address|location)\s*[:\-]?\s*([^\n]{8,180})",
        text,
        flags=re.IGNORECASE,
    )
    if explicit:
        value = explicit.group(1).strip(" .|-")
        if re.search(r"\d", value):
            return value

    street = re.search(
        r"(\d{1,5}[A-Za-z]?\s*,\s*[^,\n]{3,70}(?:,\s*[^,\n]{2,70}){0,4}"
        r"(?:\s*[-–]\s*\d{5,6})?)",
        text,
    )
    if street:
        return street.group(1).strip(" .|-")

    return None


def _clean_title(title: str) -> str:
    value = html_lib.unescape(str(title or "")).strip()
    value = re.sub(r"\s*[-|]\s*Google Search\s*$", "", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def _coerce_rating(value: Any) -> Optional[float]:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return rating if 1.0 <= rating <= 5.0 else None


def _extract_candidate(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a structured business candidate from a Serper organic result.

    Only includes fields actually present in the search result; missing fields
    stay None rather than being fabricated.
    """
    title = _clean_title(result.get("title", ""))
    snippet = str(result.get("snippet") or result.get("description") or "").strip()
    link = str(result.get("link") or result.get("url") or "").strip()
    position = result.get("position", 0)
    try:
        position = int(position)
    except (TypeError, ValueError):
        position = 0

    domain = ""
    if link:
        try:
            parsed = urlparse(link)
            domain = parsed.netloc.lower().replace("www.", "")
        except Exception:
            pass

    structured_address = str(result.get("address") or "").strip() or None
    address = structured_address or _extract_address(snippet)
    phone = str(result.get("phoneNumber") or result.get("phone") or "").strip() or _extract_phone(snippet)
    rating = _coerce_rating(result.get("rating"))
    if rating is None:
        rating = _extract_rating(snippet)

    website = str(result.get("website") or "").strip() or link

    return {
        "name": title,
        "description": snippet,
        "website": website,
        "source_url": link,
        "address": address,
        "phone": phone or None,
        "rating": rating,
        "domain": domain,
        "position": position,
    }


# ---------------------------------------------------------------------------
# Candidate validation / relevance
# ---------------------------------------------------------------------------

def _category_terms(service_category: str) -> List[str]:
    category = normalize_category(service_category)
    return CATEGORY_RELEVANCE_TERMS.get(category, [category] if category else [])


def _category_relevance(candidate: Dict[str, Any], service_category: str) -> bool:
    text = _normalize_for_matching(
        f"{candidate.get('name') or ''} {candidate.get('description') or ''} "
        f"{candidate.get('address') or ''}"
    )
    for term in _category_terms(service_category):
        normalized = _normalize_for_matching(term)
        if not normalized:
            continue
        if " " in normalized:
            if _contains_phrase(text, normalized):
                return True
        elif _contains_phrase(text, normalized):
            return True
    return False


def _evaluate_candidate(
    candidate: Dict[str, Any],
    service_category: str,
    location_profile: Dict[str, Any],
) -> Tuple[bool, str, str]:
    """
    Validate a candidate using separate relevance dimensions.

    Returns (is_valid, rejection_reason, location_relevance).
    Optional fields are never required.
    """
    name = (candidate.get("name") or "").strip()
    description = (candidate.get("description") or "").lower()
    source_url = (candidate.get("source_url") or candidate.get("website") or "").lower()
    domain = (candidate.get("domain") or "").lower()

    if not name or not source_url:
        return False, "missing_business_name_or_source", "none"

    for pattern in _REJECT_URL_PATTERNS:
        if re.search(pattern, source_url):
            return False, f"reject_url:{pattern}", "none"

    name_lower = name.lower()
    for kw in _REJECT_TITLE_KEYWORDS:
        if kw in name_lower:
            return False, f"reject_title:{kw}", "none"

    location_relevance = _location_relevance(candidate, location_profile)
    if location_relevance == "none":
        return False, "location_mismatch", "none"

    if not _category_relevance(candidate, service_category):
        return False, f"wrong_category:no_match_for_{normalize_category(service_category)}", location_relevance

    return True, "", location_relevance


def _is_relevant_candidate(
    candidate: Dict[str, Any],
    service_category: str,
    location: str,
) -> Tuple[bool, str]:
    """Backward-compatible validation helper returning (is_valid, reason)."""
    valid, reason, _ = _evaluate_candidate(
        candidate, service_category, normalize_location(location)
    )
    return valid, reason


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a business name for deduplication."""
    name = html_lib.unescape(str(name or "")).lower().strip()
    name = re.sub(r"\s*(?:\||–|—)\s*.*$", "", name)
    name = re.sub(r"\s+-\s+.*$", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return url.strip().lower()
    netloc = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/+$", "", parsed.path or "")
    return f"{netloc}{path}".lower()


def _names_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if (a in b or b in a) and min(len(a), len(b)) >= 8:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.92


def _deduplicate(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate businesses without collapsing distinct businesses that
    merely share a domain or a common word.
    """
    seen_urls: set = set()
    seen: List[Tuple[str, str]] = []  # (normalized_name, domain)
    unique: List[Dict[str, Any]] = []

    for candidate in candidates:
        canonical_url = _canonical_url(
            candidate.get("source_url") or candidate.get("website") or ""
        )
        if canonical_url and canonical_url in seen_urls:
            continue

        norm_name = _normalize_name(candidate.get("name") or "")
        domain = (candidate.get("domain") or "").lower()

        duplicate = False
        for other_name, other_domain in seen:
            if norm_name and norm_name == other_name:
                duplicate = True
                break
            if (_names_similar(norm_name, other_name)
                    and (not domain or not other_domain or domain == other_domain)):
                duplicate = True
                break

        if duplicate:
            continue

        if canonical_url:
            seen_urls.add(canonical_url)
        seen.append((norm_name, domain))
        unique.append(candidate)

    return unique


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

_LOCATION_SCORE = {"exact": 6.0, "nearby": 4.0, "city": 3.0, "none": 0.0}


def _rank_candidates(
    candidates: List[Dict[str, Any]],
    service_category: str,
    special_requirements: str = "",
) -> List[Dict[str, Any]]:
    """Rank validated candidates by category, location, and evidence quality."""
    req_lower = (special_requirements or "").lower()
    req_words = [word for word in re.findall(r"[a-z0-9]+", req_lower) if len(word) > 2]
    category_terms = _category_terms(service_category)

    def _score(candidate: Dict[str, Any]) -> float:
        score = 0.0
        name = _normalize_for_matching(candidate.get("name") or "")
        description = _normalize_for_matching(candidate.get("description") or "")
        combined = f"{name} {description}"

        for term in category_terms:
            normalized = _normalize_for_matching(term)
            if normalized and _contains_phrase(combined, normalized):
                score += 2.0

        location_relevance = candidate.get("_location_relevance")
        if not location_relevance:
            location_relevance = _location_relevance(candidate, normalize_location(""))
        score += _LOCATION_SCORE.get(location_relevance, 0.0)

        # Evidence quality: source URL is mandatory, other fields are bonuses.
        if candidate.get("source_url") or candidate.get("website"):
            score += 0.5
        if candidate.get("phone"):
            score += 0.75
        if candidate.get("address"):
            score += 0.75
        rating = _coerce_rating(candidate.get("rating"))
        if rating is not None:
            score += min(rating, 5.0) * 0.4

        if req_words:
            for word in req_words:
                if _contains_phrase(combined, word):
                    score += 1.25

        position = candidate.get("position") or 99
        try:
            position = int(position)
        except (TypeError, ValueError):
            position = 99
        score += max(0.0, (10 - position) * 0.2)

        return score

    return sorted(candidates, key=_score, reverse=True)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _base_query(parsed: Optional[Dict[str, Any]], location: str, category: str) -> Dict[str, Any]:
    if parsed:
        profile = parsed["location_profile"]
        return {
            "location": parsed["location"],
            "normalized_location": parsed["normalized_location"],
            "search_location": profile["search_location"],
            "city": profile.get("city"),
            "area": profile.get("area"),
            "service_category": parsed["service_category"],
            "search_queries": parsed["search_queries"],
            "special_requirements": parsed["special_requirements"],
            "extracted_info": parsed["extracted_info"],
        }
    profile = normalize_location(location)
    return {
        "location": location,
        "normalized_location": profile["normalized"],
        "search_location": profile["search_location"],
        "city": profile.get("city"),
        "area": profile.get("area"),
        "service_category": normalize_category(category),
        "search_queries": [],
        "special_requirements": "",
        "extracted_info": [],
    }


def _failure(
    parsed: Optional[Dict[str, Any]],
    location: str,
    category: str,
    error_code: str,
    message: str,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "error": message,
        "error_code": error_code,
        "query": _base_query(parsed, location, category),
        "results": [],
        "count": 0,
        "source": "Web Search",
        "diagnostics": diagnostics or {},
    }


def _provider_error_code(status: Optional[int]) -> str:
    if status in (401, 403):
        return "provider_auth_error"
    if status == 429:
        return "provider_rate_limited"
    if status is not None and 500 <= status:
        return "provider_unavailable"
    return "provider_http_error"


def _provider_error_message(status: Optional[int]) -> str:
    if status in (401, 403):
        return "Search API key is invalid or quota exceeded."
    if status == 429:
        return "Too many requests. Please try again later."
    return "Service search is temporarily unavailable. Please try again."


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Location autocomplete suggestions
# ---------------------------------------------------------------------------


def _get_city_info(canonical_city: Optional[str]) -> Dict[str, Any]:
    if not canonical_city:
        return {}
    for group in _LOCATION_GROUPS:
        if group["kind"] == "city" and group["canonical"] == canonical_city:
            return {
                "city_canonical": group["canonical"],
                "city_display": group["display"],
                "state": group.get("state", ""),
            }
    return {"city_canonical": canonical_city}


def suggest_locations(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Suggest locations (cities and localities) based on user input.

    Returns structured suggestions with fields like display_name, city,
    locality, state, type, source. Uses the built-in extensible dataset.
    """
    q = _normalize_for_matching(query)
    if not q or len(q) < 2:
        return []

    limit = max(1, min(int(limit or 8), 10))
    suggestions = []
    seen = set()

    # First pass: check all groups
    for group in _LOCATION_GROUPS:
        aliases = group.get("aliases") or []
        matched_alias = _matched_alias(q, q.replace(" ", ""), aliases)
        if not matched_alias:
            continue

        kind = group.get("kind")
        if kind == "city":
            display_name = group["display"]
            city_canonical = group["canonical"]
            city_display = group["display"]
            locality = None
            state = group.get("state", "")
            type_ = "city"
        elif kind == "area":
            display_name = group["display"]
            city_canonical = group.get("city") or ""
            city_info = _get_city_info(city_canonical)
            city_display = city_info.get("city_display") or (city_canonical.title() if city_canonical else "")
            locality = group["display"]
            state = group.get("state") or city_info.get("state", "")
            type_ = "neighborhood"
        else:
            continue

        # Build full display name with context
        if type_ == "neighborhood" and city_display:
            full_display = f"{display_name}, {city_display}"
        else:
            full_display = display_name

        # Deduplicate
        key = _normalize_for_matching(full_display)
        if key in seen:
            continue
        seen.add(key)

        # Calculate score for ranking
        score = 0
        matched_norm = matched_alias
        if q == matched_norm:
            score += 100  # exact match
        elif matched_norm.startswith(q):
            score += 50   # prefix match
        elif q in matched_norm:
            score += 20   # partial match
        else:
            score += 10

        if type_ == "neighborhood":
            score += 15  # locality matches rank high as per requirement
        elif type_ == "city":
            score += 10

        suggestions.append({
            "display_name": full_display,
            "city": city_display or "",
            "locality": locality or "",
            "state": state or "",
            "type": type_,
            "source": "local_dataset",
            "_score": score,
            "_matched_alias": matched_norm,
        })

    # Also handle Bangalore/Bengaluru aliases explicitly mentioned
    q_stripped = q.replace(" ", "")
    # If user types Bangalore, ensure Bengaluru is suggested
    if "bangalore" in q or "bengaluru" in q:
        pass  # already handled via aliases

    # Sort by score desc, then by length for stability
    suggestions.sort(key=lambda x: (-x["_score"], len(x.get("display_name", ""))))
    
    # Remove internal scoring fields
    results = []
    for s in suggestions:
        s_clean = {k: v for k, v in s.items() if not k.startswith("_")}
        results.append(s_clean)
        if len(results) >= limit:
            break

    return results


def search_services(
    location: str,
    service_category: str,
    special_requirements: str = "",
) -> Dict[str, Any]:
    """
    Search for real local service providers using Google Serper web search.

    Args:
        location: City or area (e.g., "Bangalore", "T Nagar, Chennai").
        service_category: Type of service (e.g., "catering", "event planner").
        special_requirements: Free-text requirements (optional).

    Returns:
        Dict with keys: success, query, results, count, source, diagnostics, etc.
    """
    try:
        parsed = parse_user_request(location, service_category, special_requirements)
    except ValueError as exc:
        return _failure(None, location, service_category, "invalid_request", str(exc))

    if not os.environ.get("SERPER_API_KEY", ""):
        return _failure(
            parsed, location, service_category, "missing_api_key",
            "Search API key is not configured. Please try again later.",
        )

    start_time = time.time()
    profile = parsed["location_profile"]
    search_queries = parsed["search_queries"]
    raw_results: List[Dict[str, Any]] = []
    extracted_count = 0
    validated: List[Dict[str, Any]] = []
    rejection_reasons: Counter = Counter()
    parse_failures = 0
    num_searches = 0
    provider_status = "ok"
    seen_raw_urls: set = set()
    query_stats: List[Dict[str, Any]] = []

    try:
        for index, query in enumerate(search_queries):
            # Fallback queries are only consumed while we still need results.
            if index > 0 and len(validated) >= MAX_RESULTS_RETURNED:
                break

            query_start = time.time()
            try:
                rows = _serper_search(query, num_results=MAX_RESULTS_PER_QUERY)
            except requests.exceptions.Timeout:
                provider_status = "timeout"
                logger.warning("SERVICE_FINDER | Serper timeout for query: %s", query)
                if validated:
                    query_stats.append({"query": query, "status": "timeout", "raw": 0})
                    break
                diagnostics = {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "queries_executed": num_searches + 1,
                    "raw_results": len(raw_results),
                    "validated": len(validated),
                }
                return _failure(
                    parsed, location, service_category, "provider_timeout",
                    "Service search timed out. Please try again.", diagnostics,
                )
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                provider_status = f"http_{status}" if status is not None else "http_error"
                logger.error("SERVICE_FINDER | Serper HTTP error: %s", status)
                query_stats.append({"query": query, "status": provider_status, "raw": 0})
                if validated:
                    break
                diagnostics = {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "queries_executed": num_searches + 1,
                    "raw_results": len(raw_results),
                    "validated": len(validated),
                }
                return _failure(
                    parsed, location, service_category,
                    _provider_error_code(status), _provider_error_message(status),
                    diagnostics,
                )
            except SerperConfigError:
                return _failure(
                    parsed, location, service_category, "missing_api_key",
                    "Search API key is not configured. Please try again later.",
                )
            except SerperResponseError:
                provider_status = "malformed_response"
                logger.error("SERVICE_FINDER | Serper returned malformed JSON/shape")
                if validated:
                    break
                diagnostics = {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "queries_executed": num_searches + 1,
                    "raw_results": len(raw_results),
                    "validated": len(validated),
                }
                return _failure(
                    parsed, location, service_category, "malformed_provider_response",
                    "Service search returned an unexpected response. Please try again later.",
                    diagnostics,
                )
            except requests.exceptions.RequestException:
                provider_status = "unavailable"
                logger.warning("SERVICE_FINDER | Serper connection failure")
                if validated:
                    break
                diagnostics = {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "queries_executed": num_searches + 1,
                    "raw_results": len(raw_results),
                }
                return _failure(
                    parsed, location, service_category, "provider_unavailable",
                    "Service search is temporarily unavailable. Please try again.",
                    diagnostics,
                )
            except Exception as exc:
                provider_status = "unexpected_error"
                logger.error(
                    "SERVICE_FINDER | unexpected Serper client error: %s",
                    type(exc).__name__,
                )
                if validated:
                    break
                diagnostics = {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "queries_executed": num_searches + 1,
                    "raw_results": len(raw_results),
                }
                return _failure(
                    parsed, location, service_category, "provider_unavailable",
                    "Service search is temporarily unavailable. Please try again.",
                    diagnostics,
                )

            num_searches += 1
            raw_results.extend(rows)
            query_stats.append({
                "query": query,
                "status": "ok",
                "raw": len(rows),
                "duration_ms": int((time.time() - query_start) * 1000),
            })

            for row in rows:
                source_url = str(row.get("link") or row.get("url") or "").strip()
                raw_key = _canonical_url(source_url)
                if raw_key and raw_key in seen_raw_urls:
                    continue
                if raw_key:
                    seen_raw_urls.add(raw_key)

                try:
                    candidate = _extract_candidate(row)
                except Exception as exc:
                    parse_failures += 1
                    logger.debug(
                        "SERVICE_FINDER | parse_failure | %s", type(exc).__name__
                    )
                    continue

                extracted_count += 1

                if not candidate.get("name") or not candidate.get("source_url"):
                    parse_failures += 1
                    rejection_reasons["missing_business_name_or_source"] += 1
                    continue

                is_valid, reason, location_relevance = _evaluate_candidate(
                    candidate, parsed["service_category"], profile
                )
                if is_valid:
                    candidate["_location_relevance"] = location_relevance
                    validated.append(candidate)
                else:
                    rejection_reasons[reason] += 1
                    logger.debug(
                        "SERVICE_FINDER | rejected | name=%s | reason=%s",
                        (candidate.get("name") or "")[:60], reason,
                    )

        # A fully malformed provider payload that produced no extractable
        # candidates is a parsing failure, not a legitimate empty search.
        if raw_results and extracted_count == 0 and parse_failures:
            return _failure(
                parsed, location, service_category, "candidate_parse_error",
                "Search results could not be read. Please try again later.",
                {
                    "provider": "serper",
                    "provider_status": provider_status,
                    "raw_results": len(raw_results),
                    "candidates_extracted": extracted_count,
                    "parse_failures": parse_failures,
                },
            )

        deduplicated = _deduplicate(validated)
        ranked = _rank_candidates(
            deduplicated, parsed["service_category"], parsed["special_requirements"]
        )

        top_results: List[Dict[str, Any]] = []
        for candidate in ranked[:MAX_RESULTS_RETURNED]:
            clean = {
                "name": candidate.get("name", ""),
                "description": candidate.get("description", ""),
                "website": candidate.get("website"),
                "source_url": candidate.get("source_url"),
                "address": candidate.get("address"),
                "phone": candidate.get("phone"),
                "rating": candidate.get("rating"),
                "location_relevance": candidate.get("_location_relevance"),
            }
            clean = {key: value for key, value in clean.items() if value not in (None, "")}
            top_results.append(clean)

        total_latency_ms = int((time.time() - start_time) * 1000)

        if not raw_results:
            empty_reason = "no_provider_results"
            message = (
                f"No web results were found for {parsed['service_category']} in "
                f"{parsed['location']}. Try a nearby area or a different category."
            )
        elif not top_results:
            empty_reason = "all_candidates_rejected"
            message = (
                f"Web results were found for {parsed['location']}, but none matched "
                f"{parsed['service_category']} closely enough. Try a nearby area or "
                f"a different category."
            )
        else:
            empty_reason = None
            message = None

        diagnostics = {
            "provider": "serper",
            "provider_status": provider_status,
            "category": parsed["service_category"],
            "normalized_location": profile["normalized"],
            "search_location": profile["search_location"],
            "queries": search_queries,
            "query_count": len(search_queries),
            "queries_executed": num_searches,
            "query_stats": query_stats,
            "raw_results": len(raw_results),
            "candidates_extracted": extracted_count,
            "parse_failures": parse_failures,
            "validated": len(validated),
            "rejected": sum(rejection_reasons.values()),
            "rejection_reasons": dict(rejection_reasons),
            "deduplicated": len(deduplicated),
            "duplicates_removed": len(validated) - len(deduplicated),
            "returned": len(top_results),
            "empty_reason": empty_reason,
            "total_latency_ms": total_latency_ms,
            "stages": {
                "service_query_generation": {
                    "query_count": len(search_queries),
                    "queries": search_queries,
                },
                "serper_search": {
                    "provider": "serper",
                    "status": provider_status,
                    "queries_executed": num_searches,
                    "raw_results": len(raw_results),
                },
                "service_candidate_extraction": {
                    "extracted": extracted_count,
                    "parse_failures": parse_failures,
                },
                "service_validation": {
                    "validated": len(validated),
                    "rejected": sum(rejection_reasons.values()),
                    "rejection_reasons": dict(rejection_reasons),
                },
                "service_deduplication": {
                    "before": len(validated),
                    "after": len(deduplicated),
                    "removed": len(validated) - len(deduplicated),
                },
                "service_ranking": {
                    "ranked": len(ranked),
                    "returned": len(top_results),
                },
            },
        }

        logger.info(
            "SERVICE_FINDER | searches=%d | raw=%d | validated=%d | rejected=%d | "
            "deduplicated=%d | returned=%d | provider=%s | latency=%dms",
            num_searches, len(raw_results), len(validated),
            sum(rejection_reasons.values()), len(deduplicated),
            len(top_results), provider_status, total_latency_ms,
        )

        response: Dict[str, Any] = {
            "success": True,
            "query": _base_query(parsed, location, service_category),
            "results": top_results,
            "count": len(top_results),
            "source": "Web Search",
            "timestamp": time.strftime("%H:%M:%S"),
            "search_latency_ms": total_latency_ms,
            "total_latency_ms": total_latency_ms,
            "num_searches": num_searches,
            "raw_count": len(raw_results),
            "validated_count": len(validated),
            "rejected_count": sum(rejection_reasons.values()),
            "diagnostics": diagnostics,
        }
        if message:
            response["message"] = message
            response["empty_reason"] = empty_reason
        return response

    except Exception as exc:
        logger.error(
            "SERVICE_FINDER | unexpected failure: %s", type(exc).__name__,
            exc_info=True,
        )
        return _failure(
            parsed, location, service_category, "internal_error",
            "Service search is temporarily unavailable. Please try again.",
            {
                "provider": "serper",
                "provider_status": provider_status,
                "queries_executed": num_searches,
                "raw_results": len(raw_results),
            },
        )
