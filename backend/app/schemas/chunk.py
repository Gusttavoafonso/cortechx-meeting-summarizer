from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """Representação estruturada de uma fração da transcrição preparada para LLM."""

    model_config = ConfigDict(from_attributes=True)

    index: int = Field(
        ...,
        description="Índice sequencial do chunk na reunião (iniciando em 0).",
        ge=0,
    )
    text: str = Field(
        ...,
        description="Texto formatado contendo falas, timestamps e speakers.",
    )
    start_time: float | None = Field(
        None,
        description="Timestamp inicial em segundos relativo ao início do áudio.",
    )
    end_time: float | None = Field(
        None,
        description="Timestamp final em segundos relativo ao início do áudio.",
    )
    speakers: list[str] = Field(
        default_factory=list,
        description=("Lista ordenada e sem duplicatas dos speakers participantes."),
    )
    segment_count: int = Field(
        0,
        description="Quantidade de segmentos de transcrição agrupados neste chunk.",
        ge=0,
    )
    estimated_tokens: int = Field(
        0,
        description="Estimativa da quantidade de tokens do texto do chunk.",
        ge=0,
    )


class ChunkingConfig(BaseModel):
    """Configurações determinísticas para divisão das transcrições."""

    max_duration_seconds: float = Field(
        default=900.0,
        description="Duração máxima alvo em segundos (padrão: 15 min = 900s).",
        gt=0,
    )
    max_tokens: int = Field(
        default=3000,
        description="Limite de tokens para não estourar o contexto do LLM.",
        gt=0,
    )
    overlap_duration_seconds: float = Field(
        default=120.0,
        description="Duração do overlap em segundos (padrão: 2 min = 120s).",
        ge=0,
    )
    overlap_segments: int = Field(
        default=1,
        description="Qtd mínima de segmentos de overlap sem timestamps.",
        ge=0,
    )
