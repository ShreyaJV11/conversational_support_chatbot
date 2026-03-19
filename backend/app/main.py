from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import jwt

# Routes import
from app.routes import chat, kb_upload, bot

# Yeh values auth_service.py se match honi chahiye
SECRET_KEY = "k3J9@xP!92kLm#Q7zA1$D5"
ALGORITHM = "HS256"

app = FastAPI(title="Highwire Bot Backend")

# 1. THE TOKEN ENDPOINT (Swagger isi ko call karta hai)
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Dummy login for HighwirePress testing
    if form_data.username == "admin" and form_data.password == "highwire123":
        expire = datetime.utcnow() + timedelta(minutes=60)
        # 'sub' key zaroori hai kyunki verify_jwt_token isi ko read karta hai
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

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/static", StaticFiles(directory="app/static"), name="static")