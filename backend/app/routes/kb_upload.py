from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.ingestion_service import ingest_file
from app.services.bot_service import get_bot_config
import shutil
import os
from datetime import datetime
from typing import Optional

# Router prefix set once for admin tasks
router = APIRouter(prefix="/admin")

BASE_UPLOAD_DIR = "uploads"
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)

# 🚀 UPGRADE: Support for codebase and documentation file types
ALLOWED_EXTENSIONS = {".txt", ".py", ".js", ".ts", ".java", ".cpp", ".md"}

# ==========================================================
# LIST KB FILES (Bot Scoped)
# ==========================================================

@router.get("/kb-files/{bot_id}")
def list_kb_files(bot_id: int):
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    files_data = []

    if os.path.exists(bot_upload_dir):
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
# UPLOAD KNOWLEDGE BASE FILE (Enterprise Upgraded)
# ==========================================================

@router.post("/upload-kb")
async def upload_kb(
    bot_id: int = Query(...),
    file: UploadFile = File(...),
    # 🚀 UPGRADE: Parameters to support Source Attribution and Routing
    source_system: str = Query("manual_upload", description="e.g., github, confluence, jira"),
    source_url: str = Query("", description="The direct link for citations"),
    is_verified: bool = Query(True, description="Mark as official company documentation")
):

    bot_config = get_bot_config(str(bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    # 🚀 UPGRADE: Validate against the expanded allowed list
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not supported. Allowed: {list(ALLOWED_EXTENSIONS)}"
        )

    contents = await file.read()

    # Max 5MB check
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large (max 5MB)"
        )

    await file.seek(0)

    # Scoped upload directory per bot
    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    file_path = os.path.join(bot_upload_dir, file.filename)

    # Save file locally
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 🚀 UPGRADE: Passing metadata into the ingestion service
    # This ensures the DB stores the correct 'category' and 'source_url'
    result = ingest_file(
        file_path=file_path,
        bot_id=bot_id,
        source_system=source_system,
        source_url=source_url,
        is_verified=is_verified,
        ingest_config=bot_config.get("ingest_config", {})
    )

    return {
        "message": "File processed and indexed",
        "file_name": result.get("file_name"),
        "category": result.get("category"),  # Will show 'codebase' or 'support'
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }