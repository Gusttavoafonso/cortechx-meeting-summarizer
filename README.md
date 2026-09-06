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

## Upload de Áudio e Formatos Suportados

O endpoint `POST /meetings/{meeting_id}/audio` recebe gravações de reuniões via `multipart/form-data`.

* **Formatos / Extensões Suportadas:** `.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`.
* **MIME Types Aceitos:** `audio/mpeg`, `audio/wav`, `audio/x-wav`, `audio/mp4`, `audio/x-m4a`, `audio/webm`, `video/mp4`, `video/webm`.
* **Tamanho Máximo Padrão:** `250 MB` (configurável via variável de ambiente `MAX_AUDIO_SIZE_MB`).
* **Validações:** Rejeição imediata de arquivos vazios (0 bytes), arquivos com formatos não suportados e identificadores de reunião inexistentes ou inválidos.

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