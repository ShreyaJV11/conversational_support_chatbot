import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
import jwt

from app.routes import chat, kb_upload, bot, email
from app.services.email_processor import process_emails

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# SECURITY CONFIGURATION (Load from .env in production)
# ---------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "k3J9@xP!92kLm#Q7zA1$D5")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "highwire123")
ALGORITHM = "HS256"

app = FastAPI(title="Highwire Bot Backend")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",
    "https://mps.com",
    "https://support.mps.com",
]

# ---------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------
# Built-in CORS is highly secure and handles origin checking natively.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Suggestions"]
)

# ---------------------------------------------------------
# BACKGROUND POLLING LOOP (Auto-checks emails)
# ---------------------------------------------------------
@app.on_event("startup")
async def start_background_polling():
    """Starts automatically when the FastAPI server boots up."""
    
    async def poll_inbox():
        logger.info("Background email polling started. Checking every 2 minutes...")
        while True:
            # Wait for 120 seconds (2 minutes)
            await asyncio.sleep(120) 
            
            try:
                logger.info("Running automatic background email check...")
                # asyncio.to_thread runs your script safely without freezing the web server
                await asyncio.to_thread(process_emails)
            except Exception as e:
                logger.error(f"Error during automatic email check: {e}")

    # Fire and forget the background task
    asyncio.create_task(poll_inbox())

# ---------------------------------------------------------
# AUTHENTICATION ROUTE
# ---------------------------------------------------------
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USERNAME and form_data.password == ADMIN_PASSWORD:
        # Fixed deprecation warning by using timezone-aware UTC
        expire = datetime.now(timezone.utc) + timedelta(minutes=60)
        payload = {
            "sub": form_data.username,
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )

# ---------------------------------------------------------
# ROUTERS & STATIC FILES
# ---------------------------------------------------------
app.include_router(chat.router, prefix="/api")
app.include_router(kb_upload.router, prefix="/api")
app.include_router(bot.router)
app.include_router(email.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/static", StaticFiles(directory="app/static"), name="static")