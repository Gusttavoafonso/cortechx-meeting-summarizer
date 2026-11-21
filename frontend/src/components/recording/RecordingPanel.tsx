import React, { useEffect, useRef, useState } from 'react'
import {
  Mic,
  Volume2,
  Laptop,
  Pause,
  Play,
  Square,
  X,
  AlertCircle,
  Loader2,
  RotateCcw,
} from 'lucide-react'
import { useRecordingContext } from '../../context/RecordingContext'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { LiveTranscriptPanel } from './LiveTranscriptPanel'
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
    isStartingRecording,
    isPaused,
    elapsedMs,
    captureMode: mode,
    setCaptureMode: setMode,
    recordingError: errorMessage,
    liveTranscription,
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
      setLocalError(err instanceof Error ? err.message : 'Falha ao finalizar gravação.')
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
          <div className="flex flex-wrap items-center justify-center gap-2 mb-5 bg-surface/50 p-1 rounded-2xl border border-[#DCE2FB]/70">
            <button
              type="button"
              disabled={disabled || isStartingRecording}
              onClick={() => setMode('both')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all disabled:opacity-60 ${
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
              disabled={disabled || isStartingRecording}
              onClick={() => setMode('mic_only')}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all disabled:opacity-60 ${
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
          <div className="flex flex-col items-center gap-2 mb-5">
            <button
              type="button"
              disabled={disabled || isStartingRecording}
              onClick={handleStart}
              title="Iniciar gravação agora"
              className={`relative w-16 h-16 rounded-full border-2 transition-all flex items-center justify-center shadow-sm group focus:outline-none focus:ring-4 ${
                isStartingRecording
                  ? 'border-brand/50 bg-surface text-brand cursor-wait focus:ring-brand/20'
                  : 'border-rose-500 bg-rose-50/70 text-rose-600 hover:bg-rose-100/90 active:scale-95 focus:ring-rose-200 disabled:opacity-50'
              }`}
            >
              {!isStartingRecording && (
                <span className="absolute -inset-1 rounded-full bg-rose-400/20 opacity-0 group-hover:opacity-100 transition-opacity" />
              )}
              {isStartingRecording ? (
                <Loader2 className="w-7 h-7 animate-spin stroke-[2.2]" />
              ) : (
                <Mic className="w-7 h-7 stroke-[2.2] group-hover:scale-105 transition-transform" />
              )}
            </button>
            <span className="text-xs font-semibold text-ink tracking-tight">
              {isStartingRecording
                ? 'Aguardando permissão de captura...'
                : 'Iniciar gravação'}
            </span>
          </div>

          {/* Micro-guia visual de Onboarding */}
          {mode === 'both' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl text-left">
              <div className="flex items-start gap-2.5 bg-surface/60 border border-[#DCE2FB] rounded-xl px-3.5 py-2.5">
                <span className="w-5 h-5 rounded-full bg-primary-btn text-white text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  1
                </span>
                <p className="text-[11px] text-ink-light leading-snug">
                  Escolha a aba da reunião e marque{' '}
                  <strong>Compartilhar áudio da aba</strong>.
                </p>
              </div>
              <div className="flex items-start gap-2.5 bg-surface/60 border border-[#DCE2FB] rounded-xl px-3.5 py-2.5">
                <span className="w-5 h-5 rounded-full bg-primary-btn text-white text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  2
                </span>
                <p className="text-[11px] text-ink-light leading-snug">
                  Autorize o microfone — a transcrição aparecerá ao vivo automaticamente.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 max-w-lg bg-surface/60 border border-[#DCE2FB] rounded-xl px-3.5 py-2.5 text-left">
              <Mic className="w-4 h-4 text-brand shrink-0 stroke-[2]" />
              <p className="text-[11px] text-ink-light leading-snug">
                Apenas o microfone será capturado, com transcrição simultânea em tempo
                real na tela.
              </p>
            </div>
          )}
        </div>
      ) : (
        /* Estado 2: Gravando Ativamente (Estúdio + Transcrição ao Vivo) */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          {/* Coluna Esquerda: Controles e Telemetria */}
          <div className="lg:col-span-5 flex flex-col items-center justify-between text-center bg-slate-50/70 border border-slate-200/80 rounded-2xl p-5">
            <div className="flex flex-col items-center w-full">
              {/* Badge Indicador de Gravação */}
              <div
                className={`flex items-center gap-2 px-3 py-1 rounded-full mb-4 ${
                  isPaused ? 'bg-amber-50/80' : 'bg-rose-50/80'
                }`}
              >
                <span className="relative flex h-2 w-2">
                  {!isPaused && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                  )}
                  <span
                    className={`relative inline-flex rounded-full h-2 w-2 ${
                      isPaused ? 'bg-amber-500' : 'bg-rose-600'
                    }`}
                  />
                </span>
                <span
                  className={`text-[11px] font-semibold uppercase tracking-wider ${
                    isPaused ? 'text-amber-700' : 'text-rose-700'
                  }`}
                >
                  {isPaused ? 'Gravação pausada' : 'Gravando ao vivo'}
                </span>
              </div>

              {/* Cronômetro */}
              <div className="font-mono text-3xl sm:text-4xl font-bold text-ink mb-5 tracking-tight">
                {formatSecondsToTime(Math.floor(elapsedMs / 1000))}
              </div>

              {/* VU Meters Minimalistas */}
              <div className="w-full space-y-3 mb-6 bg-white border border-slate-200/80 rounded-xl p-4 text-left">
                {/* Microfone */}
                <div>
                  <div className="flex items-center justify-between text-xs font-medium text-muted mb-1.5">
                    <span className="flex items-center gap-1.5">
                      <Mic
                        className={`w-3.5 h-3.5 stroke-[2] transition-colors ${
                          micLevel > 0.04 ? 'text-emerald-600' : 'text-muted'
                        }`}
                      />
                      <span
                        className={micLevel > 0.04 ? 'text-ink font-semibold' : undefined}
                      >
                        Microfone
                      </span>
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
                        <Volume2
                          className={`w-3.5 h-3.5 stroke-[2] transition-colors ${
                            systemLevel > 0.04 ? 'text-brand' : 'text-muted'
                          }`}
                        />
                        <span
                          className={
                            systemLevel > 0.04 ? 'text-ink font-semibold' : undefined
                          }
                        >
                          Áudio da chamada
                        </span>
                      </span>
                      <span className="font-mono text-[11px]">
                        {Math.round(systemLevel * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-200/80 rounded-full overflow-hidden">
                      <div
                        style={{
                          width: `${Math.min(100, Math.round(systemLevel * 100))}%`,
                        }}
                        className="h-full bg-primary-btn rounded-full transition-all duration-75"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Controles de Gravação */}
            <div className="flex flex-wrap items-center justify-center gap-2 w-full">
              <Button
                type="button"
                variant="outline"
                size="sm"
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
                size="sm"
                onClick={handleCancel}
                leftIcon={<X className="w-3.5 h-3.5 stroke-[2.2]" />}
              >
                Descartar
              </Button>

              <Button
                type="button"
                variant="danger"
                size="sm"
                onClick={handleStop}
                leftIcon={<Square className="w-3.5 h-3.5 fill-current" />}
              >
                Concluir gravação
              </Button>
            </div>
          </div>

          {/* Coluna Direita: Painel de Transcrição Simultânea */}
          <div className="lg:col-span-7">
            <LiveTranscriptPanel
              transcription={liveTranscription}
              isPaused={isPaused}
              isAudioActive={micLevel > 0.04 || systemLevel > 0.04}
              className="h-full"
            />
          </div>
        </div>
      )}

      {/* Erro com recuperação em 1 clique */}
      {displayError && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 mt-5 text-left">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{displayError}</span>
          </div>
          {!isRecording && (
            <button
              type="button"
              onClick={handleStart}
              disabled={disabled || isStartingRecording}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-rose-200 text-rose-700 font-semibold hover:bg-rose-100/60 transition-colors shrink-0"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Tentar novamente</span>
            </button>
          )}
        </div>
      )}
    </Card>
  )
}
