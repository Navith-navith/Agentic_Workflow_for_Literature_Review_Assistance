# 🤖 Agentic Workflow for Automated Literature Review Assistance (mini research agent)
## Automated literature review assistance with hybrid retrieval and agentic reasoning

A production-grade research assistant that combines hybrid retrieval (semantic + BM25),
FastAPI backend, and a Next.js chat interface to support evidence-backed review of engineering literature.

---

## 📁 Folder Structure

```
healthcare-rag/
├── backend/
│   ├── main.py                          # FastAPI entry point
│   ├── requirements.txt
│   ├── .env.example                     # Copy to .env and fill in
│   ├── core/
│   │   ├── config.py                    # Pydantic settings (reads .env)
│   │   ├── models.py                    # Shared Pydantic schemas
│   │   └── vector_store.py              # FAISS / ChromaDB abstraction
│   ├── agents/
│   │   ├── reasoning_agent.py           # Intent classification & query planning
│   │   ├── retrieval_agent.py           # Hybrid BM25 + semantic search
│   │   ├── document_agent.py            # PDF ingestion & chunk management
│   │   ├── answer_generation_agent.py   # Groq LLM answer synthesis
│   │   ├── evaluation_agent.py          # Response quality scoring
│   │   └── orchestrator.py             # Coordinates all agents
│   └── utils/
│       └── pdf_processor.py             # PDF extraction & chunking
│
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx               # Root layout + fonts
        │   ├── page.tsx                 # Main page (state + routing)
        │   └── globals.css              # Design tokens + prose styles
        ├── components/
        │   ├── layout/Sidebar.tsx       # Upload + document list panel
        │   └── chat/
        │       ├── ChatWindow.tsx       # Message list + welcome screen
        │       ├── ChatInput.tsx        # Textarea + quick actions
        │       └── MessageBubble.tsx    # Per-message renderer + sources
        ├── lib/api.ts                   # Typed API client
        └── types/index.ts               # Shared TypeScript types
```

---

## 🤖 Agent Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│   ReasoningAgent    │  Classifies intent (QA / Summarize / Compare / Trend)
│                     │  Extracts paper references, comparison aspects
└────────┬────────────┘
         │ ReasoningPlan
         ▼
┌─────────────────────┐
│   RetrievalAgent    │  Hybrid search:
│                     │   • Semantic (sentence-transformers + FAISS/Chroma)
│                     │   • BM25 keyword (rank-bm25)
│                     │   • Reciprocal Rank Fusion + alpha blend
└────────┬────────────┘
         │ List[RetrievalResult]
         ▼
┌─────────────────────┐
│   DocumentAgent     │  Owns PDF ingestion, chunking, chunk registry
│                     │  Provides full-doc chunks for summarization
└────────┬────────────┘
         │ Context chunks
         ▼
┌──────────────────────────┐
│  AnswerGenerationAgent   │  Intent-specific prompts → Groq (LLaMA 3-70B)
│                          │   • QA prompt      • Summarize prompt
│                          │   • Compare prompt • Trend prompt
└────────┬─────────────────┘
         │ Raw answer
         ▼
┌─────────────────────┐
│  EvaluationAgent    │  Scores: groundedness + completeness + format
│                     │  Returns confidence score [0-1] + warnings
└────────┬────────────┘
         │ AgentResponse
         ▼
    API Response
```

---

## ⚙️ Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- A free Groq API key from https://console.groq.com

---

### 1. Backend Setup

```bash
cd healthcare-rag/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download NLTK data (needed by BM25 tokeniser)
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Configure environment
cp .env.example .env
# Edit .env and set your GROQ_API_KEY

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000
Interactive docs at http://localhost:8000/docs

---

### 2. Frontend Setup

```bash
cd healthcare-rag/frontend

# Install dependencies
npm install

# Set environment (optional — defaults to localhost:8000)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start the dev server
npm run dev
```

The UI will be available at http://localhost:3000

---

## 🔑 Environment Variables

| Variable           | Default              | Description                      |
|--------------------|----------------------|----------------------------------|
| `GROQ_API_KEY`     | **required**         | Your Groq API key                |
| `LLM_MODEL`        | `llama3-70b-8192`    | Groq model to use                |
| `VECTOR_STORE_TYPE`| `faiss`              | `faiss` or `chroma`              |
| `EMBEDDING_MODEL`  | `all-MiniLM-L6-v2`   | Sentence-transformers model      |
| `CHUNK_SIZE`       | `512`                | Characters per chunk             |
| `CHUNK_OVERLAP`    | `64`                 | Overlap between chunks           |
| `HYBRID_ALPHA`     | `0.6`                | Semantic weight (0=BM25, 1=semantic) |
| `TOP_K_SEMANTIC`   | `5`                  | Semantic candidates              |
| `TOP_K_BM25`       | `5`                  | BM25 candidates                  |

---

## 🚀 API Endpoints

| Method | Path              | Description                        |
|--------|-------------------|------------------------------------|
| POST   | `/upload`         | Upload and index a PDF             |
| POST   | `/query`          | Ask a question (hybrid RAG)        |
| POST   | `/summarize`      | Summarise one or more papers       |
| POST   | `/compare`        | Compare two or more papers         |
| GET    | `/documents`      | List indexed documents             |
| DELETE | `/documents/{id}` | Remove a document                  |
| GET    | `/health`         | API liveness check                 |

### Example API calls

```bash
# Upload a paper
curl -X POST http://localhost:8000/upload \
  -F "file=@my_paper.pdf"

# Ask a question
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main contributions of this paper?"}'

# Summarise a paper
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"doc_ids": ["my_paper.pdf"], "focus": "methodology"}'

# Compare papers
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"doc_ids": ["paper_a.pdf", "paper_b.pdf"], "aspects": ["methodology", "results"]}'
```

---

## 💡 Example Queries

- `"What is the accuracy of the proposed model?"`
- `"Summarize this paper's methodology"`
- `"Compare paper A and paper B on their datasets and results"`
- `"What are the trends in wearable health monitoring?"`
- `"What limitations are identified across all papers?"`
- `"How does the deep learning approach compare to traditional methods?"`

---

## 🏗️ Production Considerations

For production deployment, consider:

1. **Database**: Replace in-memory document registry with PostgreSQL
2. **Auth**: Add API key or JWT authentication
3. **Vector store**: Switch to a managed service (Pinecone, Weaviate, Qdrant)
4. **Queue**: Use Celery + Redis for async PDF processing
5. **Caching**: Cache embeddings and LLM responses with Redis
6. **Monitoring**: Add OpenTelemetry tracing across agent calls
7. **Docker**: Containerise both services with docker-compose

---

## 📦 Tech Stack

| Layer         | Technology                              |
|---------------|-----------------------------------------|
| Frontend      | Next.js 14, Tailwind CSS, React Markdown |
| Backend       | FastAPI, Uvicorn                        |
| LLM           | Groq (LLaMA 3-70B)                      |
| Embeddings    | sentence-transformers (MiniLM)          |
| Vector Store  | FAISS (default) or ChromaDB             |
| Keyword Search| rank-bm25                               |
| PDF Parsing   | pdfplumber + PyPDF2                     |
