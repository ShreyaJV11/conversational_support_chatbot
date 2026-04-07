import os
import json
import hashlib
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from app.services.llm_service import detect_category
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language 
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
# UTILS & CLEANERS (🔥 NEW: FAANG-LEVEL PREPROCESSING)
# ==========================================================

def generate_hash(text: str) -> str:
    """Generates a SHA-256 hash for duplicate detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def create_embeddings(model_name: str):
    """Factory for embedding models."""
    return HuggingFaceEmbeddings(model_name=model_name)

def extract_text_from_jira_adf(data) -> str:
    """Recursively pulls plain text from Jira's nested ADF JSON."""
    text = ""
    if isinstance(data, dict):
        if data.get("type") == "text" and "text" in data:
            text += data["text"] + " "
        for key, value in data.items():
            text += extract_text_from_jira_adf(value)
    elif isinstance(data, list):
        for item in data:
            text += extract_text_from_jira_adf(item)
    return text

def clean_enterprise_data(raw_text: str, source_system: str, file_ext: str) -> str:
    """
    Intelligently cleans HTML/JSON based on the source system.
    Leaves code and markdown completely untouched.
    """
    # 1. DO NOT TOUCH CODE OR MARKDOWN (GitHub)
    code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.go', '.md'}
    if source_system == "github" or file_ext in code_extensions:
        return raw_text

    # 2. CLEAN JIRA (ADF JSON or HTML)
    if source_system == "jira":
        try:
            # If it's a JSON string, extract the text recursively
            parsed_json = json.loads(raw_text)
            return extract_text_from_jira_adf(parsed_json).strip()
        except json.JSONDecodeError:
            # If it's just HTML rich text, strip it
            pass 

    # 3. CLEAN CONFLUENCE / SALESFORCE / JIRA FALLBACK (HTML)
    if source_system in ["confluence", "salesforce", "jira"]:
        try:
            soup = BeautifulSoup(raw_text, "html.parser")
            # Using separator=" " ensures words don't mash together when tags vanish
            clean_text = soup.get_text(separator=" ").strip()
            # Remove excessive newlines/spaces
            import re
            return re.sub(r'\s+', ' ', clean_text)
        except Exception as e:
            print(f"HTML cleaning failed: {e}")
            return raw_text

    # 4. DEFAULT
    return raw_text.strip()


# ==========================================================
# MAIN INGEST FUNCTION (ENTERPRISE UPGRADED)
# ==========================================================

def ingest_file(
    file_path: str,
    bot_id: int,
    source_system: str = "local", 
    source_url: str = "",         
    is_verified: bool = False,    
    ingest_config: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Finalized ingestion logic that supports:
    1. Source-Aware Cleaning (HTML/JSON stripping)
    2. AST-Aware Code Chunking (Python, JS, Java, etc.)
    3. Enterprise Metadata (Source System & URL)
    4. Duplicate Prevention (Hash-based)
    """

    config = {**DEFAULT_INGEST_CONFIG, **(ingest_config or {})}

    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1].lower() 

    # ------------------------------------------------------
    # 1️⃣ Load File Content & CLEAN IT
    # ------------------------------------------------------
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()

    raw_text = "\n".join([doc.page_content for doc in documents])
    
    # 🔥 CRITICAL UPGRADE: Clean the text BEFORE hashing and chunking
    full_text = clean_enterprise_data(raw_text, source_system, file_extension)
    
    # Update the document so the splitter uses the clean text
    documents[0].page_content = full_text

    file_hash = generate_hash(full_text)

    # ------------------------------------------------------
    # 2️⃣ Select Splitter & Detect Category (AST vs Standard)
    # ------------------------------------------------------
    # 🚀 Language mapping for Logic-Aware AST Chunking
    language_map = {
        '.py': Language.PYTHON,
        '.js': Language.JS,
        '.ts': Language.TS,
        '.java': Language.JAVA,
        '.cpp': Language.CPP,
        '.go': Language.GO
    }

    if file_extension in language_map:
        # CODE FILE: Use AST Splitter to keep functions/classes together
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language_map[file_extension],
            chunk_size=800,  # Larger for code snippets
            chunk_overlap=50
        )
        file_category = "codebase" 
    else:
        # TEXT FILE: Use Standard Recursive Splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config["chunk_size"],
            chunk_overlap=config["chunk_overlap"]
        )
        # Classify document type using your detect_category utility
        file_category = detect_category(full_text[:500]) 

    chunks = splitter.split_documents(documents)

    # ------------------------------------------------------
    # 3️⃣ Create Embedding Model 
    # ------------------------------------------------------
    embeddings = create_embeddings(config["embedding_model"])

    # ------------------------------------------------------
    # 4️⃣ DB Connection & Setup
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
        # 5️⃣ Prevent Duplicate File Ingestion
        # --------------------------------------------------
        cur.execute(
            f"SELECT id FROM {kb_files_table} WHERE file_hash = %s AND bot_id = %s;",
            (file_hash, bot_id)
        )

        if cur.fetchone():
            return {
                "file_name": file_name,
                "message": "File already ingested - skipping duplicates.",
                "chunks_inserted": 0,
                "chunks_skipped": 0,
                "category": file_category
            }

        # --------------------------------------------------
        # 6️⃣ Insert Master File Record
        # --------------------------------------------------
        cur.execute(
            f"INSERT INTO {kb_files_table} (file_name, file_hash, bot_id) VALUES (%s, %s, %s) RETURNING id;",
            (file_name, file_hash, bot_id)
        )

        kb_file_id = cur.fetchone()[0]

        # --------------------------------------------------
        # 7️⃣ Process & Insert Individual Chunks
        # --------------------------------------------------
        for chunk in chunks:
            chunk_text = chunk.page_content.strip()

            if not chunk_text:
                continue

            chunk_hash = generate_hash(chunk_text)

            # Check if this exact chunk text already exists for this bot
            cur.execute(
                f"SELECT id FROM {kb_chunks_table} WHERE chunk_hash = %s AND bot_id = %s;",
                (chunk_hash, bot_id)
            )

            if cur.fetchone():
                skipped_chunks += 1
                continue

            # Generate Vector Embedding
            vector = embeddings.embed_query(chunk_text)

            # 🚀 Insert with FULL Metadata for Source Attribution & Routing
            cur.execute(
                f"""
                INSERT INTO {kb_chunks_table}
                (chunk_text, chunk_hash, embedding, kb_file_id, bot_id, category, source_system, source_url, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    chunk_text, 
                    chunk_hash, 
                    vector, 
                    kb_file_id, 
                    bot_id, 
                    file_category, 
                    source_system, 
                    source_url, 
                    is_verified
                )
            )

            inserted_chunks += 1

        conn.commit()

        return {
            "file_name": file_name,
            "chunks_inserted": inserted_chunks,
            "chunks_skipped": skipped_chunks,
            "category": file_category,
            "status": "Success"
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()