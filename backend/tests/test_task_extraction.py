from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.chunk import Chunk
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import LLMProviderError
from app.services.llm.service import LLMService
from app.services.task_extraction.exceptions import (
    TaskExtractionInvalidResponseError,
    TaskExtractionLLMFailureError,
)
from app.services.task_extraction.service import TaskExtractionService


class DummyLLMProvider(BaseLLMProvider):
    def __init__(self, response_text: str = '{"tasks": []}') -> None:
        self.response_text = response_text
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response_text


def create_mock_segment(
    start_time: float,
    end_time: float,
    speaker: str,
    text: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        start_time=start_time,
        end_time=end_time,
        speaker=speaker,
        text=text,
    )


class TestTaskExtractionService:
    def test_extract_none_or_empty_returns_empty_list(self) -> None:
        provider = DummyLLMProvider()
        service = TaskExtractionService(llm_service=LLMService(provider))

        assert service.extract(None) == []
        assert service.extract("") == []
        assert service.extract("   ") == []
        assert service.extract([]) == []
        assert len(provider.calls) == 0

    def test_meeting_without_tasks_returns_empty_list(self) -> None:
        provider = DummyLLMProvider(response_text='{"tasks": []}')
        service = TaskExtractionService(llm_service=LLMService(provider))

        transcript = (
            "Olá a todos, hoje apenas nos reunimos para conversar e comemorar os "
            "resultados."
        )
        tasks = service.extract(transcript)

        assert tasks == []
        assert len(provider.calls) == 1
        assert "LOCUTORES IDENTIFICADOS" not in provider.calls[0]
        assert transcript in provider.calls[0]

    def test_single_task_extraction(self) -> None:
        response_json = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Revisar o backend",
                        "responsible": "Gustavo",
                        "deadline": "sexta-feira",
                    }
                ]
            }
        )
        provider = DummyLLMProvider(response_text=response_json)
        service = TaskExtractionService(llm_service=LLMService(provider))

        transcript = "Gustavo fica responsável por revisar o backend até sexta-feira."
        tasks = service.extract(transcript)

        assert len(tasks) == 1
        assert tasks[0].task == "Revisar o backend"
        assert tasks[0].responsible == "Gustavo"
        assert tasks[0].deadline == "sexta-feira"

    def test_multiple_tasks_extraction(self) -> None:
        response_json = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Implementar endpoints da API",
                        "responsible": "Carlos",
                        "deadline": "amanhã",
                    },
                    {
                        "task": "Escrever testes unitários",
                        "responsible": "Ana",
                        "deadline": None,
                    },
                ]
            }
        )
        provider = DummyLLMProvider(response_text=response_json)
        service = TaskExtractionService(llm_service=LLMService(provider))

        tasks = service.extract(
            "Carlos implementa os endpoints e Ana escreve os testes."
        )

        assert len(tasks) == 2
        assert tasks[0].task == "Implementar endpoints da API"
        assert tasks[0].responsible == "Carlos"
        assert tasks[0].deadline == "amanhã"
        assert tasks[1].task == "Escrever testes unitários"
        assert tasks[1].responsible == "Ana"
        assert tasks[1].deadline is None

    def test_task_without_responsible(self) -> None:
        response_json = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Validar integração",
                        "responsible": None,
                        "deadline": None,
                    }
                ]
            }
        )
        provider = DummyLLMProvider(response_text=response_json)
        service = TaskExtractionService(llm_service=LLMService(provider))

        tasks = service.extract(
            "Precisamos validar a integração antes de subir para produção."
        )

        assert len(tasks) == 1
        assert tasks[0].task == "Validar integração"
        assert tasks[0].responsible is None
        assert tasks[0].deadline is None

    def test_task_with_responsible_as_speaker(self) -> None:
        response_json = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Configurar o banco de dados",
                        "responsible": "SPEAKER_01",
                        "deadline": None,
                    }
                ]
            }
        )
        provider = DummyLLMProvider(response_text=response_json)
        service = TaskExtractionService(llm_service=LLMService(provider))

        segments = [
            create_mock_segment(
                0.0, 10.0, "SPEAKER_00", "Quem pode configurar o banco?"
            ),
            create_mock_segment(11.0, 20.0, "SPEAKER_01", "Eu cuido disso hoje."),
        ]

        tasks = service.extract(segments)

        assert len(tasks) == 1
        assert tasks[0].task == "Configurar o banco de dados"
        assert tasks[0].responsible == "SPEAKER_01"
        assert "SPEAKER_00, SPEAKER_01" in provider.calls[0]

    def test_task_with_and_without_deadline(self) -> None:
        response_json = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Finalizar documentação",
                        "responsible": "Mariana",
                        "deadline": "quarta-feira às 18h",
                    },
                    {
                        "task": "Organizar backlog",
                        "responsible": "Lucas",
                        "deadline": None,
                    },
                ]
            }
        )
        provider = DummyLLMProvider(response_text=response_json)
        service = TaskExtractionService(llm_service=LLMService(provider))

        tasks = service.extract(
            "Mariana finaliza doc na quarta às 18h e Lucas organiza backlog."
        )

        assert len(tasks) == 2
        assert tasks[0].deadline == "quarta-feira às 18h"
        assert tasks[1].deadline is None

    def test_markdown_code_fence_handling(self) -> None:
        raw_markdown = """```json
{
  "tasks": [
    {
      "task": "Publicar release",
      "responsible": "DevOps",
      "deadline": "fim da sprint"
    }
  ]
}
```"""
        provider = DummyLLMProvider(response_text=raw_markdown)
        service = TaskExtractionService(llm_service=LLMService(provider))

        tasks = service.extract("Release deve ser publicada no fim da sprint.")

        assert len(tasks) == 1
        assert tasks[0].task == "Publicar release"
        assert tasks[0].responsible == "DevOps"
        assert tasks[0].deadline == "fim da sprint"

    def test_multiple_chunks_processing_and_consolidation(self) -> None:
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.generate.side_effect = [
            json.dumps(
                {
                    "tasks": [
                        {
                            "task": "Desenvolver funcionalidade A",
                            "responsible": "Alice",
                            "deadline": None,
                        }
                    ]
                }
            ),
            json.dumps(
                {
                    "tasks": [
                        {
                            "task": "Desenvolver funcionalidade B",
                            "responsible": "Bob",
                            "deadline": "segunda-feira",
                        }
                    ]
                }
            ),
        ]

        service = TaskExtractionService(llm_service=LLMService(mock_provider))

        chunks = [
            Chunk(index=0, text="Texto do chunk 1", speakers=["Alice"]),
            Chunk(index=1, text="Texto do chunk 2", speakers=["Bob"]),
        ]

        tasks = service.extract(chunks)

        assert len(tasks) == 2
        assert tasks[0].task == "Desenvolver funcionalidade A"
        assert tasks[0].responsible == "Alice"
        assert tasks[1].task == "Desenvolver funcionalidade B"
        assert tasks[1].responsible == "Bob"
        assert mock_provider.generate.call_count == 2

    def test_deduplication_of_overlapping_tasks_with_enriched_metadata(
        self,
    ) -> None:
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.generate.side_effect = [
            # Chunk 1 identificou a tarefa sem prazo
            json.dumps(
                {
                    "tasks": [
                        {
                            "task": "Revisar o backend",
                            "responsible": "Gustavo",
                            "deadline": None,
                        }
                    ]
                }
            ),
            # Chunk 2 (overlap) identificou a mesma tarefa com prazo
            json.dumps(
                {
                    "tasks": [
                        {
                            "task": "Revisar o backend!",
                            "responsible": "Gustavo",
                            "deadline": "sexta-feira",
                        },
                        {
                            "task": "Criar migration",
                            "responsible": "João",
                            "deadline": None,
                        },
                    ]
                }
            ),
        ]

        service = TaskExtractionService(llm_service=LLMService(mock_provider))

        chunks = [
            Chunk(index=0, text="Parte 1"),
            Chunk(index=1, text="Parte 2 com overlap"),
        ]

        tasks = service.extract(chunks)

        # Deve haver apenas 2 tarefas e o prazo de sexta-feira deve ser mesclado
        assert len(tasks) == 2
        assert tasks[0].task == "Revisar o backend"
        assert tasks[0].responsible == "Gustavo"
        assert tasks[0].deadline == "sexta-feira"
        assert tasks[1].task == "Criar migration"

    def test_invalid_json_response_raises_error(self) -> None:
        provider = DummyLLMProvider(response_text="Isso não é um JSON válido")
        service = TaskExtractionService(llm_service=LLMService(provider))

        with pytest.raises(TaskExtractionInvalidResponseError) as exc_info:
            service.extract("Algum texto de reunião")

        assert "não é um JSON válido" in str(exc_info.value)

    def test_schema_mismatch_raises_error(self) -> None:
        # Faltando a chave obrigatória 'task' dentro do item
        provider = DummyLLMProvider(
            response_text=json.dumps({"tasks": [{"responsible": "Gustavo"}]})
        )
        service = TaskExtractionService(llm_service=LLMService(provider))

        with pytest.raises(TaskExtractionInvalidResponseError) as exc_info:
            service.extract("Algum texto")

        assert "não compatível com o schema" in str(exc_info.value)

    def test_llm_failure_raises_task_extraction_llm_failure_error(
        self,
    ) -> None:
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.generate.side_effect = LLMProviderError(
            "Erro de timeout na API do LLM"
        )

        service = TaskExtractionService(llm_service=LLMService(mock_provider))

        with pytest.raises(TaskExtractionLLMFailureError) as exc_info:
            service.extract("Discussão sobre tarefas")

        assert "Erro durante chamada ao serviço de LLM" in str(exc_info.value)

    def test_representative_example_validation(self) -> None:
        """Validação com o exemplo representativo exato da Issue."""
        representative_input = """
        Gustavo fica responsável por revisar o backend.

        João deve atualizar a documentação até quinta-feira.

        Também precisamos validar o pipeline antes da apresentação.
        """

        mock_llm_response = json.dumps(
            {
                "tasks": [
                    {
                        "task": "Revisar o backend",
                        "responsible": "Gustavo",
                        "deadline": None,
                    },
                    {
                        "task": "Atualizar a documentação",
                        "responsible": "João",
                        "deadline": "quinta-feira",
                    },
                    {
                        "task": "Validar o pipeline antes da apresentação",
                        "responsible": None,
                        "deadline": None,
                    },
                ]
            }
        )

        provider = DummyLLMProvider(response_text=mock_llm_response)
        service = TaskExtractionService(llm_service=LLMService(provider))

        tasks = service.extract(representative_input)

        assert len(tasks) == 3

        # 1. Gustavo - Revisar o backend
        assert tasks[0].task == "Revisar o backend"
        assert tasks[0].responsible == "Gustavo"
        assert tasks[0].deadline is None

        # 2. João - Atualizar a documentação até quinta-feira
        assert tasks[1].task == "Atualizar a documentação"
        assert tasks[1].responsible == "João"
        assert tasks[1].deadline == "quinta-feira"

        # 3. Sem responsável - Validar o pipeline antes da apresentação
        assert tasks[2].task == "Validar o pipeline antes da apresentação"
        assert tasks[2].responsible is None
        assert tasks[2].deadline is None
