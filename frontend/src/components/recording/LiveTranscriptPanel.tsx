import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, AudioLines, Check, Copy, Pause } from 'lucide-react'
import {
  buildFullTranscriptText,
  LiveTranscriptionState,
} from '../../lib/liveTranscription'
import { formatSecondsToTime } from '../../lib/utils'

interface LiveTranscriptPanelProps {
  transcription: LiveTranscriptionState
  isPaused: boolean
  isAudioActive?: boolean
  className?: string
}

const AUTO_SCROLL_THRESHOLD_PX = 48

export const LiveTranscriptPanel: React.FC<LiveTranscriptPanelProps> = ({
  transcription,
  isPaused,
  isAudioActive = false,
  className = '',
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true)
  const [copied, setCopied] = useState(false)

  const fullText = useMemo(
    () => buildFullTranscriptText(transcription.segments, transcription.interimText),
    [transcription.segments, transcription.interimText]
  )

  useEffect(() => {
    if (!autoScrollEnabled) return
    const container = scrollContainerRef.current
    if (!container) return
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    })
  }, [
    autoScrollEnabled,
    transcription.segments.length,
    transcription.interimText,
    transcription.status,
  ])

  const handleScroll = () => {
    const container = scrollContainerRef.current
    if (!container) return
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight
    setAutoScrollEnabled(distanceFromBottom <= AUTO_SCROLL_THRESHOLD_PX)
  }

  const handleScrollToLive = () => {
    const container = scrollContainerRef.current
    if (!container) return
    setAutoScrollEnabled(true)
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    })
  }

  const handleCopy = async () => {
    if (!fullText) return
    try {
      await navigator.clipboard.writeText(fullText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignora erro caso clipboard esteja bloqueado pelo navegador
    }
  }

  const renderStatusPill = () => {
    const basePill =
      'inline-flex items-center justify-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap shrink-0 border'

    if (isPaused || transcription.status === 'paused') {
      return (
        <span className={`${basePill} bg-amber-50/70 text-amber-700 border-transparent`}>
          <Pause className="w-3 h-3 shrink-0" />
          <span>Pausada</span>
        </span>
      )
    }

    if (transcription.status === 'completed') {
      return (
        <span className={`${basePill} bg-emerald-50 text-emerald-700 border-emerald-200`}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          <span>Concluída</span>
        </span>
      )
    }

    if (transcription.status === 'connecting') {
      return (
        <span className={`${basePill} bg-surface text-brand border-[#DCE2FB]`}>
          <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse shrink-0" />
          <span>Preparando...</span>
        </span>
      )
    }

    return (
      <span className={`${basePill} bg-emerald-50 text-emerald-700 border-emerald-200`}>
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span>{isAudioActive ? 'Captando fala...' : 'Transcrevendo ao vivo'}</span>
      </span>
    )
  }

  const hasContent =
    transcription.segments.length > 0 || transcription.interimText.trim().length > 0

  return (
    <div
      className={`relative flex flex-col bg-page/90 border border-subtle-border rounded-2xl overflow-hidden text-left ${className}`}
    >
      {/* Cabeçalho principal (linha única fixa, sem quebra ao trocar status) */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 bg-white/80 border-b border-subtle-border">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-surface text-brand flex items-center justify-center shrink-0">
            <AudioLines className="w-4 h-4 stroke-[2.2]" />
          </div>
          <h4 className="font-sans text-sm font-semibold text-ink whitespace-nowrap truncate">
            Transcrição em tempo real
          </h4>
          {renderStatusPill()}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          disabled={!fullText}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 bg-white text-ink-light hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap shrink-0"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-emerald-700">Copiado</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-muted" />
              <span>Copiar</span>
            </>
          )}
        </button>
      </div>

      {/* Sub-barra estável de modo e métricas */}
      <div className="flex items-center justify-between gap-2 px-4 py-1.5 bg-slate-50/70 border-b border-subtle-border">
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-surface text-brand border border-[#DCE2FB] whitespace-nowrap">
          Simulação por chunks
        </span>
        <div className="flex items-center gap-2 font-mono text-[11px] text-muted tabular-nums whitespace-nowrap">
          <span>{transcription.chunksReceived} chunks</span>
          <span className="text-slate-300">/</span>
          <span>{transcription.wordCount} palavras</span>
        </div>
      </div>

      {/* Área de transcrição */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Transcrição em tempo real da reunião"
        className="h-[260px] sm:h-[320px] overflow-y-auto px-4 py-4 space-y-3 bg-white/50"
      >
        {!hasContent ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <div className="w-10 h-10 rounded-xl bg-surface text-brand flex items-center justify-center mb-3 animate-pulse">
              <AudioLines className="w-5 h-5 stroke-[2]" />
            </div>
            <p className="text-sm font-medium text-ink-light max-w-sm">
              Escutando o áudio da reunião... as palavras começarão a aparecer aqui
              automaticamente.
            </p>
            <p className="text-xs text-muted mt-1.5 font-mono">
              {transcription.chunksReceived} chunks recebidos
            </p>
          </div>
        ) : (
          <>
            {transcription.segments.map((segment) => (
              <div key={segment.id} className="flex items-start gap-3 animate-live-fade">
                <span className="font-mono text-[11px] text-muted/80 pt-1 shrink-0 select-none">
                  {formatSecondsToTime(Math.floor(segment.startMs / 1000))}
                </span>
                <p className="text-sm leading-relaxed text-ink">{segment.text}</p>
              </div>
            ))}

            {transcription.interimText && (
              <div className="flex items-start gap-3 animate-live-fade">
                <span className="font-mono text-[11px] text-brand/80 pt-1 shrink-0 select-none">
                  {formatSecondsToTime(
                    Math.floor((transcription.interimStartMs ?? 0) / 1000)
                  )}
                </span>
                <p className="text-sm leading-relaxed text-ink-light">
                  <span>{transcription.interimText}</span>
                  <span
                    aria-hidden="true"
                    className="inline-block w-[2px] h-[1em] bg-brand align-middle ml-1 rounded-full animate-live-caret"
                  />
                </p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Faixa de pausa inline */}
      {(isPaused || transcription.status === 'paused') && (
        <div className="px-4 py-2 bg-slate-50/90 border-t border-subtle-border text-xs text-muted font-medium">
          Transcrição pausada. Clique em Retomar para continuar capturando.
        </div>
      )}

      {/* Botão flutuante para voltar ao ao vivo */}
      {!autoScrollEnabled && hasContent && (
        <button
          type="button"
          onClick={handleScrollToLive}
          className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary-btn text-white text-xs font-semibold shadow-md hover:bg-primary-btn-hover transition-all"
        >
          <ArrowDown className="w-3.5 h-3.5" />
          <span>Voltar ao ao vivo</span>
        </button>
      )}
    </div>
  )
}
