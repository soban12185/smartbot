"""Tests for PDF text extraction and chunking."""
import os
import tempfile
import pytest
import fitz

# Ensure project root is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_pdf(text: str) -> str:
    """Create a temporary PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


class TestPDFExtraction:
    """Test PyMuPDF text extraction."""

    def test_extract_basic_text(self):
        from pdf_analyzer import load_document
        path = _make_pdf("Hello world. This is a test document.")
        try:
            pages = load_document(path)
            assert len(pages) >= 1
            assert "Hello world" in pages[0]["text"]
            assert pages[0]["page"] == 1
        finally:
            os.remove(path)

    def test_extract_empty_pdf(self):
        doc = fitz.open()
        doc.new_page()
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        doc.save(path)
        doc.close()
        try:
            from pdf_analyzer import load_document
            pages = load_document(path)
            assert len(pages) == 0
        finally:
            os.remove(path)

    def test_extract_multi_page(self):
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i+1} content here.", fontsize=12)
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        doc.save(path)
        doc.close()
        try:
            from pdf_analyzer import load_document
            pages = load_document(path)
            assert len(pages) == 3
            assert pages[0]["page"] == 1
            assert pages[2]["page"] == 3
        finally:
            os.remove(path)

    def test_invalid_pdf(self):
        from pdf_analyzer import analyze_pdf
        result = analyze_pdf("/nonexistent/file.pdf", "bad.pdf")
        assert "error" in result


class TestChunking:
    """Test text chunking."""

    def test_basic_chunking(self):
        from pdf_analyzer import chunk_document
        # Use sentences with periods to trigger sentence splitting
        text = ". ".join(["This is sentence number %d with enough words to fill the chunk." % i for i in range(50)])
        pages = [{"page": 1, "text": text}]
        chunks = chunk_document(pages)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "page" in chunk
            assert "chunk_id" in chunk
            assert "section" in chunk

    def test_chunk_ids_are_sequential(self):
        from pdf_analyzer import chunk_document
        pages = [{"page": 1, "text": "word " * 500}]
        chunks = chunk_document(pages)
        ids = [c["chunk_id"] for c in chunks]
        assert ids == list(range(len(chunks)))

    def test_chunk_page_tracking(self):
        from pdf_analyzer import chunk_document
        pages = [
            {"page": 1, "text": "word " * 300},
            {"page": 2, "text": "word " * 300},
        ]
        chunks = chunk_document(pages)
        page1_chunks = [c for c in chunks if c["page"] == 1]
        page2_chunks = [c for c in chunks if c["page"] == 2]
        assert len(page1_chunks) > 0
        assert len(page2_chunks) > 0

    def test_heading_detection(self):
        from pdf_analyzer import is_heading
        assert is_heading("CHAPTER 1 INTRODUCTION") is True
        assert is_heading("1.2 Background") is True
        assert is_heading("This is a long sentence that goes on and on and on and should not be detected as a heading because it exceeds the character limit for headings.") is False

    def test_empty_text(self):
        from pdf_analyzer import chunk_document
        chunks = chunk_document([{"page": 1, "text": ""}])
        assert len(chunks) == 0

    def test_normalize_text(self):
        from pdf_analyzer import normalize_text
        result = normalize_text("  hello   world  \n\n\n\n  test  ")
        assert "hello world" in result
        assert "\n\n\n\n" not in result


class TestSentenceSplit:
    """Test sentence splitting."""

    def test_basic_split(self):
        from pdf_analyzer import sentence_split
        sentences = sentence_split("First sentence. Second sentence. Third sentence.")
        assert len(sentences) == 3

    def test_empty(self):
        from pdf_analyzer import sentence_split
        assert sentence_split("") == []

    def test_single_sentence(self):
        from pdf_analyzer import sentence_split
        sentences = sentence_split("Just one sentence here.")
        assert len(sentences) == 1
