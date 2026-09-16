"""Tests for the evaluation system."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDataset:
    """Test evaluation dataset."""

    def test_dataset_loads(self):
        from evaluation.dataset import get_evaluation_data
        data = get_evaluation_data()
        assert len(data) >= 50

    def test_dataset_schema(self):
        from evaluation.dataset import get_evaluation_data
        data = get_evaluation_data()
        for example in data:
            assert "id" in example
            assert "question" in example
            assert "reference_answer" in example
            assert "reference_context" in example
            assert "ground_truth_chunks" in example
            assert "metadata" in example
            assert "difficulty" in example["metadata"]
            assert "type" in example["metadata"]

    def test_dataset_categories(self):
        from evaluation.dataset import get_category_counts
        counts = get_category_counts()
        assert len(counts) >= 8

    def test_filter_by_type(self):
        from evaluation.dataset import get_evaluation_data_by_type
        factual = get_evaluation_data_by_type("factual")
        assert len(factual) >= 5

    def test_filter_by_difficulty(self):
        from evaluation.dataset import get_evaluation_data_by_difficulty
        easy = get_evaluation_data_by_difficulty("easy")
        hard = get_evaluation_data_by_difficulty("hard")
        assert len(easy) > 0
        assert len(hard) > 0


class TestEvaluateAll:
    """Test composite evaluator."""

    def test_evaluate_all_basic(self):
        from evaluation.evaluators import evaluate_all
        result = evaluate_all(
            question="What is X?",
            reference_answer="X is Y",
            reference_context="X is Y because of Z.",
            generated_answer="X is Y.",
            retrieved_chunks=[{"text": "X is Y because of Z."}],
            ground_truth_texts=["X is Y because of Z."],
            retrieval_k=5,
        )
        assert "correctness" in result
        assert "relevance" in result
        assert "faithfulness" in result
        assert "retrieval" in result
        assert "has_errors" in result
        assert "error_details" in result

    def test_evaluate_all_no_retrieval(self):
        from evaluation.evaluators import evaluate_all
        result = evaluate_all(
            question="What is X?",
            reference_answer="X is Y",
            reference_context="X is Y.",
            generated_answer="X is Y.",
        )
        assert result["retrieval"]["error"] is not None
        assert "NOT_EVALUATED" in result["retrieval"]["error"]

    def test_evaluate_all_no_answer(self):
        from evaluation.evaluators import evaluate_all
        result = evaluate_all(
            question="What is X?",
            reference_answer="X is Y",
            reference_context="X is Y.",
            generated_answer="",
        )
        assert result["has_errors"] is True
