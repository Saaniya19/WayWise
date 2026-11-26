from fastapi import FastAPI
from app.api.planning import router as planningRouter

app = FastAPI(title="WayWise API")

app.include_router(planningRouter)

@app.get("/health")
def health():
    return {"status": "ok"}