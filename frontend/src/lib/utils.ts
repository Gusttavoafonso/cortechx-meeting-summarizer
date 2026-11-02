import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { MeetingStatus } from '../types/meeting'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (!bytes || bytes <= 0) return '0 B'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

export function formatSecondsToTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export function formatMeetingTimeBadge(dateStr: string): {
  time: string
  period: string
} {
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) {
      return { time: '10:00', period: 'AM' }
    }
    let hours = d.getHours()
    const minutes = d.getMinutes().toString().padStart(2, '0')
    const period = hours >= 12 ? 'PM' : 'AM'
    hours = hours % 12
    if (hours === 0) hours = 12
    return {
      time: `${hours}:${minutes}`,
      period,
    }
  } catch {
    return { time: '10:00', period: 'AM' }
  }
}

export function formatMeetingDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(d)
  } catch {
    return dateStr
  }
}

export function getStatusBadgeConfig(status: MeetingStatus): {
  label: string
  bg: string
  text: string
  dot: string
} {
  switch (status) {
    case 'completed':
      return {
        label: 'Concluída',
        bg: 'bg-emerald-50 border-emerald-200',
        text: 'text-emerald-700',
        dot: 'bg-emerald-500',
      }
    case 'processing':
      return {
        label: 'Processando resumo',
        bg: 'bg-blue-50 border-blue-200',
        text: 'text-blue-700',
        dot: 'bg-blue-500 animate-pulse',
      }
    case 'transcribing':
      return {
        label: 'Transcrevendo áudio',
        bg: 'bg-indigo-50 border-indigo-200',
        text: 'text-indigo-700',
        dot: 'bg-indigo-500 animate-pulse',
      }
    case 'transcribed':
      return {
        label: 'Transcrita',
        bg: 'bg-sky-50 border-sky-200',
        text: 'text-sky-700',
        dot: 'bg-sky-500',
      }
    case 'audio_uploaded':
      return {
        label: 'Áudio enviado',
        bg: 'bg-amber-50 border-amber-200',
        text: 'text-amber-700',
        dot: 'bg-amber-500',
      }
    case 'received':
      return {
        label: 'Aguardando áudio',
        bg: 'bg-slate-50 border-slate-200',
        text: 'text-slate-600',
        dot: 'bg-slate-400',
      }
    case 'failed':
      return {
        label: 'Falha no processamento',
        bg: 'bg-rose-50 border-rose-200',
        text: 'text-rose-700',
        dot: 'bg-rose-500',
      }
    default:
      return {
        label: status,
        bg: 'bg-slate-50 border-slate-200',
        text: 'text-slate-600',
        dot: 'bg-slate-400',
      }
  }
}
