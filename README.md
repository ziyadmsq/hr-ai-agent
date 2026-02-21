# 🤖 HR Operations Agent

> A full-stack tutorial for building an AI-powered HR chatbot using RAG (Retrieval-Augmented Generation) and AI Agents with tool calling.

Learn how to build a **multi-tenant HR platform** where employees chat with an AI agent that can check leave balances, search company policies via RAG, submit leave requests, and generate HR documents — all powered by LangChain, LangGraph, and your choice of LLM provider.

---

## ✨ Features

- **AI HR Chatbot with Tool Calling** — Check leave balances, submit requests, and generate documents through natural conversation
- **RAG-Powered Policy Search** — Semantic search over HR policy documents using pgvector embeddings
- **Multi-Provider AI Support** — Switch between OpenAI, Groq, and Ollama via LangChain/LangGraph
- **Multi-Tenant Architecture** — Full organization isolation with per-tenant data and configuration
- **Real-Time Chat** — WebSocket-powered chat interface for instant AI responses
- **Employee Directory** — Searchable employee list with detail panels (profile, leave balances, requests)
- **Proactive Alert System** — Configurable HR monitoring triggers (compliance, sentiment, leave patterns)
- **WhatsApp & Email Integrations** — Webhook structure for multi-channel HR communication
- **Admin Settings** — Configure AI provider, model, and credentials per organization

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 + TypeScript + Vite |
| UI Components | shadcn/ui |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| AI/LLM | LangChain + LangGraph |
| AI Providers | OpenAI, Groq, Ollama |
| Embeddings | OpenAI text-embedding-3-small |
| Auth | JWT + bcrypt |
| Containers | Docker + Docker Compose |

---

## 📁 Project Structure

```
hr-operations-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API routes (auth, chat, employees, leave, policies, etc.)
│   │   ├── core/            # Config, database, auth dependencies
│   │   ├── models/          # SQLAlchemy models (12 models)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/
│   │       ├── agent/       # AI agent (LangGraph), tools, conversation manager
│   │       ├── rag/         # RAG pipeline (embeddings, chunker, retriever)
│   │       ├── channels/    # WhatsApp & Email integrations
│   │       └── alerts/      # Proactive monitoring system
│   ├── alembic/             # Database migrations
│   ├── seed.py              # Sample data seeder
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # 8 pages (Login, Register, Dashboard, Chat, etc.)
│   │   ├── components/      # Chat UI + 17 shadcn/ui components
│   │   ├── hooks/           # useChat (WebSocket), useToast
│   │   ├── contexts/        # Auth context
│   │   └── layouts/         # Auth & Dashboard layouts
│   └── package.json
├── docker-compose.yml       # Full stack orchestration
├── .env                     # API keys (create from .env.example)
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Docker & Docker Compose** installed on your machine
- An **OpenAI API key** (or Groq API key, or local Ollama installation)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/hr-operations-agent.git
cd hr-operations-agent

# 2. Create your environment file
cp .env.example .env
# Edit .env and add your API key:
# OPENAI_API_KEY=sk-your-key-here

# 3. Start the full stack
docker-compose up --build -d

# 4. Wait for services to be healthy (~15 seconds)
docker-compose ps

# 5. Run the seed script to populate sample data
docker-compose exec backend python seed.py

# 6. Open the app
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000/docs
```

### Default Login

After seeding, you can log in with any of the 10 pre-created users:

- **Admin**: `sarah.chen@acme.com` / `password123`
- **Employee**: `emily.johnson@acme.com` / `password123`

> All 10 seeded users use `password123` as their password.

---

## 🧠 Architecture Overview

Here's how the AI agent processes a user message:

1. **User sends a message** via the chat interface (REST or WebSocket)
2. **Message is routed** to the LangGraph ReAct agent
3. **The agent decides** which tools to call based on the user's intent:
   - `check_leave_balance` — Query the employee's remaining leave days
   - `submit_leave_request` — File a new leave request
   - `search_policies` — Search HR policies using RAG (pgvector similarity search)
   - `get_employee_info` — Look up employee profile details
   - `generate_document` — Create HR documents (offer letters, etc.)
4. **For policy questions**, the agent calls `search_policies`, which queries the pgvector database using embedding similarity to find relevant policy chunks
5. **The agent responds** with real data from your database — no hallucinated answers
6. **All conversations** are stored per-tenant in PostgreSQL

---

## 🔧 AI Provider Configuration

Admins can configure the AI provider from the **Settings** page. The platform supports three providers:

| Provider | Config | Default Model |
|----------|--------|---------------|
| **OpenAI** | Set provider to `openai`, add your API key | `gpt-4o-mini` |
| **Groq** | Set provider to `groq`, add your Groq API key | `llama-3.3-70b-versatile` |
| **Ollama** | Set provider to `ollama`, set base URL (`http://localhost:11434`) | `llama3` |

Configuration is stored per-organization, so each tenant can use a different AI provider.

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register-org` | POST | Register a new organization |
| `/api/v1/auth/login` | POST | Login and get JWT token |
| `/api/v1/chat/conversations` | POST | Create a new conversation |
| `/api/v1/chat/message` | POST | Send a message to the AI agent |
| `/api/v1/chat/ws/{employee_id}` | WS | WebSocket for real-time chat |
| `/api/v1/employees` | GET | List employees |
| `/api/v1/leave/balance` | GET | Check leave balances |
| `/api/v1/policies` | GET | List HR policies |
| `/api/v1/org/ai-config` | GET/PATCH | AI provider configuration |
| `/api/v1/rag/query` | POST | Query policies via RAG |

Full API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs) when the backend is running.

---

## 🛑 Stopping the App

```bash
# Stop containers (preserves data)
docker-compose down

# Stop and remove all data (clean slate)
docker-compose down -v
```

---

Made with ❤️ by Ziyad Alqahtani
