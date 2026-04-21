import os
import hashlib
import shutil
import uuid
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from app.services.llm_service import detect_category
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    UnstructuredPDFLoader,
)
from PIL import Image
import pytesseract
from langchain_core.documents import Document
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

# Base URL for serving uploaded files — change this in production
BASE_UPLOAD_URL = os.getenv("BASE_UPLOAD_URL", "http://localhost:8000")


# ==========================================================
# UTILS
# ==========================================================

def generate_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_embeddings(model_name: str):
    return HuggingFaceEmbeddings(model_name=model_name)


def get_public_url(bot_id: int, filename: str) -> str:
    """Build a public URL for a file stored in uploads/{bot_id}/"""
    return f"{BASE_UPLOAD_URL}/uploads/{bot_id}/{filename}"


# ==========================================================
# HTML PROCESSOR
# Extracts clean text and collects image URLs separately.
# Returns (clean_text: str, image_urls: list[str])
# ==========================================================

def process_html_with_images(file_path: str, bot_id: int):
    bot_upload_dir = f"uploads/{bot_id}"
    os.makedirs(bot_upload_dir, exist_ok=True)

    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    image_urls = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            img.decompose()
            continue

        if src.startswith("http://") or src.startswith("https://"):
            # External image — keep URL as-is
            image_urls.append(src)
            img.decompose()
            continue

        # Local image — copy to uploads and build public URL
        html_dir = os.path.dirname(file_path)
        local_img_path = os.path.join(html_dir, src)

        if os.path.exists(local_img_path):
            safe_name = f"html_img_{uuid.uuid4().hex[:6]}_{os.path.basename(src)}"
            new_img_path = os.path.join(bot_upload_dir, safe_name)
            shutil.copy2(local_img_path, new_img_path)
            public_url = get_public_url(bot_id, safe_name)
            image_urls.append(public_url)

        img.decompose()

    # Clean text only — no HTML tags, no markdown noise
    clean_text = soup.get_text(separator="\n", strip=True)
    return clean_text, image_urls


# ==========================================================
# BUILD CHUNK TEXT WITH IMAGES
# Injects image markdown at the END of chunk text so the LLM
# can include it in its answer.
# Format:  [IMAGE_REF:url]  — a unique marker the LLM is
# instructed to preserve, and the frontend can render.
# ==========================================================

def build_chunk_text_with_images(text: str, image_urls: list) -> str:
    if not image_urls:
        return text
    image_block = "\n".join(
        f"[IMAGE_REF:{url}]" for url in image_urls
    )
    return f"{text}\n\n{image_block}"


# ==========================================================
# MULTI FILE LOADER
# ==========================================================

def get_loader(file_path: str):
    _, ext = os.path.splitext(file_path.lower())

    if ext in [".txt", ".md", ".json", ".yaml", ".yml"]:
        return TextLoader(file_path, encoding="utf-8")

    elif ext == ".pdf":
        try:
            return UnstructuredPDFLoader(file_path, strategy="hi_res")
        except Exception:
            return PyPDFLoader(file_path)

    elif ext == ".docx":
        return Docx2txtLoader(file_path)

    elif ext == ".pptx":
        return UnstructuredPowerPointLoader(file_path)

    elif ext in [".xlsx", ".xls"]:
        return UnstructuredExcelLoader(file_path)

    elif ext == ".csv":
        return CSVLoader(file_path)

    elif ext == ".svg":
        return TextLoader(file_path, encoding="utf-8")

    elif ext in [".png", ".jpg", ".jpeg"]:
        return None  # handled separately

    else:
        try:
            return TextLoader(file_path, encoding="utf-8")
        except Exception:
            raise ValueError(f"Unsupported file type: {ext}")


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
    _, ext = os.path.splitext(file_name.lower())

    # ------------------------------------------------------
    # 1️⃣ LOAD FILE
    # ------------------------------------------------------

    image_urls = []  # collected image URLs for this file

    if ext in [".html", ".htm"]:
        clean_text, image_urls = process_html_with_images(file_path, bot_id)
        documents = [
            Document(
                page_content=clean_text,
                metadata={"source": file_name, "type": "html", "image_urls": image_urls}
            )
        ]

    elif ext in [".png", ".jpg", ".jpeg"]:
        bot_upload_dir = f"uploads/{bot_id}"
        os.makedirs(bot_upload_dir, exist_ok=True)

        safe_name = f"ocr_{uuid.uuid4().hex[:6]}_{file_name}"
        new_img_path = os.path.join(bot_upload_dir, safe_name)
        shutil.copy2(file_path, new_img_path)

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image).strip()

        if not text:
            text = f"[Visual Asset: {file_name} — diagram or logo without readable text]"

        img_url = get_public_url(bot_id, safe_name)
        image_urls = [img_url]

        documents = [
            Document(
                page_content=text,
                metadata={"source": file_name, "type": "image", "image_urls": image_urls}
            )
        ]

    else:
        loader = get_loader(file_path)
        if loader is None:
            raise ValueError(f"No loader available for {ext}")
        documents = loader.load()

        # For PDFs and PPTX, UnstructuredLoader may extract embedded images
        # as separate elements — collect any image paths from metadata if present
        for doc in documents:
            for key in ("image_url", "img_url", "image_path"):
                val = doc.metadata.get(key)
                if val:
                    image_urls.append(val)

    # ------------------------------------------------------
    # 2️⃣ HASH
    # ------------------------------------------------------

    full_text = "\n".join([
        doc.page_content.replace('\x00', '') for doc in documents
    ])
    file_hash = generate_hash(full_text)

    # ------------------------------------------------------
    # 3️⃣ SPLIT
    # ------------------------------------------------------

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"]
    )
    chunks = splitter.split_documents(documents)

    # ------------------------------------------------------
    # 4️⃣ EMBEDDINGS
    # ------------------------------------------------------

    embeddings = create_embeddings(config["embedding_model"])

    # ------------------------------------------------------
    # 5️⃣ CATEGORY
    # ------------------------------------------------------

    file_category = detect_category(full_text[:500])

    # ------------------------------------------------------
    # 6️⃣ DB
    # ------------------------------------------------------

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    inserted_chunks = 0
    skipped_chunks = 0

    try:
        # Duplicate file check
        cur.execute(
            f"""
            SELECT id FROM {config['kb_files_table']}
            WHERE file_hash = %s AND bot_id = %s;
            """,
            (file_hash, bot_id)
        )
        if cur.fetchone():
            return {
                "file_name": file_name,
                "message": "File already ingested",
                "chunks_inserted": 0,
                "chunks_skipped": 0
            }

        # Insert file record
        cur.execute(
            f"""
            INSERT INTO {config['kb_files_table']}
            (file_name, file_hash, bot_id)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (file_name, file_hash, bot_id)
        )
        kb_file_id = cur.fetchone()[0]

        # Insert chunks
        # ✅ KEY FIX: image URLs are attached to the FIRST chunk of the document.
        # All other chunks get the text only.
        # This means the LLM will see [IMAGE_REF:url] markers when the first
        # chunk is retrieved, and the frontend will render them.

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.page_content.replace('\x00', '').strip()
            if not chunk_text:
                continue

            # Attach image refs only to the first chunk of each document
            # so images aren't duplicated across every chunk
            chunk_image_urls = []
            if i == 0 and image_urls:
                chunk_image_urls = image_urls
            elif "image_urls" in chunk.metadata and chunk.metadata["image_urls"]:
                # If splitter preserved metadata, use that
                chunk_image_urls = chunk.metadata["image_urls"]

            final_chunk_text = build_chunk_text_with_images(chunk_text, chunk_image_urls)

            chunk_hash = generate_hash(final_chunk_text)

            # Dedup check
            cur.execute(
                f"""
                SELECT id FROM {config['kb_chunks_table']}
                WHERE chunk_hash = %s AND bot_id = %s;
                """,
                (chunk_hash, bot_id)
            )
            if cur.fetchone():
                skipped_chunks += 1
                continue

            vector = embeddings.embed_query(final_chunk_text)

            cur.execute(
                f"""
                INSERT INTO {config['kb_chunks_table']}
                (chunk_text, chunk_hash, embedding, kb_file_id, bot_id, category)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (final_chunk_text, chunk_hash, vector, kb_file_id, bot_id, file_category)
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