from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat,kb_upload
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Highwire Bot Backend")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Testing ke liye "*" theek hai
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,prefix="/api")
app.include_router(kb_upload.router, prefix="/api")
from app.routes import bot

app.include_router(bot.router)

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}


@app.get("/health")
def health():
    return {"status": "healthy"}
from app.routes import kb_upload

app.mount("/static", StaticFiles(directory="app/static"), name="static")

