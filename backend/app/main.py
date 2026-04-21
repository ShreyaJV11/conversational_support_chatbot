import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Sentry for error monitoring (optional)
try:
    import sentry_sdk
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=1.0,
            environment=os.getenv("ENVIRONMENT", "development"),
        )
        logger_temp = logging.getLogger(__name__)
        logger_temp.info("Sentry error monitoring initialized")
except ImportError:
    pass

# Routes import
from app.routes import chat, kb_upload, bot
from app.routes.graph import router as graph_router
from app.services.graph_service import process_emails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load from environment
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "k3J9@xP!92kLm#Q7zA1$D5")
ALGORITHM = "HS256"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS]

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Highwire Bot Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request ID tracking middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response
@app.post("/token")
@limiter.limit("5/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Load admin credentials from environment
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "highwire123")
    
    if form_data.username == admin_username and form_data.password == admin_password:
        expire = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "sub": form_data.username,
            "email": f"{form_data.username}@highwirepress.com",
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"User {form_data.username} logged in successfully")
        return {"access_token": token, "token_type": "bearer"}
    
    logger.warning(f"Failed login attempt for username: {form_data.username}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password"
    )

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Suggestions"]
)
logger.info(f"CORS configured with origins: {ALLOWED_ORIGINS}")

# Routes with API versioning
app.include_router(chat.router, prefix="/api/v1")
app.include_router(kb_upload.router, prefix="/api/v1")
app.include_router(bot.router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")

# Legacy routes (backward compatibility)
app.include_router(chat.router, prefix="/api", tags=["legacy"])
app.include_router(kb_upload.router, prefix="/api", tags=["legacy"])
app.include_router(bot.router, prefix="/api", tags=["legacy"])
app.include_router(graph_router, prefix="/api", tags=["legacy"])

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    """Enhanced health check that verifies all dependencies"""
    checks = {
        "status": "healthy",
        "database": check_database(),
        "redis": check_redis(),
    }
    
    # Overall status is unhealthy if any check fails
    all_healthy = all(
        check.get("status") == "healthy" 
        for check in [checks["database"], checks["redis"]]
    )
    
    checks["status"] = "healthy" if all_healthy else "unhealthy"
    
    return checks


def check_database():
    """Check PostgreSQL connection"""
    try:
        from app.db.database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "healthy", "message": "Database connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}


def check_redis():
    """Check Redis connection"""
    try:
        from app.core.redis_config import redis_client
        redis_client.ping()
        return {"status": "healthy", "message": "Redis connected"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

app.mount("/static", StaticFiles(directory="app/static"), name="static")

import threading 
import time
from app.services.graph_service import process_emails
def background_worker():
    while True:
        try:
            logger.info("Checking for new emails...")
            result = process_emails()
            logger.info(f"Email processing result: {result}")
        except Exception as e:
            logger.error(f"Error in background worker: {e}", exc_info=True)
        time.sleep(180)
@app.on_event("startup")
def start_background_worker():
    logger.info("Starting background email polling processor...")
    threading.Thread(target=background_worker, daemon=True).start()
