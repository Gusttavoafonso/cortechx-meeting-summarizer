from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

router = APIRouter(tags=["Frontend"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
INDEX_HTML = STATIC_DIR / "index.html"


def configure_frontend(app: FastAPI) -> None:
    """Configura o serviço de arquivos estáticos e a rota principal da UI."""
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)


@router.get("/", include_in_schema=False)
def serve_index():
    if INDEX_HTML.is_file():
        return FileResponse(INDEX_HTML)
    return {"message": "CortechX Meeting Summarizer API"}
