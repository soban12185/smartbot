# SmartBot – AI Assistant with Memory, RAG, Web Search & Product Research

SmartBot is an AI-powered assistant built using **LangChain**, **LangGraph**, **Groq**, and **Flask**. It combines conversational AI, Retrieval-Augmented Generation (RAG), web search, persistent memory, and product research to deliver intelligent, context-aware interactions through a modern ChatGPT-inspired interface.

## Live Demo

[https://smartbot-omega.vercel.app](https://smartbot-omega.vercel.app)

---

## Features

- **Hybrid RAG Pipeline** — PDF upload, question answering, hybrid retrieval (Jina embeddings + BM25 + Jina reranker), page-aware chunking with section preservation
- **Conversational AI** — Multi-turn chat with context retention via LangGraph state, personalized responses from stored user info
- **Long-Term Memory** — PostgreSQL-backed memory storing user preferences and conversation history across sessions
- **Real-Time Web Search** — Google Serper API integration for current information retrieval
- **Product Research Agent** — Intent detection, requirement extraction, multi-store search, AI-powered recommendations (Best Overall/Budget/Performance/Value)
- **Service Discovery** — Real-time local service provider search via web search with category validation, deduplication, and ranking
- **AI Event Planning** — Generate comprehensive event plans with venue, catering, and vendor recommendations
- **LangSmith Observability** — End-to-end tracing for every request, production monitoring, evaluation framework with LLM-as-judge evaluators
- **Automated Test Suite** — 112 tests covering PDF processing, retrieval metrics, evaluation system, product research, service finder, API endpoints, and error handling

---

## Tech Stack

| Category      | Technologies                                      |
| ------------- | ------------------------------------------------- |
| Language      | Python 3.13                                        |
| Backend       | Flask                                              |
| LLM           | Groq (openai/gpt-oss-120b), Gemini fallback       |
| AI Frameworks | LangChain 0.3.26, LangGraph 1.0.10                |
| Memory        | PostgreSQL (Long-Term + Short-Term)                |
| RAG           | Jina Embeddings v3 + BM25 + Jina Reranker        |
| Search        | Google Serper API                                  |
| Observability | LangSmith 0.3.45                                   |
| Frontend      | HTML5, CSS3, JavaScript                            |
| Testing       | pytest 9.0.3                                       |
| Deployment    | Vercel                                             |

---

## System Architecture

```
                     User
                       │
                       ▼
              SmartBot Interface
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
       Normal Chat  Product     PDF RAG
            │       Research      │
            │          │          │
            ▼          ▼          ▼
      LangGraph   Intent      Hybrid
       Agent     Detection   Retrieval
            │          │          │
            ▼          ▼          ▼
       Groq LLM   Serper API  Jina API
            │          │          │
            ▼          ▼          ▼
       AI Response  Products  Doc Answer

                     │
                     ▼
                  LangSmith
            ┌────────┼────────┐
            ▼        ▼        ▼
         Tracing  Evaluation  Monitoring
```

---

## Project Structure

```
smartbot/
├── main.py                  # Flask application & API routes
├── product_research.py      # Product Research Agent
├── pdf_analyzer.py          # RAG pipeline (chunking, embedding, retrieval, generation)
├── memory_system.py         # Long-term memory (PostgreSQL)
├── tracing.py               # LangSmith tracing (non-blocking)
├── web_search.py            # Google Serper API integration
├── services/
│   ├── __init__.py
│   └── service_finder.py  # Web search (Serper) based service discovery
├── event_planner.py         # AI event planning
├── api/
│   └── index.py             # Vercel serverless entry point
├── evaluation/
│   ├── dataset.py           # 56 evaluation examples across 10 categories
│   ├── evaluators.py        # LLM-as-judge + retrieval metric evaluators
│   └── run_evaluation.py    # Evaluation runner with retry logic
├── tests/
│   ├── test_pdf.py          # 13 tests: extraction, chunking, heading detection
│   ├── test_retrieval.py    # 10 tests: Hit Rate, Recall, Precision, MRR
│   ├── test_api.py          # 14 tests: all Flask API endpoints
│   ├── test_evaluation.py   # 8 tests: dataset, evaluators, composite scoring
│   ├── test_memory.py       # 4 tests: graceful failure handling
│   ├── test_product_research.py  # 28 tests: intent, validation, compatibility
│   ├── test_service_finder.py   # 46 tests: parsing, validation, dedup, ranking, API errors
├── templates/
│   └── index.html           # Main HTML template
├── static/
│   ├── js/main.js           # Frontend JavaScript
│   └── css/style.css        # Styles
├── requirements.txt
├── vercel.json
├── .env                     # Environment variables (not committed)
└── README.md
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/soban12185/smartbot.git
cd smartbot
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key
JINA_API_KEY=your_jina_api_key
DATABASE_URI=your_postgresql_uri

# LangSmith (optional — SmartBot works without it)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=smartbot
```

### Run Application

```bash
python main.py
```

Open `http://localhost:5000`

---

## Running Tests

```bash
# Run all tests (excluding network-dependent API tests)
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_pdf.py -v
python -m pytest tests/test_retrieval.py -v
python -m pytest tests/test_evaluation.py -v
python -m pytest tests/test_service_finder.py -v
```

**Test Coverage:**
- PDF processing: extraction, chunking, heading detection, sentence splitting
- Retrieval metrics: Hit Rate, Recall, Precision, MRR, text matching
- Service finder: input parsing, search query generation, candidate extraction, validation, deduplication, ranking, API error handling
- Evaluation system: dataset loading, filtering, evaluator functions, composite scoring
- API endpoints: input validation, error handling, service discovery, feedback
- Memory: graceful failure handling when database unavailable
- Product research: intent detection for product queries

---

## Evaluation

SmartBot includes a comprehensive RAG evaluation framework with **56 evaluation examples** across **10 categories**:

| Category | Count | Description |
|----------|-------|-------------|
| Factual | 10 | Direct fact extraction from context |
| Multi-Chunk | 7 | Information spanning multiple sections |
| Reasoning | 6 | Requires inference over context |
| Multi-Context | 6 | Multiple independent context pieces needed |
| Difficult | 5 | Nuanced or technical questions |
| Ambiguous | 4 | Multiple valid interpretations |
| Unanswerable | 4 | Questions with no answer in context |
| Irrelevant | 4 | Questions outside context scope |
| Hallucination Resistance | 4 | Tests against fabricated answers |
| Technical Deep-Dive | 6 | Detailed technical questions |

### Running Evaluation

```bash
# Run full evaluation (all 56 examples)
python evaluation/run_evaluation.py

# Run with limited examples
python evaluation/run_evaluation.py --max 5

# Filter by difficulty
python evaluation/run_evaluation.py --difficulty easy

# Filter by category
python evaluation/run_evaluation.py --type factual
```

### Evaluation Metrics

**LLM-as-Judge Evaluators:**
- **Answer Correctness** — Factual accuracy of generated answer
- **Answer Relevance** — Whether the answer addresses the question
- **Faithfulness** — Whether the answer is grounded in retrieved context

**Retrieval Metrics (real pipeline):**
- **Recall@K** — Fraction of ground truth chunks found in top-K results
- **Hit Rate@K** — Whether at least one relevant chunk was retrieved
- **Precision@K** — Fraction of retrieved chunks that are relevant
- **MRR** — Mean Reciprocal Rank of first relevant result

### Example Output

```
SmartBot RAG Evaluation Results
============================================================
Examples: 5 | Passed: 5 | Failed: 0 | Errors: 0

LLM Evaluation (on passed examples):
  Correctness:  0.880
  Relevance:    1.000
  Faithfulness: 1.000
  Overall:      0.960

Retrieval Evaluation (real pipeline, top-5):
  Recall@5:    1.000
  Hit Rate@5:  1.000
  Precision@5: 0.240
  MRR:          1.000
```

---

## LangSmith Observability

LangSmith is integrated as a non-blocking dependency. SmartBot works fully without it.

### Tracing

Every request traces end-to-end execution:
- User query → Flask API → LangGraph → Agent/Decision → RAG or Web Search → LLM → Response
- Captures: LLM calls, tool calls, retrieval queries, token usage, errors, latency

### Monitoring

Production dashboard tracks:
- Request volume and latency
- LLM latency and token usage
- RAG retrieval performance
- Error rates and failure points
- Tool call success rates

---

## API Endpoints

| Endpoint               | Method | Description                          |
| ---------------------- | ------ | ------------------------------------ |
| `/api/chat`            | POST   | Chat with intent detection           |
| `/api/products/search` | POST   | Product research search              |
| `/api/search`          | POST   | Web search                           |
| `/api/pdf/summary`     | POST   | Upload and analyze PDF               |
| `/api/pdf/ask`         | POST   | Ask question about PDF               |
| `/api/services/search`  | POST   | Real-time service search (Google Places) |
| `/api/event/plan`      | POST   | AI event planning                    |
| `/api/memory/facts`    | GET    | Get user memory facts                |
| `/api/memory/history`  | GET    | Get conversation history             |
| `/api/memory/clear`    | POST   | Clear user memory                    |
| `/api/feedback`        | POST   | Submit user feedback                 |
| `/api/langsmith/status`| GET    | Check LangSmith tracing status       |

---

## Environment Variables

| Variable              | Required | Description                         |
| --------------------- | -------- | ----------------------------------- |
| `GROQ_API_KEY`        | Yes      | Groq API key for LLM                |
| `GOOGLE_API_KEY`      | Yes      | Google API key for Gemini           |
| `SERPER_API_KEY`      | Yes      | Serper API key for web search       |
| `JINA_API_KEY`        | Yes      | Jina API key for embeddings         |
| `DATABASE_URI`        | Yes      | PostgreSQL connection string        |
| `LANGSMITH_TRACING`   | No       | Enable LangSmith tracing            |
| `LANGSMITH_API_KEY`   | No       | LangSmith API key                   |
| `LANGSMITH_PROJECT`   | No       | LangSmith project name              |

---

## Key Capabilities

- Hybrid RAG (Embeddings + BM25 + Reranker) with page-aware chunking
- LangGraph workflow with intent detection
- Short-term and long-term memory (PostgreSQL)
- Product Research Agent with multi-store search and AI recommendations
- PDF question answering with document indexing
- Real-time web search
- Real-time service discovery with web search, category validation, deduplication, and ranking
- AI event planning
- LangSmith tracing and observability
- RAG evaluation framework with 56 examples and LLM-as-judge evaluators
- Automated test suite (112 tests)
- Production error handling (proper HTTP status codes, no internal error exposure)
- User feedback collection linked to LangSmith runs
- Responsive ChatGPT-inspired web interface

---

## Author

**Soban S**

AI Engineer | Generative AI Engineer | Python Developer

📧 [sobansoban12185@gmail.com](mailto:sobansoban12185@gmail.com)

🔗 GitHub: https://github.com/soban12185

🔗 LinkedIn: https://linkedin.com/in/soban-s-884759297

---

⭐ If you found this project useful, consider giving it a star.
