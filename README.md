# 🤖 Study-Bot — Multimodal RAG Assistant (with Citations & Evaluation)
An end-to-end Retrieval-Augmented Generation (RAG) assistant built to query academic PDFs and Python codebases with strict grounding, structured page-level citations, and automated LLM-as-a-Judge evaluation.

🏗️ Architecture & Key Features
Ingestion Pipeline (ingest.py): Extracts text from PDFs (PyMuPDF) and Python scripts using overlapping chunking (chunk_size=1000, overlap=200), generates dense embeddings via gemini-embedding-001 with batching and rate-limit handling, and persists vectors in a local ChromaDB store.

Grounded Retrieval & Structured Output (rag_engine.py): Uses semantic vector search (top_k=5) combined with Pydantic schemas to enforce structured JSON responses (answer, found_in_notes, and exact file/page citations), preventing hallucinations on out-of-scope queries. Includes model fallback and exponential backoff for API resilience.

Full-Stack Web Interface (app.py): FastAPI backend serving a responsive chat UI with live document upload and citation cards.

LLMOps & Automated Evaluation (evaluate.py): Runs a benchmark suite (including out-of-domain trap questions) scored by an LLM-as-a-Judge on Faithfulness, Relevance, Latency, and Hallucination Guardrail accuracy, exporting results to eval_report.json.

🛠️ Tech Stack
Language: Python 3.14

LLM & Embeddings: Google GenAI SDK (gemini-3.8-flash, gemini-3.1-flash-lite, gemini-embedding-001)

Vector Database: ChromaDB

Backend & Validation: FastAPI, Uvicorn, Pydantic

Document Parsing: PyMuPDF

🚀 How to Run Locally
Install dependencies:
pip install -r requirements.txt

Set up your API key: Create a .env file in the root directory and add:
GEMINI_API_KEY=your_api_key_here

Build the vector database: Place your .pdf or .py files inside the data/ folder and run:
python ingest.py

Launch the app (and optionally run evaluations):
uvicorn app:app --reload
Open http://localhost:8000 in your browser. To run the automated LLM-as-a-Judge benchmark, execute python evaluate.py.