from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.frontend import configure_frontend
from app.api.v1.auth import router as auth_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.meetings import router as meetings_router
from app.services.meeting_service import InvalidMeetingTransitionError

app = FastAPI(
    title="CortechX Meeting Summarizer",
    description="API para transcrição e sumarização de reuniões.",
    version="0.1.0",
)

configure_frontend(app)


@app.exception_handler(InvalidMeetingTransitionError)
def invalid_transition_handler(request: Request, exc: InvalidMeetingTransitionError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(meetings_router, prefix="/meetings", tags=["Meetings"])
app.include_router(integrations_router, prefix="/meetings", tags=["Integrations"])
