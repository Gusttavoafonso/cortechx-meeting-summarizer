# Zumo Desktop (Tauri)

App desktop do CortechX Zumo: detecta reuniões abertas (Google Meet, Zoom,
Microsoft Teams, Discord) e mostra um aviso para iniciar a gravação com um
clique.

## Pré-requisito: backend rodando localmente

Este é um projeto acadêmico e ainda não existe um backend hospedado. O app
sempre fala com `http://localhost:8001` (mesma `VITE_API_URL` usada em
desenvolvimento). **Antes de abrir o Zumo, rode o backend Python
localmente** (veja o README na raiz do repositório). Sem o backend rodando,
o app abre normalmente, mas criar/gravar reuniões vai falhar.

## Como baixar e instalar

1. Acesse [Releases](https://github.com/Gusttavoafonso/cortechx-meeting-summarizer/releases/latest).
2. Baixe o instalador do seu sistema:
   - Windows: `Zumo_<versão>_x64-setup.exe`
   - macOS: `Zumo_<versão>_universal.dmg` (funciona em Mac Intel e Apple Silicon)

### Windows — aviso do SmartScreen

O instalador não é assinado digitalmente (não há certificado de assinatura
de código neste projeto), então o Windows vai mostrar o aviso **"Windows
protegeu seu PC"** ao executar o instalador. Isso é esperado:

1. Clique em **"Mais informações"**.
2. Clique em **"Executar assim mesmo"**.

### macOS — aviso do Gatekeeper

Pelo mesmo motivo (sem conta Apple Developer para assinar/notarizar), o
macOS vai bloquear a primeira abertura do app. Para liberar:

1. Clique com o botão direito no app → **"Abrir"**.
2. Confirme no diálogo que aparece.
3. Se ainda for bloqueado, vá em **Configurações do Sistema → Privacidade e
   Segurança** e libere o app manualmente.

## Como publicar uma nova versão

1. Atualize o campo `"version"` para o mesmo valor em:
   - `desktop/src-tauri/tauri.conf.json`
   - `desktop/package.json`
2. Commit essa mudança.
3. Crie e envie a tag (substitua pela versão escolhida):
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. O workflow **Desktop Release** builda Windows e macOS automaticamente e
   publica os instaladores na Release correspondente à tag.

## Como testar o pipeline de CI sem criar uma release

O workflow também pode ser disparado manualmente pela aba **Actions** do
GitHub (`workflow_dispatch`), sem precisar criar uma tag. Isso é útil para
validar que o build do frontend e do Tauri continuam passando. Sem uma tag
associada ao commit, a etapa de publicação da Release pode falhar ao nomear
a release — use esse disparo manual para validar só os passos de build, não
o fluxo completo de publicação.
