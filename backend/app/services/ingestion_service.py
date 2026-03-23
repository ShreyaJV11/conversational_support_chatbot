import os
import hashlib
from typing import Dict, Any, Optional
from app.services.llm_service import detect_category
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.psycopg2 import register_vector

from app.db.database import get_connection


# ==========================================================
# DEFAULT CONFIG
# ==========================================================

DEFAULT_INGEST_CONFIG = {
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "kb_files_table": "kb_files",
    "kb_chunks_table": "kb_chunks"
}


# ==========================================================
# UTILS
# ==========================================================

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_embeddings(model_name: str):
    return HuggingFaceEmbeddings(model_name=model_name)


# ==========================================================
# MAIN INGEST FUNCTION
# ==========================================================

def ingest_file(
    file_path: str,
    bot_id: int,
    ingest_config: Optional[Dict[str, Any]] = None
) -> dict:

    config = {**DEFAULT_INGEST_CONFIG, **(ingest_config or {})}

    file_name = os.path.basename(file_path)

    # ------------------------------------------------------
    # 1️⃣ Load File
    # ------------------------------------------------------

    loader = TextLoader(file_path)
    documents = loader.load()

    full_text = "\n".join([doc.page_content for doc in documents])
    file_hash = generate_hash(full_text)

    # ------------------------------------------------------
    # 2️⃣ Create Splitter (Configurable)
    # ------------------------------------------------------

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"]
    )

    chunks = splitter.split_documents(documents)

    # ------------------------------------------------------
    # 3️⃣ Create Embedding Model (Configurable)
    # ------------------------------------------------------

    embeddings = create_embeddings(config["embedding_model"])

    # ------------------------------------------------------
    # 4️⃣ Detect Category ONCE per file (not per chunk)
    # ------------------------------------------------------

    file_category = detect_category(full_text[:500])

    # ------------------------------------------------------
    # 5️⃣ DB Connection
    # ------------------------------------------------------

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    inserted_chunks = 0
    skipped_chunks = 0

    kb_files_table = config["kb_files_table"]
    kb_chunks_table = config["kb_chunks_table"]

    try:

        # --------------------------------------------------
        # 6️⃣ Prevent Duplicate File (by hash + bot_id)
        # --------------------------------------------------

        cur.execute(
            f"""
            SELECT id FROM {kb_files_table}
            WHERE file_hash = %s AND bot_id = %s;
            """,
            (file_hash, bot_id)
        )

        existing_file = cur.fetchone()

        if existing_file:
            return {
                "file_name": file_name,
                "message": "File already ingested",
                "chunks_inserted": 0,
                "chunks_skipped": 0
            }

        # --------------------------------------------------
        # 7️⃣ Insert File Record
        # --------------------------------------------------

        cur.execute(
            f"""
            INSERT INTO {kb_files_table}
            (file_name, file_hash, bot_id)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (file_name, file_hash, bot_id)
        )

        kb_file_id = cur.fetchone()[0]

        # --------------------------------------------------
        # 8️⃣ Insert Chunks (reuse file_category for all)
        # --------------------------------------------------

        for chunk in chunks:
            chunk_text = chunk.page_content.strip()

            if not chunk_text:
                continue

            chunk_hash = generate_hash(chunk_text)

            # Duplicate check per bot
            cur.execute(
                f"""
                SELECT id FROM {kb_chunks_table}
                WHERE chunk_hash = %s AND bot_id = %s;
                """,
                (chunk_hash, bot_id)
            )

            if cur.fetchone():
                skipped_chunks += 1
                continue

            vector = embeddings.embed_query(chunk_text)

            cur.execute(
                f"""
                INSERT INTO {kb_chunks_table}
                (chunk_text, chunk_hash, embedding, kb_file_id, bot_id, category)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (chunk_text, chunk_hash, vector, kb_file_id, bot_id, file_category)
            )

            inserted_chunks += 1

        conn.commit()

        return {
            "file_name": file_name,
            "chunks_inserted": inserted_chunks,
            "chunks_skipped": skipped_chunks,
            "category": file_category
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()