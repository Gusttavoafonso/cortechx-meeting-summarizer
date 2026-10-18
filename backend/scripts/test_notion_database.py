from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

from app.core.config import settings
from app.integrations.service import IntegrationService
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


def build_sample_payload(meeting_id: int) -> MeetingIntegrationPayload:
    return MeetingIntegrationPayload(
        meeting_id=meeting_id,
        title="Reunião de Demonstração - Integração Notion",
        summary=(
            "Esta reunião foi publicada pelo NotionProvider do CortechX Meeting "
            "Summarizer. O resultado estruturado do pipeline vira uma linha na "
            "database e um documento legível no corpo da página."
        ),
        objective="Validar o NotionProvider em ambiente real.",
        key_points=[
            "Mapper (NotionFormatter) separado da chamada à API.",
            "Properties tipadas: título, número, data e seleção.",
            "Conteúdo longo dividido sem truncar.",
            "Retry apenas em falha temporária, respeitando Retry-After.",
        ],
        decisions=[
            "Agrupar as tarefas por responsável no corpo da página.",
            "Usar meeting_id como identificador externo da reunião.",
        ],
        tasks=[
            TaskIntegrationPayload(
                description="Conferir a página criada na database",
                responsible="Rhian",
                deadline=date.today(),
            ),
            TaskIntegrationPayload(
                description="Revisar os critérios de aceitação da Issue #31",
                responsible="Rhian",
            ),
            TaskIntegrationPayload(
                description="Validar o agrupamento por responsável",
                responsible="Equipe CortechX",
                deadline="sexta-feira",
            ),
            TaskIntegrationPayload(
                description="Tarefa sem responsável definido",
            ),
        ],
        created_at=datetime.now(timezone.utc),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envia reunião de teste para o Notion via NotionProvider."
    )
    parser.add_argument(
        "--database-id",
        type=str,
        default=None,
        help="Data source da database (padrão: NOTION_DATABASE_ID do .env)",
    )
    parser.add_argument(
        "--meeting-id",
        type=int,
        default=31,
        help="meeting_id usado como identificador externo (padrão: 31)",
    )
    args = parser.parse_args()

    database_id = args.database_id or settings.notion_database_id

    if not settings.notion_token or not database_id:
        print("\n❌ Integração do Notion não configurada.")
        print("Defina no .env do backend:")
        print("  NOTION_API_KEY=ntn_...")
        print("  NOTION_DATABASE_ID=<data source da database>")
        print("E conecte a database à integração em ⋯ -> Conexões.\n")
        sys.exit(1)

    payload = build_sample_payload(args.meeting_id)
    service = IntegrationService()

    print("\n🚀 Publicando reunião de demonstração no Notion...")
    result = service.send("notion", payload, database_id=database_id)

    if not result.success:
        print(f"❌ Falha no envio: {result.error}")
        print(f"   Detalhes (metadata): {result.metadata}\n")
        sys.exit(1)

    print("✅ Sucesso! Página criada na database do Notion.")
    print(f"   Provider: {result.provider}")
    print(f"   meeting_id: {result.metadata.get('meeting_id')}")
    print(f"   URL: {result.metadata.get('url')}")
    print(f"   Data de execução: {result.executed_at}")

    # Reenvio: comprova a idempotência exigida pela issue #31.
    print("\n🔁 Reenviando a mesma reunião para checar a idempotência...")
    again = service.send("notion", payload, database_id=database_id)

    if not again.success:
        print(f"❌ O reenvio falhou: {again.error}\n")
        sys.exit(1)

    same_page = again.metadata.get("page_id") == result.metadata.get("page_id")

    print(f"   already_exists: {again.metadata.get('already_exists')}")
    print(f"   Mesma página: {same_page}")

    if again.metadata.get("already_exists") and same_page:
        print("✅ Nenhuma página duplicada foi criada.\n")
    else:
        print("❌ O reenvio não reaproveitou a página existente.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
