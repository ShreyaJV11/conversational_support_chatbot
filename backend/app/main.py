from fastapi import FastAPI
from app.routes import chat
from app.routes import health

app = FastAPI(title="Highwire Bot Backend")

app.include_router(chat.router)
app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}
