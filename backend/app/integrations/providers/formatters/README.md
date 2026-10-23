# Estratégia de formatação do Discord

O `DiscordFormatter` transforma `MeetingIntegrationPayload` em mensagens Markdown
compatíveis com um webhook do Discord. A formatação fica separada do provider:
o formatter não realiza requisições HTTP e o provider não decide como apresentar
os dados da reunião.

## Formato escolhido

Foi escolhido Markdown em mensagens comuns, em vez de embeds. Isso evita depender
de limites e estruturas específicas de campos de embed e deixa a mensagem legível
em clientes desktop e mobile. A mensagem segue esta ordem:

```text
## Reunião: <título>

### Resumo
<resumo>

### Objetivo
<objetivo>

### Principais pontos
- <ponto>

### Decisões
- <decisão>

### Tarefas
- [ ] <descrição> (Responsável: <nome> | Prazo: <data>)
```

`Resumo` é sempre exibido, pois é obrigatório no payload. As seções opcionais
(`Objetivo`, `Principais pontos`, `Decisões` e `Tarefas`) sóo incluídas quando
possuem conteúdo. Responsável e prazo também são omitidos individualmente
quando ausentes; a mensagem nunca deve exibir `None`.

## Limite e divisão

O Discord aceita no máximo 2.000 caracteres no campo `content` de uma mensagem.
O formatter retorna uma lista de mensagens, cada uma com no máximo esse limite.
Ele prioriza quebrar entre linhas para manter itens e seções legíveis. Uma linha
excepcionalmente longa é cortada em blocos de 2.000 caracteres, sem descarte de
conteúdo. O `DiscordProvider` deverá enviar cada item retornado, na ordem recebida.
