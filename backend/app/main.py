from fastapi import FastAPI

app = FastAPI(title="WayWise API")


@app.get("/health")
def health():
    return {"status": "ok"}