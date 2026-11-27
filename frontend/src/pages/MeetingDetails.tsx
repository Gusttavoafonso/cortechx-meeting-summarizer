import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  ChevronRight,
  Copy,
  Download,
  FileAudio,
  ListTodo,
  Play,
  PlugZap,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'
import {
  deleteMeeting,
  fetchMeetingById,
  fetchMeetingIntegrations,
  fetchMeetingStatus,
  fetchMeetingSummary,
  getMeetingAudioUrl,
  processMeeting,
  retryMeeting,
  retryMeetingIntegrations,
  uploadMeetingAudio,
} from '../api/meetings'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { MeetingAudioPlayer } from '../components/MeetingAudioPlayer'
import {
  cn,
  formatBytes,
  formatMeetingDate,
  formatSecondsToTime,
} from '../lib/utils'
import { Meeting, SummaryResponse } from '../types/meeting'

function buildMarkdownExport(meeting: Meeting, summary: SummaryResponse | null): string {
  const lines: string[] = [`# ${meeting.title}`, '']
  lines.push(`- **Data:** ${formatMeetingDate(meeting.created_at)}`)
  lines.push(`- **Status:** ${meeting.status}`)
  lines.push('')

  if (summary) {
    if (summary.objective) {
      lines.push('## Objetivo', '', summary.objective, '')
    }
    if (summary.summary) {
      lines.push('## Resumo Executivo', '', summary.summary, '')
    }
    if (summary.key_points?.length) {
      lines.push('## Pontos Principais', '')
      for (const pt of summary.key_points) {
        lines.push(`- ${pt}`)
      }
      lines.push('')
    }
    if (summary.decisions?.length) {
      lines.push('## Decisões', '')
      for (const dec of summary.decisions) {
        lines.push(`- ${dec}`)
      }
      lines.push('')
    }
    if (summary.tasks?.length) {
      lines.push('## Tarefas', '')
      for (const t of summary.tasks) {
        const meta: string[] = []
        if (t.responsible) meta.push(`Responsável: ${t.responsible}`)
        if (t.deadline) meta.push(`Prazo: ${t.deadline}`)
        const suffix = meta.length ? ` (${meta.join(' • ')})` : ''
        lines.push(`- [ ] ${t.description}${suffix}`)
      }
      lines.push('')
    }
  }

  if (meeting.transcript) {
    lines.push('## Transcrição', '')
    if (meeting.transcript.segments?.length) {
      for (const seg of meeting.transcript.segments) {
        lines.push(`- [${formatSecondsToTime(seg.start_time)}] ${seg.text}`)
      }
    } else if (meeting.transcript.content) {
      lines.push(meeting.transcript.content)
    }
    lines.push('')
  }

  return lines.join('\n')
}

export const MeetingDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const meetingId = Number(id)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
  })

  const isProcessing =
    meeting?.status === 'processing' || meeting?.status === 'transcribing'

  // Lightweight polling via /status while processing
  const { data: statusData } = useQuery({
    queryKey: ['meeting-status', meetingId],
    queryFn: () => fetchMeetingStatus(meetingId),
    enabled: !isNaN(meetingId) && meetingId > 0 && isProcessing,
    refetchInterval: isProcessing ? 4000 : false,
  })

  const prevStatusRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    const observedStatus = statusData?.status ?? meeting?.status
    if (!observedStatus) return
    const prev = prevStatusRef.current
    prevStatusRef.current = observedStatus

    if (
      prev &&
      (prev === 'processing' || prev === 'transcribing') &&
      (observedStatus === 'completed' || observedStatus === 'failed')
    ) {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
      queryClient.invalidateQueries({ queryKey: ['meeting-summary', meetingId] })
      queryClient.invalidateQueries({ queryKey: ['meeting-integrations', meetingId] })
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
      queryClient.invalidateQueries({ queryKey: ['meetings-stats'] })
      queryClient.invalidateQueries({ queryKey: ['meetings-tasks'] })

      if (
        observedStatus === 'completed' &&
        localStorage.getItem('zumo_browser_notifications') === 'true' &&
        typeof window !== 'undefined' &&
        'Notification' in window &&
        Notification.permission === 'granted'
      ) {
        new Notification('Reunião concluída', {
          body: `${meeting?.title || 'Sua reunião'} foi processada com sucesso.`,
        })
      }
    }
  }, [statusData?.status, meeting?.status, meeting?.title, meetingId, queryClient])

  const { data: summaryData } = useQuery({
    queryKey: ['meeting-summary', meetingId],
    queryFn: () => fetchMeetingSummary(meetingId),
    enabled: !isNaN(meetingId) && meetingId > 0 && meeting?.status === 'completed',
    retry: false,
  })

  const {
    data: integrationsData,
    isLoading: isLoadingIntegrations,
    refetch: refetchIntegrations,
  } = useQuery({
    queryKey: ['meeting-integrations', meetingId],
    queryFn: () => fetchMeetingIntegrations(meetingId),
    enabled: !isNaN(meetingId) && meetingId > 0 && meeting?.status === 'completed',
    retry: false,
  })

  const [isRetrying, setIsRetrying] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const [recoveryFile, setRecoveryFile] = useState<File | null>(null)
  const [isRecovering, setIsRecovering] = useState(false)

  const [isRetryingIntegrations, setIsRetryingIntegrations] = useState(false)

  const [confirmDelete, setConfirmDelete] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const [copiedSummary, setCopiedSummary] = useState(false)
  const [copiedTranscript, setCopiedTranscript] = useState(false)

  const handleRetry = async () => {
    if (!meetingId) return
    setIsRetrying(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await retryMeeting(meetingId)
      await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
      await queryClient.invalidateQueries({ queryKey: ['meetings'] })
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Falha ao reprocessar reunião.'
      )
    } finally {
      setIsRetrying(false)
    }
  }

  const handleUploadAndProcess = async () => {
    if (!meetingId || !recoveryFile) return
    setIsRecovering(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await uploadMeetingAudio(meetingId, recoveryFile)
      await processMeeting(meetingId)
      setRecoveryFile(null)
      await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
      await queryClient.invalidateQueries({ queryKey: ['meetings'] })
      setActionSuccess('Áudio enviado e processamento iniciado!')
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Falha ao enviar áudio e processar.'
      )
      await refetch()
    } finally {
      setIsRecovering(false)
    }
  }

  const handleStartProcessing = async () => {
    if (!meetingId) return
    setIsRecovering(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await processMeeting(meetingId)
      await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
      await queryClient.invalidateQueries({ queryKey: ['meetings'] })
      setActionSuccess('Processamento iniciado!')
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Falha ao iniciar processamento.'
      )
    } finally {
      setIsRecovering(false)
    }
  }

  const handleRetryIntegrations = async () => {
    if (!meetingId) return
    setIsRetryingIntegrations(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const res = await retryMeetingIntegrations(meetingId)
      await refetchIntegrations()
      setActionSuccess(
        `Reenvio agendado para: ${res.providers.join(', ')}.`
      )
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Falha ao reenviar integrações.'
      )
    } finally {
      setIsRetryingIntegrations(false)
    }
  }

  const handleDelete = async () => {
    if (!meetingId) return
    setIsDeleting(true)
    setActionError(null)
    try {
      await deleteMeeting(meetingId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['meetings'] }),
        queryClient.invalidateQueries({ queryKey: ['meetings-stats'] }),
        queryClient.invalidateQueries({ queryKey: ['meetings-tasks'] }),
      ])
      navigate('/meetings', { replace: true })
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Não foi possível excluir a reunião.'
      )
      setConfirmDelete(false)
    } finally {
      setIsDeleting(false)
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
          <h2 className="text-lg font-bold font-sans text-ink mb-1">Reunião não encontrada</h2>
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

  const fullSummary: SummaryResponse | null =
    summaryData ??
    (meeting.summary && 'key_points' in meeting.summary ? meeting.summary : null)

  const handleCopySummary = async () => {
    const textParts: string[] = []
    if (fullSummary?.objective) {
      textParts.push(`Objetivo: ${fullSummary.objective}`)
    }
    if (fullSummary?.summary) {
      textParts.push(fullSummary.summary)
    } else if (meeting.summary?.summary) {
      textParts.push(meeting.summary.summary)
    }
    if (fullSummary?.key_points?.length) {
      textParts.push(
        `Pontos Principais:\n${fullSummary.key_points.map((p) => `- ${p}`).join('\n')}`
      )
    }
    if (fullSummary?.decisions?.length) {
      textParts.push(
        `Decisões:\n${fullSummary.decisions.map((d) => `- ${d}`).join('\n')}`
      )
    }
    const text = textParts.join('\n\n').trim()
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopiedSummary(true)
      setTimeout(() => setCopiedSummary(false), 2000)
    } catch {
      // Ignora erro de clipboard
    }
  }

  const handleDownloadMarkdown = () => {
    const md = buildMarkdownExport(meeting, fullSummary)
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const safeTitle = meeting.title
      .toLowerCase()
      .replace(/[^a-z0-9-_]+/gi, '-')
      .replace(/^-|-$/g, '')
    a.href = url
    a.download = `${safeTitle || `reuniao-${meeting.id}`}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const handleCopyTranscript = async () => {
    const text = meeting.transcript?.segments?.length
      ? meeting.transcript.segments
          .map((s) => `[${formatSecondsToTime(s.start_time)}] ${s.text}`)
          .join('\n')
      : meeting.transcript?.content || ''
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopiedTranscript(true)
      setTimeout(() => setCopiedTranscript(false), 2000)
    } catch {
      // Ignora erro de clipboard
    }
  }

  const deliveries = integrationsData?.integrations ?? []
  const hasRetryableDelivery =
    deliveries.length === 0 ||
    deliveries.some((d) => d.status === 'failed' || d.status === 'pending')

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
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <h1 className="text-3xl font-bold font-sans text-ink">{meeting.title}</h1>
            <StatusBadge status={meeting.status} className="bg-transparent" />
          </div>
          <p className="text-xs text-muted flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5" />
              Criada em {formatMeetingDate(meeting.created_at)}
            </span>
            {meeting.audio && (
              <span className="flex items-center gap-1">
                <FileAudio className="w-3.5 h-3.5" />
                {formatBytes(meeting.audio.file_size_bytes)}
                {meeting.audio.duration_seconds
                  ? ` • ${formatSecondsToTime(meeting.audio.duration_seconds)}`
                  : ''}
              </span>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(fullSummary || meeting.transcript) && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadMarkdown}
              leftIcon={<Download className="w-3.5 h-3.5" />}
            >
              Baixar .md
            </Button>
          )}

          {meeting.status === 'failed' && (
            <Button
              size="sm"
              onClick={handleRetry}
              isLoading={isRetrying}
              leftIcon={<RefreshCw className="w-4 h-4" />}
            >
              Reprocessar reunião
            </Button>
          )}

          {!confirmDelete ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={isProcessing}
              onClick={() => setConfirmDelete(true)}
              leftIcon={<Trash2 className="w-3.5 h-3.5 text-current" />}
              className="bg-transparent text-rose-600 hover:bg-transparent hover:text-rose-700 active:bg-transparent"
            >
              Excluir
            </Button>
          ) : (
            <div className="flex items-center gap-1.5 bg-rose-50 border border-rose-200 rounded-xl px-2.5 py-1">
              <span className="text-xs text-rose-700 font-medium">Confirmar?</span>
              <Button
                size="sm"
                variant="danger"
                onClick={handleDelete}
                isLoading={isDeleting}
                className="h-7 px-2.5 text-xs"
              >
                Excluir
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmDelete(false)}
                disabled={isDeleting}
                className="h-7 px-2 text-xs"
              >
                Cancelar
              </Button>
            </div>
          )}
        </div>
      </div>

      {actionError && (
        <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{actionError}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Dedicated failure alert displaying last_error */}
      {meeting.status === 'failed' && (
        <Card className="p-5 mb-6 border-rose-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-bold font-sans text-rose-800">
                Falha no processamento desta reunião
              </h3>
              <p className="text-xs font-sans text-rose-700 mt-1 leading-relaxed">
                {meeting.last_error ||
                  'Ocorreu um erro durante a transcrição ou sumarização. Tente reprocessar.'}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Orphan State Recovery: received */}
      {meeting.status === 'received' && (
        <Card className="p-6 mb-8 border-amber-200 bg-amber-50/30">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-sm font-bold font-sans text-ink flex items-center gap-2">
                <Upload className="w-4 h-4 text-amber-600" />
                <span>Reunião aguardando arquivo de áudio</span>
              </h3>
              <p className="text-xs text-muted">
                Selecione a gravação desta reunião para enviar o áudio e iniciar o
                processamento.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,video/*,.mp3,.m4a,.wav,.mp4,.webm,.ogg"
                onChange={(e) => setRecoveryFile(e.target.files?.[0] ?? null)}
                className="hidden"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={isRecovering}
              >
                {recoveryFile ? recoveryFile.name : 'Selecionar áudio'}
              </Button>
              <Button
                size="sm"
                onClick={handleUploadAndProcess}
                disabled={!recoveryFile}
                isLoading={isRecovering}
                leftIcon={<Play className="w-3.5 h-3.5" />}
              >
                Enviar e processar
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Orphan State Recovery: audio_uploaded / transcribed */}
      {(meeting.status === 'audio_uploaded' || meeting.status === 'transcribed') && (
        <Card className="p-6 mb-8 border-brand/25 bg-surface/50">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-sm font-bold font-sans text-ink">
                {meeting.status === 'audio_uploaded'
                  ? 'Áudio carregado e pronto para processamento'
                  : 'Transcrição concluída, resumo ainda pendente'}
              </h3>
              <p className="text-xs text-muted">
                Inicie o pipeline para gerar o resumo executivo, extrair tarefas e
                disparar as integrações.
              </p>
            </div>
            <Button
              size="sm"
              onClick={handleStartProcessing}
              isLoading={isRecovering}
              leftIcon={<Play className="w-3.5 h-3.5" />}
            >
              Iniciar processamento
            </Button>
          </div>
        </Card>
      )}

      {/* Processing State Banner */}
      {isProcessing && (
        <Card className="p-6 mb-8 border-brand/30 bg-surface/40 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center shrink-0">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold font-sans text-ink">
              {meeting.status === 'transcribing'
                ? 'Transcrição de áudio em andamento...'
                : 'Análise e sumarização em andamento...'}
            </h3>
            <p className="text-xs text-muted mt-0.5">
              Acompanhando progresso automaticamente a cada 4 segundos.
            </p>
          </div>
        </Card>
      )}

      {/* Native Audio Player */}
      {meeting.audio && (
        <Card className="p-5 mb-8">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <FileAudio className="w-4 h-4 text-brand" />
              <span>Áudio da reunião</span>
              <span className="text-muted font-normal">
                ({meeting.audio.original_filename})
              </span>
            </div>
          </div>
          <MeetingAudioPlayer
            src={getMeetingAudioUrl(meeting.id)}
            durationSeconds={meeting.audio.duration_seconds}
          />
        </Card>
      )}

      {/* Summary Section (if available) */}
      {fullSummary && (
        <div className="space-y-6 mb-8">
          <Card className="p-6">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2 text-brand font-semibold text-sm">
                <Sparkles className="w-4 h-4" />
                <span>Resumo Executivo</span>
              </div>
              <button
                type="button"
                onClick={handleCopySummary}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-ink-light hover:bg-slate-50 transition-colors cursor-pointer"
              >
                {copiedSummary ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Copiado</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-muted" />
                    <span>Copiar resumo</span>
                  </>
                )}
              </button>
            </div>
            {fullSummary.objective && (
              <div className="mb-4 p-3.5 rounded-xl bg-surface/50 border border-[#DCE2FB]">
                <p className="text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                  Objetivo
                </p>
                <p className="text-sm text-ink">{fullSummary.objective}</p>
              </div>
            )}
            <p className="text-sm text-ink leading-relaxed whitespace-pre-line">
              {fullSummary.summary}
            </p>
            {fullSummary.key_points?.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <p className="text-xs font-semibold text-ink uppercase tracking-wider mb-2">
                  Pontos Principais
                </p>
                <ul className="list-disc list-inside space-y-1 text-sm text-ink-light">
                  {fullSummary.key_points.map((point, idx) => (
                    <li key={idx}>{point}</li>
                  ))}
                </ul>
              </div>
            )}
            {fullSummary.decisions?.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <p className="text-xs font-semibold text-ink uppercase tracking-wider mb-2">
                  Decisões
                </p>
                <ul className="list-disc list-inside space-y-1 text-sm text-ink-light">
                  {fullSummary.decisions.map((decision, idx) => (
                    <li key={idx}>{decision}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {fullSummary.tasks?.length > 0 && (
            <Card className="p-6">
              <div className="flex items-center gap-2 text-ink font-semibold text-sm mb-4">
                <ListTodo className="w-4 h-4 text-brand" />
                <span>Tarefas e Próximos Passos ({fullSummary.tasks.length})</span>
              </div>
              <ul className="space-y-2.5">
                {fullSummary.tasks.map((task) => (
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

      {/* Integrations Delivery Panel */}
      {meeting.status === 'completed' && (
        <Card className="p-6 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2 text-ink font-semibold text-sm">
              <PlugZap className="w-4 h-4 text-brand" />
              <span>Entregas de Integrações</span>
            </div>
            {hasRetryableDelivery && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleRetryIntegrations}
                isLoading={isRetryingIntegrations}
                leftIcon={<Send className="w-3.5 h-3.5" />}
              >
                Reenviar pendentes
              </Button>
            )}
          </div>

          {isLoadingIntegrations ? (
            <p className="text-xs text-muted">Consultando entregas...</p>
          ) : deliveries.length === 0 ? (
            <p className="text-xs text-muted">
              Nenhuma entrega registrada para esta reunião. Caso tenha configurado
              Discord, Notion ou Obsidian, clique em &quot;Reenviar pendentes&quot;.
            </p>
          ) : (
            <div className="space-y-2.5">
              {deliveries.map((delivery) => (
                <div
                  key={delivery.provider}
                  className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-ink capitalize">
                        {delivery.provider}
                      </span>
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded-full font-semibold border text-[11px]',
                          delivery.status === 'success'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : delivery.status === 'failed'
                              ? 'bg-rose-50 text-rose-700 border-rose-200'
                              : delivery.status === 'running'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                        )}
                      >
                        {delivery.status === 'success'
                          ? 'Entregue'
                          : delivery.status === 'failed'
                            ? 'Falhou'
                            : delivery.status === 'running'
                              ? 'Enviando'
                              : 'Pendente'}
                      </span>
                      <span className="text-muted">
                        ({delivery.attempts}{' '}
                        {delivery.attempts === 1 ? 'tentativa' : 'tentativas'})
                      </span>
                    </div>
                    {delivery.error_message && (
                      <p className="text-rose-700 mt-1">{delivery.error_message}</p>
                    )}
                  </div>
                  <span className="text-[11px] text-muted shrink-0">
                    {formatMeetingDate(delivery.updated_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Transcript Section (if available) */}
      {meeting.transcript && (
        <Card className="p-6">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h3 className="text-sm font-semibold font-sans text-ink">Transcrição da Reunião</h3>
            <button
              type="button"
              onClick={handleCopyTranscript}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-ink-light hover:bg-slate-50 transition-colors cursor-pointer"
            >
              {copiedTranscript ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-emerald-700">Copiada</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-muted" />
                  <span>Copiar transcrição</span>
                </>
              )}
            </button>
          </div>
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
