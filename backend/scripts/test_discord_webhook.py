from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

from app.core.config import settings
from app.integrations.service import IntegrationService
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload


def build_sample_payload() -> MeetingIntegrationPayload:
    return MeetingIntegrationPayload(
        meeting_id=1,
        title="Reunião de Demonstração - CortechX Summarizer",
        summary=(
            "Esta é uma mensagem de teste da integração com Discord realizada pelo "
            "CortechX Meeting Summarizer. A arquitetura de integração conecta o "
            "resultado processado pelo pipeline diretamente ao canal de notificações."
        ),
        objective="Validar o funcionamento do DiscordProvider em ambiente real.",
        key_points=[
            "Integração baseada em Webhook do Discord implementada com sucesso.",
            "Formatação com Markdown legível em desktop e mobile.",
            "Suporte a divisão automática caso a mensagem exceda 2.000 caracteres.",
            "Tratamento automático de rate limiting (HTTP 429) e retentativas.",
        ],
        decisions=[
            "Utilizar mensagens Markdown padrão para máxima compatibilidade.",
            "Isolar completamente erros de rede sem afetar o fluxo da aplicação.",
        ],
        tasks=[
            TaskIntegrationPayload(
                description="Validar recebimento da mensagem no canal do Discord",
                responsible="Sergio Caua",
                deadline=date.today(),
            ),
            TaskIntegrationPayload(
                description="Revisar logs e critérios de aceitação da Issue #30",
                responsible="Equipe CortechX",
                deadline=date.today(),
            ),
        ],
        created_at=datetime.now(timezone.utc),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envia reunião de teste para o Discord via DiscordProvider."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL do Webhook do Discord (padrão: DISCORD_WEBHOOK_URL do .env)",
    )
    args = parser.parse_args()

    webhook_url = args.url or (
        str(settings.discord_webhook_url) if settings.discord_webhook_url else None
    )

    if not webhook_url:
        print("\n❌ Nenhuma URL de webhook foi fornecida ou configurada.")
        print("Você pode fornecer a URL de duas formas:")
        print("  1. Passando o argumento --url:")
        print(
            "     docker compose exec backend python -m "
            "scripts.test_discord_webhook --url 'SUA_URL'"
        )
        print("  2. Configurando DISCORD_WEBHOOK_URL no .env e executando:")
        print(
            "     docker compose exec backend python -m scripts.test_discord_webhook\n"
        )
        sys.exit(1)

    print("\n🚀 Enviando reunião de demonstração para o Discord...")
    payload = build_sample_payload()

    service = IntegrationService()
    result = service.send("discord", payload, webhook_url=webhook_url)

    if result.success:
        chunks_sent = result.metadata.get("chunks_sent", 1)
        total_chunks = result.metadata.get("total_chunks", 1)
        print("✅ Sucesso! Mensagem enviada com sucesso para o canal do Discord.")
        print(f"   Provider: {result.provider}")
        print(f"   Mensagens enviadas: {chunks_sent}/{total_chunks}")
        print(f"   Data de execução: {result.executed_at}\n")
    else:
        print(f"❌ Falha no envio: {result.error}")
        print(f"   Detalhes (metadata): {result.metadata}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
