"""
RAG Evaluation Dataset for SmartBot

Contains questions with reference answers and contexts for evaluating
SmartBot's RAG pipeline.

Categories:
1. Simple factual questions
2. Multi-chunk questions
3. Multi-page questions
4. Reasoning questions
5. Difficult retrieval questions
6. Ambiguous questions
7. Questions requiring multiple pieces of context
8. Questions where the answer is NOT present
9. Questions designed to test irrelevant retrieval
10. Questions designed to test hallucination

Schema:
    id: Unique identifier
    question: User question
    reference_answer: Expected answer
    reference_context: Expected context/source material
    ground_truth_chunks: List of reference text strings that are relevant
    metadata: Additional info (document, page, difficulty, type)
"""

from typing import Any, Dict, List

RAG_EVALUATION_DATA: List[Dict[str, Any]] = [
    # =========================================================================
    # CATEGORY 1: Simple factual questions (10)
    # =========================================================================
    {
        "id": "factual_01",
        "question": "What is the capital of France?",
        "reference_answer": "The capital of France is Paris.",
        "reference_context": "France is a country in Western Europe. Its capital city is Paris, which is also the largest city in the country.",
        "ground_truth_chunks": [
            "France is a country in Western Europe. Its capital city is Paris, which is also the largest city in the country."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "geography.pdf"},
    },
    {
        "id": "factual_02",
        "question": "What is the recommended chunk size for text splitting?",
        "reference_answer": "The recommended chunk size is 800 characters with an overlap of 150 characters.",
        "reference_context": "For optimal retrieval performance, we recommend splitting text into chunks of 800 characters with an overlap of 150 characters between consecutive chunks.",
        "ground_truth_chunks": [
            "For optimal retrieval performance, we recommend splitting text into chunks of 800 characters with an overlap of 150 characters between consecutive chunks."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "technical_guide.pdf"},
    },
    {
        "id": "factual_03",
        "question": "What embedding model does SmartBot use?",
        "reference_answer": "SmartBot uses the Jina embeddings v3 model (jina-embeddings-v3) for text embeddings.",
        "reference_context": "SmartBot employs the jina-embeddings-v3 model from Jina AI for generating text embeddings used in the hybrid RAG retrieval pipeline.",
        "ground_truth_chunks": [
            "SmartBot employs the jina-embeddings-v3 model from Jina AI for generating text embeddings used in the hybrid RAG retrieval pipeline."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "factual_04",
        "question": "What is LangSmith?",
        "reference_answer": "LangSmith is a platform for debugging, testing, evaluating, and monitoring LLM applications.",
        "reference_context": "LangSmith is an observability and evaluation platform for LLM applications. It enables developers to trace runs, evaluate responses, monitor production usage, and iteratively improve their applications.",
        "ground_truth_chunks": [
            "LangSmith is an observability and evaluation platform for LLM applications.",
            "It enables developers to trace runs, evaluate responses, monitor production usage, and iteratively improve their applications."
        ],
        "metadata": {"difficulty": "easy", "type": "definition", "document_name": "langsmith_overview.pdf"},
    },
    {
        "id": "factual_05",
        "question": "What is the maximum number of PDF pages supported?",
        "reference_answer": "SmartBot supports PDF files with up to 20 pages.",
        "reference_context": "This application supports PDF files with up to 20 pages only. For larger documents, please split them into smaller files.",
        "ground_truth_chunks": [
            "This application supports PDF files with up to 20 pages only."
        ],
        "metadata": {"difficulty": "easy", "type": "numerical", "document_name": "smartbot_docs.pdf"},
    },
    {
        "id": "factual_06",
        "question": "What is the primary LLM used by SmartBot?",
        "reference_answer": "SmartBot uses Groq as the primary LLM provider with the openai/gpt-oss-120b model.",
        "reference_context": "SmartBot uses Groq as its primary LLM provider, running the openai/gpt-oss-120b model. Gemini is used as a fallback when Groq is unavailable.",
        "ground_truth_chunks": [
            "SmartBot uses Groq as its primary LLM provider, running the openai/gpt-oss-120b model."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "factual_07",
        "question": "What reranker does SmartBot use?",
        "reference_answer": "SmartBot uses the Jina reranker v2 base multilingual model.",
        "reference_context": "SmartBot uses the jina-reranker-v2-base-multilingual model from Jina AI for reranking retrieved chunks. The reranker takes the top 20 candidates and selects the top 5 most relevant results.",
        "ground_truth_chunks": [
            "SmartBot uses the jina-reranker-v2-base-multilingual model from Jina AI for reranking retrieved chunks."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "factual_08",
        "question": "What database does SmartBot use for long-term memory?",
        "reference_answer": "SmartBot uses PostgreSQL (via Neon) for long-term memory storage.",
        "reference_context": "SmartBot stores long-term memory facts and conversation history in a PostgreSQL database hosted on Neon. The memory system uses psycopg3 for connection pooling.",
        "ground_truth_chunks": [
            "SmartBot stores long-term memory facts and conversation history in a PostgreSQL database hosted on Neon."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "factual_09",
        "question": "What is the default chunk overlap size?",
        "reference_answer": "The default chunk overlap size is 60 characters.",
        "reference_context": "SmartBot uses a chunk overlap of 60 characters to maintain context between consecutive chunks during text splitting.",
        "ground_truth_chunks": [
            "SmartBot uses a chunk overlap of 60 characters to maintain context between consecutive chunks during text splitting."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "technical_guide.pdf"},
    },
    {
        "id": "factual_10",
        "question": "What file format does SmartBot support for document upload?",
        "reference_answer": "SmartBot supports PDF files for document upload.",
        "reference_context": "SmartBot currently supports PDF files for document upload and analysis. The system uses PyMuPDF (fitz) for text extraction from PDF documents.",
        "ground_truth_chunks": [
            "SmartBot currently supports PDF files for document upload and analysis."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "smartbot_docs.pdf"},
    },
    # =========================================================================
    # CATEGORY 2: Multi-chunk questions (7)
    # =========================================================================
    {
        "id": "multi_chunk_01",
        "question": "What are the key differences between LangChain and LangGraph?",
        "reference_answer": "LangChain is a framework for building LLM applications with chains and agents, while LangGraph is a library for building stateful, multi-actor applications with LLMs using graph-based workflows.",
        "reference_context": "LangChain provides the foundational abstractions for LLM-powered applications. LangGraph extends LangChain by adding graph-based workflow orchestration for complex, stateful applications.",
        "ground_truth_chunks": [
            "LangChain provides the foundational abstractions for LLM-powered applications.",
            "LangGraph extends LangChain by adding graph-based workflow orchestration for complex, stateful applications."
        ],
        "metadata": {"difficulty": "hard", "type": "comparison", "document_name": "framework_comparison.pdf"},
    },
    {
        "id": "multi_chunk_02",
        "question": "What factors affect RAG retrieval quality?",
        "reference_answer": "Key factors include chunk size, embedding quality, retrieval method (semantic vs keyword), reranking quality, and the relevance of the source documents.",
        "reference_context": "RAG retrieval quality is influenced by: 1) Chunk size and overlap strategy, 2) Embedding model quality, 3) Hybrid retrieval weights (semantic vs BM25), 4) Reranker effectiveness, 5) Source document quality and relevance.",
        "ground_truth_chunks": [
            "RAG retrieval quality is influenced by: 1) Chunk size and overlap strategy, 2) Embedding model quality, 3) Hybrid retrieval weights (semantic vs BM25), 4) Reranker effectiveness, 5) Source document quality and relevance."
        ],
        "metadata": {"difficulty": "hard", "type": "analytical", "document_name": "rag_best_practices.pdf"},
    },
    {
        "id": "multi_chunk_03",
        "question": "What retrieval method does SmartBot combine with semantic search?",
        "reference_answer": "SmartBot combines semantic search with BM25 keyword retrieval in a hybrid approach with 70% semantic weight and 30% BM25 weight.",
        "reference_context": "SmartBot uses a hybrid retrieval approach combining Jina embeddings (semantic) with BM25 keyword retrieval. The hybrid score is calculated as 70% semantic + 30% BM25, followed by Jina reranking to select the top 5 results.",
        "ground_truth_chunks": [
            "SmartBot uses a hybrid retrieval approach combining Jina embeddings (semantic) with BM25 keyword retrieval.",
            "The hybrid score is calculated as 70% semantic + 30% BM25, followed by Jina reranking to select the top 5 results."
        ],
        "metadata": {"difficulty": "medium", "type": "multi_hop", "document_name": "retrieval_system.pdf"},
    },
    {
        "id": "multi_chunk_04",
        "question": "Describe SmartBot's full RAG pipeline from PDF upload to answer generation.",
        "reference_answer": "SmartBot's pipeline: 1) Extract text from PDF using PyMuPDF, 2) Split into chunks with overlap, 3) Generate embeddings via Jina, 4) Store in vector index with BM25, 5) Retrieve via hybrid search, 6) Rerank with Jina reranker, 7) Generate answer with LLM.",
        "reference_context": "SmartBot's RAG pipeline consists of: 1) Page-aware PDF text extraction using PyMuPDF, 2) Structure-aware chunking with configurable chunk size and overlap, 3) Jina embeddings v3 for vector representations, 4) Hybrid retrieval combining semantic similarity and BM25 keyword matching, 5) Jina reranker to select top results, 6) LLM generation using Groq or Gemini.",
        "ground_truth_chunks": [
            "SmartBot's RAG pipeline consists of: 1) Page-aware PDF text extraction using PyMuPDF, 2) Structure-aware chunking with configurable chunk size and overlap, 3) Jina embeddings v3 for vector representations, 4) Hybrid retrieval combining semantic similarity and BM25 keyword matching, 5) Jina reranker to select top results, 6) LLM generation using Groq or Gemini."
        ],
        "metadata": {"difficulty": "hard", "type": "procedural", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_chunk_05",
        "question": "What are all the components SmartBot uses for its retrieval pipeline?",
        "reference_answer": "SmartBot uses Jina embeddings, BM25 keyword retrieval, hybrid scoring (70/30 weights), and Jina reranker.",
        "reference_context": "The retrieval pipeline uses Jina embeddings v3 for semantic search, a custom BM25 implementation for keyword retrieval, hybrid scoring with 70% semantic and 30% BM25 weights, and the Jina reranker v2 for final ranking.",
        "ground_truth_chunks": [
            "The retrieval pipeline uses Jina embeddings v3 for semantic search, a custom BM25 implementation for keyword retrieval, hybrid scoring with 70% semantic and 30% BM25 weights, and the Jina reranker v2 for final ranking."
        ],
        "metadata": {"difficulty": "medium", "type": "enumeration", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_chunk_06",
        "question": "How does SmartBot handle conversation memory?",
        "reference_answer": "SmartBot uses LangGraph's MemorySaver for short-term session memory and PostgreSQL-backed long-term memory for fact extraction and retrieval.",
        "reference_context": "SmartBot implements a dual memory system: 1) Short-term memory via LangGraph's MemorySaver checkpointer for session-level conversation history, 2) Long-term memory via PostgreSQL database for persistent fact storage and retrieval across sessions.",
        "ground_truth_chunks": [
            "SmartBot implements a dual memory system: 1) Short-term memory via LangGraph's MemorySaver checkpointer for session-level conversation history, 2) Long-term memory via PostgreSQL database for persistent fact storage and retrieval across sessions."
        ],
        "metadata": {"difficulty": "medium", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_chunk_07",
        "question": "What are the different intent types SmartBot can detect?",
        "reference_answer": "SmartBot can detect product research, web search, PDF analysis, event planning, and general chat intents.",
        "reference_context": "SmartBot's intent detection system can identify: product research queries, web search requests, PDF document questions, event planning requests, and general conversational queries. Each intent triggers a different processing pipeline.",
        "ground_truth_chunks": [
            "SmartBot's intent detection system can identify: product research queries, web search requests, PDF document questions, event planning requests, and general conversational queries."
        ],
        "metadata": {"difficulty": "medium", "type": "enumeration", "document_name": "architecture_guide.pdf"},
    },
    # =========================================================================
    # CATEGORY 3: Reasoning questions (6)
    # =========================================================================
    {
        "id": "reasoning_01",
        "question": "Why does SmartBot use hybrid retrieval instead of pure semantic search?",
        "reference_answer": "Hybrid retrieval combines semantic understanding with keyword matching, providing better recall than either approach alone. BM25 catches exact keyword matches that semantic search might miss.",
        "reference_context": "SmartBot uses hybrid retrieval (70% semantic + 30% BM25) because pure semantic search can miss exact keyword matches, while pure keyword search lacks semantic understanding. The combination provides more robust retrieval across different query types.",
        "ground_truth_chunks": [
            "SmartBot uses hybrid retrieval (70% semantic + 30% BM25) because pure semantic search can miss exact keyword matches, while pure keyword search lacks semantic understanding."
        ],
        "metadata": {"difficulty": "hard", "type": "reasoning", "document_name": "rag_best_practices.pdf"},
    },
    {
        "id": "reasoning_02",
        "question": "Why is reranking important in the RAG pipeline?",
        "reference_answer": "Reranking improves precision by re-scoring the top retrieved candidates using a more sophisticated model, filtering out less relevant results that passed initial retrieval.",
        "reference_context": "After initial hybrid retrieval returns the top 20 candidates, the Jina reranker re-evaluates each candidate's relevance to the query. This second-stage ranking improves precision by filtering out results that were retrieved due to keyword overlap but are not actually relevant to the query.",
        "ground_truth_chunks": [
            "After initial hybrid retrieval returns the top 20 candidates, the Jina reranker re-evaluates each candidate's relevance to the query.",
            "This second-stage ranking improves precision by filtering out results that were retrieved due to keyword overlap but are not actually relevant to the query."
        ],
        "metadata": {"difficulty": "hard", "type": "reasoning", "document_name": "rag_best_practices.pdf"},
    },
    {
        "id": "reasoning_03",
        "question": "What are the trade-offs of using a smaller chunk size?",
        "reference_answer": "Smaller chunks improve retrieval precision but may split important context across chunks, potentially losing semantic coherence.",
        "reference_context": "Smaller chunk sizes (e.g., 200 characters) increase retrieval precision by making each chunk more focused, but risk splitting important context across multiple chunks. Larger chunks (e.g., 1000 characters) preserve context but may dilute relevance signals.",
        "ground_truth_chunks": [
            "Smaller chunk sizes (e.g., 200 characters) increase retrieval precision by making each chunk more focused, but risk splitting important context across multiple chunks."
        ],
        "metadata": {"difficulty": "hard", "type": "reasoning", "document_name": "rag_best_practices.pdf"},
    },
    {
        "id": "reasoning_04",
        "question": "Why does SmartBot use Jina embeddings instead of OpenAI embeddings?",
        "reference_answer": "Jina embeddings v3 provides competitive quality with better cost efficiency and supports the reranker integration for a unified retrieval stack.",
        "reference_context": "SmartBot uses Jina embeddings v3 because it provides high-quality embeddings at lower cost compared to OpenAI, and integrates natively with the Jina reranker API for a unified retrieval and reranking stack.",
        "ground_truth_chunks": [
            "SmartBot uses Jina embeddings v3 because it provides high-quality embeddings at lower cost compared to OpenAI, and integrates natively with the Jina reranker API for a unified retrieval and reranking stack."
        ],
        "metadata": {"difficulty": "medium", "type": "reasoning", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "reasoning_05",
        "question": "How does the confidence score work in SmartBot's RAG responses?",
        "reference_answer": "The confidence score is a heuristic combining reranker score, hybrid score, and semantic score using weighted normalization.",
        "reference_context": "SmartBot calculates a confidence score as a heuristic indicator. When a reranker score is available, it uses: 0.45 * sigmoid(reranker) + 0.30 * hybrid + 0.25 * semantic. Without reranker, it falls back to: 0.65 * hybrid + 0.35 * semantic. The result is clamped to 0-99%.",
        "ground_truth_chunks": [
            "SmartBot calculates a confidence score as a heuristic indicator.",
            "When a reranker score is available, it uses: 0.45 * sigmoid(reranker) + 0.30 * hybrid + 0.25 * semantic."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "reasoning_06",
        "question": "Why might SmartBot's retrieval return low-precision results for very short queries?",
        "reference_answer": "Short queries provide fewer keywords for BM25 matching and less semantic signal for embedding similarity, making it harder to distinguish relevant from irrelevant chunks.",
        "reference_context": "Short queries (1-3 words) produce weaker BM25 scores due to fewer keyword matches and less discriminative embedding vectors. This can cause the retriever to return chunks that match on individual common words rather than semantic relevance.",
        "ground_truth_chunks": [
            "Short queries (1-3 words) produce weaker BM25 scores due to fewer keyword matches and less discriminative embedding vectors."
        ],
        "metadata": {"difficulty": "hard", "type": "reasoning", "document_name": "rag_best_practices.pdf"},
    },
    # =========================================================================
    # CATEGORY 4: Questions requiring multiple pieces of context (6)
    # =========================================================================
    {
        "id": "multi_context_01",
        "question": "What is SmartBot's complete technology stack?",
        "reference_answer": "SmartBot uses Flask, LangChain, LangGraph, Jina embeddings, BM25, Jina reranker, Groq LLM, PostgreSQL memory, PyMuPDF, and LangSmith tracing.",
        "reference_context": "SmartBot's technology stack includes: Flask web framework, LangChain and LangGraph for orchestration, Jina embeddings v3 and BM25 for retrieval, Jina reranker v2 for ranking, Groq (openai/gpt-oss-120b) for LLM generation, PostgreSQL for long-term memory, PyMuPDF for PDF processing, and LangSmith for observability.",
        "ground_truth_chunks": [
            "SmartBot's technology stack includes: Flask web framework, LangChain and LangGraph for orchestration, Jina embeddings v3 and BM25 for retrieval, Jina reranker v2 for ranking, Groq (openai/gpt-oss-120b) for LLM generation, PostgreSQL for long-term memory, PyMuPDF for PDF processing, and LangSmith for observability."
        ],
        "metadata": {"difficulty": "medium", "type": "enumeration", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_context_02",
        "question": "How does SmartBot handle errors in the RAG pipeline?",
        "reference_answer": "SmartBot implements graceful degradation: if Groq fails, it falls back to Gemini; if reranking fails, it uses hybrid scores; if LangSmith fails, tracing is disabled but the app continues.",
        "reference_context": "SmartBot implements graceful degradation throughout the pipeline: 1) LLM generation falls back from Groq to Gemini if the primary provider fails, 2) Reranking falls back to hybrid score ordering if the Jina API fails, 3) LangSmith tracing failures are logged but never crash the application, 4) Memory system failures are caught and logged without affecting the response.",
        "ground_truth_chunks": [
            "SmartBot implements graceful degradation throughout the pipeline: 1) LLM generation falls back from Groq to Gemini if the primary provider fails, 2) Reranking falls back to hybrid score ordering if the Jina API fails, 3) LangSmith tracing failures are logged but never crash the application, 4) Memory system failures are caught and logged without affecting the response."
        ],
        "metadata": {"difficulty": "hard", "type": "procedural", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_context_03",
        "question": "What are all the API endpoints available in SmartBot?",
        "reference_answer": "SmartBot exposes endpoints for chat, web search, PDF upload/ask, product research, event planning, service lookup/booking, memory management, feedback, and LangSmith status.",
        "reference_context": "SmartBot API endpoints: POST /api/chat, POST /api/search, POST /api/pdf/summary, POST /api/pdf/ask, POST /api/products/search, POST /api/event/plan, POST /api/services/lookup, POST /api/services/book, GET /api/memory/facts, GET /api/memory/history, POST /api/memory/clear, POST /api/feedback, GET /api/langsmith/status.",
        "ground_truth_chunks": [
            "SmartBot API endpoints: POST /api/chat, POST /api/search, POST /api/pdf/summary, POST /api/pdf/ask, POST /api/products/search, POST /api/event/plan, POST /api/services/lookup, POST /api/services/book, GET /api/memory/facts, GET /api/memory/history, POST /api/memory/clear, POST /api/feedback, GET /api/langsmith/status."
        ],
        "metadata": {"difficulty": "medium", "type": "enumeration", "document_name": "api_docs.pdf"},
    },
    {
        "id": "multi_context_04",
        "question": "How does SmartBot's product research pipeline work?",
        "reference_answer": "SmartBot detects product intent, searches via Serper API, validates results for accuracy, and synthesizes findings with relevance scoring.",
        "reference_context": "SmartBot's product research pipeline: 1) Intent detection with confidence scoring, 2) Web search via Google Serper API, 3) Two-stage validation (relevance filtering, data accuracy checking), 4) Category taxonomy matching, 5) Cross-category mismatch detection, 6) Synthesis with relevance scoring and confidence levels.",
        "ground_truth_chunks": [
            "SmartBot's product research pipeline: 1) Intent detection with confidence scoring, 2) Web search via Google Serper API, 3) Two-stage validation (relevance filtering, data accuracy checking), 4) Category taxonomy matching, 5) Cross-category mismatch detection, 6) Synthesis with relevance scoring and confidence levels."
        ],
        "metadata": {"difficulty": "hard", "type": "procedural", "document_name": "product_research.pdf"},
    },
    {
        "id": "multi_context_05",
        "question": "What monitoring and observability features does SmartBot have?",
        "reference_answer": "SmartBot uses LangSmith for tracing all operations, LLM-as-judge evaluation, real retrieval metrics, and user feedback collection.",
        "reference_context": "SmartBot's observability features: 1) LangSmith tracing for all RAG, chat, and tool operations, 2) LLM-as-judge evaluation for correctness, relevance, and faithfulness, 3) Real retrieval metrics (Recall@K, Hit Rate@K, Precision@K, MRR), 4) User feedback collection via thumbs up/down, 5) Rate limiting with daily and per-minute caps.",
        "ground_truth_chunks": [
            "SmartBot's observability features: 1) LangSmith tracing for all RAG, chat, and tool operations, 2) LLM-as-judge evaluation for correctness, relevance, and faithfulness, 3) Real retrieval metrics (Recall@K, Hit Rate@K, Precision@K, MRR), 4) User feedback collection via thumbs up/down, 5) Rate limiting with daily and per-minute caps."
        ],
        "metadata": {"difficulty": "medium", "type": "enumeration", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "multi_context_06",
        "question": "What are the different ways SmartBot can process a user query?",
        "reference_answer": "SmartBot can route queries to: chat (general), PDF analysis, web search, product research, event planning, or service lookup depending on intent.",
        "reference_context": "SmartBot routes queries based on intent detection: 1) Product research queries go to the product research pipeline, 2) General questions go through LangGraph chat, 3) PDF queries use the RAG pipeline, 4) Web search queries use Serper API, 5) Event planning triggers the event planner, 6) Service keywords trigger service lookup.",
        "ground_truth_chunks": [
            "SmartBot routes queries based on intent detection: 1) Product research queries go to the product research pipeline, 2) General questions go through LangGraph chat, 3) PDF queries use the RAG pipeline, 4) Web search queries use Serper API, 5) Event planning triggers the event planner, 6) Service keywords trigger service lookup."
        ],
        "metadata": {"difficulty": "medium", "type": "procedural", "document_name": "architecture_guide.pdf"},
    },
    # =========================================================================
    # CATEGORY 5: Difficult retrieval questions (5)
    # =========================================================================
    {
        "id": "difficult_01",
        "question": "What is the exact formula used for hybrid scoring in SmartBot?",
        "reference_answer": "hybrid_score = 0.70 * semantic_normalized + 0.30 * bm25_normalized, where both scores are min-max normalized.",
        "reference_context": "SmartBot calculates the hybrid score as: hybrid_score = SEMANTIC_WEIGHT * semantic_norm + BM25_WEIGHT * lexical_norm, where SEMANTIC_WEIGHT = 0.70, BM25_WEIGHT = 0.30, and both scores are min-max normalized across all candidates.",
        "ground_truth_chunks": [
            "SmartBot calculates the hybrid score as: hybrid_score = SEMANTIC_WEIGHT * semantic_norm + BM25_WEIGHT * lexical_norm, where SEMANTIC_WEIGHT = 0.70, BM25_WEIGHT = 0.30, and both scores are min-max normalized across all candidates."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "retrieval_system.pdf"},
    },
    {
        "id": "difficult_02",
        "question": "How does SmartBot's BM25 implementation handle term frequency normalization?",
        "reference_answer": "SmartBot's BM25 uses k1=1.5 and b=0.75 parameters with standard IDF weighting and document length normalization.",
        "reference_context": "SmartBot's SimpleBM25 class uses parameters k1=1.5 and b=0.75. The term frequency is normalized by document length relative to average document length. IDF is calculated as max(0, log(1 + (N - df + 0.5) / (df + 0.5))).",
        "ground_truth_chunks": [
            "SmartBot's SimpleBM25 class uses parameters k1=1.5 and b=0.75.",
            "The term frequency is normalized by document length relative to average document length.",
            "IDF is calculated as max(0, log(1 + (N - df + 0.5) / (df + 0.5)))."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "retrieval_system.pdf"},
    },
    {
        "id": "difficult_03",
        "question": "What happens when SmartBot encounters a PDF with more than 20 pages?",
        "reference_answer": "SmartBot rejects the PDF and returns an error message asking the user to split the document.",
        "reference_context": "SmartBot enforces a maximum of 20 pages per PDF. If a user uploads a PDF with more than 20 pages, the system returns an error: 'This application supports PDF files with up to 20 pages only. For larger documents, please split them into smaller files.'",
        "ground_truth_chunks": [
            "SmartBot enforces a maximum of 20 pages per PDF.",
            "If a user uploads a PDF with more than 20 pages, the system returns an error: 'This application supports PDF files with up to 20 pages only. For larger documents, please split them into smaller files.'"
        ],
        "metadata": {"difficulty": "medium", "type": "edge_case", "document_name": "smartbot_docs.pdf"},
    },
    {
        "id": "difficult_04",
        "question": "How does min-max normalization affect retrieval when all candidates have similar scores?",
        "reference_answer": "Min-max normalization amplifies small differences when scores are close, potentially making irrelevant distinctions between candidates.",
        "reference_context": "SmartBot uses min-max normalization for hybrid scoring: normalized = (value - min) / (max - min). When all candidates have similar raw scores, small differences get amplified, which can lead to unstable rankings. This is a known limitation of min-max normalization.",
        "ground_truth_chunks": [
            "SmartBot uses min-max normalization for hybrid scoring: normalized = (value - min) / (max - min).",
            "When all candidates have similar raw scores, small differences get amplified, which can lead to unstable rankings."
        ],
        "metadata": {"difficulty": "hard", "type": "reasoning", "document_name": "rag_best_practices.pdf"},
    },
    {
        "id": "difficult_05",
        "question": "What are the limitations of SmartBot's current RAG implementation?",
        "reference_answer": "Limitations include: max 20 pages, no image/OCR support, chunking may split context, min-max normalization instability, and dependency on external APIs.",
        "reference_context": "SmartBot's RAG limitations: 1) Maximum 20 pages per PDF, 2) No image or OCR support (text-only extraction), 3) Fixed chunk size may split important context, 4) Min-max normalization can be unstable with similar scores, 5) Full dependency on Jina and Groq APIs for core functionality.",
        "ground_truth_chunks": [
            "SmartBot's RAG limitations: 1) Maximum 20 pages per PDF, 2) No image or OCR support (text-only extraction), 3) Fixed chunk size may split important context, 4) Min-max normalization can be unstable with similar scores, 5) Full dependency on Jina and Groq APIs for core functionality."
        ],
        "metadata": {"difficulty": "hard", "type": "analytical", "document_name": "architecture_guide.pdf"},
    },
    # =========================================================================
    # CATEGORY 6: Ambiguous questions (4)
    # =========================================================================
    {
        "id": "ambiguous_01",
        "question": "Is SmartBot good?",
        "reference_answer": "SmartBot is a functional RAG-powered assistant with hybrid retrieval, memory, and multiple tool integrations. Its quality depends on the use case.",
        "reference_context": "SmartBot is a portfolio project demonstrating RAG, hybrid retrieval, memory, and multi-tool integration. It works well for PDF Q&A and general chat but has limitations like the 20-page PDF cap and dependency on external APIs.",
        "ground_truth_chunks": [
            "SmartBot is a portfolio project demonstrating RAG, hybrid retrieval, memory, and multi-tool integration."
        ],
        "metadata": {"difficulty": "medium", "type": "ambiguous", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "ambiguous_02",
        "question": "How fast is SmartBot?",
        "reference_answer": "SmartBot's response time depends on the pipeline: chat responses take 2-5 seconds, PDF RAG takes 5-15 seconds (embedding + retrieval + generation), and product research takes 10-30 seconds.",
        "reference_context": "SmartBot performance varies by pipeline: chat responses (LangGraph + LLM) typically take 2-5 seconds. PDF RAG adds embedding, retrieval, and reranking, taking 5-15 seconds total. Product research involves web search and validation, taking 10-30 seconds.",
        "ground_truth_chunks": [
            "SmartBot performance varies by pipeline: chat responses (LangGraph + LLM) typically take 2-5 seconds.",
            "PDF RAG adds embedding, retrieval, and reranking, taking 5-15 seconds total."
        ],
        "metadata": {"difficulty": "medium", "type": "ambiguous", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "ambiguous_03",
        "question": "Can SmartBot replace ChatGPT?",
        "reference_answer": "SmartBot is a specialized RAG assistant, not a general-purpose chatbot. It excels at document Q&A but lacks ChatGPT's broad knowledge and capabilities.",
        "reference_context": "SmartBot is designed as a specialized RAG-powered assistant for document analysis and specific tools (product research, event planning). It is not intended as a general-purpose chatbot replacement and relies on external LLMs for generation.",
        "ground_truth_chunks": [
            "SmartBot is designed as a specialized RAG-powered assistant for document analysis and specific tools (product research, event planning)."
        ],
        "metadata": {"difficulty": "medium", "type": "ambiguous", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "ambiguous_04",
        "question": "What does SmartBot use AI for?",
        "reference_answer": "SmartBot uses AI for: LLM chat, RAG document Q&A, embedding generation, reranking, product research synthesis, event planning, and intent detection.",
        "reference_context": "SmartBot uses AI/ML in multiple components: 1) LLM for chat and generation (Groq/Gemini), 2) Embeddings for semantic search (Jina), 3) Reranking for result ranking (Jina), 4) NLP for intent detection, 5) LLM for product research synthesis, 6) LLM for event planning generation.",
        "ground_truth_chunks": [
            "SmartBot uses AI/ML in multiple components: 1) LLM for chat and generation (Groq/Gemini), 2) Embeddings for semantic search (Jina), 3) Reranking for result ranking (Jina), 4) NLP for intent detection, 5) LLM for product research synthesis, 6) LLM for event planning generation."
        ],
        "metadata": {"difficulty": "medium", "type": "ambiguous", "document_name": "architecture_guide.pdf"},
    },
    # =========================================================================
    # CATEGORY 7: Questions where answer is NOT present (4)
    # =========================================================================
    {
        "id": "unanswerable_01",
        "question": "What is the exact revenue of SmartBot in 2024?",
        "reference_answer": "This information was not found in the document.",
        "reference_context": "SmartBot is an open-source AI assistant project. No financial information is provided.",
        "ground_truth_chunks": [
            "SmartBot is an open-source AI assistant project. No financial information is provided."
        ],
        "metadata": {"difficulty": "medium", "type": "unanswerable", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "unanswerable_02",
        "question": "How many users does SmartBot have?",
        "reference_answer": "This information was not found in the document.",
        "reference_context": "SmartBot is a portfolio project. No user statistics or adoption metrics are provided in the documentation.",
        "ground_truth_chunks": [
            "SmartBot is a portfolio project. No user statistics or adoption metrics are provided in the documentation."
        ],
        "metadata": {"difficulty": "medium", "type": "unanswerable", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "unanswerable_03",
        "question": "What is the cost of running SmartBot per month?",
        "reference_answer": "This information was not found in the document.",
        "reference_context": "SmartBot's operational costs depend on API usage (Groq, Jina, Serper) and infrastructure (Vercel, Neon). No specific cost figures are provided in the documentation.",
        "ground_truth_chunks": [
            "SmartBot's operational costs depend on API usage (Groq, Jina, Serper) and infrastructure (Vercel, Neon). No specific cost figures are provided in the documentation."
        ],
        "metadata": {"difficulty": "medium", "type": "unanswerable", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "unanswerable_04",
        "question": "What programming language is SmartBot's backend written in?",
        "reference_answer": "SmartBot's backend is written in Python.",
        "reference_context": "SmartBot's backend is implemented in Python using the Flask web framework. The codebase uses Python 3.12+ with type hints throughout.",
        "ground_truth_chunks": [
            "SmartBot's backend is implemented in Python using the Flask web framework."
        ],
        "metadata": {"difficulty": "easy", "type": "factual", "document_name": "smartbot_readme.pdf"},
    },
    # =========================================================================
    # CATEGORY 8: Questions testing irrelevant retrieval (4)
    # =========================================================================
    {
        "id": "irrelevant_01",
        "question": "What is the weather in Tokyo today?",
        "reference_answer": "SmartBot does not have information about current weather conditions.",
        "reference_context": "SmartBot is a RAG assistant for document analysis. It does not provide real-time weather data or access weather APIs.",
        "ground_truth_chunks": [
            "SmartBot is a RAG assistant for document analysis. It does not provide real-time weather data or access weather APIs."
        ],
        "metadata": {"difficulty": "easy", "type": "out_of_scope", "document_name": "smartbot_docs.pdf"},
    },
    {
        "id": "irrelevant_02",
        "question": "What is the meaning of life?",
        "reference_answer": "SmartBot does not have information about philosophical questions.",
        "reference_context": "SmartBot is designed for document analysis, product research, and event planning. It does not provide philosophical or abstract answers.",
        "ground_truth_chunks": [
            "SmartBot is designed for document analysis, product research, and event planning."
        ],
        "metadata": {"difficulty": "easy", "type": "out_of_scope", "document_name": "smartbot_docs.pdf"},
    },
    {
        "id": "irrelevant_03",
        "question": "Can SmartBot play chess?",
        "reference_answer": "SmartBot does not have chess-playing capabilities.",
        "reference_context": "SmartBot is a conversational AI assistant focused on document Q&A, web search, product research, and event planning. It does not include game-playing capabilities.",
        "ground_truth_chunks": [
            "SmartBot is a conversational AI assistant focused on document Q&A, web search, product research, and event planning."
        ],
        "metadata": {"difficulty": "easy", "type": "out_of_scope", "document_name": "smartbot_docs.pdf"},
    },
    {
        "id": "irrelevant_04",
        "question": "What movies are currently playing in theaters?",
        "reference_answer": "SmartBot does not have access to current movie listings.",
        "reference_context": "SmartBot can perform web searches via the Serper API, but it is not designed for real-time entertainment information like movie listings.",
        "ground_truth_chunks": [
            "SmartBot can perform web searches via the Serper API, but it is not designed for real-time entertainment information like movie listings."
        ],
        "metadata": {"difficulty": "easy", "type": "out_of_scope", "document_name": "smartbot_docs.pdf"},
    },
    # =========================================================================
    # CATEGORY 9: Questions testing hallucination resistance (4)
    # =========================================================================
    {
        "id": "hallucination_01",
        "question": "What is SmartBot's stock ticker symbol?",
        "reference_answer": "SmartBot is not a publicly traded company and does not have a stock ticker symbol.",
        "reference_context": "SmartBot is an open-source portfolio project. It is not a company and has no stock listing.",
        "ground_truth_chunks": [
            "SmartBot is an open-source portfolio project. It is not a company and has no stock listing."
        ],
        "metadata": {"difficulty": "medium", "type": "hallucination_resistance", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "hallucination_02",
        "question": "What awards has SmartBot won?",
        "reference_answer": "No awards information was found in the document.",
        "reference_context": "SmartBot is a portfolio project demonstrating AI engineering capabilities. No awards or recognition are mentioned in the documentation.",
        "ground_truth_chunks": [
            "SmartBot is a portfolio project demonstrating AI engineering capabilities. No awards or recognition are mentioned in the documentation."
        ],
        "metadata": {"difficulty": "medium", "type": "hallucination_resistance", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "hallucination_03",
        "question": "Who is the CEO of SmartBot?",
        "reference_answer": "SmartBot does not have a CEO. It is an open-source project.",
        "reference_context": "SmartBot is an open-source project maintained by a developer. It is not a company and does not have executive roles.",
        "ground_truth_chunks": [
            "SmartBot is an open-source project maintained by a developer."
        ],
        "metadata": {"difficulty": "medium", "type": "hallucination_resistance", "document_name": "smartbot_readme.pdf"},
    },
    {
        "id": "hallucination_04",
        "question": "What is SmartBot's market share in the AI assistant space?",
        "reference_answer": "No market share information was found in the document.",
        "reference_context": "SmartBot is a portfolio project, not a commercial product. No market analysis or competitive positioning data is available.",
        "ground_truth_chunks": [
            "SmartBot is a portfolio project, not a commercial product. No market analysis or competitive positioning data is available."
        ],
        "metadata": {"difficulty": "medium", "type": "hallucination_resistance", "document_name": "smartbot_readme.pdf"},
    },
    # =========================================================================
    # CATEGORY 10: Technical deep-dive questions (6)
    # =========================================================================
    {
        "id": "technical_01",
        "question": "How does SmartBot implement sentence-aware chunking?",
        "reference_answer": "SmartBot splits text into sentences using punctuation-based regex, then groups sentences into chunks up to the chunk size limit, with overlap from previous chunk.",
        "reference_context": "SmartBot's sentence-aware chunking: 1) Split text on sentence boundaries using regex (?<=[.!?])\\s+(?=[A-Z0-9]), 2) Group sentences into chunks up to CHUNK_SIZE words, 3) When a chunk exceeds the limit, start a new chunk with OVERLAP_SIZE words from the end of the previous chunk.",
        "ground_truth_chunks": [
            "SmartBot's sentence-aware chunking: 1) Split text on sentence boundaries using regex, 2) Group sentences into chunks up to CHUNK_SIZE words, 3) When a chunk exceeds the limit, start a new chunk with OVERLAP_SIZE words from the end of the previous chunk."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "technical_guide.pdf"},
    },
    {
        "id": "technical_02",
        "question": "How does SmartBot detect section headings in documents?",
        "reference_answer": "SmartBot uses heuristics: uppercase ratio >= 0.65, line length <= 140 chars, and patterns like 'Chapter X' or numbered sections.",
        "reference_context": "SmartBot's heading detection uses multiple heuristics: 1) Lines matching patterns like 'chapter/section/part + word', 2) Lines matching numbered section patterns (1.2.3), 3) Short lines (<=140 chars) with >= 65% uppercase letters, 4) Lines that don't end with sentence punctuation.",
        "ground_truth_chunks": [
            "SmartBot's heading detection uses multiple heuristics: 1) Lines matching patterns like 'chapter/section/part + word', 2) Lines matching numbered section patterns (1.2.3), 3) Short lines (<=140 chars) with >= 65% uppercase letters, 4) Lines that don't end with sentence punctuation."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "technical_guide.pdf"},
    },
    {
        "id": "technical_03",
        "question": "What is the structure of SmartBot's vector store?",
        "reference_answer": "SmartBot stores chunks, embeddings, and BM25 index in an in-memory dictionary keyed by document ID.",
        "reference_context": "SmartBot's vector_store is a Python dictionary keyed by doc_id (UUID string). Each entry contains: 'chunks' (list of chunk dicts), 'embeddings' (list of embedding vectors), 'bm25' (SimpleBM25 instance). This in-memory store is reset when the server restarts.",
        "ground_truth_chunks": [
            "SmartBot's vector_store is a Python dictionary keyed by doc_id (UUID string).",
            "Each entry contains: 'chunks' (list of chunk dicts), 'embeddings' (list of embedding vectors), 'bm25' (SimpleBM25 instance)."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "technical_04",
        "question": "How does SmartBot handle concurrent PDF uploads?",
        "reference_answer": "SmartBot uses an in-memory vector store, so concurrent uploads are stored in the same dictionary. Each upload gets a unique doc_id to prevent collisions.",
        "reference_context": "SmartBot's in-memory vector store handles concurrent uploads by assigning unique UUID-based doc_ids to each document. The global vector_store dictionary is shared across requests, but each document is isolated by its doc_id. Note: the store is reset on server restart.",
        "ground_truth_chunks": [
            "SmartBot's in-memory vector store handles concurrent uploads by assigning unique UUID-based doc_ids to each document."
        ],
        "metadata": {"difficulty": "hard", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "technical_05",
        "question": "What is the format of a SmartBot chunk object?",
        "reference_answer": "A chunk contains: text (string), page (int), section (heading string), chunk_id (sequential int).",
        "reference_context": "SmartBot chunk format: {'text': str, 'page': int, 'section': str, 'chunk_id': int}. The chunk_id is sequential within each document, starting from 0. The page number is 1-indexed. The section is the detected heading or 'Page content' as default.",
        "ground_truth_chunks": [
            "SmartBot chunk format: {'text': str, 'page': int, 'section': str, 'chunk_id': int}."
        ],
        "metadata": {"difficulty": "medium", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
    {
        "id": "technical_06",
        "question": "How does SmartBot's rate limiting work?",
        "reference_answer": "SmartBot uses in-memory rate limiting with per-minute and daily caps, tracked via timestamp list.",
        "reference_context": "SmartBot implements rate limiting using an in-memory list of request timestamps. Per-minute limit: configurable (default 10). Daily limit: configurable (default 1000). The list is pruned on each request to remove entries older than 24 hours.",
        "ground_truth_chunks": [
            "SmartBot implements rate limiting using an in-memory list of request timestamps.",
            "Per-minute limit: configurable (default 10). Daily limit: configurable (default 1000)."
        ],
        "metadata": {"difficulty": "medium", "type": "technical", "document_name": "architecture_guide.pdf"},
    },
]


def get_evaluation_data() -> List[Dict[str, Any]]:
    """Return the full evaluation dataset."""
    return RAG_EVALUATION_DATA


def get_evaluation_data_by_type(question_type: str) -> List[Dict[str, Any]]:
    """Return evaluation data filtered by question type."""
    return [d for d in RAG_EVALUATION_DATA if d.get("metadata", {}).get("type") == question_type]


def get_evaluation_data_by_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    """Return evaluation data filtered by difficulty."""
    return [d for d in RAG_EVALUATION_DATA if d.get("metadata", {}).get("difficulty") == difficulty]


def get_category_counts() -> Dict[str, int]:
    """Return count of examples per category."""
    counts: Dict[str, int] = {}
    for d in RAG_EVALUATION_DATA:
        t = d.get("metadata", {}).get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
