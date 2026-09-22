"""Serviço simples para dividir transcrições em blocos processáveis pela LLM."""

class TranscriptChunker:
    """Divide transcrições em blocos de tamanho controlado, com sobreposição."""

    def __init__(self, max_chars: int = 12000, overlap_chars: int = 500) -> None:
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    @property
    def max_chars(self) -> int:
        return self._max_chars

    @property
    def overlap_chars(self) -> int:
        return self._overlap_chars

    def split(self, transcript: str) -> list[str]:
        text = transcript.strip()
        if not text:
            return []
        if self.max_chars <= 0:
            raise ValueError("max_chars deve ser maior que zero")
        if self.overlap_chars < 0 or self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars deve estar entre 0 e max_chars - 1")

        chunks: list[str] = []
        start = 0
        length = len(text)

        while start < length:
            end = min(start + self.max_chars, length)
            if end < length:
                boundary = max(
                    text.rfind("\n", start, end),
                    text.rfind(". ", start, end),
                    text.rfind("? ", start, end),
                    text.rfind("! ", start, end),
                )
                if boundary > start + self.max_chars // 2:
                    end = boundary + (1 if text[boundary] in ".!?" else 0)

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= length:
                break
            start = max(end - self.overlap_chars, start + 1)

        return chunks