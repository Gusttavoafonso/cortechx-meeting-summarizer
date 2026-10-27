# Documentação da Estratégia de Chunking da Transcrição

Este documento detalha a estratégia arquitetural e algorítmica adotada para a divisão de transcrições de reuniões no projeto **Cortechx Meeting Summarizer** (Issue 16).

---

## 1. Contexto e Motivação

Reuniões podem durar desde poucos minutos até várias horas. O envio de uma transcrição inteira de 1h ou 2h diretamente para um modelo de linguagem (LLM) traz problemas severos:
1. **Estouro da Janela de Contexto (*Context Window*)**: Mesmo modelos com janelas grandes sofrem degradação de atenção ao receber textos excessivamente longos.
2. **Perda de Informação no Meio (*Lost in the Middle*)**: Modelos tendem a reter melhor o início e o fim do texto, ignorando pontos cruciais discutidos no meio da reunião.
3. **Custo e Latência**: Processar um bloco monolítico gigante é custoso e impede o processamento paralelo ou em etapas (*map-reduce*).

O **`ChunkingService`** atua como uma etapa intermediária e determinística, desacoplada de rotas HTTP, responsável por receber a transcrição e transformá-la em uma sequência ordenada de `Chunk`s estruturados.

---

## 2. Estratégia de Divisão Escolhida

Avaliamos as estratégias comumente utilizadas:
* **Divisão puramente por caracteres/palavras:** Pode cortar palavras ao meio ou quebrar frases no meio de um raciocínio.
* **Divisão puramente por tokens de texto corrido:** Ignora a estrutura de fala e temporalidade dos participantes.
* **Divisão híbrida baseada em Segmentos Temporais (`TranscriptSegment`) + Salvaguarda de Tokens:** **(Estratégia Escolhida)**.

### Pilares da Decisão:

1. **Agrupamento por `TranscriptSegment`**:
   - Cada segmento já representa uma unidade semântica de fala delimitada pelo modelo de transcrição (Whisper/Diarização), contendo `speaker`, `start_time`, `end_time` e `text`.
   - O chunking **nunca quebra uma fala ao meio**. Ele agrupa falas inteiras sequencialmente.

2. **Janela Temporal Principal: 15 Minutos (900 segundos)**:
   - Em média, blocos de 15 minutos representam um ciclo completo de discussão de um tópico em reuniões de trabalho.
   - Uma reunião padrão de 1 hora resulta em cerca de 4 a 5 chunks ordenados.

3. **Salvaguarda de Volume: 3.000 Tokens**:
   - Modelos modernos em português consomem cerca de 1.4 tokens por palavra.
   - Em 15 minutos de fala ativa contínua (140 palavras/minuto), geram-se ~2.100 palavras ($\approx$ 2.900 a 3.000 tokens com formatação de timestamps e falantes).
   - O teto de 3.000 tokens garante que, caso os participantes falem muito rápido ou caso a transcrição não possua timestamps, o bloco nunca estoure a janela segura de processamento do LLM.
   - O fechamento do chunk ocorre por **quem for atingido primeiro** (15 minutos ou 3.000 tokens).

---

## 3. Política de Sobreposição (*Overlap*): 2 Minutos (120 segundos)

### Por que o Overlap é necessário?
Quando uma discussão importante se inicia nos últimos instantes de um bloco (ex: aos 14m30s), um corte abrupto no minuto 15m00s faria com que o Chunk 0 tivesse apenas o início do assunto e o Chunk 1 começasse no meio da conclusão.

### Como funciona:
* Configuramos **`overlap_duration_seconds = 120.0` (2 minutos)**.
* Ao finalizar o `Chunk N` (que terminou no segundo $T_{fim}$), o serviço calcula o ponto de corte de sobreposição:
  $$T_{overlap} = \max(0, T_{fim} - 120)$$
* O algoritmo busca o primeiro segmento do bloco anterior cujo término invade a janela $[T_{overlap}, T_{fim}]$ e inicia o `Chunk N+1` a partir dele.
* **Garantia de Progresso**: O índice de início do próximo chunk sempre avança estritamente para a frente em relação ao chunk anterior, eliminando loops infinitos.
* **Transcrições Curtas**: Se a reunião couber inteira no limite de 15 minutos, é gerado apenas 1 chunk, **sem duplicação desnecessária de overlap**.

---

## 4. Formatação Padronizada do Texto do Chunk

Para que o LLM consiga distinguir cronologia e autoria de cada argumento, as falas são consolidadas no atributo `text` no padrão:

* **Reuniões com menos de 1 hora:**
  ```text
  [01:15] Gabriel: Olá pessoal, vamos iniciar a revisão de arquitetura.
  [01:30] Juliana: Perfeito, podemos avaliar o diagrama de serviços.
  ```
* **Reuniões longas (≥ 1 hora):**
  ```text
  [01:05:20] Gabriel: Agora vamos para a pauta final de deploys.
  ```
* **Fallback sem falante ou sem timestamp:**
  - Sem falante: `[01:15] Olá pessoal...`
  - Sem timestamp: `Gabriel: Olá pessoal...`
  - Sem ambos: `Olá pessoal...`

---

## 5. Estrutura de Dados e Schemas

Localizado em `backend/app/schemas/chunk.py`:

```python
class Chunk(BaseModel):
    index: int                  # Índice sequencial: 0, 1, 2...
    text: str                   # Texto consolidado e formatado
    start_time: float | None    # Início do bloco em segundos
    end_time: float | None      # Fim do bloco em segundos
    speakers: list[str]         # Falantes únicos que falaram neste bloco
    segment_count: int          # Qtd de falas agregadas
    estimated_tokens: int       # Estimativa conservadora de tokens

class ChunkingConfig(BaseModel):
    max_duration_seconds: float = 900.0      # 15 minutos
    max_tokens: int = 3000                   # Teto de tokens
    overlap_duration_seconds: float = 120.0  # 2 minutos
    overlap_segments: int = 1                # Fallback sem timestamp
```

---

## 6. Tratamento de Casos de Borda (*Edge Cases*)

| Cenário | Comportamento do Serviço |
| :--- | :--- |
| **Transcrição Vazia** (`None`, `""`, `[]`) | Retorna lista vazia `[]` sem lançar exceções. |
| **Transcrição Curta** (< 15 minutos) | Retorna exatamente 1 chunk (`index = 0`), sem overlap. |
| **Transcrição no Limite Exato** (= 15 minutos) | Retorna 1 chunk contendo todos os segmentos. |
| **Transcrição Extensa** (> 15 minutos) | Gera múltiplos chunks ordenados com overlap de 2 min entre adjacentes. |
| **Fala Individual Gigante** (> limite do chunk) | Incluída como bloco unitário para garantir progresso e integridade. |
| **Transcrição sem Segmentos** (apenas texto bruto) | Fallback automático particionando por parágrafos e teto de tokens. |

---

## 7. Como Executar os Testes

A suíte completa de testes unitários do serviço está em `backend/tests/test_chunking_service.py`:

```bash
# Rodar testes do serviço de chunking
pytest tests/test_chunking_service.py -v

# Rodar verificação de linter e formatação (Ruff)
ruff check app/schemas/chunk.py app/services/chunking/ tests/test_chunking_service.py
```
