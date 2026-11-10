## Endpoints

| Rota | Descrição | Respostas |
|---|---|---|
| `POST /auth/register` | Recebe nome, e-mail e senha (8 a 128 caracteres). | 201 sem expor a senha nem o hash; 409 e-mail já cadastrado; 422 dados inválidos |
| `POST /auth/login` | Formulário OAuth2 (`username` = e-mail, `password`). | 200 `{access_token, token_type}`; 401 com mensagem única |
| `GET /users/me` | Dados do usuário autenticado. | 200; 401 com `WWW-Authenticate: Bearer` |
| `PATCH /users/me` | Edita o nome. | 200; 401; 422 |
| `PUT /users/me/password` | Troca a senha, exigindo a atual. | 204; 400 senha atual incorreta; 401; 422 |

O token também é aceito pelo cookie de sessão do login Google (`/auth/google`).

## Variáveis de ambiente

(tabela e geração da chave como antes)

**Docker Compose:** o `docker-compose.yml` repassa `JWT_SECRET_KEY` por `environment`, e
esse bloco tem precedência sobre o `env_file`. Por isso a chave precisa estar no `.env`
**da raiz do repositório** (ou exportada no shell). Se estiver só em `backend/.env`, o
container recebe o valor vazio e a aplicação não sobe. Confira com
`docker compose config | grep JWT_SECRET_KEY` (o comando imprime o segredo: não cole a
saída em chats nem em logs).

## Fixtures de teste

| Fixture / helper | Uso |
|---|---|
| `anon_client` | Cliente **sem** token e sem override: autenticação real (testes de 401). |
| `auth_user` | Usuário ativo já persistido (senha: `DEFAULT_PASSWORD`). |
| `auth_client` | Cliente já autenticado como `auth_user`, com Bearer token real. |
| `make_auth_client(**dados)` | Fábrica `(client, usuário)`; chame duas vezes para testes de isolamento. |
| `client` | **Legado**: usa um usuário padrão fixo, sem token. Não misture com as fixtures acima. |
| `create_test_user`, `make_token`, `tamper_token`, `auth_headers` | Helpers em `test_auth_helpers.py`. |

`create_test_user(password=None)` cria uma conta sem senha (como as do login Google), e
`make_token(user, expires_delta=timedelta(seconds=-1))` gera um token expirado. Use
e-mails `@example.com`: `.test` e `.local` são rejeitados.

## Decisões de segurança

- **Senha:** hash Argon2 (`pwdlib`), nunca em texto. De 8 a 128 caracteres, sem `strip`;
  é `SecretStr` nos schemas, então não aparece em `repr` nem em logs.
- **Token:** JWT de acesso, expiração curta, `sub` = id do usuário **como string**,
  algoritmo fixado na decodificação e `exp`/`sub` obrigatórios.
- **Login:** mesma mensagem para e-mail inexistente, senha errada, conta inativa e conta
  sem senha. Para e-mail inexistente ou sem senha, gasta-se um hash falso (tempo igual).
  Senhas acima de 128 caracteres são recusadas sem hashear.
- **Erros 422:** o valor enviado não é devolvido (o padrão do FastAPI ecoaria a senha).
- **E-mail:** normalizado (trim e minúsculas) ao salvar e consultar; único no banco; a
  corrida entre dois cadastros vira 409 pelo índice único.
- **Unificação de Contas (Account Linking):** Previne apropriação de conta (*Account Takeover*) descartando senhas não verificadas cadastradas manualmente quando o proprietário legítimo do e-mail faz login através do Google Identity Services.
- **Limitação conhecida:** o JWT é stateless. Trocar a senha ou desativar a conta não
  invalida tokens já emitidos até expirarem (não há refresh nem revogação nesta issue).