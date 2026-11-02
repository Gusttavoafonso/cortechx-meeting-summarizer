import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  Calendar,
  Clock,
  MessagesSquare,
  Plus,
  RefreshCw,
} from 'lucide-react'
import { fetchMeetings } from '../api/meetings'
import { SearchInput } from '../components/ui/Input'
import { TimeBadge, StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { formatMeetingDate, formatMeetingTimeBadge } from '../lib/utils'
import { Meeting } from '../types/meeting'

export const MeetingsList: React.FC = () => {
  const navigate = useNavigate()
  const [searchTerm, setSearchTerm] = useState('')

  const {
    data: meetings,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['meetings'],
    queryFn: fetchMeetings,
    staleTime: 1000 * 15,
  })

  const filteredMeetings = useMemo(() => {
    if (!meetings) return []
    const term = searchTerm.toLowerCase().trim()
    if (!term) return meetings
    return meetings.filter(
      (m) =>
        m.title.toLowerCase().includes(term) ||
        (m.summary?.summary && m.summary.summary.toLowerCase().includes(term))
    )
  }, [meetings, searchTerm])

  const renderDescription = (meeting: Meeting) => {
    if (meeting.summary?.summary) {
      return meeting.summary.summary
    }
    if (meeting.summary?.objective) {
      return meeting.summary.objective
    }
    if (meeting.last_error) {
      return `Erro: ${meeting.last_error}`
    }
    switch (meeting.status) {
      case 'processing':
        return 'Processando resumo inteligente e extração de tarefas...'
      case 'transcribing':
        return 'Transcrevendo áudio com reconhecimento de locutores...'
      case 'audio_uploaded':
        return 'Áudio carregado. Pronto para iniciar processamento.'
      case 'received':
        return 'Reunião criada. Aguardando envio do arquivo de áudio.'
      case 'completed':
        return 'Reunião transcrita com sucesso.'
      default:
        return 'Nenhum resumo disponível ainda.'
    }
  }

  const getEstimatedDuration = (meeting: Meeting) => {
    if (meeting.transcript?.segments?.length) {
      const lastSegment =
        meeting.transcript.segments[meeting.transcript.segments.length - 1]
      if (lastSegment?.end_time) {
        const minutes = Math.ceil(lastSegment.end_time / 60)
        return `${minutes} ${minutes === 1 ? 'minuto' : 'minutos'}`
      }
    }
    if (meeting.audio?.file_size_bytes) {
      // Rough estimate if not transcribed yet (1MB approx 1 min for compressed audio)
      const approxMins = Math.max(
        1,
        Math.round(meeting.audio.file_size_bytes / (1024 * 1024))
      )
      return `~${approxMins} min`
    }
    return '30 minutos'
  }

  return (
    <div className="flex-1 px-8 py-10 max-w-6xl mx-auto w-full">
      {/* Page Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink font-fredoka">
            Reuniões
          </h1>
          <p className="text-sm text-muted mt-1">Todas as suas reuniões transcritas</p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <span className="text-xs text-muted flex items-center gap-1.5 animate-pulse">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-brand" />
              Atualizando...
            </span>
          )}
          <Button
            onClick={() => navigate('/meetings/new')}
            size="sm"
            leftIcon={<Plus className="w-4 h-4" />}
            className="md:hidden"
          >
            Nova
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-8">
        <SearchInput
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Buscar reunião..."
        />
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <Card className="p-4 divide-y divide-slate-100">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="py-4 px-4 flex items-center gap-5 animate-pulse">
              <div className="w-14 h-14 rounded-xl bg-slate-200/70 shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-slate-200/80 rounded w-1/3" />
                <div className="h-3 bg-slate-100 rounded w-2/3" />
              </div>
              <div className="w-24 h-8 bg-slate-100 rounded hidden sm:block" />
              <div className="w-24 h-10 bg-slate-200/70 rounded-xl" />
            </div>
          ))}
        </Card>
      ) : isError ? (
        <Card className="p-8 text-center border-rose-200 bg-rose-50/30">
          <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-ink mb-1">
            Não foi possível carregar as reuniões
          </h3>
          <p className="text-sm text-muted max-w-md mx-auto mb-6">
            {error instanceof Error
              ? error.message
              : 'Verifique se o backend está em execução na porta 8000.'}
          </p>
          <Button
            variant="outline"
            onClick={() => refetch()}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Tentar novamente
          </Button>
        </Card>
      ) : filteredMeetings.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4">
            <MessagesSquare className="w-8 h-8 stroke-[1.5]" />
          </div>
          <h3 className="text-lg font-bold text-ink font-fredoka mb-1">
            {searchTerm ? 'Nenhuma reunião encontrada' : 'Nenhuma reunião cadastrada'}
          </h3>
          <p className="text-sm text-muted max-w-sm mx-auto mb-6">
            {searchTerm
              ? `Nenhum resultado corresponde à busca por "${searchTerm}". Tente outro termo.`
              : 'Crie sua primeira reunião com upload de áudio para gerar transcrições e resumos inteligentes.'}
          </p>
          {searchTerm ? (
            <Button variant="outline" onClick={() => setSearchTerm('')}>
              Limpar busca
            </Button>
          ) : (
            <Button
              onClick={() => navigate('/meetings/new')}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Criar primeira reunião
            </Button>
          )}
        </Card>
      ) : (
        <Card className="p-3 sm:p-5 divide-y divide-slate-100">
          {filteredMeetings.map((meeting) => {
            const timeBadge = formatMeetingTimeBadge(meeting.created_at)
            const duration = getEstimatedDuration(meeting)

            return (
              <div
                key={meeting.id}
                className="py-4 px-2 sm:px-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 hover:bg-slate-50/60 rounded-xl transition-colors group"
              >
                {/* Left section: Time Badge + Info */}
                <div className="flex items-start sm:items-center gap-4 min-w-0 flex-1">
                  <TimeBadge time={timeBadge.time} period={timeBadge.period} />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-base font-semibold text-ink group-hover:text-primary-btn transition-colors truncate">
                        {meeting.title}
                      </h3>
                      {meeting.status !== 'completed' && (
                        <StatusBadge status={meeting.status} />
                      )}
                    </div>

                    <p className="text-xs sm:text-sm text-muted line-clamp-1">
                      {renderDescription(meeting)}
                    </p>

                    <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted sm:hidden">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatMeetingDate(meeting.created_at)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {duration}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right section: Duration + Details button */}
                <div className="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                  <div className="text-right hidden sm:block">
                    <span className="text-[11px] text-muted block leading-none">
                      Duração
                    </span>
                    <span className="text-sm font-medium text-ink mt-1 block">
                      {duration}
                    </span>
                  </div>

                  <Button
                    onClick={() => navigate(`/meetings/${meeting.id}`)}
                    className="h-10 px-5 text-sm font-medium shadow-none w-full sm:w-auto"
                  >
                    Detalhes
                  </Button>
                </div>
              </div>
            )
          })}
        </Card>
      )}
    </div>
  )
}
