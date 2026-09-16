"""
RAG Evaluators for SmartBot

Provides LLM-as-a-judge evaluators for:
- Answer correctness
- Answer relevance
- Faithfulness / groundedness

And real retrieval metrics for:
- Hit Rate@K
- Recall@K
- Precision@K
- MRR (Mean Reciprocal Rank)

These evaluators are used ONLY during evaluation runs,
not in production inference.

When the LLM judge is unavailable (missing API key), evaluators
return None with a clear error message rather than a silent 0.0.

When a judge call fails, the evaluator retries once, then returns
an ERROR status with the actual reason.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set

from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Judge Configuration
# ---------------------------------------------------------------------------

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 1
RETRY_DELAY = 1.0


def _get_judge_client() -> Optional[OpenAI]:
    """Get LLM client for evaluation judges."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        return OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        return OpenAI(api_key=google_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    return None


def _judge_llm(system_prompt: str, user_prompt: str) -> tuple[Optional[str], Optional[str]]:
    """
    Call LLM for evaluation judgment.
    Returns (response_text, error_message).
    On success: (text, None)
    On failure: (None, error_description)
    """
    client = _get_judge_client()
    if not client:
        return None, "No LLM API key available (set GROQ_API_KEY or GOOGLE_API_KEY)"

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip(), None
            last_error = "LLM returned empty content"
        except Exception as exc:
            last_error = f"API call failed: {exc}"

        if attempt < MAX_RETRIES:
            logger.debug("Judge LLM attempt %d failed, retrying in %ss: %s", attempt + 1, RETRY_DELAY, last_error)
            time.sleep(RETRY_DELAY)

    return None, last_error


def _parse_judge_response(response: str, label: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse judge response JSON.
    Returns (parsed_dict, error_message).
    """
    if not response:
        return None, "Empty response"

    try:
        result = json.loads(response)
        score = float(result.get("score", -1))
        if score < 0 or score > 1:
            return None, f"Invalid score {score} (expected 0-1)"
        return {"score": score, "reasoning": result.get("reasoning", "")}, None
    except json.JSONDecodeError:
        match = re.search(r'"score"\s*:\s*(\d+\.?\d*)', response)
        if match:
            score = float(match.group(1))
            if 0 <= score <= 1:
                return {"score": score, "reasoning": response[:200]}, None
        return None, f"Could not parse JSON from: {response[:150]}"
    except Exception as exc:
        return None, f"Parse error: {exc}"


# ---------------------------------------------------------------------------
# Answer Correctness Evaluator
# ---------------------------------------------------------------------------

CORRECTNESS_SYSTEM = """You are an evaluation judge. Your task is to evaluate whether a generated answer is correct.

You will receive:
1. A reference answer (ground truth)
2. A generated answer

Evaluate if the generated answer is factually correct compared to the reference.
Assign a score between 0 and 1:
- 1.0: Completely correct
- 0.8: Mostly correct with minor differences
- 0.6: Partially correct
- 0.4: Significantly different
- 0.2: Mostly incorrect
- 0.0: Completely incorrect or unrelated

Respond with ONLY a JSON object: {"score": <float>, "reasoning": "<brief explanation>"}
"""


def evaluate_correctness(
    reference_answer: str,
    generated_answer: str,
) -> Dict[str, Any]:
    """
    Evaluate answer correctness using LLM-as-judge.
    Returns {"score": float|None, "reasoning": str, "error": str|None}.
    """
    if not generated_answer:
        return {"score": None, "reasoning": "", "error": "No generated answer provided"}

    user_prompt = f"""Reference Answer: {reference_answer}

Generated Answer: {generated_answer}

Evaluate the correctness of the generated answer."""

    response, err = _judge_llm(CORRECTNESS_SYSTEM, user_prompt)
    if err:
        return {"score": None, "reasoning": "", "error": err}

    parsed, parse_err = _parse_judge_response(response, "correctness")
    if parsed:
        parsed["error"] = None
        return parsed

    return {"score": None, "reasoning": response[:200], "error": parse_err}


# ---------------------------------------------------------------------------
# Answer Relevance Evaluator
# ---------------------------------------------------------------------------

RELEVANCE_SYSTEM = """You are an evaluation judge. Your task is to evaluate whether an answer is relevant to the question.

You will receive:
1. A user question
2. A generated answer

Evaluate if the generated answer directly addresses the user's question.
Assign a score between 0 and 1:
- 1.0: Directly and completely answers the question
- 0.8: Mostly relevant with minor tangential content
- 0.6: Partially relevant
- 0.4: Somewhat related but misses the main point
- 0.2: Barely relevant
- 0.0: Completely irrelevant

Respond with ONLY a JSON object: {"score": <float>, "reasoning": "<brief explanation>"}
"""


def evaluate_relevance(
    question: str,
    generated_answer: str,
) -> Dict[str, Any]:
    """
    Evaluate answer relevance using LLM-as-judge.
    Returns {"score": float|None, "reasoning": str, "error": str|None}.
    """
    if not generated_answer:
        return {"score": None, "reasoning": "", "error": "No generated answer provided"}

    user_prompt = f"""Question: {question}

Generated Answer: {generated_answer}

Evaluate the relevance of the answer to the question."""

    response, err = _judge_llm(RELEVANCE_SYSTEM, user_prompt)
    if err:
        return {"score": None, "reasoning": "", "error": err}

    parsed, parse_err = _parse_judge_response(response, "relevance")
    if parsed:
        parsed["error"] = None
        return parsed

    return {"score": None, "reasoning": response[:200], "error": parse_err}


# ---------------------------------------------------------------------------
# Faithfulness / Groundedness Evaluator
# ---------------------------------------------------------------------------

FAITHFULNESS_SYSTEM = """You are an evaluation judge. Your task is to evaluate whether a generated answer is grounded in (faithful to) the provided context.

You will receive:
1. A context (retrieved documents/passages)
2. A generated answer

Evaluate if the answer is supported by the context. The answer should not contain information that contradicts or is not present in the context.
Assign a score between 0 and 1:
- 1.0: Fully supported by context
- 0.8: Mostly supported with minor unsupported claims
- 0.6: Partially supported
- 0.4: Mostly unsupported
- 0.2: Barely supported
- 0.0: Completely unsupported or contradictory

Respond with ONLY a JSON object: {"score": <float>, "reasoning": "<brief explanation>"}
"""


def evaluate_faithfulness(
    context: str,
    generated_answer: str,
) -> Dict[str, Any]:
    """
    Evaluate faithfulness/groundedness using LLM-as-judge.
    Returns {"score": float|None, "reasoning": str, "error": str|None}.
    """
    if not generated_answer:
        return {"score": None, "reasoning": "", "error": "No generated answer provided"}

    user_prompt = f"""Context: {context[:2000]}

Generated Answer: {generated_answer}

Evaluate if the answer is grounded in the context."""

    response, err = _judge_llm(FAITHFULNESS_SYSTEM, user_prompt)
    if err:
        return {"score": None, "reasoning": "", "error": err}

    parsed, parse_err = _parse_judge_response(response, "faithfulness")
    if parsed:
        parsed["error"] = None
        return parsed

    return {"score": None, "reasoning": response[:200], "error": parse_err}


# ---------------------------------------------------------------------------
# Real Retrieval Metrics
# ---------------------------------------------------------------------------

def _texts_overlap(text_a: str, text_b: str, threshold: float = 0.5) -> bool:
    """Check if two texts have significant word overlap (Jaccard)."""
    words_a = set(re.findall(r"\b\w+\b", text_a.lower()))
    words_b = set(re.findall(r"\b\w+\b", text_b.lower()))
    if not words_a or not words_b:
        return False
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) >= threshold


def _chunk_matches_ground_truth(
    retrieved_text: str,
    ground_truth_texts: List[str],
) -> bool:
    """Check if a retrieved chunk matches any ground-truth text."""
    retrieved_lower = retrieved_text.lower().strip()
    for gt_text in ground_truth_texts:
        gt_lower = gt_text.lower().strip()
        if gt_lower in retrieved_lower or retrieved_lower in gt_lower:
            return True
        if _texts_overlap(retrieved_text, gt_text, threshold=0.5):
            return True
    return False


def evaluate_retrieval(
    retrieved_chunks: List[Dict[str, Any]],
    ground_truth_texts: List[str],
    k: int = 5,
) -> Dict[str, Any]:
    """
    Evaluate retrieval quality using actual retrieved chunks and ground-truth texts.

    Returns dict with hit_rate@k, recall@k, precision@k, mrr.
    Returns None for all metrics when ground truth is missing (NOT_EVALUATED).
    """
    if not ground_truth_texts:
        return {
            "hit_rate": None,
            "recall": None,
            "precision": None,
            "mrr": None,
            "matched_gt_count": 0,
            "total_gt": 0,
            "relevant_in_top_k": 0,
            "first_relevant_rank": None,
            "k": k,
            "error": "NOT_EVALUATED: no ground-truth texts provided",
        }

    top_k = retrieved_chunks[:k]
    gt_set: Set[int] = set(range(len(ground_truth_texts)))
    matched_gt: Set[int] = set()
    relevant_retrieved = 0
    first_relevant_rank = None

    for rank_idx, chunk in enumerate(top_k):
        chunk_text = chunk.get("text", "")
        for gt_idx in gt_set:
            if gt_idx in matched_gt:
                continue
            if _chunk_matches_ground_truth(chunk_text, [ground_truth_texts[gt_idx]]):
                matched_gt.add(gt_idx)
                relevant_retrieved += 1
                if first_relevant_rank is None:
                    first_relevant_rank = rank_idx + 1

    total_gt = len(ground_truth_texts)
    recall = len(matched_gt) / total_gt if total_gt > 0 else 0.0
    hit_rate = 1.0 if matched_gt else 0.0
    precision = relevant_retrieved / k if k > 0 else 0.0
    mrr = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0

    return {
        "hit_rate": round(hit_rate, 3),
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "mrr": round(mrr, 3),
        "matched_gt_count": len(matched_gt),
        "total_gt": total_gt,
        "relevant_in_top_k": relevant_retrieved,
        "first_relevant_rank": first_relevant_rank,
        "k": k,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Composite Evaluator
# ---------------------------------------------------------------------------

def evaluate_all(
    question: str,
    reference_answer: str,
    reference_context: str,
    generated_answer: str,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    ground_truth_texts: Optional[List[str]] = None,
    retrieval_k: int = 5,
) -> Dict[str, Any]:
    """
    Run all evaluators and return composite results.

    Returns a dict with:
    - correctness, relevance, faithfulness: each has {score, reasoning, error}
    - retrieval: {hit_rate, recall, precision, mrr, error}
    - average_score: float or None (only from successful LLM scores)
    - scores_available: int
    - has_errors: bool (True if ANY evaluator returned an error)
    """
    results = {
        "correctness": evaluate_correctness(reference_answer, generated_answer),
        "relevance": evaluate_relevance(question, generated_answer),
        "faithfulness": evaluate_faithfulness(reference_context, generated_answer),
    }

    # Real retrieval metrics
    if ground_truth_texts and retrieved_chunks is not None:
        results["retrieval"] = evaluate_retrieval(
            retrieved_chunks, ground_truth_texts, k=retrieval_k
        )
    else:
        results["retrieval"] = {
            "hit_rate": None,
            "recall": None,
            "precision": None,
            "mrr": None,
            "matched_gt_count": 0,
            "total_gt": len(ground_truth_texts) if ground_truth_texts else 0,
            "relevant_in_top_k": 0,
            "first_relevant_rank": None,
            "k": retrieval_k,
            "error": "NOT_EVALUATED: ground-truth texts missing or retrieval not performed",
        }

    # Calculate average score (only from valid LLM scores)
    scores = []
    for key in ["correctness", "relevance", "faithfulness"]:
        s = results[key]["score"]
        if s is not None:
            scores.append(s)

    results["average_score"] = round(sum(scores) / len(scores), 3) if scores else None
    results["scores_available"] = len(scores)

    # Check for any errors across all evaluators
    has_errors = False
    error_details = []
    for key in ["correctness", "relevance", "faithfulness", "retrieval"]:
        if results[key].get("error"):
            has_errors = True
            error_details.append(f"{key}: {results[key]['error']}")
    results["has_errors"] = has_errors
    results["error_details"] = error_details

    return results
