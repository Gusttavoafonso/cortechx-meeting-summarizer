from fastapi import FastAPI

from app.api.api import router as summarization_router

app = FastAPI(
    title="CortechX Meeting Summarizer",
    description="API para transcrição e sumarização de reuniões.",
    version="0.1.0",
)

app.include_router(summarization_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
