# kb_upload.py
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Header
from pydantic import BaseModel, validator, constr
from app.services.ingestion_service import ingest_file, ingest_from_url
from app.services.bot_service import get_bot_config
from app.services.auth_service import verify_admin_token
import shutil
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Router prefix only once
router = APIRouter(prefix="/admin")

BASE_UPLOAD_DIR = "uploads"
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)


# ==========================================================
# PYDANTIC MODELS FOR INPUT VALIDATION
# ==========================================================

class IngestURLRequest(BaseModel):
    url: constr(min_length=10, max_length=2048)
    bot_id: int
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        # Basic URL validation
        if ' ' in v:
            raise ValueError('URL cannot contain spaces')
        return v.strip()
    
    @validator('bot_id')
    def validate_bot_id(cls, v):
        if v < 1:
            raise ValueError('bot_id must be positive')
        return v


# ==========================================================
# LIST KB FILES (Bot Scoped)
# ==========================================================

@router.get("/kb-files/{bot_id}")
def list_kb_files(bot_id: int):

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
# UPLOAD KNOWLEDGE BASE FILE
# ==========================================================

@router.post("/upload-kb")
async def upload_kb(
    bot_id: int = Query(..., gt=0, description="Bot ID must be positive"),
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info(f"File upload request for bot_id={bot_id}, filename={file.filename}")

    # Validate filename
    if not file.filename or len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Sanitize filename
    safe_filename = os.path.basename(file.filename)
    if safe_filename != file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename path")

    # Fetch bot config (string is fine here if your service expects it)
    bot_config = get_bot_config(str(bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    # ✅ Allow multiple file types
    allowed = [".txt", ".md", ".html", ".pdf", ".png", ".jpg", ".jpeg", ".pptx"]
    if not any(safe_filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .md, .html, .pdf, .png, .jpg, .jpeg, .pptx files allowed"
        )

    contents = await file.read()

    # ✅ File size check (20MB)
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large (max 20MB)"
        )
    
    # Check for empty files
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    await file.seek(0)

    # Create bot-specific directory
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    # Optional: sanitize filename
    file_name = safe_filename

    file_path = os.path.join(bot_upload_dir, file_name)

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ✅ FIX: pass bot_id as int (NOT string)
    result = ingest_file(
        file_path=file_path,
        bot_id=bot_id,
        ingest_config=bot_config.get("ingest_config", {})
    )

    logger.info(f"File processed: {result.get('file_name')}, chunks_inserted={result.get('chunks_inserted', 0)}")
    
    return {
        "message": "File processed",
        "file_name": result.get("file_name"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }


# ==========================================================
# INGEST FROM URL (web page / Confluence / any HTML page)
# ==========================================================

@router.post("/ingest-url")
async def ingest_url(request: IngestURLRequest, authorization: str = Header(None)):
    # Verify admin authentication
    verify_admin_token(authorization)
    
    logger.info(f"URL ingestion request for bot_id={request.bot_id}, url={request.url}")

    bot_config = get_bot_config(str(request.bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        result = ingest_from_url(
            url=request.url,
            bot_id=request.bot_id,
            ingest_config=bot_config.get("ingest_config", {})
        )
    except Exception as e:
        logger.error(f"Failed to ingest URL {request.url}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch or ingest URL: {str(e)}")

    logger.info(f"URL ingested: {result.get('source')}, chunks_inserted={result.get('chunks_inserted', 0)}")
    
    return {
        "message": "URL ingested",
        "source": result.get("source"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }
