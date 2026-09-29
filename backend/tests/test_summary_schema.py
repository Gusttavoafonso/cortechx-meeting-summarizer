from app.schemas.summary import SummaryResult


def test_summary_response_validates_llm_output():
    payload = {
        "objective": "Definir prioridades da próxima sprint.",
        "summary": "A equipe revisou as entregas da sprint atual.",
        "key_points": ["Finalizar o backend."],
        "decisions": ["O backend deverá ser finalizado até sexta-feira."],
        "tasks": [],
    }

    summary = SummaryResult.model_validate(payload)

    assert summary.model_dump() == payload
