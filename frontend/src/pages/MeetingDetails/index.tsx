import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronRight,
  FileAudio,
  CheckCircle2,
  Calendar,
  AlertCircle,
  RefreshCw,
  Sparkles,
  ListTodo,
} from 'lucide-react'
import { fetchMeetingById, retryMeeting } from '../../api/meetings'
import { Card } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { formatBytes, formatMeetingDate, formatSecondsToTime } from '../../lib/utils'

export const MeetingDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const meetingId = Number(id)

  const {
    data: meeting,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => fetchMeetingById(meetingId),
    enabled: !isNaN(meetingId) && meetingId > 0,
    // Poll every 4 seconds if in progress
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'processing' || status === 'transcribing') {
        return 4000
      }
      return false
    },
  })

  const [isRetrying, setIsRetrying] = React.useState(false)
  const [retryError, setRetryError] = React.useState<string | null>(null)

  const handleRetry = async () => {
    if (!meetingId) return
    setIsRetrying(true)
    setRetryError(null)
    try {
      await retryMeeting(meetingId)
      await refetch()
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : 'Falha ao reprocessar reunião.')
    } finally {
      setIsRetrying(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
        <div className="h-6 bg-slate-200/60 rounded w-48 mb-6 animate-pulse" />
        <div className="h-10 bg-slate-200/80 rounded w-2/3 mb-8 animate-pulse" />
        <Card className="p-8 space-y-4 animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-1/4" />
          <div className="h-24 bg-slate-100 rounded" />
        </Card>
      </div>
    )
  }

  if (isError || !meeting) {
    return (
      <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
        <Card className="p-10 text-center border-rose-200 bg-rose-50/20">
          <AlertCircle className="w-10 h-10 text-rose-600 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-ink mb-1">Reunião não encontrada</h2>
          <p className="text-sm text-muted mb-6">
            {error instanceof Error
              ? error.message
              : 'Não foi possível carregar os dados desta reunião.'}
          </p>
          <Link to="/meetings">
            <Button variant="outline">Voltar para reuniões</Button>
          </Link>
        </Card>
      </div>
    )
  }

  const isProcessing =
    meeting.status === 'processing' || meeting.status === 'transcribing'

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted mb-6">
        <Link
          to="/meetings"
          className="hover:text-ink hover:underline transition-colors font-medium"
        >
          Reuniões
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-muted/60" />
        <span className="text-ink font-semibold truncate max-w-md">{meeting.title}</span>
      </nav>

      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <h1 className="text-3xl font-bold font-sans text-ink">{meeting.title}</h1>
            <StatusBadge status={meeting.status} />
          </div>
          <p className="text-xs text-muted flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              Criada em {formatMeetingDate(meeting.created_at)}
            </span>
            {meeting.audio && (
              <span className="flex items-center gap-1">
                <FileAudio className="w-3.5 h-3.5" />
                {formatBytes(meeting.audio.file_size_bytes)}
              </span>
            )}
          </p>
        </div>

        {meeting.status === 'failed' && (
          <Button
            onClick={handleRetry}
            isLoading={isRetrying}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Reprocessar reunião
          </Button>
        )}
      </div>

      {retryError && (
        <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
          {retryError}
        </div>
      )}

      {/* Processing State Banner */}
      {isProcessing && (
        <Card className="p-6 mb-8 border-brand/30 bg-surface/40 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center shrink-0">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-ink">
              {meeting.status === 'transcribing'
                ? 'Transcrição de áudio em andamento...'
                : 'Análise e sumarização em andamento...'}
            </h3>
            <p className="text-xs text-muted mt-0.5">
              Esta página é atualizada automaticamente assim que o modelo concluir a
              geração do resumo.
            </p>
          </div>
        </Card>
      )}

      {/* Summary Section (if available) */}
      {meeting.summary && (
        <div className="space-y-6 mb-8">
          <Card className="p-6">
            <div className="flex items-center gap-2 text-brand font-semibold text-sm mb-3">
              <Sparkles className="w-4 h-4" />
              <span>Resumo Executivo</span>
            </div>
            {meeting.summary.objective && (
              <div className="mb-4 p-3.5 rounded-xl bg-surface/50 border border-[#DCE2FB]">
                <p className="text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                  Objetivo
                </p>
                <p className="text-sm text-ink">{meeting.summary.objective}</p>
              </div>
            )}
            <p className="text-sm text-ink leading-relaxed whitespace-pre-line">
              {meeting.summary.summary}
            </p>
          </Card>

          {meeting.summary.tasks?.length > 0 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 text-ink font-semibold text-sm mb-4">
                <ListTodo className="w-4 h-4 text-brand" />
                <span>Tarefas e Próximos Passos ({meeting.summary.tasks.length})</span>
              </div>
              <ul className="space-y-2.5">
                {meeting.summary.tasks.map((task) => (
                  <li
                    key={task.id}
                    className="flex items-start gap-3 p-3 rounded-xl bg-slate-50/70 border border-slate-100 text-sm"
                  >
                    <CheckCircle2 className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-ink font-medium">{task.description}</p>
                      <div className="flex items-center gap-3 text-xs text-muted mt-1">
                        {task.responsible && (
                          <span>
                            Responsável: <strong>{task.responsible}</strong>
                          </span>
                        )}
                        {task.deadline && <span>Prazo: {task.deadline}</span>}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* Transcript Section (if available) */}
      {meeting.transcript && (
        <Card className="p-6">
          <h3 className="text-sm font-semibold text-ink mb-4">
            Transcrição com Identificação de Locutores
          </h3>
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
            {meeting.transcript.segments?.length ? (
              meeting.transcript.segments.map((seg, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-slate-50/60 border border-slate-100 flex items-start gap-3 text-xs"
                >
                  <span className="font-mono text-muted/80 shrink-0">
                    {formatSecondsToTime(seg.start_time)}
                  </span>
                  <div className="flex-1">
                    {seg.speaker && (
                      <span className="font-semibold text-brand block mb-0.5">
                        {seg.speaker}
                      </span>
                    )}
                    <p className="text-ink leading-relaxed">{seg.text}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-ink leading-relaxed whitespace-pre-line">
                {meeting.transcript.content}
              </p>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
