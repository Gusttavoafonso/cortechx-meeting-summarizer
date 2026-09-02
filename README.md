# CortechX Meeting Summarizer

## Backend (Windows)

Com o Python 3.14+ instalado, execute no PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
fastapi dev app/main.py
```
Para rodar os testes execute no Powershell:

```powershell
python -m pytest
```

A API ficará disponível em `http://127.0.0.1:8000`. Verifique o status em
`http://127.0.0.1:8000/health`.

## Backend (Linux)

Com o Python 3.14+ instalado, execute no terminal:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
fastapi dev app/main.py
```
Para rodar os testes execute no terminal:

```bash
python -m pytest
```

A API ficará disponível em `http://127.0.0.1:8000`. Verifique o status em
`http://127.0.0.1:8000/health`.

 ## Organização do backend

```text
backend/
│
├── app/
│   ├── main.py             # Criação da aplicação FastAPI e definição dos endpoints
│   │
│   ├── api/
│   │
│   ├── core/
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   └── services/
│
├── tests/
│     ├── conftest.py       # Configurações e fixtures compartilhadas dos testes
|     └── test_health.py    # Testes do health check e da documentação automática
|
├── .env.example
├── .gitignore
├── pyproject.toml          # Configuração do projeto, dependências e ferramentas de teste
└── README.md
```