from app.prompts.summarization import build_summarization_prompt


def test_build_summarization_prompt_includes_the_transcript_and_rules():
    transcript = "Ana: Vamos aprovar o orçamento."

    prompt = build_summarization_prompt(transcript)

    assert transcript in prompt
    assert "somente informações explicitamente presentes" in prompt
    assert "Não identificado na transcrição." in prompt
    assert '"objective"' in prompt
    assert '"summary"' in prompt
    assert '"main_points"' in prompt
    assert '"decisions"' in prompt
