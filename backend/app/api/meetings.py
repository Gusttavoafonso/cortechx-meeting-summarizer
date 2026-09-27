"""Alias para app.api.v1.meetings mantendo compatibilidade de importações."""
from app.api.v1.meetings import (
    create_meeting,
    get_meeting,
    get_meeting_job_dispatcher,
    get_meeting_repository,
    get_meeting_service,
    list_meetings,
    process_meeting_async,
    router,
)

__all__ = [
    "create_meeting",
    "get_meeting",
    "get_meeting_job_dispatcher",
    "get_meeting_repository",
    "get_meeting_service",
    "list_meetings",
    "process_meeting_async",
    "router",
]