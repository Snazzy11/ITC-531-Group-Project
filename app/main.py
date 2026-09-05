from fastapi import FastAPI

app = FastAPI(title="Campus Seekr")


@app.get("/")
def read_root():
    return {"message": "Welcome to Campus Seekr"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
