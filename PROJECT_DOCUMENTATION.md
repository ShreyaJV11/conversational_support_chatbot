# HighwirePress Chatbot - Complete Project Documentation

This document provides a comprehensive overview of every file in the project, explaining its purpose and functionality.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Backend Structure](#backend-structure)
3. [Frontend Structure](#frontend-structure)
4. [Detailed File Documentation](#detailed-file-documentation)

---

## Project Overview

This is a **full-stack AI chatbot application** for HighwirePress - a scholarly publishing platform. The chatbot uses **RAG (Retrieval Augmented Generation)** to answer support questions from knowledge base documents.

### Tech Stack
- **Backend**: FastAPI (Python), PostgreSQL + pgvector, Redis, LangChain
- **Frontend**: React + TypeScript, Vite, Tailwind CSS
- **AI/LLM**: Groq (Llama 3.1), HuggingFace Embeddings
- **Integrations**: Microsoft Graph API (Outlook), Salesforce

---

## Backend Structure

### `backend/app/` - Main Application

#### **Core Configuration**

| File | Description |
|------|-------------|
| `app/main.py` | FastAPI application entry point. Sets up CORS, mounts routes, includes `/token` endpoint for JWT authentication, and starts a background thread that polls for emails every 3 minutes. |
| `app/__init__.py` | Package marker file (empty) |
| `app/init.py` | Empty initialization file |
| `app/core/config.py` | Loads environment variables using `dotenv`. Defines `Settings` class with DB credentials (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT) and HF_TOKEN. |
| `app/core/redis_config.py` | Initializes Redis client on localhost:6379. Provides `get_redis()` function for cache operations. Used for rate limiting tickets. |

#### **Database Layer**

| File | Description |
|------|-------------|
| `app/db/database.py` | PostgreSQL connection manager using `psycopg2`. Creates connection using settings from config.py. Used across services for DB operations. |
| `app/db/models.py` | Empty file (SQLAlchemy models not used - direct SQL queries instead) |
| `app/utils/helpers.py` | Empty file (utility functions placeholder) |

#### **API Routes**

| File | Description |
|------|-------------|
| `app/routes/chat.py` | **Main chat endpoint** (`POST /api/chat`). Handles user registration flow, smalltalk detection, ticket creation workflow (collects issue → site → duration), RAG retrieval, LLM response streaming. Returns streaming responses. Also has `GET /api/chat/initial-message/{bot_id}` for welcome messages. |
| `app/routes/kb_upload.py` | **Knowledge base management**. `GET /admin/kb-files/{bot_id}` - lists uploaded files. `POST /admin/upload-kb` - uploads .txt files, triggers ingestion. Bot-scoped uploads in `uploads/{bot_id}/` directory. |
| `app/routes/bot.py` | Bot suggestions endpoint (`GET /bot/{bot_id}/suggestions`) - returns AI-generated suggested questions based on KB content. |
| `app/routes/graph.py` | **Microsoft Graph API endpoints** for Outlook integration. `POST /graph/create-draft` - creates email drafts. `GET /graph/unread` - fetches unread emails. `POST /graph/reply-draft` - creates reply drafts. `GET /graph/process-emails` - processes all unread emails. |
| `app/routes/health.py` | Empty health check placeholder |

#### **Services - Business Logic**

| File | Description |
|------|-------------|
| `app/services/llm_service.py` | **LLM orchestration**. Creates ChatGroq models, implements query rewriting for follow-up questions, `get_answers()` for RAG responses with SHORT_ANSWER/DETAILED_ANSWER format, `detect_ticket_intent()` for ticket creation, `detect_category()` for classifying queries (chrome_extension, escalation_process, ecommerce_setup, jcore_platform, site_operations, platform_overview). Also handles email reply generation. |
| `app/services/retrieval_service.py` | **RAG Retrieval**. Uses HuggingFace embeddings (all-MiniLM-L6-v2). Implements follow-up query detection (`is_followup_query`), query rewriting using chat history, vector search in `kb_chunks` table with domain threshold checking (0.85), smart filtering by distance margin. Bot-scoped retrieval. |
| `app/services/ingestion_service.py` | **Knowledge base ingestion**. Loads .txt files using TextLoader, splits with RecursiveCharacterTextSplitter (500 chars, 50 overlap), generates embeddings, checks duplicates by hash, inserts into `kb_files` and `kb_chunks` tables. Bot-scoped. |
| `app/services/memory_service.py` | **Conversation memory**. Functions: `get_or_create_user()` - creates/links users by bot_id+email, `link_session_to_user()` - maps session to user, `get_user_by_session()` - retrieves user from session, `get_or_create_conversation()` - manages active conversations, `save_message()` - stores messages with category, `get_recent_messages()` - retrieves last N messages for context. |
| `app/services/auth_service.py` | **JWT authentication**. `create_jwt_token()` - generates 24h tokens, `verify_jwt_token()` - validates and decodes, `check_rate_limit()` - uses Redis to limit tickets to 3 per day per email. |
| `app/services/bot_service.py` | **Bot configuration**. `get_bot_config()` returns bot settings: require_registration flag, initial_message, domain_message, escalation_message, memory_limit (6), retriever_config, llm_config (llama-3.1-8b-instant). |
| `app/services/salesforce_service.py` | **Salesforce integration**. `create_salesforce_case()` - creates support tickets in Salesforce with subject, description, user email, chat history. Returns mock if credentials not configured. |
| `app/services/graph_service.py` | **Microsoft Graph API**. OAuth2 authentication, creates HTML email drafts for resolved tickets, fetches unread emails, creates reply drafts. Includes `process_emails()` that auto-responds to incoming emails using RAG. Falls back to mock mode if credentials not set. |
| `app/services/suggestion_service.py` | **AI-generated suggestions**. Queries 15 random KB chunks, uses LLM to generate 3 suggested support questions. Returns JSON array. |
| `app/services/embedding_service.py` | Empty placeholder |
| `app/services/chat_service.py` | Simple wrapper combining retrieval + LLM for basic chat workflow |

#### **Static Files**

| File | Description |
|------|-------------|
| `app/static/widget.js` | JavaScript widget for embedding chat in external websites. Creates iframe, handles resize events. |

### `backend/scripts/` - Utility Scripts

| File | Description |
|------|-------------|
| `scripts/ingest.py` | Standalone script to ingest `questions_answer.txt` into kb_chunks table. Loads file, splits, embeds, inserts. |
| `scripts/test_chat.py` | Tests chat endpoint with scenarios: initial query, memory check, domain guardrail, product query. |
| `scripts/test_full_rag.py` | Tests complete RAG pipeline: retrieve chunks → generate answer |
| `scripts/test_retrieval.py` | Tests vector retrieval only |
| `scripts/test_llm.py` | Tests LLM response generation (if exists) |

### `backend/` - Root Level

| File | Description |
|------|-------------|
| `requirements.txt` | Python dependencies: fastapi, uvicorn, psycopg2-binary, python-dotenv, langchain, langchain-community, langchain-text-splitters, langchain-huggingface, sentence-transformers, pgvector, PyJWT, redis |
| `.env` | Environment variables (API keys, DB credentials, Graph API config) |
| `.gitignore` | Ignores .env, __pycache__, venv, .vscode, OS files |
| `test_api.py` | API testing script |

---

## Frontend Structure

### `frontend/chat/` - Chat Widget

#### **Components**

| File | Description |
|------|-------------|
| `src/components/ChatWidget.tsx` | **Main chat widget component**. Manages open/minimized state, message list, user registration (name,email format), streaming responses, suggestions display, chat reset, resizable panel (drag corner), sends POST to `/api/chat` with session_id, handles JWT token storage |
| `src/components/MessageBubble.tsx` | Renders individual chat messages (user/bot) with styling |
| `src/components/TypingIndicator.tsx` | Shows "bot is typing" animation |

#### **Services**

| File | Description |
|------|-------------|
| `src/services/chatApi.ts` | **API client** for chat widget. `sendMessage()` - sends messages with streaming support, handles JSON response for registration (saves JWT token), `getInitialMessage()` - fetches welcome message, `getSuggestions()` - fetches suggested questions |
| `src/services/TicketService.ts` | Ticket-related API calls |

#### **Types**

| File | Description |
|------|-------------|
| `src/types/index.ts` | TypeScript interfaces: ChatRequest, ChatResponse, ChatMessage, ChatWidgetConfig, ChatWidgetState, InitialMessageResponse |

#### **Pages & Config**

| File | Description |
|------|-------------|
| `src/WidgetPage.tsx` | Standalone page wrapper for widget |
| `src/main.tsx` | React entry point. Reads `bot_id` from URL params, renders ChatWidget |
| `src/styles/index.css` | Tailwind CSS styles |
| `package.json` | React + TypeScript + Vite + Tailwind + lucide-react icons + react-markdown |
| `vite.config.ts` | Vite bundler configuration |
| `tailwind.config.js` | Tailwind theme config |
| `postcss.config.js` | PostCSS for Tailwind |
| `tsconfig.json` | TypeScript config |
| `index.html` | HTML entry point |
| `DEV-README.md` | Development instructions |
| `README.md` | Project readme |
| `examples/basic-integration.html` | Example HTML to embed widget |
| `examples/wordpress-integration.php` | WordPress plugin example |

### `frontend/admin/` - Admin Dashboard

#### **Pages**

| File | Description |
|------|-------------|
| `src/pages/KBDashboard.tsx` | Knowledge base dashboard - shows uploaded files and status |
| `src/pages/KBUpload.tsx` | Upload page - selects .txt file, POSTs to `/api/admin/upload-kb`, shows index status |
| `src/pages/BotScript.tsx` | Generates embeddable script for chatbots |

#### **Components**

| File | Description |
|------|-------------|
| `src/components/Layout.tsx` | Admin layout with sidebar/navigation |

#### **App Structure**

| File | Description |
|------|-------------|
| `src/App.tsx` | React Router setup - routes `/` to KBDashboard, `/kb-upload` to KBUpload |
| `src/main.tsx` | Entry point |
| `src/index.css` | Global styles |
| `package.json` | React + Vite + Tailwind + React Router |
| `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`, `tsconfig*.json` | Build configs |
| `index.html` | HTML entry |
| `README.md` | Project readme |

---

## Data Flow

### Chat Flow
1. User opens widget → `main.tsx` reads `bot_id` from URL
2. ChatWidget mounts → calls `getInitialMessage()` → shows welcome message
3. User enters "name,email" → API creates user, returns JWT token
4. User asks question → POST to `/api/chat`
5. Backend checks smalltalk → handles greeting/closing
6. Checks ticket intent → triggers ticket workflow (issue → site → duration)
7. Else: retrieves relevant chunks via vector search (RAG)
8. Sends context + question to LLM (Groq Llama)
9. Streams response back to widget
10. Saves message to `messages` table

### KB Upload Flow
1. Admin uploads .txt file via admin panel
2. `kb_upload.py` receives file, saves to `uploads/{bot_id}/`
3. Calls `ingest_file()` from ingestion_service
4. Splits into chunks, generates embeddings
5. Inserts into `kb_chunks` table with bot_id scope

### Email Processing Flow
1. Background thread runs every 3 minutes
2. Calls `process_emails()` in graph_service
3. Fetches unread emails via Graph API
4. For each email: retrieves context via RAG
5. Generates LLM response
6. Creates reply draft in user's inbox

---

## Database Schema (Implied)

Tables used (via SQL):
- `users` - bot_id, name, email
- `sessions` - bot_id, user_id, session_id
- `organizations` - domain, organization_name
- `conversations` - user_id, bot_id, status, updated_at
- `messages` - conversation_id, role, content, category, created_at
- `kb_files` - file_name, file_hash, bot_id
- `kb_chunks` - chunk_text, chunk_hash, embedding, kb_file_id, bot_id, category (vector column for pgvector)

---

## Integration Points

| Service | Purpose |
|---------|---------|
| PostgreSQL + pgvector | Vector storage for KB chunks, user/conversation data |
| Redis | Rate limiting for tickets |
| Groq API | LLM for responses (Llama 3.1) |
| HuggingFace | Sentence embeddings (all-MiniLM-L6-v2) |
| Microsoft Graph | Outlook email drafts |
| Salesforce | Support ticket creation |

---

*Generated on: 2026-04-06*