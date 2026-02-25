from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ingestion_service import ingest_file
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/admin/upload-kb")
async def upload_db(
    
    file: UploadFile = File(...)
    ):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files allowed")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = ingest_file(file_path)

    return {
        "message": "File indexed successfully",
        "chunks_created": result["chunks_inserted"],   
        "chunks_skipped": result["chunks_skipped"]
    }