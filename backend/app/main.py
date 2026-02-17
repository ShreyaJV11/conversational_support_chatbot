from fastapi import FastAPI

app = FastAPI(title="Highwire Bot Backend")

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}
