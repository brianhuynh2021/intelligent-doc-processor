from fastapi import FastAPI

app = FastAPI(title="Intelligent Document Processor")


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
