# Integrações

O módulo recebe um `MeetingIntegrationPayload` e o encaminha para um provider.
O pipeline de processamento não conhece plataformas externas.

## Criar um provider

1. Crie `app/integrations/providers/<nome>.py`.
2. Herde de `IntegrationProvider`.
3. Registre a classe com `@register_provider("<nome>")`.
4. Implemente `send(payload) -> IntegrationResult`.
5. Importe a classe em `app/integrations/providers/__init__.py` para executar o registro.

```python
from app.integrations.base import IntegrationProvider
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload


@register_provider("example")
class ExampleProvider(IntegrationProvider):
    name = "example"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        try:
            # Envie o payload para a plataforma externa.
            return IntegrationResult(provider=self.name, success=True)
        except Exception:
            return IntegrationResult(
                provider=self.name,
                success=False,
                error="Não foi possível enviar a reunião para o Example.",
            )
```

## Configuração

`IntegrationService` combina as fontes nesta ordem, da menor para a maior prioridade:

1. `IntegrationConfiguration.configuration`, específica da reunião e do provider.
2. Argumentos passados diretamente a `send()`.

Uma configuração com `enabled=False` impede a execução daquele provider para a
reunião. Nunca inclua segredos em `IntegrationResult.error` ou `metadata`.

## Uso

```python
service = IntegrationService(
    configuration_resolver=ProviderConfigurationResolver(db=session),
)

result = service.send_persisted_meeting("teste", meeting)
```

## Obsidian

O `ObsidianProvider` grava o Markdown produzido por `ObsidianFormatter` em
`OBSIDIAN_VAULT_PATH`/`OBSIDIAN_NOTES_FOLDER`. Configure `OBSIDIAN_ENABLED=true`
para incluir o provider na entrega automática e no reenvio manual. No Docker,
monte o vault em `/vault` nos serviços `backend` e `worker` usando
`docker-compose.obsidian.yml` junto com o Compose principal; defina
`OBSIDIAN_VAULT_HOST_PATH` para uma pasta existente no host.

O nome segue `AAAA-MM-DD - Título (meeting_id).md`; títulos são sanitizados e
limitados para manter o arquivo dentro da pasta de notas. Sem data, o prefixo é
`sem-data`. O reenvio atualiza a nota da mesma reunião por escrita atômica.
Vaults individuais, sincronização bidirecional e acesso por API não são
suportados: o vault precisa estar acessível ao backend e ao worker.
