import os
import re
from typing import List, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pgvector.psycopg2 import register_vector

from app.db.database import get_connection
from app.services.llm_service import chat_model


# ==========================================
# 🔹 Embedding Model Setup
# ==========================================

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME
)


# ==========================================
# 🔹 Follow-up Detection (Improved + Safe)
# ==========================================

def is_followup_query(user_query: str) -> bool:
    """
    Detect likely follow-up queries:
    - Contains pronouns
    - Starts with vague connectors
    - Short contextual questions
    """

    text = user_query.lower().strip()

    pronouns = ["it", "they", "them", "this", "that"]
    vague_starts = ("what", "why", "how", "if", "when", "where")

    pronoun_match = any(
        re.search(rf"\b{p}\b", text)
        for p in pronouns
    )

    vague_start = text.startswith(vague_starts)

    short_query = len(text.split()) <= 6

    return pronoun_match or vague_start or short_query


# ==========================================
# 🔹 Rewrite Follow-up → Standalone
# ==========================================

def rewrite_question(chat_history: List, user_query: str) -> str:
    """
    Rewrite follow-up into standalone using last user + assistant message.
    Keeps rewrite minimal and safe.
    """

    if not chat_history:
        return user_query

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
Keep it under 20 words.
Do not explain anything.
"""

    try:
        response = chat_model.invoke([
            SystemMessage(content="You rewrite follow-up support questions clearly and minimally."),
            HumanMessage(content=prompt)
        ])

        rewritten = response.content.strip()

        # Safety guard (avoid hallucinated long rewrite)
        if len(rewritten.split()) > 20:
            return user_query

        print(f"🔁 Contextual Rewritten Query: {rewritten}")
        return rewritten

    except Exception as e:
        print("⚠️ Rewrite failed:", e)
        return user_query


# ==========================================
# 🔹 MAIN RETRIEVER
# ==========================================

def retrieve_chunks(
    user_query: str,
    chat_history: List = None,
    top_k: int = 5,
    domain_threshold: float = 0.75,  # Slightly safer
    distance_margin: float = 0.05
) -> Tuple[List[str], bool]:

    if chat_history is None:
        chat_history = []

    conn = None
    cur = None

    try:
        # ----------------------------------
        # 1️⃣ Rewrite if needed
        # ----------------------------------
        if chat_history and is_followup_query(user_query):
            user_query = rewrite_question(chat_history, user_query)

        # ----------------------------------
        # 2️⃣ Generate embedding
        # ----------------------------------
        query_vector = embeddings.embed_query(user_query)

        if not query_vector:
            print("❌ Embedding generation failed")
            return [], False

        # ----------------------------------
        # 3️⃣ DB Connection
        # ----------------------------------
        conn = get_connection()
        register_vector(conn)
        cur = conn.cursor()

        # ----------------------------------
        # 4️⃣ Vector Search
        # ----------------------------------
        cur.execute(
            """
            SELECT chunk_text, embedding <=> %s::vector AS distance
            FROM kb_chunks
            ORDER BY distance ASC
            LIMIT %s;
            """,
            (query_vector, top_k)
        )

        results = cur.fetchall()

        if not results:
            return [], False

        best_distance = results[0][1]
        print(f"📏 Best Match Distance: {best_distance:.4f}")

        # ----------------------------------
        # 5️⃣ Smart Domain Guard
        # ----------------------------------

        # Allow slightly relaxed threshold for short contextual queries
        if len(user_query.split()) <= 8 and best_distance < 0.9:
            domain_override = True
        else:
            domain_override = False

        if best_distance > domain_threshold and not domain_override:
            print("⚠️ Query outside knowledge base domain")
            return [], False

        # ----------------------------------
        # 6️⃣ Smart Distance Filtering
        # ----------------------------------

        filtered_chunks = [
            row[0]
            for row in results
            if row[1] <= best_distance + distance_margin
        ]

        if not filtered_chunks:
            filtered_chunks = [results[0][0]]

        return filtered_chunks[:3], True

    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        return [], False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()