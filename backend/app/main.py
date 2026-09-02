from fastapi import FastAPI

app = FastAPI(
    title="CortechX Meeting Summarizer",
    description="API para transcrição e sumarização de reuniões.",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
