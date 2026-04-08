# kb_upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from app.services.ingestion_service import ingest_file, ingest_from_url
from app.services.bot_service import get_bot_config
import shutil
import os
from datetime import datetime

# Router prefix only once
router = APIRouter(prefix="/admin")

BASE_UPLOAD_DIR = "uploads"
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)


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
    bot_id: int = Query(...),
    file: UploadFile = File(...)
):

    # Fetch bot config (string is fine here if your service expects it)
    bot_config = get_bot_config(str(bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    # ✅ Allow multiple file types
    allowed = [".txt", ".md", ".html", ".pdf", ".png", ".jpg", ".jpeg", ".pptx"]
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .md, .html, .pdf, .png, .jpg, .jpeg, .pptx files allowed"
        )

    contents = await file.read()

    # ✅ File size check (5MB)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large (max 5MB)"
        )

    await file.seek(0)

    # Create bot-specific directory
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    # Optional: sanitize filename
    file_name = os.path.basename(file.filename)

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

    return {
        "message": "File processed",
        "file_name": result.get("file_name"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }


# ==========================================================
# INGEST FROM URL (web page / Confluence / any HTML page)
# ==========================================================

class IngestURLRequest(BaseModel):
    url: str
    bot_id: int


@router.post("/ingest-url")
async def ingest_url(request: IngestURLRequest):

    bot_config = get_bot_config(str(request.bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    if not request.url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        result = ingest_from_url(
            url=request.url,
            bot_id=request.bot_id,
            ingest_config=bot_config.get("ingest_config", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch or ingest URL: {str(e)}")

    return {
        "message": "URL ingested",
        "source": result.get("source"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }
