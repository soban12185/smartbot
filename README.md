# 🤖 SmartBot – AI Assistant with Memory, RAG & Web Search

SmartBot is an AI-powered assistant built using **LangChain**, **LangGraph**, **Google Gemini**, and **Flask**. It combines conversational AI, Retrieval-Augmented Generation (RAG), web search, and persistent memory to deliver intelligent, context-aware interactions through a modern ChatGPT-inspired interface.

---

# Features

###  Intelligent Memory System

* **Short-Term Memory** using **LangGraph State** for maintaining conversation context.
* **Long-Term Memory** using **LangGraph PostgresStore** to remember user preferences and information across sessions.

### 📄 Document Intelligence (RAG)

* Upload PDF documents and ask natural language questions.
* Generate document summaries using Retrieval-Augmented Generation (RAG).
* FAISS vector search with Google Gemini for accurate document retrieval.

###  Real-Time Web Search

* Integrated **Google Serper API** to retrieve current information from the web.
* Combines web search results with LLM reasoning for improved responses.

###  Conversational AI

* Multi-turn conversations with context retention.
* Personalized responses based on stored user information.

### 🛠 Service Discovery

* Search and discover professional services such as Catering, Plumbing, IT Support, and more.

###  Modern User Interface

* ChatGPT-inspired responsive interface.
* Authentication with Login and Sign-up pages.
* Clean and user-friendly chat experience.

---

#  Tech Stack

| Category      | Technologies                             |
| ------------- | ---------------------------------------- |
| Language      | Python                                   |
| Backend       | Flask                                    |
| LLM           | Google Gemini 1.5 Flash                  |
| AI Frameworks | LangChain, LangGraph                     |
| Memory        | LangGraph State, LangGraph PostgresStore |
| Vector Store  | FAISS                                    |
| Search        | Google Serper API                        |
| Frontend      | HTML5, CSS3, JavaScript                  |
| Deployment    | Render                                   |

---

# System Architecture

```text
                 User
                   │
                   ▼
            SmartBot Interface
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
LangGraph State      LangGraph PostgresStore
(Short-Term Memory)  (Long-Term Memory)
        │                     │
        └──────────┬──────────┘
                   ▼
            LangChain Agent
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
 Google Gemini   FAISS      Serper API
     LLM        (RAG)      Web Search
                   │
                   ▼
             AI Response
```

---

#  Project Structure

```text
smartbot/
│
├── app.py                 # Flask application
├── chatbot.py             # Conversational AI logic
├── rag.py                 # RAG pipeline
├── memory.py              # LangGraph memory implementation
├── services.py            # Service discovery
├── templates/             # HTML pages
├── static/                # CSS & JavaScript
├── requirements.txt
├── .env
└── README.md
```

---

#  Installation

## Clone Repository

```bash
git clone https://github.com/soban12185/smartbot.git
cd smartbot
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Configure Environment Variables

Create a `.env` file.

```env
GOOGLE_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key
DATABASE_URL=your_langgraph_postgres_database
```

## Run Application

```bash
python app.py
```

Open

```
http://localhost:5000
```

---

#  Key Capabilities

* AI Chat Assistant
* LangGraph Workflow
* Short-Term Memory
* Long-Term Memory
* Retrieval-Augmented Generation (RAG)
* PDF Question Answering
* Document Summarization
* Real-Time Web Search
* Service Discovery
* Responsive Web Interface

---

#  Screenshots

Add screenshots of:

* Login Page
* Chat Interface
* PDF Upload
* RAG Question Answering
* Web Search Results
* User Memory Demonstration

---

#  Future Improvements

* Voice-based conversations
* Multi-agent workflow
* Authentication with OAuth
* Conversation analytics dashboard
* Multi-document RAG
* Streaming responses

---

# Author

**Soban S**

AI Engineer | Generative AI Engineer | Python Developer

📧 [sobansoban12185@gmail.com](mailto:sobansoban12185@gmail.com)

🔗 GitHub: https://github.com/soban12185

🔗 LinkedIn: https://linkedin.com/in/soban-s-884759297

---

⭐ If you found this project useful, consider giving it a star.

