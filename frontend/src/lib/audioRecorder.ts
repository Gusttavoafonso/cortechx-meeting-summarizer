/**
 * Zumo Audio Recorder Engine (TypeScript / Web Audio API)
 * Captura simultânea do microfone e do áudio do sistema/abas do navegador sem emojis.
 */

export type CaptureMode = 'both' | 'mic_only'

export interface RecordingResult {
  blob: Blob
  file: File
  durationMs: number
  mimeType: string
}

export interface AudioLevels {
  micLevel: number
  systemLevel: number
}

export interface AudioChunkEvent {
  blob: Blob
  seqIndex: number
  elapsedMs: number
  sizeBytes: number
  mimeType: string
}

export class AudioRecorderEngine {
  private audioContext: AudioContext | null = null
  private micStream: MediaStream | null = null
  private systemStream: MediaStream | null = null
  private destinationNode: MediaStreamAudioDestinationNode | null = null
  private mediaRecorder: MediaRecorder | null = null
  private recordedChunks: Blob[] = []

  private micAnalyser: AnalyserNode | null = null
  private systemAnalyser: AnalyserNode | null = null
  private micDataArray: Uint8Array | null = null
  private systemDataArray: Uint8Array | null = null

  public isRecording = false
  public isPaused = false
  private startTime = 0
  private elapsedTime = 0
  private chunkSeq = 0
  private timerInterval: ReturnType<typeof setInterval> | null = null

  public onTick?: (elapsedMs: number) => void
  public onStateChange?: (state: 'recording' | 'paused' | 'stopped') => void
  public onSourceEnded?: (source: 'system' | 'mic') => void
  public onChunk?: (chunk: AudioChunkEvent) => void

  static isSupported(): boolean {
    return !!(
      typeof navigator !== 'undefined' &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === 'function' &&
      typeof navigator.mediaDevices.getDisplayMedia === 'function' &&
      (window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext) &&
      typeof MediaRecorder !== 'undefined'
    )
  }

  async start({
    mode = 'both',
    onTick,
    onStateChange,
    onSourceEnded,
    onChunk,
  }: {
    mode?: CaptureMode
    onTick?: (elapsedMs: number) => void
    onStateChange?: (state: 'recording' | 'paused' | 'stopped') => void
    onSourceEnded?: (source: 'system' | 'mic') => void
    onChunk?: (chunk: AudioChunkEvent) => void
  } = {}): Promise<void> {
    if (this.isRecording) {
      throw new Error('A gravação já está em andamento.')
    }

    this.onTick = onTick
    this.onStateChange = onStateChange
    this.onSourceEnded = onSourceEnded
    this.onChunk = onChunk
    this.recordedChunks = []
    this.chunkSeq = 0

    // 1. Capturar Áudio da Aba / Sistema PRIMEIRO (se modo 'both') para preservar o user gesture do clique
    if (mode === 'both') {
      try {
        this.systemStream = await navigator.mediaDevices.getDisplayMedia({
          video: {
            displaySurface: 'browser',
          },
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
        })
      } catch (err) {
        this.cleanup()
        if (err instanceof Error && err.name === 'NotAllowedError') {
          throw new Error('Compartilhamento de tela/aba cancelado pelo usuário.')
        }
        throw new Error(
          `Falha ao selecionar áudio da aba: ${err instanceof Error ? err.message : String(err)}`
        )
      }

      const systemAudioTracks = this.systemStream.getAudioTracks()
      if (!systemAudioTracks || systemAudioTracks.length === 0) {
        this.cleanup()
        throw new Error(
          'Nenhum áudio detectado na seleção. Certifique-se de marcar a opção "Compartilhar áudio da aba" ao selecionar a janela no navegador.'
        )
      }
    }

    // 2. Capturar Microfone
    try {
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      })
    } catch (err) {
      this.cleanup()
      throw new Error(
        `Permissão de microfone negada ou dispositivo indisponível: ${err instanceof Error ? err.message : String(err)}`
      )
    }

    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext
    this.audioContext = new AudioContextClass({ latencyHint: 'interactive' })
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume()
    }

    this.destinationNode = this.audioContext.createMediaStreamDestination()

    const micSource = this.audioContext.createMediaStreamSource(this.micStream)
    this.micAnalyser = this.audioContext.createAnalyser()
    this.micAnalyser.fftSize = 256
    this.micDataArray = new Uint8Array(this.micAnalyser.frequencyBinCount)

    const micGain = this.audioContext.createGain()
    micGain.gain.value = 1.0

    micSource.connect(this.micAnalyser)
    this.micAnalyser.connect(micGain)
    micGain.connect(this.destinationNode)

    // 3. Conectar Áudio da Aba / Sistema ao mixer (se modo 'both')
    if (mode === 'both' && this.systemStream) {
      const systemAudioTracks = this.systemStream.getAudioTracks()

      const handleSystemEnded = () => {
        if (this.isRecording) {
          if (this.onSourceEnded) {
            this.onSourceEnded('system')
          }
        }
      }

      this.systemStream.getVideoTracks().forEach((track) => {
        track.onended = handleSystemEnded
      })
      systemAudioTracks.forEach((track) => {
        track.onended = handleSystemEnded
      })

      const systemAudioStream = new MediaStream(systemAudioTracks)
      const systemSource = this.audioContext.createMediaStreamSource(systemAudioStream)

      this.systemAnalyser = this.audioContext.createAnalyser()
      this.systemAnalyser.fftSize = 256
      this.systemDataArray = new Uint8Array(this.systemAnalyser.frequencyBinCount)

      const systemGain = this.audioContext.createGain()
      systemGain.gain.value = 1.0

      systemSource.connect(this.systemAnalyser)
      this.systemAnalyser.connect(systemGain)
      systemGain.connect(this.destinationNode)
    }

    // 3. MediaRecorder
    const mimeTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ]

    let selectedMime = ''
    for (const mime of mimeTypes) {
      if (MediaRecorder.isTypeSupported(mime)) {
        selectedMime = mime
        break
      }
    }

    const options: MediaRecorderOptions = selectedMime
      ? { mimeType: selectedMime, audioBitsPerSecond: 128000 }
      : {}
    this.mediaRecorder = new MediaRecorder(this.destinationNode.stream, options)

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.recordedChunks.push(event.data)
        const elapsedMs =
          this.startTime > 0 ? Math.max(0, Date.now() - this.startTime) : 0
        try {
          this.onChunk?.({
            blob: event.data,
            seqIndex: this.chunkSeq++,
            elapsedMs,
            sizeBytes: event.data.size,
            mimeType: this.mediaRecorder?.mimeType || selectedMime || 'audio/webm',
          })
        } catch {
          // A partial callback must never break capture or the complete audio file.
        }
      }
    }

    this.mediaRecorder.start(1000)
    this.isRecording = true
    this.isPaused = false
    this.startTime = Date.now()
    this.elapsedTime = 0

    this.startTimer()
    if (this.onStateChange) this.onStateChange('recording')
  }

  private startTimer() {
    this.stopTimer()
    this.timerInterval = setInterval(() => {
      if (this.isRecording && !this.isPaused) {
        this.elapsedTime = Date.now() - this.startTime
        if (this.onTick) this.onTick(this.elapsedTime)
      }
    }, 250)
  }

  private stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval)
      this.timerInterval = null
    }
  }

  pause() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      try {
        this.mediaRecorder.requestData()
      } catch {
        // Alguns navegadores podem ignorar requestData imediatamente antes de pause
      }
      this.mediaRecorder.pause()
      this.isPaused = true
      if (this.onStateChange) this.onStateChange('paused')
    }
  }

  resume() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
      this.mediaRecorder.resume()
      this.isPaused = false
      this.startTime = Date.now() - this.elapsedTime
      if (this.onStateChange) this.onStateChange('recording')
    }
  }

  async stop({
    userId = 1,
  }: { userId?: number | string } = {}): Promise<RecordingResult> {
    if (!this.isRecording) {
      throw new Error('Nenhuma gravação em andamento.')
    }

    this.stopTimer()

    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        this.cleanup()
        return reject(new Error('Gravador não inicializado.'))
      }

      this.mediaRecorder.onerror = (e) => {
        this.cleanup()
        reject(e)
      }

      this.mediaRecorder.onstop = () => {
        const mimeType = this.mediaRecorder?.mimeType || 'audio/webm'
        const blob = new Blob(this.recordedChunks, { type: mimeType })
        const durationMs = this.elapsedTime
        const ext = mimeType.includes('ogg')
          ? 'ogg'
          : mimeType.includes('mp4')
            ? 'm4a'
            : 'webm'

        const now = new Date()
        const pad = (n: number) => String(n).padStart(2, '0')
        const formattedDate = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
        const fileName = `gravacao-u${userId}-${formattedDate}.${ext}`
        const file = new File([blob], fileName, { type: mimeType })

        this.cleanup()
        if (this.onStateChange) this.onStateChange('stopped')

        resolve({ blob, file, durationMs, mimeType })
      }

      try {
        this.mediaRecorder.stop()
      } catch (err) {
        this.cleanup()
        reject(err)
      }
    })
  }

  getAudioLevels(): AudioLevels {
    let micLevel = 0
    let systemLevel = 0

    if (this.micAnalyser && this.micDataArray) {
      this.micAnalyser.getByteFrequencyData(this.micDataArray)
      let sum = 0
      for (let i = 0; i < this.micDataArray.length; i++) {
        sum += this.micDataArray[i]
      }
      micLevel = Math.min(1.0, sum / this.micDataArray.length / 128)
    }

    if (this.systemAnalyser && this.systemDataArray) {
      this.systemAnalyser.getByteFrequencyData(this.systemDataArray)
      let sum = 0
      for (let i = 0; i < this.systemDataArray.length; i++) {
        sum += this.systemDataArray[i]
      }
      systemLevel = Math.min(1.0, sum / this.systemDataArray.length / 128)
    }

    return { micLevel, systemLevel }
  }

  private cleanupStreams() {
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop())
      this.micStream = null
    }
    if (this.systemStream) {
      this.systemStream.getTracks().forEach((track) => track.stop())
      this.systemStream = null
    }
  }

  cleanup() {
    this.stopTimer()
    const recorder = this.mediaRecorder
    if (recorder) {
      recorder.ondataavailable = null
      recorder.onstop = null
      recorder.onerror = null
      if (recorder.state !== 'inactive') {
        try {
          recorder.stop()
        } catch {
          // Ignora erro se o recorder já estiver encerrado
        }
      }
    }
    this.onChunk = undefined
    this.recordedChunks = []
    this.isRecording = false
    this.isPaused = false
    this.chunkSeq = 0
    this.cleanupStreams()

    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        this.audioContext.close()
      } catch {
        // Ignora erro ao fechar contexto
      }
      this.audioContext = null
    }

    this.micAnalyser = null
    this.systemAnalyser = null
    this.mediaRecorder = null
  }
}
