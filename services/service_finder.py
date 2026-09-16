"""
Service Finder – Real-time local service discovery via web search.

Uses the existing Google Serper web-search integration to find real
local service providers.  No fake/static businesses.  No Google Places API.
No additional API keys required.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Serper configuration (reuses existing SERPER_API_KEY)
# ---------------------------------------------------------------------------

SERPER_API_URL = "https://google.serper.dev/search"

# ---------------------------------------------------------------------------
# Service category → search-term mappings
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
    "event planner": ["event planner", "event management", "wedding planner"],
    "makeup artist": ["makeup artist", "beauty makeup", "bridal makeup"],
}

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
# Input parsing
# ---------------------------------------------------------------------------

def parse_user_request(
    location: str,
    service_category: str,
    special_requirements: str = "",
) -> Dict[str, Any]:
    """
    Parse and normalise the user's service search request.

    Returns a structured dict with:
        location, service_category, search_queries, special_requirements, extracted_info
    """
    location = (location or "").strip()
    service_category = (service_category or "").strip()
    special_requirements = (special_requirements or "").strip()

    if not location:
        raise ValueError("Location is required. Please provide a city or area.")
    if not service_category:
        raise ValueError("Service category is required. Please specify the type of service.")

    category_lower = service_category.lower().strip()

    # Build targeted search queries (1–3)
    search_queries = _build_search_queries(category_lower, location, special_requirements)

    # Extract info keywords from special requirements
    extracted_info: List[str] = []
    if special_requirements:
        req_lower = special_requirements.lower()
        for kw in INFO_KEYWORDS:
            if kw in req_lower:
                extracted_info.append(kw)

    return {
        "location": location,
        "service_category": category_lower,
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
    Generate 1–3 targeted Serper search queries.
    Keeps API usage low while maximising recall.
    """
    terms = CATEGORY_SEARCH_TERMS.get(category, [category])
    queries: List[str] = []

    # Primary query: category + location
    primary_term = terms[0] if terms else category
    queries.append(f"{primary_term} {location}")

    # If special requirements exist, add a focused query
    if special_requirements:
        req_clean = special_requirements.strip()
        # Use the first meaningful part of the requirements
        queries.append(f"{primary_term} {req_clean} {location}")

    # If we have multiple search terms and still under 3, add one more
    if len(terms) > 1 and len(queries) < 3:
        queries.append(f"{terms[1]} {location}")

    return queries[:3]


# ---------------------------------------------------------------------------
# Serper search
# ---------------------------------------------------------------------------

def _serper_search(query: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """
    Execute a Serper web search and return organic results.
    Reuses the existing SERPER_API_KEY — no new API key needed.
    """
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
    except requests.exceptions.Timeout:
        logger.warning("Serper search timed out for query: %s", query)
        raise
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.warning("Serper HTTP error %s for query: %s", status, query)
        raise
    except Exception as exc:
        logger.warning("Serper search failed for '%s': %s", query, exc)
        return []


# ---------------------------------------------------------------------------
# Candidate extraction from web results
# ---------------------------------------------------------------------------

def _extract_candidate(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a structured business candidate from a Serper organic result.
    Only includes fields actually present in the search result — never fabricates data.
    """
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    link = result.get("link", "")
    position = result.get("position", 0)

    # Extract domain from URL for deduplication
    domain = ""
    if link:
        try:
            parsed = urlparse(link)
            domain = parsed.netloc.lower().replace("www.", "")
        except Exception:
            pass

    # Try to extract a phone number from the snippet
    phone = _extract_phone(snippet)

    # Try to extract rating from snippet (e.g., "4.5 ★" or "Rated 4.5/5")
    rating = _extract_rating(snippet)

    # Try to extract address-like text from snippet
    address = _extract_address(snippet, title)

    return {
        "name": title,
        "description": snippet,
        "website": link,
        "source_url": link,
        "address": address,
        "phone": phone,
        "rating": rating,
        "domain": domain,
        "position": position,
    }


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
    match = _PHONE_PATTERN.search(text)
    return match.group(0).strip() if match else None


def _extract_rating(text: str) -> Optional[float]:
    """Extract a numeric rating from text, if present."""
    match = _RATING_PATTERN.search(text)
    if match:
        try:
            val = float(match.group(1) or match.group(2))
            if 1.0 <= val <= 5.0:
                return val
        except (ValueError, TypeError):
            pass
    return None


def _extract_address(text: str, title: str) -> Optional[str]:
    """
    Best-effort address extraction from snippet text.
    Returns None if no address-like content is found.
    """
    # Look for common address patterns: "in <Location>", ", <City>,"
    location_hints = re.findall(
        r"(?:in|at|near|located in|based in)\s+([A-Z][a-zA-Z\s]+?)(?:[,.]|$)",
        text,
    )
    if location_hints:
        return location_hints[0].strip()
    return None


# ---------------------------------------------------------------------------
# Candidate validation
# ---------------------------------------------------------------------------

def _is_relevant_candidate(
    candidate: Dict[str, Any],
    service_category: str,
    location: str,
) -> Tuple[bool, str]:
    """
    Check if a web search result is relevant to the requested service.

    Returns (is_valid, rejection_reason).
    """
    name = (candidate.get("name") or "").lower()
    description = (candidate.get("description") or "").lower()
    source_url = (candidate.get("source_url") or "").lower()
    domain = (candidate.get("domain") or "").lower()
    combined = f"{name} {description}"

    # Reject if URL matches known non-business patterns
    for pattern in _REJECT_URL_PATTERNS:
        if re.search(pattern, source_url):
            return False, f"reject_url:{pattern}"

    # Reject if title matches article/blog patterns
    for kw in _REJECT_TITLE_KEYWORDS:
        if kw in name:
            return False, f"reject_title:{kw}"

    # Location relevance: check if location appears in combined text
    location_lower = location.lower()
    location_parts = [p.strip() for p in location_lower.split(",")]
    location_match = any(part in combined for part in location_parts if len(part) > 2)
    if not location_match:
        # Also check domain for location hints
        location_in_domain = any(part in domain for part in location_parts if len(part) > 2)
        if not location_in_domain:
            return False, "location_mismatch"

    # Category relevance: check if service keywords appear
    category_terms = CATEGORY_SEARCH_TERMS.get(service_category, [service_category])
    category_match = False

    for term in category_terms:
        term_words = term.lower().split()
        # Check name
        if any(t in name for t in term_words if len(t) > 2):
            category_match = True
            break
        # Check description
        if any(t in description for t in term_words if len(t) > 2):
            category_match = True
            break

    if not category_match:
        return False, f"wrong_category:no_match_for_{service_category}"

    return True, ""


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a business name for deduplication."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" - google search", " | ", " – ", " near me", " in bangalore",
                    " in chennai", " in delhi", " in mumbai", " in coimbatore"]:
        if suffix in name:
            name = name.split(suffix)[0]
    # Remove special characters
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _deduplicate(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate businesses using normalized name + domain.
    Keeps the first occurrence.
    """
    seen_names: set = set()
    seen_domains: set = set()
    unique: List[Dict[str, Any]] = []

    for c in candidates:
        norm_name = _normalize_name(c.get("name") or "")
        domain = (c.get("domain") or "").lower()

        name_key = norm_name[:30]  # Use first 30 chars to avoid over-dedup
        if name_key and name_key in seen_names:
            continue
        if domain and domain in seen_domains:
            continue

        seen_names.add(name_key)
        if domain:
            seen_domains.add(domain)
        unique.append(c)

    return unique


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def _rank_candidates(
    candidates: List[Dict[str, Any]],
    service_category: str,
    special_requirements: str = "",
) -> List[Dict[str, Any]]:
    """
    Rank validated candidates by relevance and quality signals.
    Returns sorted list (best first).
    """
    req_lower = special_requirements.lower() if special_requirements else ""
    category_terms = CATEGORY_SEARCH_TERMS.get(service_category, [service_category])

    def _score(candidate: Dict[str, Any]) -> float:
        score = 0.0
        name = (candidate.get("name") or "").lower()
        description = (candidate.get("description") or "").lower()
        combined = f"{name} {description}"

        # Service relevance: how many category keywords appear
        for term in category_terms:
            term_words = term.lower().split()
            for w in term_words:
                if len(w) > 2 and w in combined:
                    score += 2.0

        # Rating bonus (if available from snippet)
        rating = candidate.get("rating")
        if rating:
            score += rating * 1.5

        # Location match bonus
        location_in_text = any(
            part in combined
            for part in (candidate.get("_location_parts") or [])
            if len(part) > 2
        )
        if location_in_text:
            score += 3.0

        # Special requirements keyword bonus
        if req_lower:
            req_words = [w for w in req_lower.split() if len(w) > 2]
            for w in req_words:
                if w in combined:
                    score += 1.5

        # Position bonus (earlier results from Serper tend to be more relevant)
        position = candidate.get("position") or 99
        score += max(0, (10 - position) * 0.3)

        return score

    # Attach location parts for scoring
    location_parts_set = set()
    for c in candidates:
        # This will be set by the caller
        pass

    return sorted(candidates, key=_score, reverse=True)


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_services(
    location: str,
    service_category: str,
    special_requirements: str = "",
) -> Dict[str, Any]:
    """
    Search for real local service providers using Google Serper web search.

    Args:
        location: City or area (e.g., "Bangalore", "Koramangala, Chennai")
        service_category: Type of service (e.g., "catering", "plumber")
        special_requirements: Free-text requirements (e.g., "vegetarian, 100 people")

    Returns:
        Dict with keys: success, query, results, count, source, timestamp, etc.
    """
    # Parse request first (validates inputs before API key check)
    try:
        parsed = parse_user_request(location, service_category, special_requirements)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "query": {"location": location, "service_category": service_category},
            "results": [],
            "count": 0,
            "source": "Web Search",
        }

    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "error": "Search API key is not configured. Please try again later.",
            "query": {"location": location, "service_category": service_category},
            "results": [],
            "count": 0,
            "source": "Web Search",
        }

    search_queries = parsed["search_queries"]
    logger.info(
        "SERVICE_FINDER | queries=%s | location=%s | category=%s",
        search_queries, parsed["location"], parsed["service_category"],
    )

    # Execute Serper searches (1–3 queries)
    start_time = time.time()
    all_raw_results: List[Dict[str, Any]] = []
    num_searches = 0

    for query in search_queries:
        try:
            raw = _serper_search(query, num_results=10)
            all_raw_results.extend(raw)
            num_searches += 1
        except requests.exceptions.Timeout:
            logger.warning("SERVICE_FINDER | Serper timeout for query: %s", query)
            return {
                "success": False,
                "error": "Service search timed out. Please try again.",
                "query": parsed,
                "results": [],
                "count": 0,
                "source": "Web Search",
            }
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            logger.error("SERVICE_FINDER | Serper HTTP error: %s", status)
            if status == 403:
                error_msg = "Search API key is invalid or quota exceeded."
            elif status == 429:
                error_msg = "Too many requests. Please try again later."
            else:
                error_msg = "Service search is temporarily unavailable. Please try again."
            return {
                "success": False,
                "error": error_msg,
                "query": parsed,
                "results": [],
                "count": 0,
                "source": "Web Search",
            }
        except Exception as exc:
            logger.error("SERVICE_FINDER | Serper error: %s", exc)
            return {
                "success": False,
                "error": "Service search is temporarily unavailable. Please try again.",
                "query": parsed,
                "results": [],
                "count": 0,
                "source": "Web Search",
            }

    search_latency_ms = int((time.time() - start_time) * 1000)

    if not all_raw_results:
        return {
            "success": True,
            "query": parsed,
            "results": [],
            "count": 0,
            "source": "Web Search",
            "timestamp": time.strftime("%H:%M:%S"),
            "search_latency_ms": search_latency_ms,
            "num_searches": num_searches,
            "raw_count": 0,
            "validated_count": 0,
            "rejected_count": 0,
        }

    # Extract candidates from raw results
    candidates = [_extract_candidate(r) for r in all_raw_results]

    # Attach location parts for ranking
    location_parts = [p.strip().strip('"') for p in parsed["location"].lower().split(",")]
    for c in candidates:
        c["_location_parts"] = location_parts

    # Validate candidates
    validated: List[Dict[str, Any]] = []
    rejected_count = 0

    for candidate in candidates:
        is_valid, reason = _is_relevant_candidate(
            candidate, parsed["service_category"], parsed["location"]
        )
        if is_valid:
            validated.append(candidate)
        else:
            rejected_count += 1
            logger.debug(
                "SERVICE_FINDER | REJECTED | name=%s | reason=%s",
                (candidate.get("name") or "")[:50], reason,
            )

    # Deduplicate
    validated = _deduplicate(validated)

    # Rank
    ranked = _rank_candidates(
        validated, parsed["service_category"], parsed["special_requirements"]
    )

    # Take top 3, clean up internal fields
    top_results = []
    for c in ranked[:3]:
        clean = {
            "name": c.get("name", ""),
            "description": c.get("description", ""),
            "website": c.get("website"),
            "source_url": c.get("source_url"),
            "address": c.get("address"),
            "phone": c.get("phone"),
            "rating": c.get("rating"),
        }
        # Remove None values to keep response clean
        clean = {k: v for k, v in clean.items() if v is not None}
        top_results.append(clean)

    total_latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "SERVICE_FINDER | searches=%d | raw=%d | validated=%d | rejected=%d | "
        "deduplicated_to=%d | top=%d | latency=%dms",
        num_searches, len(all_raw_results), len(validated), rejected_count,
        len(validated), len(top_results), total_latency_ms,
    )

    return {
        "success": True,
        "query": parsed,
        "results": top_results,
        "count": len(top_results),
        "source": "Web Search",
        "timestamp": time.strftime("%H:%M:%S"),
        "search_latency_ms": search_latency_ms,
        "total_latency_ms": total_latency_ms,
        "num_searches": num_searches,
        "raw_count": len(all_raw_results),
        "validated_count": len(validated),
        "rejected_count": rejected_count,
    }
