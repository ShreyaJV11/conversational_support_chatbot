from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat

app = FastAPI(title="Highwire Bot Backend")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # 👈 Vite ka default port
    "http://127.0.0.1:5173",
]

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Ye block hona zaroori hai!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Testing ke liye "*" theek hai
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router,prefix="/api")
@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}


@app.get("/health")
def health():
    return {"status": "healthy"}
