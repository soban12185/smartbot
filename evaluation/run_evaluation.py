"""
SmartBot RAG Evaluation Runner

Runs evaluation dataset through SmartBot's ACTUAL RAG pipeline,
applies evaluators, and reports results.

For each evaluation example:
1. Indexes the reference context as a document (via SmartBot's real pipeline)
2. Runs the real retriever (hybrid retrieval + Jina reranker)
3. Compares real retrieved chunks against ground-truth texts
4. Computes genuine retrieval metrics (Hit Rate@K, Recall@K, Precision@K, MRR)

Usage:
    python evaluation/run_evaluation.py --max 5

Results are:
1. Stored in LangSmith for analysis (if configured)
2. Printed as a local summary
3. Saved to evaluation/results/ for offline analysis
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env BEFORE anything else reads environment variables
from dotenv import load_dotenv
load_dotenv()

from evaluation.dataset import get_evaluation_data
from evaluation.evaluators import evaluate_all
from tracing import trace_run, is_tracing_enabled

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RETRIEVAL_K = 5


def _check_env() -> Dict[str, bool]:
    """Check which env vars are available."""
    return {
        "GROQ_API_KEY": bool(os.environ.get("GROQ_API_KEY")),
        "GOOGLE_API_KEY": bool(os.environ.get("GOOGLE_API_KEY")),
        "JINA_API_KEY": bool(os.environ.get("JINA_API_KEY")),
        "LANGSMITH_TRACING": os.environ.get("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes"),
        "LANGSMITH_API_KEY": bool(os.environ.get("LANGSMITH_API_KEY")),
    }


def _classify_example(result: Dict[str, Any]) -> str:
    """
    Classify an evaluation example as PASS, FAIL, or ERROR.

    ERROR: any evaluator returned an error (API failure, empty content, etc.)
    FAIL: all evaluators ran but score is below threshold (average < 0.6)
    PASS: all evaluators ran and score is acceptable (average >= 0.6)
    """
    if result.get("error"):
        return "ERROR"
    if result["evaluation"].get("has_errors"):
        return "ERROR"
    avg = result["evaluation"].get("average_score")
    if avg is None:
        return "ERROR"
    if avg < 0.6:
        return "FAIL"
    return "PASS"


def run_evaluation(max_examples: int = 0) -> Dict[str, Any]:
    """
    Run the evaluation dataset through SmartBot's real RAG pipeline
    and evaluate results with genuine metrics.
    """
    env_status = _check_env()
    logger.info("SmartBot RAG Evaluation (Real Retrieval)")
    logger.info("=" * 60)
    logger.info("Environment:")
    for k, v in env_status.items():
        logger.info("  %s: %s", k, "set" if v else "MISSING")

    has_llm_key = env_status["GROQ_API_KEY"] or env_status["GOOGLE_API_KEY"]
    if not has_llm_key:
        logger.error(
            "No LLM API key found! Set GROQ_API_KEY or GOOGLE_API_KEY in .env"
        )
        logger.error("LLM-as-judge evaluators will not be able to run.")

    if not env_status["JINA_API_KEY"]:
        logger.error(
            "JINA_API_KEY not found! Real retrieval requires Jina embeddings."
        )
        logger.error("Retrieval metrics will be NOT_EVALUATED.")

    dataset = get_evaluation_data()
    if max_examples > 0:
        dataset = dataset[:max_examples]

    logger.info("Examples: %d", len(dataset))
    logger.info("Retrieval K: %d", RETRIEVAL_K)
    logger.info("LangSmith tracing: %s", "enabled" if env_status["LANGSMITH_TRACING"] else "disabled")
    logger.info("=" * 60)

    results = []
    start_time = time.time()

    for i, example in enumerate(dataset):
        question = example["question"]
        reference_answer = example["reference_answer"]
        reference_context = example["reference_context"]
        ground_truth_chunks = example.get("ground_truth_chunks", [])
        metadata = example.get("metadata", {})

        logger.info("\n[%d/%d] Question: %s", i + 1, len(dataset), question)

        generated_answer = ""
        retrieved_chunks = []
        error = None

        try:
            with trace_run(
                name=f"eval_example_{i+1}",
                run_type="chain",
                inputs={"question": question, "index": i},
                metadata={"evaluation": True, **metadata},
                tags=["evaluation", "rag"],
            ) as eval_run:

                from pdf_analyzer import index_text, search, get_stored_chunks, generate_answer

                # Step 1: Index the reference context as a document
                index_result = index_text(reference_context)
                if "error" in index_result:
                    error = f"Indexing failed: {index_result['error']}"
                    logger.error("  %s", error)
                else:
                    doc_id = index_result["doc_id"]
                    logger.info("  Indexed as doc_id=%s (%d chunks)", doc_id, index_result["chunks"])

                    # Step 2: Run the REAL retriever
                    search_result = search(question, doc_id)

                    if "error" in search_result:
                        error = f"Retrieval failed: {search_result['error']}"
                        logger.error("  %s", error)
                    else:
                        # Extract real retrieved chunks with metadata
                        sources = search_result.get("sources", [])
                        stored = get_stored_chunks(doc_id)
                        retrieved_chunks = []
                        for src in sources:
                            chunk_text = ""
                            for sc in stored:
                                if sc["chunk_id"] == src.get("chunk_id"):
                                    chunk_text = sc["text"]
                                    break
                            if not chunk_text and stored:
                                for sc in stored:
                                    if sc["page"] == src.get("page"):
                                        chunk_text = sc["text"]
                                        break

                            retrieved_chunks.append({
                                "chunk_id": src.get("chunk_id"),
                                "page": src.get("page"),
                                "section": src.get("section"),
                                "text": chunk_text,
                                "semantic_score": src.get("semantic_score", 0),
                                "bm25_score": src.get("bm25_score", 0),
                                "hybrid_score": src.get("hybrid_score", 0),
                                "reranker_score": src.get("reranker_score"),
                            })

                        logger.info("  Retrieved %d chunks", len(retrieved_chunks))

                        # Step 3: Generate answer using real retrieved context
                        context = "\n\n".join(rc["text"] for rc in retrieved_chunks if rc.get("text"))
                        generated_answer = generate_answer(question, context) or ""
                        if not generated_answer:
                            logger.warning("  No answer generated (check GROQ_API_KEY/GOOGLE_API_KEY)")

                if eval_run:
                    eval_run.end(outputs={
                        "generated_answer": generated_answer[:500] if generated_answer else "",
                        "retrieval_count": len(retrieved_chunks),
                        "doc_id": doc_id if "doc_id" in dir() else None,
                    })

        except Exception as exc:
            error = str(exc)
            logger.error("  Error: %s", error)

        # Step 4: Evaluate with real retrieval metrics
        eval_results = evaluate_all(
            question=question,
            reference_answer=reference_answer,
            reference_context=reference_context,
            generated_answer=generated_answer,
            retrieved_chunks=retrieved_chunks,
            ground_truth_texts=ground_truth_chunks,
            retrieval_k=RETRIEVAL_K,
        )

        # Log LLM evaluation
        for metric in ["correctness", "relevance", "faithfulness"]:
            r = eval_results[metric]
            if r["error"]:
                logger.info("  %s: ERROR - %s", metric, r["error"])
            else:
                logger.info("  %s: %.3f - %s", metric, r["score"], r["reasoning"][:80])

        # Log retrieval evaluation
        ret = eval_results["retrieval"]
        if ret["error"]:
            logger.info("  retrieval: NOT_EVALUATED - %s", ret["error"])
        else:
            logger.info(
                "  retrieval@%d: recall=%.3f hit_rate=%.3f precision=%.3f mrr=%.3f",
                ret["k"], ret["recall"], ret["hit_rate"], ret["precision"], ret["mrr"],
            )

        result = {
            "index": i + 1,
            "question": question,
            "reference_answer": reference_answer,
            "generated_answer": generated_answer,
            "ground_truth_chunks": ground_truth_chunks,
            "metadata": metadata,
            "evaluation": eval_results,
            "retrieval_detail": {
                "retrieved_chunks": [
                    {
                        "chunk_id": rc.get("chunk_id"),
                        "page": rc.get("page"),
                        "section": rc.get("section"),
                        "text": rc.get("text", "")[:300],
                        "semantic_score": rc.get("semantic_score"),
                        "bm25_score": rc.get("bm25_score"),
                        "hybrid_score": rc.get("hybrid_score"),
                        "reranker_score": rc.get("reranker_score"),
                    }
                    for rc in retrieved_chunks
                ],
                "total_retrieved": len(retrieved_chunks),
            },
            "error": error,
        }
        # Classify this example
        result["status"] = _classify_example(result)
        results.append(result)

    elapsed = time.time() - start_time

    # --- Classify all examples ---
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    errors = [r for r in results if r["status"] == "ERROR"]

    # --- Aggregate metrics (only from PASS examples for clean averages) ---
    if passed:
        correctness_scores = [
            r["evaluation"]["correctness"]["score"]
            for r in passed
            if r["evaluation"]["correctness"]["score"] is not None
        ]
        relevance_scores = [
            r["evaluation"]["relevance"]["score"]
            for r in passed
            if r["evaluation"]["relevance"]["score"] is not None
        ]
        faithfulness_scores = [
            r["evaluation"]["faithfulness"]["score"]
            for r in passed
            if r["evaluation"]["faithfulness"]["score"] is not None
        ]

        avg_correctness = sum(correctness_scores) / len(correctness_scores) if correctness_scores else None
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else None
        avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else None

        all_llm_scores = correctness_scores + relevance_scores + faithfulness_scores
        avg_overall = sum(all_llm_scores) / len(all_llm_scores) if all_llm_scores else None

        retrieval_results = [
            r["evaluation"]["retrieval"]
            for r in passed
            if r["evaluation"]["retrieval"]["error"] is None
        ]
        if retrieval_results:
            avg_recall = sum(r["recall"] for r in retrieval_results) / len(retrieval_results)
            avg_hit_rate = sum(r["hit_rate"] for r in retrieval_results) / len(retrieval_results)
            avg_precision = sum(r["precision"] for r in retrieval_results) / len(retrieval_results)
            avg_mrr = sum(r["mrr"] for r in retrieval_results) / len(retrieval_results)
        else:
            avg_recall = avg_hit_rate = avg_precision = avg_mrr = None
    else:
        avg_correctness = avg_relevance = avg_faithfulness = avg_overall = None
        avg_recall = avg_hit_rate = avg_precision = avg_mrr = None

    real_retrieval_count = len([
        r for r in results
        if r["evaluation"]["retrieval"]["error"] is None
    ])

    summary = {
        "total_examples": len(dataset),
        "passed": len(passed),
        "failed": len(failed),
        "errors": len(errors),
        "elapsed_seconds": round(elapsed, 2),
        "llm_metrics": {
            "answer_correctness": round(avg_correctness, 3) if avg_correctness is not None else None,
            "answer_relevance": round(avg_relevance, 3) if avg_relevance is not None else None,
            "faithfulness": round(avg_faithfulness, 3) if avg_faithfulness is not None else None,
            "overall": round(avg_overall, 3) if avg_overall is not None else None,
        },
        "retrieval_metrics": {
            "recall_at_k": round(avg_recall, 3) if avg_recall is not None else None,
            "hit_rate_at_k": round(avg_hit_rate, 3) if avg_hit_rate is not None else None,
            "precision_at_k": round(avg_precision, 3) if avg_precision is not None else None,
            "mrr": round(avg_mrr, 3) if avg_mrr is not None else None,
            "k": RETRIEVAL_K,
            "examples_with_real_retrieval": real_retrieval_count,
            "total_examples": len(dataset),
            "status": "EVALUATED" if real_retrieval_count > 0 else "NOT_EVALUATED",
        },
        "passed_indices": [r["index"] for r in passed],
        "failed_indices": [r["index"] for r in failed],
        "error_indices": [r["index"] for r in errors],
    }

    # --- Print summary ---
    print("\n" + "=" * 60)
    print("SmartBot RAG Evaluation Results")
    print("=" * 60)
    print(f"Examples: {len(dataset)} | Passed: {len(passed)} | Failed: {len(failed)} | Errors: {len(errors)}")
    print(f"Time: {elapsed:.1f}s")
    print()

    print("LLM Evaluation (on passed examples):")
    print(f"  Correctness:  {_fmt_score(avg_correctness)}")
    print(f"  Relevance:    {_fmt_score(avg_relevance)}")
    print(f"  Faithfulness: {_fmt_score(avg_faithfulness)}")
    print(f"  Overall:      {_fmt_score(avg_overall)}")
    print()

    print("Retrieval Evaluation (real pipeline, top-%d):" % RETRIEVAL_K)
    if real_retrieval_count > 0:
        print(f"  Recall@%d:    %.3f" % (RETRIEVAL_K, avg_recall if avg_recall is not None else 0))
        print(f"  Hit Rate@%d:  %.3f" % (RETRIEVAL_K, avg_hit_rate if avg_hit_rate is not None else 0))
        print(f"  Precision@%d: %.3f" % (RETRIEVAL_K, avg_precision if avg_precision is not None else 0))
        print(f"  MRR:          %.3f" % (avg_mrr if avg_mrr is not None else 0))
    else:
        print("  NOT_EVALUATED")
    print()

    # Per-example status
    for r in results:
        status = r["status"]
        icon = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERROR"}[status]
        detail = ""
        if status == "ERROR":
            detail = f" ({r['evaluation'].get('error_details', [''])[0]})"
        elif status == "FAIL":
            detail = f" (avg={r['evaluation']['average_score']})"
        print(f"  [{icon:5s}] #{r['index']}: {r['question'][:55]}...{detail}")

    print()

    if errors:
        print("ERROR details:")
        for r in errors:
            print(f"  #{r['index']}: {r['evaluation'].get('error_details', [])}")
        print()

    # Save results
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(results_dir, f"eval_{timestamp}.json")
    with open(results_file, "w") as f:
        json.dump({"summary": summary, "details": results}, f, indent=2, default=str)
    print(f"Results saved to: {results_file}")

    return summary


def _fmt_score(score: Optional[float]) -> str:
    """Format a score for display, handling None."""
    if score is None:
        return "N/A"
    return f"{score:.3f}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SmartBot RAG Evaluation")
    parser.add_argument("--max", type=int, default=0, help="Max examples to evaluate (0=all)")
    args = parser.parse_args()

    run_evaluation(max_examples=args.max)
