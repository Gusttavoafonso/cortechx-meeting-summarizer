# Integrações

O módulo recebe um `MeetingIntegrationPayload` e o encaminha para um provider.
O pipeline de processamento não conhece plataformas externas.

## Criar um provider

Um provider registrado pode ser chamado diretamente pelo `IntegrationService`.
Para também incluí-lo no disparo automático após o processamento da reunião,
siga todos os passos abaixo:

1. Crie `app/integrations/providers/<nome>.py`, herde de `IntegrationProvider`,
   registre com `@register_provider("<nome>")` e implemente
   `send(payload) -> IntegrationResult`.
2. Importe a classe em `app/integrations/providers/__init__.py`. Exporte-a em
   `app/integrations/__init__.py` se ela também fizer parte da interface pública
   do pacote.
3. Adicione as configurações necessárias a `Settings` em
   `app/core/config.py`, usando nomes de variáveis de ambiente consistentes.
   Mantenha a integração desativada por padrão e valide entradas que possam
   causar chamadas inválidas ou acesso fora do destino configurado.
4. Acrescente a flag do provider à função `enabled_providers_from_settings()`
   em `app/integrations/delivery.py`. Essa lista controla quais providers são
   selecionados no disparo automático e no reenvio manual. Registrar a classe,
   sozinho, não habilita o disparo automático.
5. Configure as variáveis no `.env.example` e no Docker Compose, quando
   necessário. Para dependências externas, como arquivos ou volumes, documente
   como disponibilizá-las tanto ao `backend` quanto ao `worker`.
6. Documente a configuração neste guia e no README principal se ela mudar o uso
   da aplicação.

O fluxo automático entrega o resultado persistido quando a reunião termina; não
é necessário chamar o provider no pipeline de processamento. O serviço de
entrega cuida do registro de cada envio, evita repetir entregas bem-sucedidas e
isola falhas entre providers. A rota manual de reenvio usa a mesma lista de
providers habilitados.

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

`ProviderConfigurationResolver` combina a configuração específica da reunião
com os argumentos explícitos enviados ao `IntegrationService`. Os argumentos
explícitos prevalecem; na ausência deles, o provider pode usar os valores
globais de `Settings` como padrão.

Uma configuração com `enabled=False` impede o envio para aquela reunião. A flag
global, por sua vez, controla a inclusão do provider nas entregas automáticas.

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
