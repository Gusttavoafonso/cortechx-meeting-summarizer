import { ApiError, request } from '../api/client'

export type PartialState = {
  state: 'idle' | 'starting' | 'recording' | 'finishing' | 'completed' | 'failed'
  text: string
  revision: number
  processedSeconds: number
  capturedSeconds: number
  pendingChunks: number
  uploadedChunks: number
  error: string | null
}

type Reply = {
  state: 'recording' | 'finishing' | 'completed' | 'failed'
  text: string | null
  revision: number
  processed_seconds: number
  error: string | null
}

export const EMPTY_PARTIAL: PartialState = {
  state: 'idle', text: '', revision: -1, processedSeconds: 0,
  capturedSeconds: 0, pendingChunks: 0, uploadedChunks: 0, error: null,
}

/** Capture never awaits this bounded, ordered network queue. */
export class PartialTranscriptionClient {
  private readonly id = crypto.randomUUID()
  private readonly endpoint = `/partial-sessions/${this.id}`
  private value: PartialState = { ...EMPTY_PARTIAL, state: 'starting' }
  private queue: { sequence: number; blob: Blob }[] = []
  private queuedBytes = 0
  private sequence = 0
  private started = false
  private pumping = false
  private finishing = false
  private finishSent = false
  private closed = false
  private pollTimer: ReturnType<typeof setTimeout> | null = null
  private controllers = new Set<AbortController>()

  constructor(
    private options: { language: 'pt' | 'en' | 'es' | 'auto' },
    private onChange: (state: PartialState) => void
  ) {}

  private emit() {
    this.onChange({ ...this.value, pendingChunks: this.queue.length })
  }

  private async call<T>(path: string, options: RequestInit = {}): Promise<T> {
    for (let attempt = 0; ; attempt += 1) {
      if (this.closed) throw new Error('Sessão parcial encerrada')
      const controller = new AbortController()
      this.controllers.add(controller)
      const timeout = setTimeout(() => controller.abort(), 10_000)
      try {
        return await request<T>(path, { ...options, signal: controller.signal })
      } catch (error) {
        const transient = !(error instanceof ApiError) || error.status === 429 || error.status >= 500
        if (this.closed || !transient || attempt >= 3) throw error
      } finally {
        clearTimeout(timeout)
        this.controllers.delete(controller)
      }
      await new Promise(resolve => setTimeout(resolve, 500 * 2 ** attempt))
    }
  }

  private async remove() {
    // Keep cleanup independent of cancelled upload controllers.
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 10_000)
    try {
      await request(this.endpoint, { method: 'DELETE', signal: controller.signal })
    } catch {
      // A disconnected client expires server-side; final recording is unaffected.
    } finally {
      clearTimeout(timeout)
    }
  }

  async start() {
    this.emit()
    try {
      const response = await this.call<Reply>('/partial-sessions', {
        method: 'POST', body: JSON.stringify({ id: this.id, ...this.options }),
      })
      if (this.closed) {
        void this.remove()
        return
      }
      this.started = true
      this.accept(response)
      if (!this.closed) {
        void this.poll()
        void this.pump()
      }
    } catch (error) {
      this.fail(error)
    }
  }

  captureTime(ms: number) {
    this.value.capturedSeconds = ms / 1000
  }

  enqueue(blob: Blob) {
    if (this.closed || blob.size === 0) return
    if ((this.sequence === 0 && !blob.type.toLowerCase().includes('webm')) ||
        blob.size > 1024 * 1024 || this.queuedBytes + blob.size > 8 * 1024 * 1024 ||
        this.queue.length >= 120 || this.sequence >= 7200) {
      this.fail(new Error('Parciais exigem WebM/Opus e fila limitada. Limite de envio excedido ou formato incompatível.'))
      return
    }
    this.queue.push({ sequence: this.sequence++, blob })
    this.queuedBytes += blob.size
    this.emit()
    void this.pump()
  }

  finish() {
    if (this.closed) return
    this.finishing = true
    this.value.state = 'finishing'
    this.emit()
    void this.pump()
  }

  private async pump() {
    if (!this.started || this.pumping || this.closed) return
    this.pumping = true
    try {
      while (this.queue.length && !this.closed) {
        const item = this.queue[0]
        await this.call(`${this.endpoint}/chunks/${item.sequence}`, {
          method: 'PUT', body: item.blob,
          headers: { 'Content-Type': item.blob.type || 'application/octet-stream' },
        })
        if (this.closed) return
        this.queue.shift()
        this.queuedBytes -= item.blob.size
        this.value.uploadedChunks += 1
        this.emit()
      }
      if (this.finishing && !this.finishSent && !this.closed) {
        const response = await this.call<Reply>(`${this.endpoint}/finish`, {
          method: 'POST', body: JSON.stringify({ chunk_count: this.sequence }),
        })
        this.finishSent = true
        this.accept(response)
      }
    } catch (error) {
      this.fail(error)
    } finally {
      this.pumping = false
    }
  }

  private accept(response: Reply) {
    if (this.closed || response.revision < this.value.revision) return
    this.value.revision = response.revision
    if (response.text !== null) this.value.text = response.text
    this.value.processedSeconds = response.processed_seconds
    this.value.state = this.finishing && response.state === 'recording' ? 'finishing' : response.state
    if (response.state === 'failed') {
      this.fail(new Error(response.error || 'Falha no decoder/transcritor local parcial.'), false)
      return
    }
    if (response.state === 'completed') this.closeNetwork()
    this.emit()
  }

  private async poll() {
    if (this.closed) return
    try {
      const response = await this.call<Reply>(`${this.endpoint}?after=${this.value.revision}`)
      this.accept(response)
    } catch (error) {
      this.fail(error)
    }
    if (!this.closed) this.pollTimer = setTimeout(() => void this.poll(), 1000)
  }

  private closeNetwork() {
    this.closed = true
    if (this.pollTimer !== null) clearTimeout(this.pollTimer)
    this.pollTimer = null
    this.controllers.forEach(controller => controller.abort())
    this.queue = []
    this.queuedBytes = 0
  }

  private fail(error: unknown, cleanup = true) {
    if (this.closed) return
    this.closeNetwork()
    this.value.state = 'failed'
    this.value.error = `${error instanceof Error ? error.message : 'Parciais indisponíveis.'} A gravação e o envio final continuam disponíveis.`
    this.emit()
    if (cleanup) void this.remove()
  }

  cancel() {
    this.closeNetwork()
    void this.remove()
    this.value = { ...EMPTY_PARTIAL }
    this.emit()
  }
}
