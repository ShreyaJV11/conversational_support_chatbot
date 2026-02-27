import os
import hashlib
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.psycopg2 import register_vector
from app.db.database import get_connection


# Initialize embedding model once (global)
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ingest_file(file_path: str) -> dict:
    file_name = os.path.basename(file_path)

    # 1️⃣ Load file
    loader = TextLoader(file_path)
    documents = loader.load()

    # 2️⃣ Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = splitter.split_documents(documents)

    # 3️⃣ DB connection
    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    inserted_chunks = 0
    skipped_chunks = 0

    try:
        # 4️⃣ Insert file if not exists & get ID
        cur.execute(
            """
            INSERT INTO kb_files (file_name)
            VALUES (%s)
            ON CONFLICT (file_name)
            DO UPDATE SET file_name = EXCLUDED.file_name
            RETURNING id;
            """,
            (file_name,)
        )

        kb_file_id = cur.fetchone()[0]

        # 5️⃣ Insert chunks
        for chunk in chunks:
            chunk_text = chunk.page_content.strip()

            # Skip empty chunks
            if not chunk_text:
                continue

            # Check duplicate chunk
            cur.execute(
                "SELECT id FROM kb_chunks WHERE chunk_text = %s;",
                (chunk_text,)
            )

            if cur.fetchone():
                skipped_chunks += 1
                continue

            # Generate embedding
            vector = embeddings.embed_query(chunk_text)

            # Insert chunk
            cur.execute(
                """
                INSERT INTO kb_chunks (chunk_text, embedding, kb_file_id)
                VALUES (%s, %s, %s);
                """,
                (chunk_text, vector, kb_file_id)
            )

            inserted_chunks += 1

        conn.commit()

        return {
            "file_name": file_name,
            "chunks_inserted": inserted_chunks,
            "chunks_skipped": skipped_chunks
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()