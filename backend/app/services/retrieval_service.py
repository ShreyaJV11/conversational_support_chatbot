import re
from typing import List, Tuple, Dict, Any, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pgvector.psycopg2 import register_vector

from app.db.database import get_connection
from app.services.llm_service import create_chat_model


# ==========================================================
# DEFAULT CONFIG
# ==========================================================

DEFAULT_RETRIEVER_CONFIG = {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "top_k": 5,
    "domain_threshold": 0.75,
    "distance_margin": 0.05,
    "max_chunks": 3,
    "enable_rewrite": True,
    "rewrite_max_words": 20,
    "kb_table": "kb_chunks"
}


# ==========================================================
# EMBEDDING FACTORY
# ==========================================================

def create_embeddings(model_name: str):
    return HuggingFaceEmbeddings(model_name=model_name)


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
        # 1️⃣ Rewrite if enabled
        # ----------------------------------

        if config["enable_rewrite"] and chat_history and is_followup_query(user_query):
            user_query = rewrite_question(chat_history, user_query, config)

        # ----------------------------------
        # 2️⃣ Create Embeddings Dynamically
        # ----------------------------------

        embeddings = create_embeddings(config["embedding_model"])
        query_vector = embeddings.embed_query(user_query)

        if not query_vector:
            return [], False

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

        if not results:
            return [], False

        best_distance = results[0][1]

        # ----------------------------------
        # 5️⃣ Domain Guard
        # ----------------------------------

        domain_threshold = config["domain_threshold"]
        distance_margin = config["distance_margin"]

        if best_distance > domain_threshold:
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

        return filtered_chunks[:max_chunks], True

    except Exception:
        return [], False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()