import re
from typing import List, Tuple, Dict, Any, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pgvector.psycopg2 import register_vector

from app.db.database import get_connection, return_connection
from app.services.llm_service import create_chat_model

import logging

logger = logging.getLogger(__name__)

# ==========================================================
# DEFAULT CONFIG
# ==========================================================

DEFAULT_RETRIEVER_CONFIG = {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "top_k": 30,
    "domain_threshold": 0.75,  # Increased from 0.60 to be more lenient (higher = more lenient)
    "distance_margin": 0.20,
    "max_chunks": 15,
    "enable_rewrite": True,
    "rewrite_max_words": 20,
    "kb_table": "kb_chunks"
}


# ==========================================================
# EMBEDDING FACTORY WITH CACHING
# ==========================================================

_embedding_cache = {}

def create_embeddings(model_name: str):
    """Create embeddings with caching to avoid cold start issues."""
    if model_name not in _embedding_cache:
        logger.info(f"Loading embedding model: {model_name}")
        _embedding_cache[model_name] = HuggingFaceEmbeddings(model_name=model_name)
        # Warmup: create a dummy embedding to load the model
        _embedding_cache[model_name].embed_query("warmup query")
        logger.info(f"Embedding model loaded and warmed up: {model_name}")
    return _embedding_cache[model_name]


# ==========================================================
# FOLLOW-UP DETECTION
# ==========================================================

def is_followup_query(user_query: str) -> bool:
    text = user_query.lower().strip()

    pronouns = ["it", "they", "them", "this", "that"]
    vague_starts = ("what", "why", "how", "if", "when", "where")

    pronoun_match = any(re.search(rf"\b{p}\b", text) for p in pronouns)
    vague_start = text.startswith(vague_starts)
    short_query = len(text.split()) <= 6

    return pronoun_match or vague_start or short_query


# ==========================================================
# FOLLOW-UP REWRITE (Configurable)
# ==========================================================

def rewrite_question(
    chat_history: List,
    user_query: str,
    bot_config: Dict[str, Any]
) -> str:

    if not chat_history:
        return user_query

    max_words = bot_config.get("rewrite_max_words", 20)

    last_user = None
    last_assistant = None

    for msg in reversed(chat_history):
        role = msg[0] if isinstance(msg, tuple) else msg.get("role")
        content = msg[1] if isinstance(msg, tuple) else msg.get("content")

        if role and role.lower() == "assistant" and not last_assistant:
            last_assistant = content
        elif role and role.lower() == "user" and not last_user:
            last_user = content

        if last_user and last_assistant:
            break

    if not last_user:
        return user_query

    prompt = f"""
Rewrite the follow-up question into a clear standalone support question.

Previous User Question:
{last_user}

Previous Assistant Answer:
{last_assistant}

Follow-up Question:
{user_query}

Return ONLY the rewritten question.
Keep it under {max_words} words.
Do not explain anything.
"""

    try:
        chat_model = create_chat_model(bot_config)

        response = chat_model.invoke([
            SystemMessage(content="You rewrite follow-up support questions clearly and minimally."),
            HumanMessage(content=prompt)
        ])

        rewritten = response.content.strip()

        if len(rewritten.split()) > max_words:
            return user_query

        return rewritten

    except Exception:
        return user_query


# ==========================================================
# MAIN RETRIEVER (Fully Configurable)
# ==========================================================

def retrieve_chunks(
    user_query: str,
    bot_id: int,
    chat_history: Optional[List] = None,
    bot_config: Optional[Dict[str, Any]] = None
) -> Tuple[List[str], bool]:

    config = {**DEFAULT_RETRIEVER_CONFIG, **(bot_config or {})}
    chat_history = chat_history or []

    conn = None
    cur = None

    try:
        # ----------------------------------
        # 0️⃣ Handle empty queries
        # ----------------------------------
        
        if not user_query or not user_query.strip():
            logger.warning("Empty query received, returning no chunks")
            return [], False
        
        # ----------------------------------
        # 1️⃣ Rewrite if enabled
        # ----------------------------------

        original_query = user_query
        if config["enable_rewrite"] and chat_history and is_followup_query(user_query):
            user_query = rewrite_question(chat_history, user_query, config)
            logger.info(f"Query rewritten: '{original_query}' -> '{user_query}'")

        # ----------------------------------
        # 2️⃣ Create Embeddings Dynamically
        # ----------------------------------

        embeddings = create_embeddings(config["embedding_model"])
        query_vector = embeddings.embed_query(user_query)

        if not query_vector:
            logger.error("Failed to create query embedding")
            return [], False

        logger.info(f"Query: '{user_query}' | Vector length: {len(query_vector)}")

        # ----------------------------------
        # 3️⃣ DB Connection
        # ----------------------------------

        conn = get_connection()
        register_vector(conn)
        cur = conn.cursor()

        # ----------------------------------
        # 4️⃣ Vector Search (Bot Scoped)
        # ----------------------------------

        kb_table = config["kb_table"]
        top_k = config["top_k"]

        cur.execute(
            f"""
            SELECT chunk_text, embedding <=> %s::vector AS distance
            FROM {kb_table}
            WHERE bot_id = %s
            ORDER BY distance ASC
            LIMIT %s;
            """,
            (query_vector, bot_id, top_k)
        )

        results = cur.fetchall()
        
        logger.info(f"Retrieved {len(results)} chunks for bot_id={bot_id}")

        if not results:
            logger.warning(f"No chunks found for query: '{user_query}'")
            return [], False

        best_distance = results[0][1]
        logger.info(f"Best distance: {best_distance:.4f}")

        # ----------------------------------
        # 5️⃣ Domain Guard
        # ----------------------------------

        domain_threshold = config["domain_threshold"]
        distance_margin = config["distance_margin"]

        if best_distance > domain_threshold:
            logger.warning(f"Best distance {best_distance:.4f} > threshold {domain_threshold}")
            return [], False

        # ----------------------------------
        # 6️⃣ Smart Filtering
        # ----------------------------------

        filtered_chunks = [
            row[0]
            for row in results
            if row[1] <= best_distance + distance_margin
        ]

        if not filtered_chunks:
            filtered_chunks = [results[0][0]]

        max_chunks = config["max_chunks"]
        
        final_chunks = filtered_chunks[:max_chunks]
        logger.info(f"Returning {len(final_chunks)} chunks (filtered from {len(filtered_chunks)})")

        return final_chunks, True

    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return [], False

    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)