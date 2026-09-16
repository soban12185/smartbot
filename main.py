import os
import time
import logging
import uuid
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from memory_system import ltm
from pdf_analyzer import analyze_pdf, search as pdf_search
from product_research import detect_product_intent, research_products
from services.service_finder import search_services
from tracing import (
    trace_run,
    trace_chat_request,
    trace_langgraph,
    trace_rag_retrieval,
    trace_rag_generation,
    trace_product_research,
    trace_web_search,
    trace_event_plan,
    trace_service_search,
    trace_llm_call,
    submit_feedback,
    is_tracing_enabled,
)

RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '10'))
RATE_LIMIT_PER_DAY = int(os.environ.get('RATE_LIMIT_PER_DAY', '1000'))

_request_log = []

def _check_rate_limit():
    now = time.time()
    _request_log.append(now)
    _request_log[:] = [t for t in _request_log if now - t < 86400]
    if len(_request_log) > RATE_LIMIT_PER_DAY:
        return False, f"Daily limit of {RATE_LIMIT_PER_DAY} requests reached. Try again tomorrow."
    recent = [t for t in _request_log if now - t < 60]
    if len(recent) > RATE_LIMIT_PER_MINUTE:
        return False, f"Rate limit of {RATE_LIMIT_PER_MINUTE} requests/minute reached. Wait a moment."
    return True, None

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.graphs import Neo4jGraph
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated, TypedDict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import random
import json

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

if GROQ_API_KEY:
    logger.info("GROQ_API_KEY loaded successfully")
else:
    logger.error("GROQ_API_KEY is missing!")

# Neo4j Setup
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

try:
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD
    )
    logger.info("Neo4j Knowledge Graph connected")
except Exception as e:
    logger.warning(f"Neo4j connection failed (optional): {str(e)}")
    graph = None

# LangGraph State Definition
class State(TypedDict):
    messages: Annotated[List[BaseMessage], "The list of messages in the conversation"]

# Define the node that calls the model
def call_model(state: State):
    # Construct the prompt with Long-Term Context (if available)
    # Note: We can pass ltm_context through the state if needed
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# Initialize LangGraph with MemorySaver for Short-Term Memory
workflow = StateGraph(State)
workflow.add_node("agent", call_model)
workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)

# MemorySaver acts as the short-term memory checkpointer
checkpointer = MemorySaver()
chat_graph = workflow.compile(checkpointer=checkpointer)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize AI components
try:
    llm = ChatOpenAI(
        model="openai/gpt-oss-120b",
        temperature=0.7,
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )
    
    search = GoogleSerperAPIWrapper(serper_api_key=SERPER_API_KEY)
    logger.info("AI components initialized successfully")
except Exception as e:
    logger.error(f"Error initializing AI components: {str(e)}")
    raise

DUMMY_API_KEY = "DUMMY_BOOKING_123"


# Routes
@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with the LLM with Postgres-backed Long-Term Memory"""
    try:
        ok, msg = _check_rate_limit()
        if not ok:
            return jsonify({'error': msg}), 429

        data = request.get_json()
        query = data.get('query', '')
        session_id = data.get('session_id', 'default_user')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        run_id = str(uuid.uuid4())[:8]

        with trace_chat_request(query, session_id, {"run_id": run_id}) as chat_run:
            # 0. Check if this is a product research query
            intent = detect_product_intent(query)
            if intent.get("is_product") and intent.get("confidence", 0) >= 0.4:
                try:
                    with trace_product_research(query, {"intent_confidence": intent.get("confidence")}) as pr_run:
                        product_result = research_products(query)
                    result = {
                        'response': product_result.get('synthesis', ''),
                        'type': 'product_research',
                        'products': product_result.get('products', []),
                        'local_stores': product_result.get('local_stores', []),
                        'recommendation': product_result.get('recommendation', {}),
                        'run_id': run_id,
                    }
                    if chat_run:
                        chat_run.end(outputs={"type": "product_research", "product_count": len(result.get("products", []))})
                    return jsonify(result)
                except Exception as e:
                    logger.error(f"Product research failed, falling back to chat: {e}")

            # 1. Retrieve LTM context from Postgres
            ltm_context = ""
            try:
                ltm_context = ltm.build_context(session_id, query)
            except Exception as e:
                logger.error(f"LTM retrieval error: {e}")

            # 2. Build prompt with LTM
            user_message_text = query
            if ltm_context:
                user_message_text = f"{ltm_context}\n\nUser Question: {query}"
            
            inputs = {"messages": [HumanMessage(content=user_message_text)]}
            config = {"configurable": {"thread_id": session_id}}
            
            # 3. Invoke LangGraph with tracing
            with trace_langgraph(query, {"session_id": session_id, "has_ltm_context": bool(ltm_context)}) as lg_run:
                output = chat_graph.invoke(inputs, config=config)
                response_text = output["messages"][-1].content

            # 4. Save to LTM
            try:
                ltm.extract_facts(session_id, query, response_text)
            except Exception as e:
                logger.error(f"LTM save error: {e}")
            
            if chat_run:
                chat_run.end(outputs={"response_length": len(response_text), "run_id": run_id})

            return jsonify({'response': response_text, 'run_id': run_id})
    
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/facts', methods=['GET'])
def get_memory_facts():
    """Return stored LTM facts for a session."""
    try:
        session_id = request.args.get('session_id', 'default_user')
        keys = ltm.list_keys(session_id)
        info = {}
        for k in keys:
            info[k] = ltm.get(session_id, k)
        return jsonify({'session_id': session_id, 'facts': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/history', methods=['GET'])
def get_memory_history():
    """Return recent conversation history for a session."""
    try:
        session_id = request.args.get('session_id', 'default_user')
        limit = int(request.args.get('limit', '10'))
        conversations = ltm.get_recent_conversations(session_id, limit)
        return jsonify({'session_id': session_id, 'history': conversations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/clear', methods=['POST'])
def clear_memory():
    """Clear all LTM data for a session."""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', 'default_user')
        ltm.clear_all(session_id)
        return jsonify({'status': 'cleared', 'session_id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search', methods=['POST'])
def web_search():
    """Perform web search"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        logger.debug(f"Search query: {query}")

        with trace_web_search(query) as search_run:
            # Get structured results instead of raw text
            results_dict = search.results(query)
            organic_results = results_dict.get('organic', [])

            logger.debug(f"Search found {len(organic_results)} organic results")

            if search_run:
                search_run.end(outputs={"result_count": len(organic_results)})
        
        return jsonify({'results': organic_results})
    
    except Exception as e:
        logger.error(f"Error in search: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/search', methods=['POST'])
def product_search():
    """Search for products online and in local stores"""
    try:
        ok, msg = _check_rate_limit()
        if not ok:
            return jsonify({'error': msg}), 429

        data = request.get_json()
        query = data.get('query', '')

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        logger.info(f"Product research query: {query}")

        with trace_product_research(query) as pr_run:
            result = research_products(query)

        if pr_run:
            pr_run.end(outputs={"product_count": result.get("total_products", 0)})

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in product search: {str(e)}", exc_info=True)
        return jsonify({'error': 'Product search failed. Please try again.'}), 500


@app.route('/api/pdf/summary', methods=['POST'])
def pdf_summary():
    """Analyze uploaded PDF — rule-based summary + FAISS index"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        with trace_run("pdf_indexing", run_type="chain", inputs={"filename": filename}, tags=["rag", "production"]) as pdf_run:
            result = analyze_pdf(filepath, filename)

        os.remove(filepath)

        if "error" in result:
            return jsonify({'error': result['error']}), 400

        if pdf_run:
            pdf_run.end(outputs={"doc_id": result.get("doc_id"), "chunks": result.get("chunks", 0)})

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in PDF analysis: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to analyze PDF. Please try again.'}), 500


@app.route('/api/pdf/ask', methods=['POST'])
def pdf_ask():
    """Ask a question about the uploaded PDF"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        doc_id = data.get('doc_id', '')

        if not question:
            return jsonify({'error': 'Question is required'}), 400

        if not doc_id:
            return jsonify({'error': 'Please upload a PDF first.'}), 400

        with trace_run("pdf_qa", run_type="chain", inputs={"question": question, "doc_id": doc_id}, tags=["rag", "production"]) as qa_run:
            result = pdf_search(question, doc_id)

        if "error" in result:
            return jsonify({'error': result['error']}), 400

        if qa_run:
            qa_run.end(outputs={
                "has_answer": "answer" in result,
                "confidence": result.get("confidence", 0),
                "source_count": len(result.get("sources", [])),
            })

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in PDF search: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to search document. Please try again.'}), 500


@app.route('/api/services/search', methods=['POST'])
def service_search():
    """Search for real local service providers via web search."""
    try:
        data = request.get_json()
        location = (data.get("location") or "").strip()
        service_category = (data.get("service_category") or "").strip()
        special_requirements = (data.get("special_requirements") or "").strip()

        if not location:
            return jsonify({"error": "Location is required. Please provide a city or area."}), 400
        if not service_category:
            return jsonify({"error": "Service category is required. Please specify the type of service."}), 400

        with trace_service_search(
            location=location,
            service_category=service_category,
            special_requirements=special_requirements,
        ) as run:
            result = search_services(
                location=location,
                service_category=service_category,
                special_requirements=special_requirements,
            )
            if run is not None:
                run.add_outputs(result)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in service search: {str(e)}", exc_info=True)
        return jsonify({"error": "Service search is temporarily unavailable. Please try again."}), 500


@app.route('/api/event/plan', methods=['POST'])
def event_plan():
    """Generate AI-powered event plan recommendations"""
    try:
        data = request.get_json()
        event_type = data.get('event_type', '')
        date = data.get('date', '')
        location = data.get('location', '')
        exactlocation = data.get('exactlocation', '')
        guest_count = int(data.get('guest_count', 0))
        total_budget = float(data.get('total_budget', 0))
        special_requirements = data.get('special_requirements', '')
        use_dummy = data.get('use_dummy', False)

        if not all([event_type, date, location, guest_count, total_budget]):
            return jsonify({'error': 'All fields are required'}), 400

        per_person_budget = total_budget / guest_count

        if use_dummy:
            food_cost = total_budget * 0.5
            decor_cost = total_budget * 0.2
            entertainment_cost = total_budget * 0.1
            buffer_budget = total_budget - (food_cost + decor_cost + entertainment_cost)

            response_text = (
                f"{event_type} Event Plan\n\n"
                f"Date: {date}\n"
                f"City: {location}\n"
                f"Venue Area: {exactlocation}\n"
                f"Total Guests: {guest_count}\n\n"
                f"--- Budget Overview ---\n"
                f"Total Budget: {total_budget:,.0f}\n"
                f"Estimated Cost Per Person: {per_person_budget:.2f}\n\n"
                f"--- Catering ---\n"
                f"South & North Indian buffet\n"
                f"Cost per plate: {per_person_budget * 0.5:.0f}\n"
                f"Total Catering Cost: {food_cost:,.0f}\n\n"
                f"--- Decoration ---\n"
                f"Floral stage decoration\n"
                f"Theme-based entrance\n"
                f"Decoration Cost: {decor_cost:,.0f}\n\n"
                f"--- Entertainment ---\n"
                f"DJ & traditional music\n"
                f"Cost: {entertainment_cost:,.0f}\n\n"
                f"--- Logistics ---\n"
                f"Guest transport, parking & coordination\n\n"
                f"--- Budget Summary ---\n"
                f"Food: {food_cost:,.0f}\n"
                f"Decoration: {decor_cost:,.0f}\n"
                f"Entertainment: {entertainment_cost:,.0f}\n"
                f"Buffer: {buffer_budget:,.0f}\n\n"
                f"--- Nearby Services ---\n"
                f"Catering: Royal Caterers, Annapoorna Foods\n"
                f"Decoration: Dream Decors, Floral Art Studio"
            )
            return jsonify({'response': response_text, 'per_person': per_person_budget})

        ok, msg = _check_rate_limit()
        if not ok:
            return jsonify({'error': msg}), 429

        prompt = f"""
You are an expert event planner. Provide a detailed event plan with venue, catering,
decoration, entertainment, logistics, budget breakdown, and nearby services.

Event Details:
- Event Type: {event_type}
- Date: {date}
- City: {location}
- Exact Location: {exactlocation}
- Total Guests: {guest_count}
- Total Budget: {total_budget}
- Per-Person Budget: {per_person_budget:.2f}
- Special Requirements: {special_requirements}
"""

        resp = llm.invoke(prompt)
        response_text = getattr(resp, "content", getattr(resp, "text", str(resp)))

        return jsonify({'response': response_text, 'per_person': per_person_budget})

    except Exception as e:
        logger.error(f"Error in event plan: {str(e)}", exc_info=True)
        err = str(e)
        if "RESOURCE_EXHAUSTED" in err or "429" in err:
            return jsonify({'error': 'AI service quota exhausted. Please try again later.'}), 429
        if "API_KEY_INVALID" in err or "403" in err:
            return jsonify({'error': 'AI service configuration error. Please contact support.'}), 403
        return jsonify({'error': 'Something went wrong while planning your event. Please try again.'}), 500


@app.route('/api/feedback', methods=['POST'])
def feedback():
    """Submit user feedback for a LangSmith run"""
    try:
        data = request.get_json()
        run_id = data.get('run_id', '')
        score = data.get('score')  # 1 = positive, 0 = negative
        comment = data.get('comment', '')

        if not run_id or score is None:
            return jsonify({'error': 'run_id and score are required'}), 400

        success = submit_feedback(run_id, int(score), comment)

        return jsonify({'status': 'submitted' if success else 'unavailable'})

    except Exception as e:
        logger.error(f"Error in feedback: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/langsmith/status', methods=['GET'])
def langsmith_status():
    """Check LangSmith tracing status"""
    enabled = is_tracing_enabled()
    return jsonify({
        'tracing_enabled': enabled,
        'project': os.environ.get('LANGSMITH_PROJECT', 'smartbot'),
    })


if __name__ == '__main__':
    logger.info("Starting SmartBot Flask application...")
    app.run(debug=True, host='0.0.0.0', port=5000)
