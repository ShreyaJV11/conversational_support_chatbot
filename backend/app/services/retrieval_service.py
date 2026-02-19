from typing import List, Tuple
from langchain_huggingface import HuggingFaceEmbeddings
from app.db.database import get_connection
from pgvector.psycopg2 import register_vector

embeddings=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def retrieve_chunks(
        user_query:str,
        top_k:int=5,
        relevance_threshold:float=0.8,
        domain_threshold:float=0.8
)-> Tuple[List[str],bool]:
    query_vector=embeddings.embed_query(user_query)
    conn=get_connection()
    register_vector(conn)
    cur=conn.cursor()
    try:
        cur.execute(
            """
            SELECT chunk_text, embedding <=> %s::vector AS distance
            FROM kb_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_vector, query_vector,top_k)
        )
        results = cur.fetchall()
        print("\n--- DEBUG: Raw Retrieval Results ---")
        for row in results:
            print("Distance:", row[1])
        if not results:
            return[],False
        best_distance=results[0][1]
        if best_distance > domain_threshold:
            print("Query classified as out-of-domain.")
            return [],False
        relevant_chunks=[
            row[0] for row in results 
            if row[1] < relevance_threshold
        ]
        return relevant_chunks, True
    finally:
        cur.close()
        conn.close()
