"""Tests for retrieval metrics and evaluators."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRetrievalMetrics:
    """Test retrieval metric calculations."""

    def test_hit_rate_found(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [{"text": "Paris is the capital of France"}, {"text": "London is in UK"}]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["hit_rate"] == 1.0
        assert result["error"] is None

    def test_hit_rate_not_found(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [{"text": "London is in UK"}]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["hit_rate"] == 0.0

    def test_recall_partial(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [
            {"text": "Paris is the capital of France"},
            {"text": "Berlin is the capital of Germany"},
        ]
        gt = [
            "Paris is the capital of France",
            "Berlin is the capital of Germany",
            "The moon is made of green cheese and nothing else matters.",
        ]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["recall"] == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_precision(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [
            {"text": "Paris is the capital of France"},
            {"text": "Some irrelevant text"},
            {"text": "More irrelevant text"},
        ]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=3)
        assert result["precision"] == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_mrr_first_rank(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [{"text": "Paris is the capital of France"}, {"text": "Other"}]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["mrr"] == 1.0

    def test_mrr_second_rank(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [{"text": "Wrong"}, {"text": "Paris is the capital of France"}]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["mrr"] == pytest.approx(0.5, abs=0.01)

    def test_mrr_not_found(self):
        from evaluation.evaluators import evaluate_retrieval
        chunks = [{"text": "Wrong"}, {"text": "Also wrong"}]
        gt = ["Paris is the capital of France"]
        result = evaluate_retrieval(chunks, gt, k=5)
        assert result["mrr"] == 0.0

    def test_not_evaluated_when_no_gt(self):
        from evaluation.evaluators import evaluate_retrieval
        result = evaluate_retrieval([], [], k=5)
        assert result["error"] is not None
        assert "NOT_EVALUATED" in result["error"]

    def test_empty_retrieved(self):
        from evaluation.evaluators import evaluate_retrieval
        result = evaluate_retrieval([], ["some gt"], k=5)
        assert result["hit_rate"] == 0.0
        assert result["recall"] == 0.0


class TestEvaluatorFunctions:
    """Test LLM evaluator functions (with mocked LLM)."""

    def test_correctness_no_answer(self):
        from evaluation.evaluators import evaluate_correctness
        result = evaluate_correctness("Paris", "")
        assert result["score"] is None
        assert result["error"] is not None

    def test_relevance_no_answer(self):
        from evaluation.evaluators import evaluate_relevance
        result = evaluate_relevance("What is X?", "")
        assert result["score"] is None
        assert result["error"] is not None

    def test_faithfulness_no_answer(self):
        from evaluation.evaluators import evaluate_faithfulness
        result = evaluate_faithfulness("context", "")
        assert result["score"] is None
        assert result["error"] is not None


class TestTextMatching:
    """Test text overlap matching."""

    def test_exact_match(self):
        from evaluation.evaluators import _texts_overlap
        assert _texts_overlap("hello world", "hello world") is True

    def test_partial_match(self):
        from evaluation.evaluators import _texts_overlap
        assert _texts_overlap("hello world test", "hello world") is True

    def test_no_match(self):
        from evaluation.evaluators import _texts_overlap
        assert _texts_overlap("completely different", "hello world") is False

    def test_chunk_matches_gt(self):
        from evaluation.evaluators import _chunk_matches_ground_truth
        assert _chunk_matches_ground_truth("Paris is the capital", ["Paris is the capital of France"]) is True

    def test_chunk_no_match(self):
        from evaluation.evaluators import _chunk_matches_ground_truth
        assert _chunk_matches_ground_truth("London bridge", ["Paris is the capital"]) is False


# Need pytest for approx
import pytest
