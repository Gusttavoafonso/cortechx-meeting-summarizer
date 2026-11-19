import React, { useEffect, useRef, useState } from 'react'
import {
  Mic,
  Volume2,
  Laptop,
  Pause,
  Play,
  Square,
  X,
  Info,
  AlertCircle,
} from 'lucide-react'
import { useRecordingContext } from '../../context/RecordingContext'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { formatSecondsToTime } from '../../lib/utils'

interface RecordingPanelProps {
  onRecordingComplete: (file: File, durationMs: number) => void
  userId?: number | string
  disabled?: boolean
}

export const RecordingPanel: React.FC<RecordingPanelProps> = ({
  onRecordingComplete,
  userId = 1,
  disabled = false,
}) => {
  const animFrameRef = useRef<number | null>(null)
  const {
    isRecording,
    isPaused,
    elapsedMs,
    captureMode: mode,
    setCaptureMode: setMode,
    recordingError: errorMessage,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    cancelRecording,
    getAudioLevels,
    clearRecordingError,
  } = useRecordingContext()

  const [localError, setLocalError] = useState<string | null>(null)
  const [micLevel, setMicLevel] = useState(0)
  const [systemLevel, setSystemLevel] = useState(0)

  useEffect(() => {
    if (!isRecording || isPaused) {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
      return
    }

    const updateLevels = () => {
      const levels = getAudioLevels()
      setMicLevel(levels.micLevel)
      setSystemLevel(levels.systemLevel)
      animFrameRef.current = requestAnimationFrame(updateLevels)
    }

    animFrameRef.current = requestAnimationFrame(updateLevels)

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
    }
  }, [isRecording, isPaused, getAudioLevels])

  const handleStart = async () => {
    setLocalError(null)
    clearRecordingError()
    try {
      await startRecording(mode)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : String(err))
    }
  }

  const handlePauseToggle = () => {
    if (isPaused) {
      resumeRecording()
    } else {
      pauseRecording()
    }
  }

  const handleCancel = () => {
    cancelRecording()
    setMicLevel(0)
    setSystemLevel(0)
    setLocalError(null)
  }

  const handleStop = async () => {
    try {
      const result = await stopRecording(userId)
      setMicLevel(0)
      setSystemLevel(0)
      onRecordingComplete(result.file, result.durationMs)
    } catch (err) {
      setLocalError(
        err instanceof Error ? err.message : 'Falha ao finalizar gravação.'
      )
    }
  }

  const displayError = localError || errorMessage

  return (
    <Card className="p-5 border-slate-200 shadow-card bg-white/70 backdrop-blur-xs">
      {/* Estado 1: Pronto para Gravar (Idle) */}
      {!isRecording ? (
        <div className="flex flex-col items-center text-center">
          <div className="mb-3">
            <h3 className="font-sans text-lg font-semibold text-ink mb-0.5">
              Gravação ao vivo
            </h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              Capture o áudio da chamada e do seu microfone em tempo real.
            </p>
          </div>

          {/* Seletor de modo minimalista */}
          <div className="flex flex-wrap items-center justify-center gap-2 mb-4 bg-surface/50 p-1 rounded-2xl border border-[#DCE2FB]/70">
            <button
              type="button"
              disabled={disabled}
              onClick={() => setMode('both')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                mode === 'both'
                  ? 'bg-primary-btn text-white shadow-xs'
                  : 'text-muted hover:text-ink'
              }`}
            >
              <Laptop className="w-3.5 h-3.5 stroke-[2.2]" />
              <span>Sistema e microfone</span>
            </button>

            <button
              type="button"
              disabled={disabled}
              onClick={() => setMode('mic_only')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                mode === 'mic_only'
                  ? 'bg-primary-btn text-white shadow-xs'
                  : 'text-muted hover:text-ink'
              }`}
            >
              <Mic className="w-3.5 h-3.5 stroke-[2.2]" />
              <span>Apenas microfone</span>
            </button>
          </div>

          {/* Botão de Gravação Minimalista com Ícone de Microfone */}
          <div className="flex flex-col items-center gap-2 mb-4">
            <button
              type="button"
              disabled={disabled}
              onClick={handleStart}
              title="Iniciar gravação agora"
              className="relative w-16 h-16 rounded-full border-2 border-rose-500 bg-rose-50/70 text-rose-600 hover:bg-rose-100/90 active:scale-95 transition-all flex items-center justify-center shadow-sm group focus:outline-none focus:ring-4 focus:ring-rose-200"
            >
              <span className="absolute -inset-1 rounded-full bg-rose-400/20 opacity-0 group-hover:opacity-100 transition-opacity" />
              <Mic className="w-7 h-7 stroke-[2.2] group-hover:scale-105 transition-transform" />
            </button>
            <span className="text-xs font-semibold text-ink tracking-tight">
              Iniciar gravação
            </span>
          </div>

          {/* Dica de Permissão no Navegador */}
          <div className="flex items-center gap-2 max-w-lg bg-surface/60 border border-[#DCE2FB] rounded-xl px-3.5 py-2 text-left">
            <Info className="w-4 h-4 text-brand shrink-0 stroke-[2]" />
            <p className="text-[11px] text-ink-light leading-snug">
              Selecione a aba da reunião (Meet, Discord, etc.) e marque{' '}
              <strong>compartilhar áudio da aba</strong> no navegador.
            </p>
          </div>
        </div>
      ) : (
        /* Estado 2: Gravando Ativamente */
        <div className="flex flex-col items-center text-center py-2">
          {/* Badge Indicador de Gravação */}
          <div className="flex items-center gap-2 px-3 py-1 bg-rose-50 border border-rose-200 rounded-full mb-4">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600" />
            </span>
            <span className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider">
              {isPaused ? 'Gravação pausada' : 'Gravando áudio'}
            </span>
          </div>

          {/* Cronômetro */}
          <div className="font-mono text-3xl sm:text-4xl font-bold text-ink mb-6 tracking-tight">
            {formatSecondsToTime(Math.floor(elapsedMs / 1000))}
          </div>

          {/* VU Meters Minimalistas */}
          <div className="w-full max-w-md space-y-3 mb-8 bg-slate-50 border border-slate-200/80 rounded-xl p-4 text-left">
            {/* Microfone */}
            <div>
              <div className="flex items-center justify-between text-xs font-medium text-muted mb-1.5">
                <span className="flex items-center gap-1.5">
                  <Mic className="w-3.5 h-3.5 text-muted stroke-[2]" />
                  <span>Microfone</span>
                </span>
                <span className="font-mono text-[11px]">
                  {Math.round(micLevel * 100)}%
                </span>
              </div>
              <div className="h-1.5 w-full bg-slate-200/80 rounded-full overflow-hidden">
                <div
                  style={{ width: `${Math.min(100, Math.round(micLevel * 100))}%` }}
                  className="h-full bg-emerald-500 rounded-full transition-all duration-75"
                />
              </div>
            </div>

            {/* Sistema / Aba */}
            {mode === 'both' && (
              <div>
                <div className="flex items-center justify-between text-xs font-medium text-muted mb-1.5">
                  <span className="flex items-center gap-1.5">
                    <Volume2 className="w-3.5 h-3.5 text-muted stroke-[2]" />
                    <span>Áudio da chamada</span>
                  </span>
                  <span className="font-mono text-[11px]">
                    {Math.round(systemLevel * 100)}%
                  </span>
                </div>
                <div className="h-1.5 w-full bg-slate-200/80 rounded-full overflow-hidden">
                  <div
                    style={{ width: `${Math.min(100, Math.round(systemLevel * 100))}%` }}
                    className="h-full bg-primary-btn rounded-full transition-all duration-75"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Controles de Gravação */}
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={handlePauseToggle}
              leftIcon={
                isPaused ? (
                  <Play className="w-3.5 h-3.5 fill-current" />
                ) : (
                  <Pause className="w-3.5 h-3.5 fill-current" />
                )
              }
            >
              {isPaused ? 'Retomar' : 'Pausar'}
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={handleCancel}
              leftIcon={<X className="w-3.5 h-3.5 stroke-[2.2]" />}
            >
              Descartar
            </Button>

            <Button
              type="button"
              variant="danger"
              size="md"
              onClick={handleStop}
              leftIcon={<Square className="w-3.5 h-3.5 fill-current" />}
            >
              Concluir gravação
            </Button>
          </div>
        </div>
      )}

      {/* Erro */}
      {displayError && (
        <div className="flex items-start gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 mt-5 text-left">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{displayError}</span>
        </div>
      )}
    </Card>
  )
}
