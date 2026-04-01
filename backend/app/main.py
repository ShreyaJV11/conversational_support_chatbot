from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import jwt

# Routes import
from app.routes import chat, kb_upload, bot
from app.routes.graph import router as graph_router
from app.services.graph_service import process_emails
SECRET_KEY = "k3J9@xP!92kLm#Q7zA1$D5"
ALGORITHM = "HS256"

app = FastAPI(title="Highwire Bot Backend")
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Dummy login for HighwirePress testing
    if form_data.username == "admin" and form_data.password == "highwire123":
        expire = datetime.utcnow() + timedelta(minutes=60)
        payload = {
            "sub": "admin@highwirepress.com", 
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bhai, username ya password galat hai!"
    )

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat.router, prefix="/api")
app.include_router(kb_upload.router, prefix="/api")
app.include_router(bot.router)
app.include_router(graph_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/static", StaticFiles(directory="app/static"), name="static")

import threading 
import time
from app.services.graph_service import process_emails
def background_worker():
    while True:
        try:
            print("🔄 Checking for new emails ...")
            result=process_emails()
            print(f"✅ Email processing result: {result}")
        except Exception as e:
            print(f"❌ Error in background worker: {e}")
        time.sleep(180)
@app.on_event("startup")
def start_background_worker():
    print("🚀 Starting background email polling processor ...")
    threading.Thread(target=background_worker,daemon=True).start()
