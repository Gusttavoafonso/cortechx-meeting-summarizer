from types import SimpleNamespace

from app.schemas.chunk import ChunkingConfig
from app.services.chunking.service import ChunkingService


def create_segment(
    id: int,
    start_time: float | None,
    end_time: float | None,
    speaker: str | None,
    text: str,
) -> SimpleNamespace:
    """Helper para simular um TranscriptSegment sem necessidade de banco de dados."""
    return SimpleNamespace(
        id=id,
        start_time=start_time,
        end_time=end_time,
        speaker=speaker,
        text=text,
    )


class TestChunkingService:
    def test_empty_transcript_returns_empty_list(self) -> None:
        service = ChunkingService()

        assert service.split(None) == []
        assert service.split("") == []
        assert service.split("   ") == []
        assert service.split([]) == []

        # Objeto Transcript vazio
        empty_transcript = SimpleNamespace(segments=[], content="")
        assert service.split(empty_transcript) == []

    def test_short_transcript_returns_single_chunk(self) -> None:
        service = ChunkingService()
        segments = [
            create_segment(1, 0.0, 30.0, "Alice", "Olá a todos, bem-vindos."),
            create_segment(2, 35.0, 80.0, "Bob", "Bom dia Alice, vamos começar."),
            create_segment(
                3, 85.0, 150.0, "Alice", "Item da pauta: metas trimestrais."
            ),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.index == 0
        assert chunk.start_time == 0.0
        assert chunk.end_time == 150.0
        assert chunk.segment_count == 3
        assert chunk.speakers == ["Alice", "Bob"]
        assert "[00:00] Alice: Olá a todos, bem-vindos." in chunk.text
        assert "[01:25] Alice: Item da pauta: metas trimestrais." in chunk.text

    def test_transcript_at_exact_duration_limit_returns_single_chunk(self) -> None:
        config = ChunkingConfig(max_duration_seconds=900.0, max_tokens=3000)
        service = ChunkingService(default_config=config)

        # Segmentos cobrindo exatamente de 0.0 a 900.0 segundos (15 minutos)
        segments = [
            create_segment(1, 0.0, 300.0, "Alice", "Abertura da reunião."),
            create_segment(2, 300.0, 600.0, "Bob", "Discussão técnica."),
            create_segment(3, 600.0, 900.0, "Carol", "Encerramento do bloco."),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert chunks[0].start_time == 0.0
        assert chunks[0].end_time == 900.0
        assert chunks[0].segment_count == 3

    def test_long_transcript_generates_multiple_ordered_chunks(self) -> None:
        # Reunião de 45 minutos (2700s) com 15 minutos (900s) por chunk
        config = ChunkingConfig(
            max_duration_seconds=900.0,
            overlap_duration_seconds=120.0,
            max_tokens=5000,
        )
        service = ChunkingService(default_config=config)

        # Criar falas a cada 2 minutos (120s) até 45 minutos
        segments = []
        seg_id = 1
        for t in range(0, 2700, 120):
            speaker = "Alice" if (seg_id % 2 == 1) else "Bob"
            segments.append(
                create_segment(
                    id=seg_id,
                    start_time=float(t),
                    end_time=float(t + 100),
                    speaker=speaker,
                    text=f"Fala {seg_id} no minuto {t // 60}.",
                )
            )
            seg_id += 1

        chunks = service.split(segments)

        assert len(chunks) > 1

        # Validação de índices, ordenação cronológica estrita e nenhum chunk vazio
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert chunk.segment_count > 0
            assert len(chunk.text.strip()) > 0
            assert chunk.start_time is not None
            assert chunk.end_time is not None
            assert chunk.start_time <= chunk.end_time

            if i > 0:
                assert chunk.start_time > chunks[i - 1].start_time

    def test_overlap_of_two_minutes_between_consecutive_chunks(self) -> None:
        # Limite de 15 minutos (900s) com overlap de 2 minutos (120s)
        config = ChunkingConfig(
            max_duration_seconds=900.0,
            overlap_duration_seconds=120.0,
            max_tokens=5000,
        )
        service = ChunkingService(default_config=config)

        # Falas distribuídas: 0min, 7min, 14min, 16min, 22min, 29min
        segments = [
            create_segment(1, 0.0, 60.0, "Alice", "Fala 0min"),
            create_segment(2, 420.0, 480.0, "Bob", "Fala 7min"),
            create_segment(
                3, 800.0, 860.0, "Alice", "Fala 14min - na janela de overlap"
            ),
            create_segment(4, 960.0, 1020.0, "Bob", "Fala 16min - inicia Chunk 2"),
            create_segment(5, 1320.0, 1380.0, "Carol", "Fala 22min"),
            create_segment(6, 1700.0, 1740.0, "Alice", "Fala 29min"),
        ]

        chunks = service.split(segments)

        assert len(chunks) >= 2
        chunk_0 = chunks[0]
        chunk_1 = chunks[1]

        # Chunk 0 vai de 0s a 860s (segmentos 1, 2, 3)
        assert chunk_0.start_time == 0.0
        assert chunk_0.end_time == 860.0

        # Segmento 3 (800s a 860s) está nos últimos 120s de Chunk 0
        # Portanto, o Chunk 1 DEVE começar no segmento 3 para o overlap de 2 min
        assert chunk_1.start_time == 800.0
        assert "Fala 14min - na janela de overlap" in chunk_0.text
        assert "Fala 14min - na janela de overlap" in chunk_1.text

    def test_no_segment_loss_across_all_chunks(self) -> None:
        service = ChunkingService(
            default_config=ChunkingConfig(
                max_duration_seconds=600.0,
                overlap_duration_seconds=60.0,
            )
        )
        segments = [
            create_segment(1, 0.0, 200.0, "A", "Texto 1"),
            create_segment(2, 210.0, 500.0, "B", "Texto 2"),
            create_segment(3, 510.0, 750.0, "C", "Texto 3"),
            create_segment(4, 760.0, 1100.0, "D", "Texto 4"),
            create_segment(5, 1110.0, 1400.0, "E", "Texto 5"),
        ]

        chunks = service.split(segments)

        # Garantir que todo segmento aparece no texto de pelo menos um chunk
        for seg in segments:
            found = any(seg.text in chunk.text for chunk in chunks)
            assert found, f"Segmento {seg.id} ('{seg.text}') foi perdido no chunking!"

    def test_preserves_speaker_and_timestamp_formatting(self) -> None:
        config = ChunkingConfig(max_duration_seconds=5000.0)
        service = ChunkingService(default_config=config)
        # Testar com timestamp < 1h [MM:SS] e >= 1h [HH:MM:SS]
        segments = [
            create_segment(1, 65.0, 95.0, "Gabriel", "Fala em 1 min e 5 seg."),
            create_segment(2, 3665.0, 3700.0, "Juliana", "Fala após 1 hora."),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert "[01:05] Gabriel: Fala em 1 min e 5 seg." in chunk.text
        assert "[01:01:05] Juliana: Fala após 1 hora." in chunk.text
        assert chunk.speakers == ["Gabriel", "Juliana"]

    def test_segment_without_speaker_or_timestamp(self) -> None:
        service = ChunkingService()
        segments = [
            create_segment(1, 10.0, 20.0, None, "Fala sem speaker."),
            create_segment(2, None, None, "Gabriel", "Fala sem timestamp."),
            create_segment(3, None, None, None, "Fala sem ambos."),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert "[00:10] Fala sem speaker." in chunk.text
        assert "Gabriel: Fala sem timestamp." in chunk.text
        assert "Fala sem ambos." in chunk.text
        assert chunk.speakers == ["Gabriel"]

    def test_fallback_with_raw_text_transcript(self) -> None:
        service = ChunkingService(default_config=ChunkingConfig(max_tokens=20))
        text = (
            "Primeiro parágrafo da reunião com várias palavras para o limite.\n"
            "Segundo parágrafo continuando a discussão sobre o produto.\n"
            "Terceiro parágrafo definindo os próximos passos do projeto."
        )

        chunks = service.split(text)

        assert len(chunks) >= 2
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert len(chunk.text) > 0
            assert chunk.start_time is None
            assert chunk.end_time is None

    def test_works_with_sqlalchemy_transcript_duck_typing(self) -> None:
        service = ChunkingService()
        segments = [
            create_segment(1, 0.0, 100.0, "João", "Discussão inicial."),
        ]
        mock_transcript = SimpleNamespace(
            id=10,
            meeting_id=1,
            content="Discussão inicial.",
            segments=segments,
        )

        chunks = service.split(mock_transcript)

        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert "João: Discussão inicial." in chunks[0].text

    def test_token_cap_forces_split_even_if_duration_is_short(self) -> None:
        # Config com teto de tokens baixo para forçar corte por tokens
        config = ChunkingConfig(max_duration_seconds=900.0, max_tokens=30)
        service = ChunkingService(default_config=config)

        # 3 falas curtas em tempo (0 a 100s), mas com muitas palavras
        segments = [
            create_segment(1, 0.0, 30.0, "A", "Palavra " * 20),
            create_segment(2, 35.0, 60.0, "B", "Palavra " * 20),
            create_segment(3, 65.0, 90.0, "C", "Palavra " * 20),
        ]

        chunks = service.split(segments)

        # Cada fala tem ~28 tokens e max_tokens é 30 -> múltiplos chunks
        assert len(chunks) > 1

    def test_concurrent_overlapping_speech_end_time(self) -> None:
        """Verifica se o end_time do chunk é o maior end_time real entre falas simultâneas."""
        service = ChunkingService()
        # Alice fala até 100s, Bob interrompe brevemente entre 70s e 80s
        segments = [
            create_segment(1, 0.0, 100.0, "Alice", "Fala longa principal."),
            create_segment(2, 70.0, 80.0, "Bob", "Interrupção rápida."),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 1
        assert chunks[0].end_time == 100.0

    def test_single_segment_exceeding_max_duration_does_not_loop(self) -> None:
        """Segmento com mais de 15 minutos é incluído como bloco unitário sem travar."""
        config = ChunkingConfig(max_duration_seconds=900.0)
        service = ChunkingService(default_config=config)
        # Fala ininterrupta de 20 minutos (1200s)
        segments = [
            create_segment(1, 0.0, 1200.0, "Palestrante", "Monólogo de 20 min."),
            create_segment(2, 1210.0, 1300.0, "Participante", "Pergunta curta."),
        ]

        chunks = service.split(segments)

        assert len(chunks) == 2
        assert chunks[0].index == 0
        assert chunks[0].segment_count == 1
        assert chunks[1].index == 1
        assert chunks[1].segment_count == 1

    def test_overlap_larger_than_chunk_duration_does_not_infinite_loop(self) -> None:
        """Configuração extrema de overlap não causa retrocesso infinito."""
        config = ChunkingConfig(
            max_duration_seconds=300.0,
            overlap_duration_seconds=600.0,  # overlap maior que duração do chunk
        )
        service = ChunkingService(default_config=config)
        segments = [
            create_segment(1, 0.0, 200.0, "A", "Parte 1"),
            create_segment(2, 250.0, 400.0, "B", "Parte 2"),
            create_segment(3, 450.0, 700.0, "C", "Parte 3"),
        ]

        chunks = service.split(segments)

        assert len(chunks) >= 2
        # Garante índices estritamente sequenciais e progresso
        for i in range(1, len(chunks)):
            assert chunks[i].start_time > chunks[i - 1].start_time

    def test_segments_without_timestamps_fallbacks_to_segment_overlap(self) -> None:
        """Quando não há timestamps, usa contagem de segmentos para overlap."""
        config = ChunkingConfig(
            max_tokens=30,
            overlap_segments=1,
        )
        service = ChunkingService(default_config=config)
        segments = [
            create_segment(1, None, None, "A", "Palavra " * 20),
            create_segment(2, None, None, "B", "Palavra " * 20),
            create_segment(3, None, None, "C", "Palavra " * 20),
        ]

        chunks = service.split(segments)

        assert len(chunks) > 1
        # Chunk 1 deve conter a fala 2 como overlap da fala anterior
        assert "Palavra " in chunks[1].text
