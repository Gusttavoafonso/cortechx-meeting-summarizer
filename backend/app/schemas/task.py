from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskItem(BaseModel):
    """Representação estruturada de uma tarefa extraída de uma reunião."""

    model_config = ConfigDict(from_attributes=True)

    task: str = Field(
        ...,
        description="Descrição curta, clara e objetiva da ação a ser realizada.",
    )
    responsible: str | None = Field(
        default=None,
        description=(
            "Pessoa responsável pela tarefa explicitamente informada ou "
            "identificador do speaker (ex: SPEAKER_01). None se não houver."
        ),
    )
    deadline: str | None = Field(
        default=None,
        description=(
            "Prazo explicitamente mencionado na transcrição (ex: 'sexta-feira', "
            "'até 15h'). None caso nenhum prazo seja especificado."
        ),
    )


class TaskList(BaseModel):
    """Contêiner para lista de tarefas extraídas."""

    model_config = ConfigDict(from_attributes=True)

    tasks: list[TaskItem] = Field(
        default_factory=list,
        description="Lista de tarefas acionáveis identificadas.",
    )
