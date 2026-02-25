import os
from typing import List, Tuple
from langchain_huggingface import HuggingFaceEmbeddings
from pgvector.psycopg2 import register_vector
from app.db.database import get_connection

# Models Setup
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def retrieve_chunks(
    user_query: str,
    chat_history: List = [],  # Can be List[Tuple] or List[dict]
    top_k: int = 5,
    relevance_threshold: float = 0.6, 
    domain_threshold: float = 0.6  # Thoda relax kiya hai taaki documents list miss na ho
) -> Tuple[List[str], bool]:
    
    # 1. Query Refinement (The "It" Fix)
    search_query = user_query
    if chat_history and any(word in user_query.lower() for word in ["it", "manage", "team", "who"]):
        # Pichle context se connect karne ke liye
        # chat_history can be list of tuples [(role, content), ...] or dicts
        last_msg = chat_history[-1]
        if isinstance(last_msg, tuple):
            last_bot_msg = last_msg[1] if len(last_msg) > 1 else ""
        else:
            last_bot_msg = last_msg.get("content", "")
        # Embeddings ko direction dene ke liye "JCore" specifically add kar rahe hain
        search_query = f"who manages JCore? Key staff and roles: {user_query}"

    query_vector = embeddings.embed_query(search_query)
    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    try:
        # 2. SQL Execution - Distance ASC (Chota distance = Zyada similarity)
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
        if not results: return [], False

        best_distance = results[0][1]
        
        # DEBUG: Chunks check karne ke liye
        print(f"--- Best Match Distance: {best_distance:.4f} ---")

        # 3. Domain Check
        if best_distance > domain_threshold:
            return [], False

        # 4. Context Stitching: Multiple chunks ko filter karke join karna
        # Key Staff ki list aksar chunks mein split hoti hai, isliye hum top results uthayenge
        relevant_chunks = [
            row[0] for row in results 
            if row[1] < relevance_threshold
        ]

        # Agar filters bahut tight hain, toh fallback to top result
        if not relevant_chunks:
            relevant_chunks = [results[0][0]]

        return relevant_chunks, True

    except Exception as e:
        print(f"❌ Error: {e}")
        return [], False
    finally:
        cur.close()
        conn.close()