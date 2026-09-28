"""Alias para app.api.v1.meetings mantendo compatibilidade com importações de nível superior."""
from app.api.v1.meetings import (
    create_meeting,
    get_meeting,
    get_meeting_repository,
    get_meeting_service,
    list_meetings,
    router,
)

__all__ = [
    "create_meeting",
    "get_meeting",
    "get_meeting_repository",
    "get_meeting_service",
    "list_meetings",
    "router",
]