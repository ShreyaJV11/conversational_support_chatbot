from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse
import shutil
import os
import re
import requests
import uuid
from datetime import datetime
from pydantic import BaseModel
from bs4 import BeautifulSoup

from app.services.ingestion_service import ingest_file
from app.services.bot_service import get_bot_config

# Router prefix only once
router = APIRouter(prefix="/admin")

BASE_UPLOAD_DIR = "uploads"
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------
# SECURITY CONFIGURATION
# ---------------------------------------------------------
# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

# Maximum URL fetch size: 10MB
MAX_URL_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# 🔥 Define allowed extensions matching your ingest_file configuration
ALLOWED_EXTENSIONS = {
    # Text formats
    ".txt", ".md", ".json", ".yaml", ".yml",
    # Document formats
    ".pdf", ".docx", ".pptx",
    # Spreadsheet formats
    ".xlsx", ".xls", ".csv",
    # Web formats
    ".html", ".htm",
    # Image formats (with OCR)
    ".png", ".jpg", ".jpeg"
}

# Allowed MIME types for additional validation
ALLOWED_MIME_TYPES = {
    "text/plain", "text/markdown", "application/json",
    "text/yaml", "application/x-yaml",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel", "text/csv",
    "text/html",
    "image/png", "image/jpeg", "image/jpg"
}


# ==========================================================
# PYDANTIC MODELS
# ==========================================================

class FetchUrlRequest(BaseModel):
    url: str
    bot_id: int


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    Removes directory separators and keeps only safe characters.
    """
    # Get just the basename (removes any path components)
    filename = os.path.basename(filename)
    
    # Remove any remaining path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Keep only alphanumeric, dots, hyphens, and underscores
    filename = re.sub(r'[^\w\.\-]', '_', filename)
    
    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


# ==========================================================
# LIST KB FILES (Bot Scoped)
# ==========================================================

@router.options("/kb-files/{bot_id}")
def list_kb_files_options(bot_id: int):
    """Handle OPTIONS preflight request for kb-files endpoint."""
    return JSONResponse(content={"message": "OK"}, status_code=200)


@router.get("/kb-files/{bot_id}")
def list_kb_files(bot_id: int):
    """List all knowledge base files for a bot."""
    
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    files_data = []

    for filename in os.listdir(bot_upload_dir):
        file_path = os.path.join(bot_upload_dir, filename)

        if os.path.isfile(file_path):
            files_data.append({
                "name": filename,
                "uploaded": datetime.fromtimestamp(
                    os.path.getctime(file_path)
                ).isoformat(),
                "status": "Processed"
            })

    return files_data


# ==========================================================
# UPLOAD KNOWLEDGE BASE FILE (WITH SECURITY IMPROVEMENTS)
# ==========================================================

@router.options("/upload-kb")
async def upload_kb_options():
    """Handle OPTIONS preflight request for upload-kb endpoint."""
    return JSONResponse(content={"message": "OK"}, status_code=200)


@router.post("/upload-kb")
async def upload_kb(
    bot_id: int = Query(...),
    file: UploadFile = File(...)
):
    """Upload a knowledge base file."""
    
    bot_config = get_bot_config(str(bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    # 1️⃣ SANITIZE FILENAME (prevent path traversal)
    safe_filename = sanitize_filename(file.filename)
    
    if not safe_filename or safe_filename == '_':
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    # 2️⃣ VALIDATE FILE SIZE
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="File is empty"
        )
    
    # Reset file pointer for later use
    await file.seek(0)

    # 3️⃣ Check File Extension securely
    _, ext = os.path.splitext(safe_filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 3️⃣ Check File Size (Max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large (max 5MB)"
        )
    await file.seek(0)  # Reset pointer after reading for size check

    # 4️⃣ Save File Locally with sanitized name
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)
    
    # Use sanitized filename
    file_path = os.path.join(bot_upload_dir, safe_filename)
    
    # Verify the path is still within the upload directory (extra safety)
    real_upload_dir = os.path.realpath(bot_upload_dir)
    real_file_path = os.path.realpath(file_path)
    
    if not real_file_path.startswith(real_upload_dir):
        raise HTTPException(
            status_code=400,
            detail="Invalid file path detected"
        )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 5️⃣ Trigger Multi-Format Ingestion
    try:
        result = ingest_file(
            file_path=file_path,
            bot_id=bot_id, 
            ingest_config=bot_config.get("ingest_config", {})
        )
    except Exception as e:
        # Catch ingestion errors (e.g. corrupt PDF) and return to frontend
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    return {
        "message": "File successfully processed and embedded.",
        "file_name": result.get("file_name"),
        "category": result.get("category", "general"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }



# ==========================================================
# FETCH CONTENT FROM URL
# ==========================================================

@router.options("/fetch-url")
async def fetch_url_options():
    """Handle OPTIONS preflight request for fetch-url endpoint."""
    return JSONResponse(content={"message": "OK"}, status_code=200)


@router.post("/fetch-url")
async def fetch_url(request: FetchUrlRequest):
    """
    Fetch content from a URL and add it to the knowledge base.
    Supports HTML pages, documentation sites, articles, etc.
    """
    
    bot_config = get_bot_config(str(request.bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    # Validate URL
    if not request.url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=400,
            detail="URL must start with http:// or https://"
        )

    try:
        # Fetch content from URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(request.url, headers=headers, timeout=30)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported content type: {content_type}. Only HTML and text pages are supported."
            )

        # Generate unique filename
        url_hash = str(uuid.uuid4().hex[:8])
        safe_filename = f"url_{url_hash}.html"

        # Save content to file
        bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(request.bot_id))
        os.makedirs(bot_upload_dir, exist_ok=True)
        file_path = os.path.join(bot_upload_dir, safe_filename)

        # Save HTML content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)

        # Ingest the file
        result = ingest_file(
            file_path=file_path,
            bot_id=request.bot_id,
            ingest_config=bot_config.get("ingest_config", {})
        )

        return {
            "message": "URL content successfully fetched and indexed.",
            "url": request.url,
            "file_name": safe_filename,
            "category": result.get("category", "general"),
            "chunks_inserted": result.get("chunks_inserted", 0),
            "chunks_skipped": result.get("chunks_skipped", 0)
        }

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=408,
            detail="Request timeout. The URL took too long to respond."
        )
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Connection error. Could not reach the URL."
        )
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"HTTP error: {e.response.status_code} - {e.response.reason}"
        )
    except Exception as e:
        # Clean up file on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch URL: {str(e)}"
        )
