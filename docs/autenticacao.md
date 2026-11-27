# Autenticação e posse das reuniões

Este documento descreve como o backend identifica o usuário e como cada reunião
é vinculada ao seu dono.

- A **identidade** (model `User`, cadastro, login e sessão) veio da issue
  [#39](https://github.com/Gusttavoafonso/cortechx-meeting-summarizer/issues/39).
- A **posse e a autorização das reuniões** vieram da issue
  [#40](https://github.com/Gusttavoafonso/cortechx-meeting-summarizer/issues/40)
  e são o assunto principal daqui para baixo.

---

## 1. Como o usuário é identificado

`app/api/deps.py::get_current_user` resolve a sessão em duas etapas:

1. lê o cookie `HttpOnly` cujo nome vem de `settings.session_cookie_name`
   (padrão `session_token`);
2. se o cookie não existir, aceita o cabeçalho `Authorization: Bearer <token>`,
   usado pelo Swagger e por clientes de API.

O token é um JWT assinado (`app/services/auth_service.py`) cujo `sub` é o id do
usuário. Sem token, com token inválido, expirado ou apontando para um usuário
inexistente, a resposta é **401**.

---

## 2. Modelo de posse

```
users.id  ◄─────────  meetings.user_id   (FK, indexada, ON DELETE RESTRICT)
```

No ORM:

- `Meeting.owner` → o `User` dono da reunião;
- `User.meetings` → as reuniões daquele usuário.

### Por que `RESTRICT` e não `CASCADE`

Apagar um usuário em cascata removeria as linhas de `meetings`, mas **não** os
arquivos de áudio já gravados em disco (`storage/`), deixando-os órfãos e sem
referência. Com `RESTRICT`, o banco barra a exclusão de um usuário que ainda
tenha reuniões: a remoção precisa passar antes por uma rotina que decida o
destino dos áudios.

No ORM, `User.meetings` usa `passive_deletes="all"` justamente para que o
SQLAlchemy não tente apagar nem desvincular as reuniões por conta própria,
deixando o `RESTRICT` do banco agir.

### Coluna nullable

`meetings.user_id` é **nullable**. A coluna não pode ser `NOT NULL` enquanto
existirem reuniões criadas antes do controle de posse (ver a seção 4).

---

## 3. Comportamento das rotas

Todas as rotas sob `/meetings` — inclusive as de integrações — exigem sessão
válida. Os dois routers declaram a dependência no nível do router:

```python
router = APIRouter(dependencies=[Depends(get_current_user)])
```

| Rota | Método |
|---|---|
| `/meetings` | POST, GET |
| `/meetings/{id}` | GET |
| `/meetings/{id}/audio` | POST, GET |
| `/meetings/{id}/transcribe` | POST |
| `/meetings/{id}/diarize` | POST |
| `/meetings/{id}/transcript` | GET |
| `/meetings/{id}/process` | POST |
| `/meetings/{id}/summary` | POST, GET |
| `/meetings/{id}/retry` | POST |
| `/meetings/{id}/status` | GET |
| `/meetings/{id}/integrations` | GET |
| `/meetings/{id}/integrations/retry` | POST |

`/health` e a documentação (`/docs`, `/openapi.json`) seguem públicas.

### 404, e não 403

Uma reunião que existe mas pertence a outro usuário responde **404**, com a
mesma mensagem de uma reunião inexistente. Um 403 confirmaria que aquele id
existe, o que permitiria enumerar as reuniões alheias. A regra vale para todas
as rotas da tabela acima.

Resumo dos códigos:

| Situação | Resposta |
|---|---|
| Sem token, ou token inválido/expirado | 401 |
| Reunião de outro usuário | 404 |
| Reunião sem dono (anterior à issue #40) | 404 |
| Reunião inexistente | 404 |

---

## 4. Decisão sobre as reuniões anteriores

**Reuniões criadas antes do controle de posse ficam com `user_id` nulo e são
inacessíveis pela API.**

Elas não pertencem a nenhum usuário, então nenhuma consulta com filtro de dono
as alcança: não aparecem em `GET /meetings` e respondem 404 em todas as rotas
por id. As linhas e os áudios continuam no banco e no disco, intactos.

Alternativas descartadas:

- **adotar um dono padrão** — atribuiria a um usuário real reuniões que podem
  não ser dele;
- **apagar as linhas** — perderia dados sem que o time tenha decidido o destino
  deles, e deixaria os áudios órfãos em disco.

Consequências e próximos passos:

- a migration não falha com dados existentes: nada é reescrito, só a FK é
  recriada com `RESTRICT`;
- um `NOT NULL` em `meetings.user_id` depende de uma issue posterior, depois de
  decidido o que fazer com essas reuniões (migrar para um dono, arquivar ou
  remover junto com os áudios).

---

## 5. O worker e o pipeline interno

O worker Celery recebe **apenas o `meeting_id`**. A posse é validada na API,
antes do enfileiramento, então o worker não precisa de usuário e não mudou.

Para deixar essa fronteira explícita, `MeetingRepository` tem dois caminhos:

| Método | Filtra por dono | Quem usa |
|---|---|---|
| `get_by_id(meeting_id, user_id)` | sim | rotas HTTP |
| `list_all(user_id)` | sim | rotas HTTP |
| `get_for_pipeline(meeting_id)` | **não** | worker, entrega de integrações, transições de estado |

`get_for_pipeline` é o único acesso sem filtro de posse e **nenhuma rota HTTP
deve chamá-lo**. `try_claim_processing` continua operando por id, sem usuário.

---

## 6. Testes

As fixtures ficam em `tests/conftest.py`:

| Fixture | O que entrega |
|---|---|
| `client` | cliente **sem** sessão — rotas públicas e testes de 401 |
| `auth_client` | cliente autenticado como `test_user`, com cookie de sessão real |
| `authenticate(user)` | fábrica de clientes autenticados, um por usuário |
| `create_user(...)` / `test_user` | usuários persistidos |

`get_current_user` **não** é substituído por override: os testes exercitam a
autenticação de verdade. Um teste que precise de rota protegida usa
`auth_client`; `test_health` e `test_documentation` seguem com `client`.

`tests/test_meeting_ownership.py` cobre, em matriz sobre todas as rotas:

- a reunião criada recebe o `user_id` do usuário autenticado;
- a listagem traz somente as reuniões do próprio usuário;
- o usuário B recebe 404 em cada rota da reunião de A, e nada do estado de A
  muda;
- sem token e com token inválido, toda rota responde 401;
- reunião sem dono responde 404 e não aparece na listagem;
- o pipeline alcança a reunião sem filtro de posse;
- a FK usa `RESTRICT` e o banco barra a exclusão de um dono com reuniões.

---

## 7. Migrations

A cadeia de revisões é:

```
f24c8e61a930 ─┬─ a62f3d9c1b20 ─ b7d3e5f1a284 ─┐
              └─ d4e5f6a7b8c9 ─ e5f6a7b8c9d0 ─┴─ f6a7b8c9d0e1 ─ a1b2c3d4e5f6
```

`d4e5f6a7b8c9` (usuários) partiu de `f24c8e61a930` em vez da head corrente,
criando duas heads e quebrando `alembic upgrade head` com *"Multiple head
revisions are present"*. Esta issue acrescenta duas revisões:

| Revisão | O que faz |
|---|---|
| `f6a7b8c9d0e1` | só une os dois ramos; não altera o esquema |
| `a1b2c3d4e5f6` | recria a FK `meetings.user_id` com `ON DELETE RESTRICT` |

A separação é proposital: com a junção e a alteração na mesma revisão,
`alembic downgrade -1` a partir da head cairia em *"Ambiguous walk"*, porque o
caminho para trás se divide em dois ramos. Separadas, o downgrade da alteração
funciona normalmente; para ir além do ponto de junção, aponte a revisão
desejada (`alembic downgrade b7d3e5f1a284`).

O teste `test_migrations_tem_uma_unica_head` falha se um novo branch aparecer.

Validado em Postgres 16 nos dois cenários exigidos pela issue:

- **banco vazio** — `alembic upgrade head` sobe toda a cadeia e a FK fica com
  `confdeltype = r` (RESTRICT);
- **banco com dados anteriores** — a partir de `b7d3e5f1a284` com reuniões já
  gravadas, o upgrade conclui, as linhas são preservadas e ficam com `user_id`
  nulo; em seguida, `DELETE FROM users` com reunião vinculada é recusado pelo
  banco.

---

## 8. Pendências conhecidas

- **`JWT_SECRET_KEY` tem valor padrão.** Em `app/core/config.py`,
  `jwt_secret_key` cai em `"dev-secret-key-change-in-production"` quando a
  variável não está definida. Em um ambiente que esqueça de configurá-la,
  qualquer pessoa que conheça esse padrão consegue assinar um token válido para
  qualquer `user_id` — o que anula todo o controle de posse descrito aqui. O
  escopo da issue #39 previa `SecretStr` **sem padrão**, falhando na
  inicialização se ausente.
- **`meetings.user_id` ainda é nullable**, pelo motivo da seção 4.
- **Compartilhamento de reuniões, perfis/admin e configuração de integrações
  por usuário** estão fora do escopo atual.
