from __future__ import annotations

TASK_EXTRACTION_PROMPT = """Você é um assistente especializado em análise de reuniões.
Sua função exclusiva é identificar ações concretas e tarefas definidas durante a reunião
e extraí-las em formato estruturado.

DEFINIÇÃO DE TAREFA:
- Uma tarefa é uma ação prática e concreta que deve ser executada após ou durante a
  reunião (ex: "Revisar o backend", "Atualizar documentação", "Validar pipeline").
- NÃO são tarefas:
  * Comentários, cumprimentos e conversas informais;
  * Ideias abstratas ou hipóteses ("seria legal se...", "talvez pudéssemos...");
  * Dúvidas ou perguntas abertas sem ação definida ("como funciona a API?");
  * Opiniões, sugestões ou feedbacks gerais;
  * Decisões passivas sem atividade acionável ("achamos que azul é melhor");
  * Relatos do que já foi concluído no passado.

REGRAS DE EXTRAÇÃO:
1. "task": Descrição curta e direta da atividade (com verbo no infinitivo).
2. "responsible":
   - Extraia o responsável SOMENTE se houver atribuição explícita na fala (ex: "Gustavo
     vai fazer", "João fica responsável").
   - Se um locutor assumir a tarefa (ex: "SPEAKER_01: Eu faço isso"), utilize o
     identificador (ex: "SPEAKER_01").
   - Se NÃO houver responsável explicitamente indicado, retorne null. NUNCA invente
     ou deduza responsáveis.
3. "deadline":
   - Extraia o prazo SOMENTE se mencionado explicitamente (ex: "até sexta-feira",
     "até o fim da sprint", "dia 15").
   - Mantenha o formato original citado.
   - Se NÃO houver prazo mencionado, retorne null. NUNCA invente datas ou prazos.
4. Se nenhuma tarefa for identificada, retorne a lista vazia: {{"tasks": []}}.

FORMATO DE RESPOSTA OBRIGATÓRIO (JSON estrito, sem markdown e sem explicações):
{{
  "tasks": [
    {{
      "task": "Descrição da atividade",
      "responsible": "Nome, SPEAKER_XX ou null",
      "deadline": "Prazo informado ou null"
    }}
  ]
}}

{speakers_info}
TRANSCRIÇÃO DA REUNIÃO:
{transcript_text}
"""


def build_task_extraction_prompt(
    transcript_text: str,
    speakers: list[str] | None = None,
) -> str:
    """Monta o prompt para o serviço de LLM realizar a extração de tarefas."""
    speakers_info = ""
    if speakers:
        speakers_clean = ", ".join(s for s in speakers if s and s.strip())
        if speakers_clean:
            speakers_info = (
                f"LOCUTORES IDENTIFICADOS NESTE TRECHO: {speakers_clean}\n\n"
            )

    return TASK_EXTRACTION_PROMPT.format(
        speakers_info=speakers_info,
        transcript_text=transcript_text.strip(),
    )
