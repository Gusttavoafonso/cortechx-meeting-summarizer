"""Entrega desacoplada dos resultados persistidos para plataformas externas."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.schemas.summary import SummaryResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntegrationResult:
    provider: str
    status: str
    message: str | None = None


class IntegrationProvider(Protocol):
    name: str

    def is_configured(self, settings: Settings) -> bool: ...
    def send(self, result: SummaryResponse, settings: Settings) -> None: ...


class DiscordProvider:
    name = "discord"

    def is_configured(self, settings: Settings) -> bool:
        return bool(settings.discord_enabled and settings.discord_webhook_url)

    def send(self, result: SummaryResponse, settings: Settings) -> None:
        summary_text = result.summary or "(sem resumo textual)"
        content = f"**Resumo da reunião #{result.meeting_id}**\n{summary_text}"
        if result.objective:
            content += f"\n**Objetivo:** {result.objective}"
        if result.key_points:
            content += "\n**Principais pontos:**\n" + "\n".join(
                f"• {point}" for point in result.key_points[:10]
            )
        request = Request(
            str(settings.discord_webhook_url),
            data=json.dumps({"content": content[:1900]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Discord respondeu HTTP {response.status}")


class NotionProvider:
    name = "notion"

    def is_configured(self, settings: Settings) -> bool:
        return bool(
            settings.notion_enabled
            and settings.notion_token
            and settings.notion_database_id
        )

    def send(self, result: SummaryResponse, settings: Settings) -> None:
        from notion_client import Client

        title = f"Reunião #{result.meeting_id}"
        children: list[dict[str, Any]] = []
        if result.objective:
            children.append(_notion_paragraph(f"Objetivo: {result.objective}"))
        children.append(_notion_paragraph(result.summary or "Resumo não informado"))
        for heading, items in (
            ("Principais pontos", result.key_points),
            ("Decisões", result.decisions),
        ):
            if items:
                children.append(
                    {
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [
                                {"type": "text", "text": {"content": heading}}
                            ]
                        },
                    }
                )
                children.extend(
                    {
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [
                                {"type": "text", "text": {"content": item[:2000]}}
                            ]
                        },
                    }
                    for item in items[:50]
                )
        Client(auth=settings.notion_token.get_secret_value()).pages.create(
            parent={"database_id": settings.notion_database_id},
            properties={"Name": {"title": [{"text": {"content": title}}]}},
            children=children,
        )


def _notion_paragraph(text: str) -> dict[str, Any]:
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        },
    }


class IntegrationService:
    """Executa todos os providers ativos sem propagar falhas externas."""

    def __init__(
        self,
        providers: list[IntegrationProvider] | None = None,
        settings: Settings | None = None,
    ):
        self.providers = (
            providers
            if providers is not None
            else [DiscordProvider(), NotionProvider()]
        )
        self.settings = settings or get_settings()

    def dispatch(self, result: SummaryResponse) -> list[IntegrationResult]:
        outcomes: list[IntegrationResult] = []
        for provider in self.providers:
            try:
                if not provider.is_configured(self.settings):
                    # Providers desabilitados ou incompletos não são executados.
                    continue
                provider.send(result, self.settings)
                outcomes.append(IntegrationResult(provider.name, "SUCCESS"))
                logger.info(
                    "Integração %s concluída para a reunião %s",
                    provider.name,
                    result.meeting_id,
                )
            except (
                Exception
            ) as exc:  # falha externa não invalida o resultado persistido
                logger.exception(
                    "Falha na integração %s para a reunião %s",
                    provider.name,
                    result.meeting_id,
                )
                outcomes.append(IntegrationResult(provider.name, "FAILED", str(exc)))
        return outcomes
