# Estratégia da integração com o Notion

Referente à issue #31. Descreve a estrutura escolhida no Notion, como configurar
a integração e as decisões de limites, idempotência e retry.

## Separação entre mapper e provider

A integração tem duas peças, seguindo a mesma divisão já usada no Discord:

- `app/integrations/providers/formatters/notion.py` — o `NotionFormatter`
  traduz `MeetingIntegrationPayload` em properties e blocos. Não faz
  requisição nenhuma e é testável isoladamente.
- `app/integrations/providers/notion.py` — o `NotionProvider` cuida só da
  conversa com a API: cliente, busca, criação, paginação de blocos, retry e
  tradução de erros.

O provider recebe o formatter por injeção (`formatter=`), o que permite trocá-lo
em teste sem tocar na chamada HTTP.

## Estrutura no Notion

Uma reunião vira **uma linha** na database, com o conteúdo no **corpo da
página**.

### Properties da database

| Property     | Tipo             | Origem                        |
|--------------|------------------|-------------------------------|
| `Name`       | Título (title)   | `payload.title`               |
| `meeting_id` | Número (number)  | `payload.meeting_id`          |
| `Data`       | Data (date)      | `payload.created_at` (opcional) |
| `Status`     | Seleção (select) | fixo `Pendente` na criação    |

`meeting_id` é o identificador externo que liga o registro à reunião do sistema
e é o que permite reconhecer a reunião depois. `Status` nasce como `Pendente`
porque o payload interno não carrega estado de reunião; a transição para
`Concluída` fica a cargo de um fluxo de atualização, fora do escopo da issue.

### Corpo da página

```text
## Objetivo        (omitido quando ausente)
<objetivo>

## Resumo
<resumo>

## Principais pontos
- <ponto>

## Decisões
- <decisão>

## Tarefas
### <responsável>
- <descrição> — Prazo: <data>
### Sem responsável
- <descrição>
```

As seções opcionais só aparecem quando têm conteúdo — a página nunca mostra
cabeçalho vazio nem `None`.

### Tarefas

As tarefas são agrupadas por responsável, com um `heading_3` por pessoa, como no
exemplo da issue. Tarefas sem responsável caem em um grupo final
`Sem responsável`, em vez de serem descartadas.

O prazo fica **na mesma linha** da tarefa (`descrição — Prazo: data`), e não em
um bullet próprio. Com um bullet separado, um responsável com duas tarefas
tornaria ambíguo a qual delas o prazo pertence. Prazos em `date` são
normalizados para ISO; prazos em texto livre são mantidos como vieram.

## Configuração

```bash
NOTION_API_KEY=ntn_...        # Internal Integration Secret
NOTION_DATABASE_ID=...        # data source da database de reuniões
```

Ambas já constam do `.env.example`. O settings aceita `NOTION_API_KEY` ou
`NOTION_TOKEN` (`AliasChoices`), e o token é um `SecretStr` — nunca é escrito em
log nem devolvido em mensagem de erro.

Passos no Notion:

1. Criar uma integração interna em <https://www.notion.so/my-integrations>.
2. Abrir a database de reuniões e conectá-la à integração
   (`⋯` → **Conexões**). Sem isso a API responde 404, mesmo com token válido.
3. Garantir que a database tenha as quatro properties da tabela acima, com os
   tipos corretos. Property com tipo errado (por exemplo `meeting_id` como
   texto) faz a busca e a criação falharem com `validation_error`.

Com `NOTION_API_KEY` ou `NOTION_DATABASE_ID` vazios, o provider devolve falha
imediata, sem chamar a API.

## Limites da API

| Limite                        | Tratamento |
|-------------------------------|------------|
| 2.000 caracteres por rich_text | `NotionFormatter._chunks` divide o texto |
| 100 blocos por requisição      | `NOTION_BLOCK_LIMIT`; o excedente vai em `blocks.children.append` |
| Rate limit (HTTP 429)          | retry respeitando o header `Retry-After` |

Nada é truncado em silêncio. Textos longos viram vários parágrafos e o título
é dividido em múltiplos itens de `rich_text`, preservando o conteúdo inteiro.

O único limite não tratado em código é o de 100 itens de `rich_text` dentro de
um mesmo bloco, que só seria atingido por um bullet de mais de 200 mil
caracteres. Nesse caso a API recusa a requisição com erro explícito, e não com
perda silenciosa.

## Idempotência

Antes de criar qualquer página, o provider busca na database uma linha com o
mesmo `meeting_id` (`data_sources.query` com filtro numérico). Se encontrar,
devolve sucesso com `already_exists: True` e não cria nada.

Essa busca roda **dentro** do bloco de retry, uma vez por tentativa. É o que
evita o caso em que a criação chega ao Notion mas a resposta se perde por
timeout: a tentativa seguinte encontra a página recém-criada em vez de criar uma
segunda.

### Falha parcial

Uma reunião com mais de 100 blocos precisa de mais de uma requisição. Se a
página for criada e um `append` posterior falhar, o conteúdo fica incompleto.

Ao reencontrar uma página existente, o provider conta os blocos já gravados e
envia apenas os que faltam, devolvendo `blocks_completed: True` quando completou
algo. Uma página íntegra não é reescrita.

A contagem parte do princípio de que o corpo da página é escrito apenas pelo
provider. Se alguém editar a página à mão e remover blocos, um reenvio
recompleta a partir de um índice que não corresponde ao que foi removido. É uma
limitação aceita: a database é destino de publicação, não de edição manual.

## Retry

Aplicado apenas a falhas temporárias:

- **Repete**: timeout, erro de rede (`httpx.TransportError`) e HTTP 409, 429,
  500, 502, 503 e 504.
- **Não repete**: HTTP 400, 401, 403 e 404. São erros de configuração ou de
  dados; repetir não muda o resultado e só consome requisição.

O intervalo é exponencial (1s, 2s, 4s, teto de 8s). Em 429, o `Retry-After`
enviado pelo Notion tem prioridade sobre o backoff.

## Erros tratados

| Situação | Mensagem devolvida |
|----------|--------------------|
| 400 | dados inválidos enviados ao Notion |
| 401 | token inválido ou sem autenticação |
| 403 | integração sem permissão na database |
| 404 | database não encontrada ou não compartilhada |
| 429 | limite de requisições excedido |
| timeout | tempo limite excedido |
| rede / resposta inválida | mensagem genérica |

Nenhuma delas repassa o conteúdo da exceção original, que poderia conter o
token. O log registra apenas o tipo da exceção.

Uma falha no Notion não altera nem apaga o resultado já persistido da reunião: o
provider sempre devolve um `IntegrationResult` e o `IntegrationService` isola o
que escapar disso.

## Validação manual

Executada contra a database de testes, pelo `IntegrationService`:

- criação da página com as quatro properties e todas as seções;
- tarefas agrupadas por responsável, incluindo o grupo `Sem responsável`;
- prazo em texto livre preservado;
- reenvio do mesmo `meeting_id` devolvendo `already_exists: True` e a mesma
  página, sem duplicar;
- página completa não reescrita no reenvio (`blocks_completed: False`).
