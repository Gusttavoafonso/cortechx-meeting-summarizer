**GUIA DE INTEGRAÇÃO \- VALIDAÇÃO INDIVIDUAL DAS API´S**

1. **Discord**  
     
   Objetivo: validar o envio de uma mensagem estática para um canal do Discord utilizando um Webhook.  
   **Biblioteca utilizada**  
   • requests — utilizada para realizar a requisição HTTP POST para o Webhook do Discord.  
   **Passo a passo para gerar o acesso**  
   1\. Criar ou selecionar um canal de teste no servidor do Discord.  
   2\. Acessar Editar canal → Integrações → Webhooks.  
   3\. Criar um novo Webhook e definir o canal de destino.  
   4\. Copiar a URL do Webhook gerada pelo Discord.  
   5\. Armazenar a URL como variável de ambiente, evitando deixá-la diretamente no código.  
   **Implementação**  
   O script discord\_webhook.py recupera a URL através da variável de ambiente DISCORD\_WEBHOOK\_URL e envia uma mensagem por HTTP POST usando requests.  
   Mensagem de teste: “Resumo da reunião gerada”.  
   **Validação**  
   Execução: python discord\_webhook.py  
   Resultado obtido: Status 204 e mensagem enviada com sucesso para o canal de teste do Discord.

2. **Notion**  
   Passo a passo para gerar o acesso:  
* Acessar o [notion.so/my-integrations](http://notion.so/my-integrations) e criar uma nova integração.  
* Copiar o secret gerado \- é o token que será utilizado no código.  
* Na página do notion, vá em configurações na aba de atalhos da tabela/banco de dados, vá até a aba de desenvolvedor(ativar caso não esteja ativa) e copie o ID do database.  
* Quando for preencher o conteúdo da mensagem a ser enviada, se atentar ao nome da coluna título(Aa), ela deve ser igual a que está no notion, senão dará erro.

	

3. **Obsidian**

   Objetivo: validar a criação e o salvamento de um arquivo Markdown (.md) em uma pasta do Vault do Obsidian.

**Biblioteca utilizada**  
• pathlib — biblioteca padrão do Python utilizada para manipulação de caminhos, arquivos e diretórios.

**Passo a passo**  
1\. Instalar o Obsidian e criar um novo Vault.

2\. Definir a pasta do Vault no computador.

3\. Configurar esse caminho no script [obsidian.py](http://obsidian.py).

4\. Executar o script para gerar automaticamente o arquivo [resumo-reuniao.md](http://resumo-reuniao.md).

**Implementação**  
O script obsidian.py utiliza pathlib para definir o caminho do Vault, criar o caminho do arquivo e gravar o conteúdo em Markdown.

Conteúdo gerado: título “Resumo da reunião” e três tópicos de exemplo.

**Validação**  
Execução: python [obsidian.py](http://obsidian.py)

Resultado obtido: arquivo resumo-reuniao.md criado com sucesso dentro do Vault é reconhecido automaticamente pelo Obsidian como uma nova nota.

4. **Bibliotecas necessárias**:  
* requests(import requests)  
* notion\_client(from notion\_client import Client)  
* Path(from pathlib import Path)

	**Opcionais**:

* datetime(from datetime import datetime) \- Pode ser usada para salvar a data e hora no nome do arquivo no caso do obsidian, ficando mais fácil de filtrar.  
* dotenv(from dotenv import load\_dotenv) \- Pode ser usada para manter um arquivo .env com os secrets(do Discord ou Notion), e importá-los sem mantê-los no código principal. Nesse caso, precisa também da biblioteca os(import os) para utilizar o os.getenv().

