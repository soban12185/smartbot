# 🚀 SmartBot – AI Event Assistant with Memory & RAG

SmartBot is a state-of-the-art AI-powered chatbot designed for intelligent conversations, document understanding, and real-world service assistance. It features a dual-memory architecture and a premium ChatGPT-inspired user interface.

## ✨ Key Features

*   **🧠 Dual-Memory Architecture**:
    *   **Short-Term**: Powered by **LangGraph** for maintaining session context.
    *   **Long-Term**: Integrated with **Neo4j Graph Database** to remember users and historical facts across sessions.
*   **🔍 Web Search Intelligence**: Integrated with **Serper API** to provide real-time information from the web.
*   **📄 PDF Intelligence (RAG)**: Upload documents to get summaries or ask specific questions using Retrieval-Augmented Generation.
*   **🛠️ Service Discovery**: Look up professional services (Catering, IT, Plumbing) with a streamlined interface.
*   **🎨 Premium UI/UX**: A modern, responsive, and animated interface inspired by the latest ChatGPT design.
*   **🔐 Authentication**: Built-in Login and Sign-up system with glassmorphism modals.

## 🛠️ Technology Stack

*   **Backend**: Flask (Python)
*   **AI Orchestration**: LangChain & LangGraph
*   **LLM**: Google Gemini (1.5 Flash)
*   **Database**: Neo4j (Knowledge Graph)
*   **Vector Store**: FAISS (for PDF RAG)
*   **Frontend**: Vanilla JS, HTML5, CSS3 (Modern Flexbox/Grid)

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Neo4j Instance (Aura or Local)
*   Google Gemini API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/soban12185/smartbot.git
   cd smartbot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_key
   SERPER_API_KEY=your_serper_key
   NEO4J_URI=neo4j+ssc://your_instance.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```
   Access the bot at `http://localhost:5000`

## ☁️ Deployment

This project is configured for easy deployment on **Render**:
*   **Build Command**: `pip install -r requirements.txt`
*   **Start Command**: `gunicorn app:app`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
Built with ❤️ by [Soban](https://github.com/soban12185)
