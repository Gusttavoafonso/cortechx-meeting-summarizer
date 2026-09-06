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

## Speech-to-Text (Transcrição de Áudio)

O pipeline de transcrição é acionado via `POST /meetings/{meeting_id}/transcribe` e suporta dois modos de execução:

1. **Modo Local (Padrão / Offline):**
   - Utiliza `faster-whisper` com o modelo `small`.
   - Inclui **Voice Activity Detection (Silero VAD)** nativo (`vad_filter=True`), que fatia o áudio em segmentos naturais de fala e ignora trechos em silêncio.
   - Não requer chaves externas ou conexão com a internet após o download inicial do modelo.

2. **Modo Nuvem (Ultra-Rápido via Groq):**
   - Utiliza a API da Groq com o modelo `whisper-large-v3`, realizando a transcrição em segundos na nuvem com alta acurácia.
   - Ativado automaticamente ao preencher a variável `GROQ_API_KEY` no `.env`.

### Como obter uma Chave Gratuita da Groq:

1. Acesse o portal oficial: [Groq Console](https://console.groq.com/).
2. Crie uma conta gratuita (login rápido com GitHub ou Google).
3. No menu lateral esquerdo, clique em [API Keys](https://console.groq.com/keys).
4. Clique no botão **"Create API Key"**, atribua um nome (ex: `cortechx-dev`) e clique em **Submit**.
5. Copie a chave gerada (iniciada por `gsk_...`).
6. No seu arquivo `.env` (na raiz do projeto), adicione a chave:
   ```env
   GROQ_API_KEY=gsk_sua_chave_aqui
   ```
> **Nota:** Se `GROQ_API_KEY` estiver vazia ou não informada, o sistema alternará automaticamente para o modo local com `faster-whisper`.


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