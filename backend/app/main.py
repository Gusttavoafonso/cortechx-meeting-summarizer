from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.partial_sessions import router as partial_sessions_router
from app.api.v1.settings import router as settings_router
from app.api.v1.system import router as system_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.services.meeting_service import InvalidMeetingTransitionError

app = FastAPI(
    title="CortechX Meeting Summarizer",
    description="API para transcrição e sumarização de reuniões.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.exception_handler(InvalidMeetingTransitionError)
def invalid_transition_handler(request: Request, exc: InvalidMeetingTransitionError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
    )


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "CortechX Meeting Summarizer API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(
    partial_sessions_router, prefix="/partial-sessions", tags=["Partial transcription"]
)
app.include_router(meetings_router, prefix="/meetings", tags=["Meetings"])
app.include_router(integrations_router, prefix="/meetings", tags=["Integrations"])
app.include_router(settings_router, prefix="/settings", tags=["Settings"])
app.include_router(system_router, prefix="/system", tags=["System"])
