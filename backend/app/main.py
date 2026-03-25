from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import jwt

from app.routes import chat, kb_upload, bot, email

SECRET_KEY = "k3J9@xP!92kLm#Q7zA1$D5"
ALGORITHM = "HS256"

app = FastAPI(title="Highwire Bot Backend")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173", 
    "https://mps.com",
    "https://support.mps.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",
    

]

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin" and form_data.password == "highwire123":
        expire = datetime.utcnow() + timedelta(minutes=60)
        payload = {
            "sub": form_data.username,   # ✅ FIXED
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )

# ✅ Secure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Suggestions"]
)

@app.middleware("http")
async def verify_origin(request: Request, call_next):
    origin = request.headers.get("origin")

    print("Origin received:", origin)  # 🔍 debug

    # Normalize origin (remove trailing slash)
    if origin:
        origin = origin.rstrip("/")

   
    if origin and origin != "null" and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Unauthorized domain")

    return await call_next(request)
# Routes
app.include_router(chat.router, prefix="/api")
app.include_router(kb_upload.router, prefix="/api")
app.include_router(bot.router)
app.include_router(email.router, prefix="/api")  # ✅ ADDED

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/static", StaticFiles(directory="app/static"), name="static")