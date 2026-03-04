from fastapi import APIRouter, UploadFile, File, HTTPException, Query

from app.services.ingestion_service import ingest_file
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

    bot_config = get_bot_config(str(bot_id))

    if not bot_config:
        raise HTTPException(status_code=404, detail="Invalid bot_id")

    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="Only .txt files allowed"
        )

    contents = await file.read()

    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large (max 5MB)"
        )

    await file.seek(0)

    bot_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(bot_id))
    os.makedirs(bot_upload_dir, exist_ok=True)

    file_path = os.path.join(bot_upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = ingest_file(
        file_path=file_path,
        bot_id=str(bot_id),
        ingest_config=bot_config.get("ingest_config", {})
    )

    return {
        "message": "File processed",
        "file_name": result.get("file_name"),
        "chunks_inserted": result.get("chunks_inserted", 0),
        "chunks_skipped": result.get("chunks_skipped", 0)
    }