import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  AudioLines,
  Calendar,
  Clock,
  ExternalLink,
  MessagesSquare,
  RefreshCw,
} from 'lucide-react'
import { fetchMeetings } from '../api/meetings'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SearchInput } from '../components/ui/Input'
import { formatMeetingDate } from '../lib/utils'

function formatDurationLabel(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '—'
  const rounded = Math.max(1, Math.round(seconds))
  if (rounded < 60) return `${rounded}s`
  const mins = Math.floor(rounded / 60)
  const secs = rounded % 60
  return secs === 0 ? `${mins} min` : `${mins}m ${secs}s`
}

export const TranscriptsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')

  const {
    data: meetings,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['meetings'],
    queryFn: fetchMeetings,
    staleTime: 15_000,
  })

  const transcribedMeetings = useMemo(() => {
    if (!meetings) return []
    const eligible = meetings.filter(
      (m) => m.status === 'completed' || m.status === 'transcribed'
    )
    const term = searchTerm.trim().toLowerCase()
    if (!term) return eligible
    return eligible.filter(
      (m) =>
        m.title.toLowerCase().includes(term) ||
        (m.summary?.summary && m.summary.summary.toLowerCase().includes(term)) ||
        (m.summary?.objective && m.summary.objective.toLowerCase().includes(term))
    )
  }, [meetings, searchTerm])

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold font-sans text-ink">Transcrições</h1>
      </div>

      <div className="mb-6">
        <SearchInput
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Buscar por título ou resumo da reunião..."
        />
      </div>

      {isLoading ? (
        <Card className="p-6 space-y-3 animate-pulse">
          {[1, 2, 3].map((idx) => (
            <div key={idx} className="h-16 bg-slate-100 rounded-xl" />
          ))}
        </Card>
      ) : isError ? (
        <Card className="p-8 text-center border-rose-200 bg-rose-50/30">
          <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-ink mb-1">
            Não foi possível carregar as transcrições
          </h3>
          <p className="text-sm text-muted mb-5">
            Verifique se o servidor está ativo e tente novamente.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Tentar novamente
          </Button>
        </Card>
      ) : transcribedMeetings.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4">
            <AudioLines className="w-7 h-7 stroke-[1.8]" />
          </div>
          <h3 className="text-lg font-bold font-sans text-ink mb-1">
            {searchTerm
              ? `Nenhuma transcrição para “${searchTerm}”`
              : 'Nenhuma transcrição disponível'}
          </h3>
          {searchTerm ? (
            <Button variant="outline" onClick={() => setSearchTerm('')}>
              Limpar busca
            </Button>
          ) : (
            <Link to="/meetings">
              <Button leftIcon={<MessagesSquare className="w-4 h-4" />}>
                Ir para Reuniões
              </Button>
            </Link>
          )}
        </Card>
      ) : (
        <Card className="divide-y divide-slate-100 overflow-hidden">
          {transcribedMeetings.map((meeting) => (
            <div
              key={meeting.id}
              className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface/30 transition-colors"
            >
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <Link
                    to={`/meetings/${meeting.id}`}
                    className="text-base font-bold text-ink hover:text-brand truncate"
                  >
                    {meeting.title}
                  </Link>
                  <StatusBadge status={meeting.status} />
                </div>
                {meeting.summary?.summary && (
                  <p className="text-xs text-muted line-clamp-2">
                    {meeting.summary.summary}
                  </p>
                )}
                <div className="flex items-center gap-4 text-xs text-muted">
                  <span className="inline-flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {formatMeetingDate(meeting.created_at)}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {formatDurationLabel(meeting.audio?.duration_seconds)}
                  </span>
                </div>
              </div>

              <Link to={`/meetings/${meeting.id}`} className="shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
                >
                  Ler transcrição
                </Button>
              </Link>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
