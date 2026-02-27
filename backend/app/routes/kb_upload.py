from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ingestion_service import ingest_file
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from datetime import datetime

@router.get("/admin/kb-files")
def list_kb_files():
    files_data = []

    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)

        if os.path.isfile(file_path):
            files_data.append({
                "name": filename,
                "uploaded": datetime.fromtimestamp(
                    os.path.getctime(file_path)
                ).isoformat(),
                "status": "Processed"
            })

    return files_data
    
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