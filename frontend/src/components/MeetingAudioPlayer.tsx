import React, { useEffect, useRef, useState } from 'react'
import { Pause, Play, Volume2, VolumeX } from 'lucide-react'
import { cn, formatSecondsToTime } from '../lib/utils'

interface MeetingAudioPlayerProps {
  src: string
  durationSeconds?: number | null
  className?: string
}

export const MeetingAudioPlayer: React.FC<MeetingAudioPlayerProps> = ({
  src,
  durationSeconds,
  className,
}) => {
  const audioRef = useRef<HTMLAudioElement>(null)
  const initialDuration =
    typeof durationSeconds === 'number' &&
    Number.isFinite(durationSeconds) &&
    durationSeconds > 0
      ? durationSeconds
      : 0

  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [mediaDuration, setMediaDuration] = useState(initialDuration)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    setIsPlaying(false)
    setCurrentTime(0)
    setHasError(false)
    setMediaDuration(initialDuration)
  }, [src, initialDuration])

  useEffect(() => {
    if (!isPlaying) return
    let rafId = 0
    let active = true
    const tick = () => {
      if (!active) return
      const el = audioRef.current
      if (el) {
        setCurrentTime(el.currentTime)
        if (Number.isFinite(el.duration) && el.duration > 0) {
          setMediaDuration(el.duration)
        }
        if (el.ended) {
          setIsPlaying(false)
          return
        }
      }
      rafId = window.requestAnimationFrame(tick)
    }
    rafId = window.requestAnimationFrame(tick)
    return () => {
      active = false
      window.cancelAnimationFrame(rafId)
    }
  }, [isPlaying])

  const effectiveDuration =
    mediaDuration > 0
      ? Math.max(mediaDuration, currentTime)
      : currentTime > 0
        ? currentTime
        : 0

  const progressPercent =
    effectiveDuration > 0
      ? Math.min(100, Math.max(0, (currentTime / effectiveDuration) * 100))
      : 0

  const handleTogglePlay = async () => {
    const el = audioRef.current
    if (!el || hasError) return
    if (el.paused) {
      if (el.ended || (effectiveDuration > 0 && el.currentTime >= effectiveDuration)) {
        el.currentTime = 0
        setCurrentTime(0)
      }
      try {
        await el.play()
        setIsPlaying(true)
      } catch {
        setIsPlaying(false)
      }
    } else {
      el.pause()
      setIsPlaying(false)
    }
  }

  const handleToggleMute = () => {
    const el = audioRef.current
    if (!el) return
    const nextMuted = !isMuted
    el.muted = nextMuted
    setIsMuted(nextMuted)
  }

  const handleSeek = (e: React.FormEvent<HTMLInputElement>) => {
    const el = audioRef.current
    if (!el || effectiveDuration <= 0) return
    const target = Number(e.currentTarget.value)
    if (!Number.isFinite(target)) return
    el.currentTime = target
    setCurrentTime(target)
  }

  const syncDurationFromElement = (el: HTMLAudioElement) => {
    if (Number.isFinite(el.duration) && el.duration > 0) {
      setMediaDuration(el.duration)
    }
  }

  const isCrossOrigin = /^https?:\/\//i.test(src)

  return (
    <div
      className={cn(
        'w-full rounded-xl bg-slate-50/80 border border-slate-200/80 px-3.5 py-2.5 flex items-center gap-3',
        className
      )}
    >
      <audio
        ref={audioRef}
        src={src}
        preload="auto"
        crossOrigin={isCrossOrigin ? 'use-credentials' : undefined}
        onLoadedMetadata={(e) => syncDurationFromElement(e.currentTarget)}
        onDurationChange={(e) => syncDurationFromElement(e.currentTarget)}
        onTimeUpdate={(e) => {
          setCurrentTime(e.currentTarget.currentTime)
          syncDurationFromElement(e.currentTarget)
        }}
        onPlay={() => setIsPlaying(true)}
        onPlaying={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={(e) => {
          setIsPlaying(false)
          const el = e.currentTarget
          if (Number.isFinite(el.duration) && el.duration > 0) {
            setMediaDuration(el.duration)
            setCurrentTime(el.duration)
          } else if (mediaDuration > 0) {
            setCurrentTime(mediaDuration)
          }
        }}
        onError={() => {
          setIsPlaying(false)
          setHasError(true)
        }}
        className="hidden"
      />

      <button
        type="button"
        onClick={handleTogglePlay}
        disabled={hasError}
        aria-label={isPlaying ? 'Pausar áudio' : 'Reproduzir áudio'}
        className="w-8 h-8 rounded-full bg-primary-btn text-white hover:bg-primary-btn-hover active:bg-primary-btn-active disabled:opacity-50 flex items-center justify-center shrink-0 transition-colors cursor-pointer"
      >
        {isPlaying ? (
          <Pause className="w-3.5 h-3.5 fill-current" />
        ) : (
          <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
        )}
      </button>

      <div className="flex-1 min-w-0 flex items-center gap-3">
        <div className="relative flex-1 h-5 flex items-center group">
          <div className="w-full h-1.5 rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-brand"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          {effectiveDuration > 0 && (
            <div
              className="pointer-events-none absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-primary-btn shadow-xs transition-transform group-hover:scale-110"
              style={{ left: `${progressPercent}%` }}
            />
          )}
          <input
            type="range"
            min={0}
            max={effectiveDuration || 0}
            step={0.01}
            value={Math.min(currentTime, effectiveDuration || 0)}
            onChange={handleSeek}
            disabled={hasError || effectiveDuration <= 0}
            aria-label="Barra de progresso do áudio"
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-default"
          />
        </div>

        <span className="font-mono text-[11px] text-muted tabular-nums shrink-0">
          {hasError
            ? 'Áudio indisponível'
            : `${formatSecondsToTime(currentTime)} / ${formatSecondsToTime(effectiveDuration)}`}
        </span>
      </div>

      <button
        type="button"
        onClick={handleToggleMute}
        disabled={hasError}
        aria-label={isMuted ? 'Ativar som' : 'Silenciar áudio'}
        className="p-1.5 rounded-lg text-muted hover:text-ink hover:bg-slate-200/60 disabled:opacity-50 transition-colors shrink-0 cursor-pointer"
      >
        {isMuted ? (
          <VolumeX className="w-4 h-4" />
        ) : (
          <Volume2 className="w-4 h-4" />
        )}
      </button>
    </div>
  )
}
