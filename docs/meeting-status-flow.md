# Estados e transições de reunião

## Estados
- `received`: reunião criada, sem áudio registrado.
- `audio_uploaded`: arquivo e metadados do áudio foram persistidos.
- `transcribing`: transcrição está em execução.
- `transcribed`: transcrição foi persistida e pode ser analisada.
- `processing`: sumarização/análise está em execução.
- `completed`: a execução solicitada terminou e o resultado foi persistido.
- `failed`: a execução falhou; `last_error` registra uma mensagem curta. Uma nova tentativa pode ser iniciada.

## Fluxo
`received -> audio_uploaded -> transcribing -> transcribed -> processing -> completed`

Falhas durante transcrição podem retornar para `audio_uploaded` quando o erro é recuperável pela aplicação; falhas durante sumarização vão de `processing` para `failed`. Falhas transitórias no enfileiramento ou cancelamentos em `processing` podem reverter para `audio_uploaded` ou `transcribed`. Reprocessamento de resumo: `completed -> processing`. Substituir áudio invalida a transcrição e retorna para `audio_uploaded`.

## Metadados
`processing_started_at` registra o início da execução mais recente, `processing_completed_at` seu fim (sucesso ou falha), `updated_at` é atualizado em cada mudança e `last_error` contém a última falha, limpo ao iniciar uma nova execução ou concluir com sucesso.

A atualização de status deve passar por `MeetingService.update_status`, que valida a transição e persiste estado e metadados. Não marque `completed` antes de salvar o resultado final.
