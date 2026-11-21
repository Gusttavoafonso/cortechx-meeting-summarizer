import type { AudioChunkEvent } from './audioRecorder'
import { PartialState, PartialTranscriptionClient } from './partialTranscription'

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
  pendingChunks?: number
  lagSeconds?: number
  revision?: number
  isRevealing?: boolean
  error: string | null
}

export interface LiveTranscriptionTransport {
  start: () => void
  pushChunk: (chunk: AudioChunkEvent) => void
  endSegment?: (epochId: number) => void
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
  isRevealing: false,
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
const CONNECTING_DELAY_MS = 250

function computeHumanizedWordDelayMs(
  prevWord: string,
  nextWord: string,
  backlog: number,
  isFinishing: boolean
): number {
  if (isFinishing) {
    let finishingDelay = backlog > 30 ? 32 : 52
    if (/[.!?…]$/.test(prevWord)) {
      finishingDelay += 40
    }
    return Math.round(finishingDelay)
  }

  let base: number
  if (backlog <= 12) {
    base = 235
  } else if (backlog <= 24) {
    base = 235 - ((backlog - 12) / 12) * 105
  } else {
    base = Math.max(65, 130 - (backlog - 24) * 3)
  }

  const coreWord = nextWord.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
  const coreLen = coreWord.length
  const lengthFactor = coreLen <= 3 ? 0.72 : coreLen >= 9 ? 1.18 : 1.0

  let punctuationPause = 0
  if (/[.!?…]$/.test(prevWord)) {
    punctuationPause = backlog > 18 ? 110 : 270
  } else if (/[,;:]$/.test(prevWord)) {
    punctuationPause = backlog > 18 ? 60 : 140
  }

  const jitter = 0.9 + Math.random() * 0.2
  const total = (base * lengthFactor + punctuationPause) * jitter
  return Math.round(Math.min(620, Math.max(40, total)))
}

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
  private revealTimer: ReturnType<typeof setTimeout> | null = null

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
      clearTimeout(this.revealTimer)
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
    const canReveal = this.state.status === 'streaming' || this.state.status === 'paused'
    if (
      this.revealTimer !== null ||
      !canReveal ||
      this.wordCursor >= this.allowedWordLimit
    ) {
      return
    }

    const backlog = this.allowedWordLimit - this.wordCursor
    const prevWord = this.wordCursor > 0 ? this.blockWords[this.wordCursor - 1] : ''
    const nextWord = this.blockWords[this.wordCursor] ?? ''
    const delayMs = computeHumanizedWordDelayMs(prevWord, nextWord, backlog, false)

    this.revealTimer = setTimeout(() => {
      this.revealTimer = null
      const stillCanReveal =
        this.state.status === 'streaming' || this.state.status === 'paused'
      if (!stillCanReveal || this.wordCursor >= this.allowedWordLimit) {
        return
      }

      this.wordCursor = Math.min(this.allowedWordLimit, this.wordCursor + 1)
      const revealedText = this.blockWords.slice(0, this.wordCursor).join(' ')
      const hasMore = this.wordCursor < this.allowedWordLimit

      if (this.wordCursor >= this.blockWords.length) {
        this.consolidateCurrentBlock(revealedText)
      } else {
        this.state = {
          ...this.state,
          interimText: revealedText,
          interimStartMs: this.currentBlockStartMs ?? this.lastChunkElapsedMs,
          wordCount: computeTotalWords(this.state.segments, revealedText),
          isRevealing: hasMore,
        }
        this.emit()
      }

      const continueReveal =
        this.state.status === 'streaming' || this.state.status === 'paused'
      if (continueReveal && this.wordCursor < this.allowedWordLimit) {
        this.startRevealLoop()
      }
    }, delayMs)
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
      isRevealing: false,
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
      isRevealing: this.wordCursor < this.allowedWordLimit,
    }
    this.emit()

    if (nextStatus === 'streaming' || nextStatus === 'paused') {
      this.startRevealLoop()
    }
  }

  pause() {
    if (this.state.status !== 'streaming' && this.state.status !== 'connecting') {
      return
    }
    if (this.connectTimer) {
      clearTimeout(this.connectTimer)
      this.connectTimer = null
    }
    const hasPending = this.wordCursor < this.allowedWordLimit
    this.state = {
      ...this.state,
      status: 'paused',
      isRevealing: hasPending,
    }
    this.emit()
    if (hasPending) {
      this.startRevealLoop()
    }
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

function splitBackendTranscript(
  fullText: string,
  processedSeconds: number,
  isFinal: boolean,
  segmentStartMsCache: number[]
): {
  segments: LiveTranscriptSegment[]
  interimText: string
  interimStartMs: number | null
} {
  const cleaned = fullText.trim()
  if (!cleaned) {
    return { segments: [], interimText: '', interimStartMs: null }
  }

  const rawSentences = cleaned.split(/(?<=[.!?])\s+/).filter(Boolean)
  const blocks: string[] = []
  let current = ''

  for (const sentence of rawSentences) {
    if (!current) {
      current = sentence
    } else if (countWords(current) + countWords(sentence) <= 24) {
      current = `${current} ${sentence}`
    } else {
      blocks.push(current)
      current = sentence
    }
  }
  if (current) {
    blocks.push(current)
  }

  let interimText = ''
  let confirmedBlocks = blocks

  if (!isFinal && blocks.length > 0) {
    interimText = blocks[blocks.length - 1]
    confirmedBlocks = blocks.slice(0, -1)
  }

  const currentTimeMs = Math.max(0, Math.round(processedSeconds * 1000))

  const segments: LiveTranscriptSegment[] = confirmedBlocks.map((text, idx) => {
    if (segmentStartMsCache[idx] === undefined) {
      const prevStart = idx > 0 ? (segmentStartMsCache[idx - 1] ?? 0) : 0
      const anchoredMs = idx === 0 ? Math.max(0, currentTimeMs - 6000) : currentTimeMs
      segmentStartMsCache[idx] = Math.max(prevStart, anchoredMs)
    }
    const startMs = segmentStartMsCache[idx]
    const nextStart = segmentStartMsCache[idx + 1]
    const endMs =
      nextStart !== undefined
        ? Math.max(startMs, nextStart)
        : Math.max(startMs, currentTimeMs)
    return {
      id: `backend-seg-${idx}`,
      seqStart: idx,
      seqEnd: idx,
      startMs,
      endMs,
      text,
      createdAt: Date.now(),
    }
  })

  let interimStartMs: number | null = null
  if (interimText) {
    const interimIdx = confirmedBlocks.length
    if (segmentStartMsCache[interimIdx] === undefined) {
      const prevStart = interimIdx > 0 ? (segmentStartMsCache[interimIdx - 1] ?? 0) : 0
      const anchoredMs =
        interimIdx === 0 ? Math.max(0, currentTimeMs - 6000) : currentTimeMs
      segmentStartMsCache[interimIdx] = Math.max(prevStart, anchoredMs)
    }
    interimStartMs = segmentStartMsCache[interimIdx]
  }
  return { segments, interimText, interimStartMs }
}

interface BackendEpoch {
  epochId: number
  client: PartialTranscriptionClient
  words: string[]
  enqueuedChunks: number
  uploadedChunks: number
  pendingChunks: number
  processedSeconds: number
  capturedSeconds: number
  revision: number
  state: PartialState['state']
  error: string | null
  ended: boolean
}

export class BackendLiveTranscriptionTransport implements LiveTranscriptionTransport {
  private readonly language: 'pt' | 'en' | 'es' | 'auto'
  private state: LiveTranscriptionState = {
    ...INITIAL_LIVE_TRANSCRIPTION_STATE,
    mode: 'backend',
  }
  private listeners = new Set<(state: LiveTranscriptionState) => void>()
  private epochs: BackendEpoch[] = []
  private epochsById = new Map<number, BackendEpoch>()
  private currentEpochId = 0
  private locallyPaused = false
  private recordingStopped = false

  private targetWords: string[] = []
  private displayedWordCount = 0
  private revealTimer: ReturnType<typeof setTimeout> | null = null
  private segmentStartMsCache: number[] = []

  constructor(options: { language?: 'pt' | 'en' | 'es' | 'auto' } = {}) {
    this.language = options.language ?? 'pt'
  }

  private emit() {
    const snapshot = this.getSnapshot()
    this.listeners.forEach((listener) => listener(snapshot))
  }

  private clearRevealTimer() {
    if (this.revealTimer !== null) {
      clearTimeout(this.revealTimer)
      this.revealTimer = null
    }
  }

  private createEpoch(epochId: number): BackendEpoch {
    const existing = this.epochsById.get(epochId)
    if (existing) {
      return existing
    }

    const epoch: BackendEpoch = {
      epochId,
      client: null as unknown as PartialTranscriptionClient,
      words: [],
      enqueuedChunks: 0,
      uploadedChunks: 0,
      pendingChunks: 0,
      processedSeconds: 0,
      capturedSeconds: 0,
      revision: -1,
      state: 'starting',
      error: null,
      ended: false,
    }

    const client = new PartialTranscriptionClient(
      { language: this.language },
      (partial) => {
        this.handleEpochUpdate(epoch, partial)
      }
    )
    epoch.client = client

    this.epochs.push(epoch)
    this.epochsById.set(epochId, epoch)
    void client.start()
    return epoch
  }

  private recomputeAndEmit() {
    const nextWords = this.epochs.flatMap((epoch) => epoch.words)
    this.targetWords = nextWords
    this.displayedWordCount = Math.min(this.displayedWordCount, nextWords.length)

    let totalUploaded = 0
    let totalPending = 0
    let totalProcessedSeconds = 0
    let totalCapturedSeconds = 0
    let totalRevision = 0

    for (const epoch of this.epochs) {
      totalUploaded += epoch.uploadedChunks
      totalPending += epoch.pendingChunks
      totalProcessedSeconds += epoch.processedSeconds
      totalCapturedSeconds = Math.max(totalCapturedSeconds, epoch.capturedSeconds)
      if (epoch.revision > 0) {
        totalRevision += epoch.revision
      }
    }

    const hasFinishingEpoch = this.epochs.some((epoch) => epoch.state === 'finishing')
    const hasActiveEpoch = this.epochs.some(
      (epoch) =>
        epoch.state === 'recording' ||
        epoch.state === 'starting' ||
        epoch.state === 'finishing'
    )
    const latestError =
      [...this.epochs].reverse().find((epoch) => epoch.error)?.error ?? null
    const currentEpoch =
      this.epochsById.get(this.currentEpochId) ?? this.epochs[this.epochs.length - 1]

    let status: LiveTranscriptionStatus
    if (this.recordingStopped) {
      if (hasActiveEpoch || this.displayedWordCount < this.targetWords.length) {
        status = 'finalizing'
      } else if (
        this.targetWords.length === 0 &&
        this.epochs.length > 0 &&
        this.epochs.every((epoch) => epoch.state === 'failed')
      ) {
        status = 'error'
      } else {
        status = 'completed'
      }
    } else if (this.locallyPaused) {
      status = 'paused'
    } else if (
      !currentEpoch ||
      (currentEpoch.state === 'starting' && this.targetWords.length === 0)
    ) {
      status = 'connecting'
    } else if (currentEpoch.state === 'failed') {
      status = 'error'
    } else {
      status = 'streaming'
    }

    const displayedText = this.targetWords.slice(0, this.displayedWordCount).join(' ')
    const isFinal = status === 'completed' || status === 'error'
    const { segments, interimText, interimStartMs } = splitBackendTranscript(
      displayedText,
      totalProcessedSeconds,
      isFinal,
      this.segmentStartMsCache
    )
    const lagSeconds =
      totalCapturedSeconds > 0
        ? Math.max(0, Math.round(totalCapturedSeconds - totalProcessedSeconds))
        : undefined

    const isRevealing =
      (this.displayedWordCount < this.targetWords.length || hasFinishingEpoch) &&
      status !== 'error'

    this.state = {
      status,
      mode: 'backend',
      segments,
      interimText,
      interimStartMs,
      chunksReceived: totalUploaded,
      wordCount: this.displayedWordCount,
      pendingChunks: totalPending,
      lagSeconds,
      revision: totalRevision,
      isRevealing,
      error: latestError,
    }
    this.emit()
  }

  private scheduleNextWordReveal() {
    if (
      this.revealTimer !== null ||
      this.epochs.length === 0 ||
      this.state.status === 'idle' ||
      this.state.status === 'error' ||
      this.displayedWordCount >= this.targetWords.length
    ) {
      return
    }

    const backlog = this.targetWords.length - this.displayedWordCount
    const isFinishing = this.recordingStopped
    const prevWord =
      this.displayedWordCount > 0 ? this.targetWords[this.displayedWordCount - 1] : ''
    const nextWord = this.targetWords[this.displayedWordCount] ?? ''
    const delayMs = computeHumanizedWordDelayMs(prevWord, nextWord, backlog, isFinishing)

    this.revealTimer = setTimeout(() => {
      this.revealTimer = null
      if (
        this.epochs.length === 0 ||
        this.state.status === 'idle' ||
        this.state.status === 'error'
      ) {
        return
      }
      if (this.displayedWordCount < this.targetWords.length) {
        this.displayedWordCount += 1
        this.recomputeAndEmit()
      }
      if (this.displayedWordCount < this.targetWords.length) {
        this.scheduleNextWordReveal()
      }
    }, delayMs)
  }

  private handleEpochUpdate(epoch: BackendEpoch, partial: PartialState) {
    if (!this.epochsById.has(epoch.epochId)) {
      return
    }

    const trimmed = partial.text.trim()
    epoch.words = trimmed ? trimmed.split(/\s+/) : []
    epoch.uploadedChunks = partial.uploadedChunks
    epoch.pendingChunks = partial.pendingChunks
    epoch.processedSeconds = partial.processedSeconds
    epoch.capturedSeconds = partial.capturedSeconds
    epoch.revision = partial.revision
    epoch.state = partial.state
    epoch.error = partial.error

    this.recomputeAndEmit()

    if (
      this.displayedWordCount < this.targetWords.length &&
      this.state.status !== 'error' &&
      this.state.status !== 'idle'
    ) {
      if (this.recordingStopped) {
        this.clearRevealTimer()
      }
      this.scheduleNextWordReveal()
    } else if (this.displayedWordCount >= this.targetWords.length) {
      this.clearRevealTimer()
    }
  }

  start() {
    this.clearRevealTimer()
    for (const epoch of this.epochs) {
      epoch.client.cancel()
    }
    this.epochs = []
    this.epochsById.clear()
    this.currentEpochId = 0
    this.locallyPaused = false
    this.recordingStopped = false
    this.targetWords = []
    this.displayedWordCount = 0
    this.segmentStartMsCache = []
    this.state = {
      ...INITIAL_LIVE_TRANSCRIPTION_STATE,
      mode: 'backend',
      status: 'connecting',
    }
    this.emit()

    this.createEpoch(0)
  }

  pushChunk(chunk: AudioChunkEvent) {
    let epoch = this.epochsById.get(chunk.epochId)
    if (!epoch) {
      epoch = this.createEpoch(chunk.epochId)
    }
    if (epoch.ended) return
    epoch.enqueuedChunks += 1
    epoch.client.enqueue(chunk.blob)
    epoch.client.captureTime(chunk.elapsedMs)
  }

  endSegment(epochId: number) {
    const epoch = this.epochsById.get(epochId)
    if (!epoch || epoch.ended) return
    epoch.ended = true

    if (epoch.enqueuedChunks === 0) {
      epoch.client.cancel()
      epoch.state = 'completed'
    } else {
      epoch.client.finish()
    }

    this.recomputeAndEmit()
  }

  pause() {
    this.locallyPaused = true
    this.recomputeAndEmit()
    if (this.displayedWordCount < this.targetWords.length) {
      this.scheduleNextWordReveal()
    }
  }

  resume() {
    this.locallyPaused = false
    this.recordingStopped = false
    this.currentEpochId += 1
    this.createEpoch(this.currentEpochId)
    this.recomputeAndEmit()
    this.scheduleNextWordReveal()
  }

  async finalize(): Promise<LiveTranscriptSegment[]> {
    this.locallyPaused = false
    this.recordingStopped = true

    for (const epoch of this.epochs) {
      if (!epoch.ended) {
        this.endSegment(epoch.epochId)
      }
    }

    if (this.displayedWordCount < this.targetWords.length) {
      this.clearRevealTimer()
      this.scheduleNextWordReveal()
    }
    this.recomputeAndEmit()
    return [...this.state.segments]
  }

  cancel() {
    this.clearRevealTimer()
    const activeEpochs = [...this.epochs]
    this.epochs = []
    this.epochsById.clear()
    this.currentEpochId = 0
    this.locallyPaused = false
    this.recordingStopped = false
    this.targetWords = []
    this.displayedWordCount = 0
    this.segmentStartMsCache = []
    for (const epoch of activeEpochs) {
      epoch.client.cancel()
    }
    this.state = {
      ...INITIAL_LIVE_TRANSCRIPTION_STATE,
      mode: 'backend',
    }
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

export function createLiveTranscriptionTransport(options?: {
  language?: 'pt' | 'en' | 'es' | 'auto'
}): LiveTranscriptionTransport {
  if (import.meta.env.VITE_LIVE_TRANSCRIPTION_MODE === 'simulated') {
    return new SimulatedLiveTranscriptionTransport()
  }
  return new BackendLiveTranscriptionTransport({ language: options?.language ?? 'pt' })
}
