# Decisão: processamento assíncrono com Celery e Redis

## Contexto

O pipeline de uma reunião inclui Speech-to-Text, diarização, chunking e
processamento por LLM. Essas etapas podem levar minutos e
não é recomendado manter a requisição HTTP aberta até a conclusão.

## Decisão

Foi escolhido o **Celery** para executar o processamento de reuniões em
background, usando o **Redis** como broker de mensagens.

```text
API → Redis → worker Celery → MeetingProcessor → PostgreSQL
```

A API enviará apenas o `meeting_id` para a fila. O worker Celery consumirá o
job, criará as dependências necessárias e executará o `MeetingProcessor`.

## Justificativa

O Celery foi escolhido por oferecer:

- execução em workers separados da API;
- suporte a filas e múltiplos workers;
- uma base preparada para retries futuros;
- maior confiabilidade caso a API seja reiniciada;
- integração consolidada com aplicações Python.

O Redis será utilizado como broker por ser leve, rápido, simples de executar
localmente com Docker e compatível com o Celery.

O PostgreSQL continuará sendo a fonte persistente de dados. O Redis terá a
função temporária de enfileirar jobs, não de armazenar os resultados finais.

## Trade-off

A solução adiciona dois containers à arquitetura:

- Redis, para a fila de mensagens;
- worker Celery, para executar os jobs.

Esse custo é aceito porque o pipeline é longo e pesado, e porque a arquitetura
precisa evoluir para retries e múltiplos workers sem sobrecarregar a API.

## Outra alternativa

O FastAPI `BackgroundTasks` exigiria menos infraestrutura, mas executaria a
tarefa no mesmo processo da API. Isso oferece menos isolamento para tarefas
longas e torna o processamento mais vulnerável a reinicializações da aplicação.

## Referência de build local

Depois das mudanças relacionadas ao Docker, em 27/09/2026, a execução de
`docker compose build` levou **7 minutos e 48,778 segundos** (468,778
segundos) no notebook pessoal de João Guilherme.

Esse tempo é apenas uma referência: pode variar de acordo com a máquina, a
rede e o uso de cache do Docker. Uma build com `--no-cache` tende a levar mais
tempo, enquanto builds posteriores podem ser mais rápidas.
