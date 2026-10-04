# Documentação da Estratégia de Extração de Tarefas e Responsáveis

Este documento detalha o funcionamento arquitetural e algorítmico do serviço de extração de tarefas do projeto **Cortechx Meeting Summarizer** (Issue 21).

---

## 1. Contexto e Objetivo

O objetivo do módulo de extração de tarefas é transformar o conteúdo de uma reunião em uma lista estruturada de atividades acionáveis contendo:
* **Tarefa (`task`)**: Ação prática e concreta a ser realizada.
* **Responsável (`responsible`)**: Pessoa atribuída ou locutor (`SPEAKER_XX`) explicitamente identificado.
* **Prazo (`deadline`)**: Data ou prazo relativo mencionado expressamente.

---

## 2. Fluxo com Múltiplos Chunks

Em reuniões longas, o volume de transcrição ultrapassa o tamanho seguro de um único prompt. O pipeline orquestra a divisão e consolidação da seguinte forma:

```text
Transcrição (ou TranscriptSegments)
                 │
                 ▼
         ChunkingService
                 │
  ┌──────────────┼──────────────┐
  ▼              ▼              ▼
Chunk 0        Chunk 1        Chunk 2
  │              │              │
  ▼              ▼              ▼
Prompt LLM     Prompt LLM     Prompt LLM
  │              │              │
  ▼              ▼              ▼
Tarefas C0     Tarefas C1     Tarefas C2
  └──────────────┬──────────────┘
                 ▼
     Consolidação & Deduplicação
                 │
                 ▼
      Lista Final de Tarefas
```

1. **Processamento Independente**: Cada chunk é processado sequencialmente através do `LLMService`, aplicando o prompt especializado com structured output.
2. **Preservação de Contexto**: Cada chunk preserva locutores (`speakers`) e formatação cronológica `[MM:SS] Speaker: fala`.
3. **Consolidação**: As listas de tarefas de cada chunk são unificadas mantendo a cronologia das discussões.

---

## 3. Estratégia de Deduplicação

Devido à janela de sobreposição (*overlap*) de 2 minutos configurada no `ChunkingService`, é natural que tarefas mencionadas na fronteira entre blocos apareçam no `Chunk N` e no `Chunk N+1`. Além disso, os participantes podem reforçar a mesma tarefa no início e no final da reunião.

### Algoritmo de Deduplicação:

1. **Normalização de Chave (`_normalize_text`)**:
   - A descrição da tarefa é convertida para caixa baixa.
   - Pontuações e caracteres especiais são removidos (`re.sub(r"[^\w\s]", "", ...)`).
   - Espaços múltiplos são colapsados para um único espaço.
   - *Exemplo*: `"Revisar o backend!"` e `"revisar o backend"` geram a mesma chave normalizada `"revisar o backend"`.

2. **Preservação da Ordem Cronológica (`ordered_keys`)**:
   - As tarefas são armazenadas respeitando a ordem da primeira vez em que foram identificadas na reunião.

3. **Enriquecimento e Fusão de Metadados**:
   - Quando uma duplicação evidente é identificada:
     - Se a ocorrência anterior não possuía responsável (`None`) e a nova ocorrência possui (`"Gustavo"`), o responsável é atualizado.
     - Se a ocorrência anterior não possuía prazo (`None`) e a nova ocorrência possui (`"sexta-feira"`), o prazo é incorporado.
   - Garante que a tarefa final retenha o conjunto de informações mais rico possível.

4. **Preservação de Atividades Semelhantes, mas Distintas**:
   - Tarefas com escopos diferentes geram chaves distintas (ex: `"Revisar backend"` e `"Revisar frontend"` ou `"Testar autenticação"` e `"Testar upload"`), evitando falsos positivos de remoção.

---

## 4. Garantia contra Alucinações

* **Sem atribuição implícita**: O prompt proíbe expressamente presumir quem fará a tarefa se não houver compromisso ou atribuição clara na transcrição. Nesses casos, o campo `responsible` é mantido como `null`.
* **Sem datas fictícias**: O modelo não calcula calendários nem inventa prazos. Captura estritamente o que foi dito (ex: *"até sexta"*, *"dia 10"*).
* **Nenhuma tarefa identificada**: Em reuniões informais ou sem deliberações de tarefas, o serviço retorna uma lista vazia `[]`.
