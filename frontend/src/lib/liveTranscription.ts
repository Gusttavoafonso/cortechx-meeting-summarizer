import type { AudioChunkEvent } from './audioRecorder'

export type LiveTranscriptionStatus =
  'idle' | 'connecting' | 'streaming' | 'paused' | 'finalizing' | 'completed' | 'error'

export interface LiveTranscriptSegment {
  id: string
  seqStart: number
  seqEnd: number
  startMs: number
  endMs: number
  text: string
  createdAt: number
}

export interface LiveTranscriptionState {
  status: LiveTranscriptionStatus
  mode: 'simulated' | 'backend'
  segments: LiveTranscriptSegment[]
  interimText: string
  interimStartMs: number | null
  chunksReceived: number
  wordCount: number
  error: string | null
}

export interface LiveTranscriptionTransport {
  start: () => void
  pushChunk: (chunk: AudioChunkEvent) => void
  pause: () => void
  resume: () => void
  finalize: () => Promise<LiveTranscriptSegment[]>
  cancel: () => void
  subscribe: (listener: (state: LiveTranscriptionState) => void) => () => void
  getSnapshot: () => LiveTranscriptionState
}

export const INITIAL_LIVE_TRANSCRIPTION_STATE: LiveTranscriptionState = {
  status: 'idle',
  mode: 'simulated',
  segments: [],
  interimText: '',
  interimStartMs: null,
  chunksReceived: 0,
  wordCount: 0,
  error: null,
}

export const AI_COMPUTING_SCRIPT_BLOCKS: readonly string[] = [
  'Bom, pessoal, vamos alinhar a arquitetura de transcrição em tempo real baseada em chunks contínuos de áudio.',
  'A ideia central é capturar janelas curtas pelo MediaRecorder e despachar cada segmento sem bloquear a captura principal.',
  'No motor de inferência local, o Whisper quantizado em INT8 consegue reduzir o consumo de memória mantendo excelente precisão.',
  'Quando operamos com streaming incremental, o controle de latência e backpressure nas filas distribuídas se torna essencial.',
  'Se um worker atrasar na decodificação, o buffer intermediário precisa absorver o pico sem descartar pacotes de áudio.',
  'Também avaliamos como o tamanho da janela de contexto dos LLMs impacta a geração do resumo executivo ao final da chamada.',
  'Em vez de reprocessar toda a gravação do zero, podemos consolidar blocos cronológicos e manter um estado incremental.',
  'Para validar a qualidade das respostas, definimos benchmarks objetivos comparando taxa de erro de palavras e coerência semântica.',
  'Outro ganho importante vem do caching de embeddings para trechos recorrentes de documentação técnica e decisões passadas.',
  'Com isso, a busca semântica entre reuniões responde em poucos milissegundos mesmo com milhares de segmentos indexados.',
  'Na camada de observabilidade, queremos rastrear o tempo entre a emissão do chunk no navegador e a chegada do texto parcial.',
  'Métricas de p95 e p99 ajudam a identificar rapidamente gargalos de I/O, serialização ou contenção na GPU.',
  'Sobre a experiência de uso, decidimos simplificar o fluxo ao vivo removendo identificadores artificiais de oradores na tela.',
  'O foco fica totalmente na leitura contínua por blocos com carimbo de tempo, deixando o acompanhamento da reunião muito mais limpo.',
  'Enquanto a API incremental definitiva do servidor é finalizada, o cliente já valida todo o ciclo de vida com transporte desacoplado.',
  'Bastará substituir o provedor simulado pela conexão real de streaming sem alterar o contexto global nem os componentes visuais.',
  'Também precisamos garantir que pausar e retomar a gravação preserve o estado exato da janela atual sem perda de palavras.',
  'Ao concluir a captura, o último trecho pendente deve ser consolidado imediatamente para que nada do fechamento se perca.',
  'Por fim, vale revisar os limites de memória do navegador em sessões longas para manter a rolagem fluida e responsiva.',
  'Com essa base pronta, conseguimos testar toda a jornada de gravação, revisão e envio para processamento com segurança.',
]

const WORDS_PER_CHUNK_BUDGET = 5
const REVEAL_INTERVAL_MS = 190
const CONNECTING_DELAY_MS = 250

function countWords(text: string): number {
  const trimmed = text.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

function computeTotalWords(
  segments: LiveTranscriptSegment[],
  interimText: string
): number {
  let total = 0
  for (const seg of segments) {
    total += countWords(seg.text)
  }
  total += countWords(interimText)
  return total
}

export function buildFullTranscriptText(
  segments: LiveTranscriptSegment[],
  interimText = ''
): string {
  const parts = segments.map((seg) => seg.text.trim()).filter(Boolean)
  const trimmedInterim = interimText.trim()
  if (trimmedInterim) {
    parts.push(trimmedInterim)
  }
  return parts.join('\n\n')
}

export class SimulatedLiveTranscriptionTransport implements LiveTranscriptionTransport {
  private state: LiveTranscriptionState = { ...INITIAL_LIVE_TRANSCRIPTION_STATE }
  private listeners = new Set<(state: LiveTranscriptionState) => void>()

  private connectTimer: ReturnType<typeof setTimeout> | null = null
  private revealTimer: ReturnType<typeof setInterval> | null = null

  private blockIndex = 0
  private blockWords: string[] = []
  private wordCursor = 0
  private allowedWordLimit = 0

  private currentBlockSeqStart: number | null = null
  private lastChunkSeqIndex = 0
  private currentBlockStartMs: number | null = null
  private lastChunkElapsedMs = 0

  private emit() {
    const snapshot = this.getSnapshot()
    this.listeners.forEach((listener) => listener(snapshot))
  }

  private clearTimers() {
    if (this.connectTimer) {
      clearTimeout(this.connectTimer)
      this.connectTimer = null
    }
    if (this.revealTimer) {
      clearInterval(this.revealTimer)
      this.revealTimer = null
    }
  }

  private loadBlock(index: number) {
    this.blockIndex = index % AI_COMPUTING_SCRIPT_BLOCKS.length
    this.blockWords = AI_COMPUTING_SCRIPT_BLOCKS[this.blockIndex].split(/\s+/)
    this.wordCursor = 0
    this.allowedWordLimit = 0
    this.currentBlockSeqStart = null
    this.currentBlockStartMs = null
  }

  private startRevealLoop() {
    if (this.revealTimer || this.state.status !== 'streaming') {
      return
    }

    this.revealTimer = setInterval(() => {
      if (this.state.status !== 'streaming') {
        if (this.revealTimer) {
          clearInterval(this.revealTimer)
          this.revealTimer = null
        }
        return
      }

      if (this.wordCursor >= this.allowedWordLimit) {
        if (this.revealTimer) {
          clearInterval(this.revealTimer)
          this.revealTimer = null
        }
        return
      }

      const step = this.allowedWordLimit - this.wordCursor > 3 ? 2 : 1
      this.wordCursor = Math.min(this.allowedWordLimit, this.wordCursor + step)
      const revealedText = this.blockWords.slice(0, this.wordCursor).join(' ')

      if (this.wordCursor >= this.blockWords.length) {
        this.consolidateCurrentBlock(revealedText)
      } else {
        this.state = {
          ...this.state,
          interimText: revealedText,
          interimStartMs: this.currentBlockStartMs ?? this.lastChunkElapsedMs,
          wordCount: computeTotalWords(this.state.segments, revealedText),
        }
        this.emit()
      }
    }, REVEAL_INTERVAL_MS)
  }

  private consolidateCurrentBlock(text: string) {
    const trimmed = text.trim()
    if (!trimmed) {
      this.loadBlock(this.blockIndex + 1)
      return
    }

    const startMs = this.currentBlockStartMs ?? this.lastChunkElapsedMs
    const endMs = Math.max(startMs, this.lastChunkElapsedMs)
    const seqStart = this.currentBlockSeqStart ?? this.lastChunkSeqIndex
    const seqEnd = Math.max(seqStart, this.lastChunkSeqIndex)

    const segment: LiveTranscriptSegment = {
      id: `seg-${seqStart}-${seqEnd}-${this.state.segments.length}`,
      seqStart,
      seqEnd,
      startMs,
      endMs,
      text: trimmed,
      createdAt: Date.now(),
    }

    const nextSegments = [...this.state.segments, segment]
    this.loadBlock(this.blockIndex + 1)

    this.state = {
      ...this.state,
      segments: nextSegments,
      interimText: '',
      interimStartMs: null,
      wordCount: computeTotalWords(nextSegments, ''),
    }
    this.emit()
  }

  start() {
    this.clearTimers()
    this.loadBlock(0)
    this.lastChunkSeqIndex = 0
    this.lastChunkElapsedMs = 0

    this.state = {
      ...INITIAL_LIVE_TRANSCRIPTION_STATE,
      status: 'connecting',
    }
    this.emit()

    this.connectTimer = setTimeout(() => {
      this.connectTimer = null
      if (this.state.status === 'connecting') {
        this.state = {
          ...this.state,
          status: 'streaming',
        }
        this.emit()
      }
    }, CONNECTING_DELAY_MS)
  }

  pushChunk(chunk: AudioChunkEvent) {
    if (
      this.state.status === 'idle' ||
      this.state.status === 'completed' ||
      this.state.status === 'finalizing' ||
      this.state.status === 'error'
    ) {
      return
    }

    const nextChunksReceived = this.state.chunksReceived + 1
    this.lastChunkSeqIndex = chunk.seqIndex
    this.lastChunkElapsedMs = chunk.elapsedMs

    if (this.currentBlockSeqStart === null) {
      this.currentBlockSeqStart = chunk.seqIndex
      this.currentBlockStartMs = Math.max(0, chunk.elapsedMs - 1000)
    }

    let nextStatus = this.state.status
    if (nextStatus === 'connecting') {
      if (this.connectTimer) {
        clearTimeout(this.connectTimer)
        this.connectTimer = null
      }
      nextStatus = 'streaming'
    }

    this.allowedWordLimit = Math.min(
      this.blockWords.length,
      this.allowedWordLimit + WORDS_PER_CHUNK_BUDGET
    )

    this.state = {
      ...this.state,
      status: nextStatus,
      chunksReceived: nextChunksReceived,
      interimStartMs: this.state.interimStartMs ?? this.currentBlockStartMs,
    }
    this.emit()

    if (nextStatus === 'streaming') {
      this.startRevealLoop()
    }
  }

  pause() {
    if (this.state.status !== 'streaming' && this.state.status !== 'connecting') {
      return
    }
    this.clearTimers()
    this.state = {
      ...this.state,
      status: 'paused',
    }
    this.emit()
  }

  resume() {
    if (this.state.status !== 'paused') {
      return
    }
    this.state = {
      ...this.state,
      status: 'streaming',
    }
    this.emit()
    if (this.wordCursor < this.allowedWordLimit) {
      this.startRevealLoop()
    }
  }

  async finalize(): Promise<LiveTranscriptSegment[]> {
    this.clearTimers()

    if (this.state.status === 'idle') {
      return []
    }

    this.state = {
      ...this.state,
      status: 'finalizing',
    }
    this.emit()

    const flushWordCount = Math.max(this.wordCursor, this.allowedWordLimit)
    const pendingText =
      flushWordCount > 0
        ? this.blockWords.slice(0, flushWordCount).join(' ').trim()
        : this.state.interimText.trim()

    let finalSegments = this.state.segments
    if (pendingText) {
      const startMs = this.currentBlockStartMs ?? this.lastChunkElapsedMs
      const endMs = Math.max(startMs, this.lastChunkElapsedMs)
      const seqStart = this.currentBlockSeqStart ?? this.lastChunkSeqIndex
      const seqEnd = Math.max(seqStart, this.lastChunkSeqIndex)

      const lastSegment: LiveTranscriptSegment = {
        id: `seg-${seqStart}-${seqEnd}-${finalSegments.length}`,
        seqStart,
        seqEnd,
        startMs,
        endMs,
        text: pendingText,
        createdAt: Date.now(),
      }
      finalSegments = [...finalSegments, lastSegment]
    }

    this.state = {
      ...this.state,
      status: 'completed',
      segments: finalSegments,
      interimText: '',
      interimStartMs: null,
      wordCount: computeTotalWords(finalSegments, ''),
    }
    this.emit()

    return finalSegments
  }

  cancel() {
    this.clearTimers()
    this.loadBlock(0)
    this.lastChunkSeqIndex = 0
    this.lastChunkElapsedMs = 0
    this.state = { ...INITIAL_LIVE_TRANSCRIPTION_STATE }
    this.emit()
  }

  subscribe(listener: (state: LiveTranscriptionState) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getSnapshot(): LiveTranscriptionState {
    return {
      ...this.state,
      segments: [...this.state.segments],
    }
  }
}

export function createLiveTranscriptionTransport(): LiveTranscriptionTransport {
  return new SimulatedLiveTranscriptionTransport()
}
