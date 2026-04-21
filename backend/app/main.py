import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
import jwt
from dotenv import load_dotenv

load_dotenv()

from app.routes import chat, kb_upload, bot, email
from app.services.email_processor import process_emails

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set in .env file")
    
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "highwire123")
ALGORITHM = "HS256"

app = FastAPI(title="Highwire Bot Backend")


if not os.path.exists("uploads"):
    os.makedirs("uploads")


# Load allowed origins from environment variable
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")

if ALLOWED_ORIGINS_ENV:
   
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
    logger.info(f"CORS: Using origins from environment variable")
else:
   
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
    ]
    logger.warning("CORS: No ALLOWED_ORIGINS in .env, using localhost defaults")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Suggestions"]
)

logger.info(f"CORS enabled for {len(ALLOWED_ORIGINS)} origin(s): {', '.join(ALLOWED_ORIGINS)}")


@app.on_event("startup")
async def start_background_polling():
    # Initialize database connection pool
    logger.info("Initializing database connection pool...")
    from app.db.database import init_connection_pool
    try:
        init_connection_pool()
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.error(f"⚠️ Database pool initialization failed: {e}")
    
   
    logger.info("Warming up embedding model...")
    from app.services.retrieval_service import create_embeddings
    try:
        embeddings = create_embeddings("sentence-transformers/all-MiniLM-L6-v2")
        embeddings.embed_query("test warmup query")
        logger.info("✅ Embedding model warmed up successfully")
    except Exception as e:
        logger.error(f"⚠️ Embedding warmup failed: {e}")
    
    # Start email polling
    async def poll_inbox():
        logger.info("Background email polling started. Checking every 2 minutes...")
        while True:
            await asyncio.sleep(120) 
            try:
                logger.info("Running automatic background email check...")
                await asyncio.to_thread(process_emails)
            except Exception as e:
                logger.error(f"Error during automatic email check: {e}")

    asyncio.create_task(poll_inbox())

@app.on_event("shutdown")
async def shutdown_event():
    # Close all database connections
    logger.info("Closing database connection pool...")
    from app.db.database import close_all_connections
    close_all_connections()
    logger.info("✅ Database connections closed")


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USERNAME and form_data.password == ADMIN_PASSWORD:
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


app.include_router(chat.router, prefix="/api")
app.include_router(kb_upload.router, prefix="/api")
app.include_router(bot.router)
app.include_router(email.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend is running "}

@app.get("/health")
def health():
    return {"status": "healthy"}


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Docker, Kubernetes, and load balancers.
    Checks database and Redis connectivity.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }
    
    # Check database
    try:
        from app.db.database import get_connection, return_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return_connection(conn)
        health_status["checks"]["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = f"error: {str(e)}"
        logger.error(f"Health check - database failed: {e}")
    
    
    try:
        from app.core.redis_config import redis_client
        redis_client.ping()
        health_status["checks"]["redis"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["redis"] = f"error: {str(e)}"
        logger.error(f"Health check - redis failed: {e}")
    
  
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)