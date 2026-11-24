import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { useAuth } from '../contexts/AuthContext'

const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm']
const MAX_BYTES = 16 * 1024 * 1024
const MAX_CHUNK_BYTES = 1024 * 1024
const MAX_SECONDS = 90

type Status = 'idle' | 'requesting' | 'recording' | 'stopping' | 'uploading' | 'done' | 'error'
type DecodeResult = {
  chunks_received: number
  bytes_received: number
  sample_rate: number
  duration_seconds: number
  windows: {
    index: number
    start_sample: number
    end_sample: number
    start_seconds: number
    end_seconds: number
    duration_seconds: number
  }[]
}

const STATUS_LABELS: Record<Status, string> = {
  idle: 'Pronto para gravar',
  requesting: 'Aguardando permissão do microfone',
  recording: 'Gravando microfone',
  stopping: 'Finalizando o último Blob',
  uploading: 'Enviando chunks e decodificando após upload',
  done: 'Decodificação concluída',
  error: 'Falha no diagnóstico',
}

export const IncrementalAudioPage: React.FC = () => {
  const { user, isLoading } = useAuth()
  const [status, setStatus] = useState<Status>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [captured, setCaptured] = useState(0)
  const [sent, setSent] = useState(0)
  const [bytes, setBytes] = useState(0)
  const [actualMime, setActualMime] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState<DecodeResult | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)
  const uploadRef = useRef<AbortController | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const bytesRef = useRef(0)
  const sessionRef = useRef(0)
  const supported = MIME_TYPES.map(mime => ({
    mime,
    supported: typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime),
  }))
  const preferredMime = supported.find(item => item.supported)?.mime
  const busy = ['requesting', 'recording', 'stopping', 'uploading'].includes(status)

  const release = useCallback(() => {
    sessionRef.current += 1
    uploadRef.current?.abort()
    uploadRef.current = null
    if (timerRef.current !== null) window.clearInterval(timerRef.current)
    timerRef.current = null
    const recorder = recorderRef.current
    recorderRef.current = null
    if (recorder) {
      recorder.ondataavailable = null
      recorder.onstop = null
      recorder.onerror = null
      if (recorder.state !== 'inactive') recorder.stop()
    }
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    chunksRef.current = []
    bytesRef.current = 0
  }, [])

  useEffect(() => release, [release])

  const clear = () => {
    release()
    setStatus('idle')
    setElapsed(0)
    setCaptured(0)
    setSent(0)
    setBytes(0)
    setActualMime('')
    setError('')
    setResult(null)
  }

  const start = async () => {
    clear()
    const session = sessionRef.current
    if (!preferredMime || !navigator.mediaDevices?.getUserMedia) {
      setError('WebM/Opus ou microfone indisponível. Use um navegador compatível em HTTPS ou localhost.')
      setStatus('error')
      return
    }
    setStatus('requesting')
    const fail = (message: string) => {
      if (session !== sessionRef.current) return
      release()
      setError(message)
      setStatus('error')
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      if (session !== sessionRef.current) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      streamRef.current = stream
      const recorder = new MediaRecorder(stream, {
        mimeType: preferredMime,
        audioBitsPerSecond: 64_000,
      })
      recorderRef.current = recorder
      setActualMime(recorder.mimeType)
      const started = performance.now()
      recorder.ondataavailable = event => {
        if (session !== sessionRef.current || event.data.size === 0) return
        if (event.data.size > MAX_CHUNK_BYTES || bytesRef.current + event.data.size > MAX_BYTES || chunksRef.current.length >= 120) {
          fail('Gravação excedeu 1 MiB por chunk, 16 MiB no total ou 120 chunks. Limpe e grave novamente.')
          return
        }
        chunksRef.current.push(event.data)
        bytesRef.current += event.data.size
        setCaptured(chunksRef.current.length)
        setBytes(bytesRef.current)
      }
      recorder.onerror = () => fail('O navegador interrompeu a gravação. Limpe e tente novamente.')
      recorder.onstop = async () => {
        if (session !== sessionRef.current) return
        if (timerRef.current !== null) window.clearInterval(timerRef.current)
        timerRef.current = null
        recorderRef.current = null
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        setElapsed((performance.now() - started) / 1000)
        if (chunksRef.current.length === 0) {
          fail('Nenhum Blob de áudio foi capturado. Grave por alguns segundos.')
          return
        }
        const body = new FormData()
        chunksRef.current.forEach((blob, index) => {
          body.append('chunks', blob, `chunk-${index}.webm`)
        })
        const controller = new AbortController()
        uploadRef.current = controller
        setSent(chunksRef.current.length)
        setStatus('uploading')
        try {
          const response = await request<DecodeResult>('/dev/incremental-audio', {
            method: 'POST',
            body,
            signal: controller.signal,
          })
          if (session !== sessionRef.current) return
          setResult(response)
          setStatus('done')
        } catch (cause) {
          if (session !== sessionRef.current) return
          const message = cause instanceof ApiError && cause.status === 404
            ? 'Endpoint indisponível. Ative APP_DEBUG=true no backend e reinicie-o.'
            : cause instanceof ApiError && cause.status === 401
              ? 'Sessão expirada. Entre novamente antes de gravar.'
              : cause instanceof Error ? cause.message : 'Falha ao enviar ou decodificar áudio.'
          setError(message)
          setStatus('error')
        } finally {
          if (session === sessionRef.current) uploadRef.current = null
        }
      }
      recorder.start(1000)
      setStatus('recording')
      timerRef.current = window.setInterval(() => {
        const seconds = (performance.now() - started) / 1000
        setElapsed(seconds)
        // Margem para o ultimo Blob antes do limite de 90s do backend.
        if (seconds >= MAX_SECONDS - 1 && recorder.state === 'recording') {
          setStatus('stopping')
          recorder.stop()
        }
      }, 250)
    } catch (cause) {
      fail(cause instanceof DOMException && cause.name === 'NotAllowedError'
        ? 'Permissão do microfone negada. Autorize o acesso no navegador.'
        : cause instanceof Error ? cause.message : 'Não foi possível iniciar o microfone.')
    }
  }

  const stop = () => {
    if (recorderRef.current?.state === 'recording') {
      setStatus('stopping')
      recorderRef.current.stop()
    }
  }

  return (
    <div className="flex-1 px-4 py-10 sm:px-8 max-w-5xl mx-auto w-full space-y-6">
      <header>
        <p className="text-sm text-muted">Desenvolvimento · Etapa A</p>
        <h1 className="text-3xl font-bold text-ink mt-1">Decoder incremental</h1>
        <p className="text-muted mt-3">
          Grave apenas o microfone. Ao parar, os Blobs originais são enviados em ordem
          e o backend decodifica o WebM/Opus contínuo. Este resultado é após upload,
          não uma medição de latência ao vivo. Não há transcrição nem diarização.
        </p>
      </header>

      <Card className="p-5 sm:p-6 space-y-4">
        <h2 className="text-lg font-semibold">Gravação de diagnóstico</h2>
        <ul className="text-sm text-muted space-y-1 break-all">
          {supported.map(item => <li key={item.mime}>{item.mime}: {item.supported ? 'suportado' : 'não suportado'}</li>)}
        </ul>
        <p className="text-sm text-muted">MIME da gravação: {actualMime || preferredMime || 'nenhum compatível'}</p>
        <p className="text-sm text-muted">Limites: 90s, 120 chunks, 1 MiB por chunk e 16 MiB no total. Blobs solicitados a cada 1s; o navegador pode atrasá-los.</p>
        {!isLoading && !user && <p role="alert">É necessário <Link className="text-brand underline" to="/login">entrar na conta</Link> para usar o diagnóstico.</p>}
        {!preferredMime && <p role="alert">Este navegador não oferece gravação WebM/Opus compatível.</p>}
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => void start()} disabled={busy || !user || !preferredMime || isLoading}>Iniciar microfone</Button>
          <Button variant="outline" onClick={stop} disabled={status !== 'recording'}>Parar e enviar</Button>
          <Button variant="ghost" onClick={clear}>Limpar</Button>
        </div>
        <p role="status" aria-live="polite">{STATUS_LABELS[status]}</p>
        <p className="text-sm text-muted tabular-nums">
          Tempo: {elapsed.toFixed(1)}s · Capturados: {captured} chunks · Enviados: {sent} chunks · {(bytes / 1024).toFixed(1)} KiB
        </p>
        {error && <p role="alert" className="text-rose-700 break-words">{error}</p>}
      </Card>

      {result && <Card className="p-5 sm:p-6 space-y-4">
        <h2 className="text-lg font-semibold">Janelas decodificadas</h2>
        <p className="text-sm text-muted">
          Recebidos: {result.chunks_received} chunks ({(result.bytes_received / 1024).toFixed(1)} KiB).
          {' '}{result.duration_seconds.toFixed(3)}s de PCM mono a {result.sample_rate} Hz.
          {' '}{result.windows.length} janelas de até 10s, avanço de 8s e overlap de 2s.
          Índices começam em zero; intervalos incluem o início e excluem o fim.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left tabular-nums">
            <caption className="sr-only">Metadados das janelas PCM, sem áudio ou texto transcrito</caption>
            <thead className="border-b border-slate-200"><tr>
              <th scope="col" className="p-2">Janela</th>
              <th scope="col" className="p-2">Amostra inicial</th>
              <th scope="col" className="p-2">Amostra final</th>
              <th scope="col" className="p-2">Início (s)</th>
              <th scope="col" className="p-2">Fim (s)</th>
              <th scope="col" className="p-2">Duração (s)</th>
            </tr></thead>
            <tbody>{result.windows.map(window => <tr key={window.index} className="border-b border-slate-100">
              <td className="p-2">{window.index}</td>
              <td className="p-2">{window.start_sample}</td>
              <td className="p-2">{window.end_sample}</td>
              <td className="p-2">{window.start_seconds.toFixed(3)}</td>
              <td className="p-2">{window.end_seconds.toFixed(3)}</td>
              <td className="p-2">{window.duration_seconds.toFixed(3)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </Card>}
    </div>
  )
}
