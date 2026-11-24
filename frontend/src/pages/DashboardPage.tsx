import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  LayoutGrid,
  MessagesSquare,
  Plus,
  RefreshCw,
} from 'lucide-react'
import { fetchMeetingStats } from '../api/meetings'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { formatMeetingDate } from '../lib/utils'

function formatTotalDuration(totalSeconds: number): string {
  if (!totalSeconds || totalSeconds <= 0) return '0h'
  const hours = totalSeconds / 3600
  if (hours >= 1) {
    return `${hours.toFixed(1)}h`
  }
  const minutes = Math.max(1, Math.round(totalSeconds / 60))
  return `${minutes} min`
}

export const DashboardPage: React.FC = () => {
  const {
    data: stats,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['meetings-stats'],
    queryFn: fetchMeetingStats,
    staleTime: 15_000,
  })

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold font-sans text-ink">Dashboard</h1>
          <p className="text-sm text-muted mt-1">
            Visão geral das suas reuniões concluídas, tempo processado e tarefas.
          </p>
        </div>
        <Link to="/meetings/new">
          <Button size="sm" leftIcon={<Plus className="w-4 h-4" />}>
            Nova Reunião
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Reuniões Concluídas
          </p>
          <p className="text-3xl font-bold font-sans text-ink">
            {isLoading ? '--' : (stats?.completed_meetings ?? 0)}
          </p>
          {stats && (
            <p className="text-xs text-muted mt-1">
              {stats.total_meetings}{' '}
              {stats.total_meetings === 1 ? 'reunião no total' : 'reuniões no total'}
              {stats.processing_meetings > 0 &&
                ` • ${stats.processing_meetings} em andamento`}
            </p>
          )}
        </Card>

        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Horas Processadas
          </p>
          <p className="text-3xl font-bold font-sans text-ink">
            {isLoading ? '--' : formatTotalDuration(stats?.total_audio_seconds ?? 0)}
          </p>
          {stats && (
            <p className="text-xs text-muted mt-1">
              Tempo total de áudio enviado
            </p>
          )}
        </Card>

        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Tarefas Extraídas
          </p>
          <p className="text-3xl font-bold font-sans text-ink">
            {isLoading ? '--' : (stats?.total_tasks ?? 0)}
          </p>
          {stats && (
            <p className="text-xs text-muted mt-1">
              Itens de ação identificados pela IA
            </p>
          )}
        </Card>
      </div>

      {isLoading ? (
        <Card className="p-6 space-y-4 animate-pulse">
          <div className="h-5 w-48 bg-slate-200 rounded" />
          {[1, 2, 3].map((idx) => (
            <div key={idx} className="h-14 bg-slate-100 rounded-xl" />
          ))}
        </Card>
      ) : isError ? (
        <Card className="p-8 text-center border-rose-200 bg-rose-50/30">
          <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-ink mb-1">
            Não foi possível carregar os indicadores
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
      ) : !stats || stats.total_meetings === 0 ? (
        <Card className="p-10 text-center">
          <div className="w-12 h-12 rounded-xl bg-surface text-brand flex items-center justify-center mx-auto mb-3">
            <LayoutGrid className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold font-sans text-ink mb-1">
            Nenhuma reunião registrada ainda
          </h3>
          <p className="text-sm text-muted max-w-sm mx-auto mb-6">
            Grave uma reunião ou envie um arquivo de áudio para gerar transcrições,
            resumos e tarefas automaticamente.
          </p>
          <Link to="/meetings/new">
            <Button leftIcon={<Plus className="w-4 h-4" />}>
              Criar primeira reunião
            </Button>
          </Link>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <div>
              <h2 className="text-base font-bold font-sans text-ink">
                Reuniões recentes
              </h2>
              <p className="text-xs text-muted">
                Últimas gravações e status do processamento
              </p>
            </div>
            <Link
              to="/meetings"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline"
            >
              <span>Ver todas</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {stats.recent_meetings.map((meeting) => (
              <div
                key={meeting.id}
                className="px-6 py-4 flex items-center justify-between gap-4 hover:bg-surface/30 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <Link
                      to={`/meetings/${meeting.id}`}
                      className="text-sm font-semibold text-ink hover:text-brand truncate"
                    >
                      {meeting.title}
                    </Link>
                    <StatusBadge status={meeting.status} />
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted mt-1">
                    <span className="inline-flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      {formatMeetingDate(meeting.created_at)}
                    </span>
                    {meeting.summary?.summary && (
                      <span className="truncate max-w-md">
                        {meeting.summary.summary}
                      </span>
                    )}
                  </div>
                </div>

                <Link to={`/meetings/${meeting.id}`} className="shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<MessagesSquare className="w-3.5 h-3.5" />}
                  >
                    Abrir
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
