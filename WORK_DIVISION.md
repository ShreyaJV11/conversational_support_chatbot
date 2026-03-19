# Project Work Division

## Conversational Support Chatbot
**Team Members**: Kanak & Shreya  
**Date**: March 2026

---

## Equal Work Distribution: 50% Each

This document outlines the equitable division of work between Kanak and Shreya for the Conversational Support Chatbot project. Each developer has both backend and frontend responsibilities with balanced workload.

---

## Developer 1: Kanak (50%)

### Backend - API & Core Services (4 files)
| File | Description |
|------|-------------|
| [`backend/app/routes/chat.py`](backend/app/routes/chat.py) | Main chat API endpoint with streaming response |
| [`backend/app/routes/bot.py`](backend/app/routes/bot.py) | Bot configuration routes |
| [`backend/app/core/config.py`](backend/app/core/config.py) | Application configuration |
| [`backend/app/main.py`](backend/app/main.py) | FastAPI app initialization & middleware |

### Backend - Services (4 files)
| File | Description |
|------|-------------|
| [`backend/app/services/llm_service.py`](backend/app/services/llm_service.py) | LLM integration with HuggingFace, query rewriting |
| [`backend/app/services/retrieval_service.py`](backend/app/services/retrieval_service.py) | RAG retrieval from vector database |
| [`backend/app/services/memory_service.py`](backend/app/services/memory_service.py) | Conversation history & user memory |
| [`backend/app/services/bot_service.py`](backend/app/services/bot_service.py) | Bot configuration management |

### Frontend - Chat Widget (3 files)
| File | Description |
|------|-------------|
| [`frontend/chat/src/components/ChatWidget.tsx`](frontend/chat/src/components/ChatWidget.tsx) | Main chat widget component |
| [`frontend/chat/src/components/TypingIndicator.tsx`](frontend/chat/src/components/TypingIndicator.tsx) | Typing animation indicator |
| [`frontend/chat/src/styles/index.css`](frontend/chat/src/styles/index.css) | Chat widget styles |

---

## Developer 2: Shreya (50%)

### Backend - Data Services (4 files)
| File | Description |
|------|-------------|
| [`backend/app/routes/kb_upload.py`](backend/app/routes/kb_upload.py) | Knowledge base upload endpoints |
| [`backend/app/services/ingestion_service.py`](backend/app/services/ingestion_service.py) | Document ingestion & chunking |
| [`backend/app/services/embedding_service.py`](backend/app/services/embedding_service.py) | Text embedding generation |
| [`backend/app/services/chat_service.py`](backend/app/services/chat_service.py) | Chat session handling |

### Backend - Database & Suggestions (3 files)
| File | Description |
|------|-------------|
| [`backend/app/db/database.py`](backend/app/db/database.py) | Database connection & session management |
| [`backend/app/db/models.py`](backend/app/db/models.py) | SQLAlchemy data models |
| [`backend/app/services/suggestion_service.py`](backend/app/services/suggestion_service.py) | AI-powered response suggestions |

### Frontend - Admin Panel (6 files)
| File | Description |
|------|-------------|
| [`frontend/admin/src/App.tsx`](frontend/admin/src/App.tsx) | Admin application root component |
| [`frontend/admin/src/main.tsx`](frontend/admin/src/main.tsx) | Admin entry point |
| [`frontend/admin/src/components/Layout.tsx`](frontend/admin/src/components/Layout.tsx) | Admin layout wrapper |
| [`frontend/admin/src/pages/KBDashboard.tsx`](frontend/admin/src/pages/KBDashboard.tsx) | Knowledge base file management UI |
| [`frontend/admin/src/pages/KBUpload.tsx`](frontend/admin/src/pages/KBUpload.tsx) | File upload interface |
| [`frontend/admin/src/pages/BotScript.tsx`](frontend/admin/src/pages/BotScript.tsx) | Widget script generation & copy |

### Frontend - Chat Services (4 files)
| File | Description |
|------|-------------|
| [`frontend/chat/src/services/chatApi.ts`](frontend/chat/src/services/chatApi.ts) | Chat API client with streaming |
| [`frontend/chat/src/services/TicketService.ts`](frontend/chat/src/services/TicketService.ts) | Ticket creation service |
| [`frontend/chat/src/components/MessageBubble.tsx`](frontend/chat/src/components/MessageBubble.tsx) | Chat message bubbles |
| [`frontend/chat/src/types/index.ts`](frontend/chat/src/types/index.ts) | TypeScript type definitions |

---

## Shared/Testing (Both Developers)
| File | Description |
|------|-------------|
| [`backend/test_api.py`](backend/test_api.py) | API endpoint testing |
| [`backend/scripts/ingest.py`](backend/scripts/ingest.py) | Knowledge base ingestion script |
| [`backend/scripts/test_chat.py`](backend/scripts/test_chat.py) | Chat functionality testing |
| [`backend/scripts/test_llm.py`](backend/scripts/test_llm.py) | LLM service testing |
| [`backend/scripts/test_retrieval.py`](backend/scripts/test_retrieval.py) | Retrieval testing |
| [`backend/scripts/test_full_rag.py`](backend/scripts/test_full_rag.py) | End-to-end RAG pipeline testing |
| [`frontend/chat/src/main.tsx`](frontend/chat/src/main.tsx) | Chat widget entry point |
| [`frontend/chat/src/WidgetPage.tsx`](frontend/chat/src/WidgetPage.tsx) | Widget demo page |
| [`frontend/chat/examples/basic-integration.html`](frontend/chat/examples/basic-integration.html) | Basic HTML integration guide |
| [`backend/app/static/widget.js`](backend/app/static/widget.js) | Embedded chat widget JavaScript |

---

## Summary

| Developer | Backend Files | Frontend Files | Total | Percentage |
|-----------|--------------|---------------|-------|------------|
| **Kanak** | 8 | 3 | 11 | 50% |
| **Shreya** | 7 | 10 | 17 | 50% |

---

## Key Features Implemented

### Kanak
- ✅ FastAPI app setup & CORS configuration
- ✅ Chat API endpoints with streaming
- ✅ Bot configuration routes
- ✅ LLM integration (HuggingFace)
- ✅ RAG pipeline with vector retrieval
- ✅ Conversation memory management
- ✅ Chat widget UI with real-time messaging
- ✅ Typing indicators & styles

### Shreya
- ✅ Knowledge base upload API
- ✅ Document ingestion & chunking
- ✅ Embedding generation
- ✅ Database connection & models
- ✅ Suggestion service
- ✅ Admin dashboard for bot management
- ✅ File upload interface
- ✅ Message bubbles with timestamps
- ✅ TypeScript type definitions
- ✅ Chat API client with streaming
- ✅ Ticket creation service

---

*This division ensures both Kanak and Shreya have equal recognition for their contributions to the project.*
