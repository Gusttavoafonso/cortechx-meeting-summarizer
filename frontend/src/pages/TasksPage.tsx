import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ExternalLink,
  MessagesSquare,
  RefreshCw,
  User,
} from 'lucide-react'
import { fetchAllTasks } from '../api/meetings'
import { StatusBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SearchInput } from '../components/ui/Input'

function formatDeadline(deadline: string): string {
  const parts = deadline.split('-')
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`
  }
  return deadline
}

export const TasksPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')

  const {
    data: tasks,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['meetings-tasks'],
    queryFn: fetchAllTasks,
    staleTime: 15_000,
  })

  const filteredTasks = useMemo(() => {
    if (!tasks) return []
    const term = searchTerm.trim().toLowerCase()
    if (!term) return tasks
    return tasks.filter(
      (task) =>
        task.description.toLowerCase().includes(term) ||
        (task.responsible && task.responsible.toLowerCase().includes(term)) ||
        task.meeting_title.toLowerCase().includes(term)
    )
  }, [tasks, searchTerm])

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold font-sans text-ink">Tarefas</h1>
      </div>

      <div className="mb-6">
        <SearchInput
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Buscar por descrição, responsável ou reunião..."
        />
      </div>

      {isLoading ? (
        <Card className="p-6 space-y-3 animate-pulse">
          {[1, 2, 3, 4].map((idx) => (
            <div key={idx} className="h-16 bg-slate-100 rounded-xl" />
          ))}
        </Card>
      ) : isError ? (
        <Card className="p-8 text-center border-rose-200 bg-rose-50/30">
          <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-ink mb-1">
            Não foi possível carregar as tarefas
          </h3>
          <p className="text-sm text-muted mb-5">
            Verifique a conexão com o backend e tente novamente.
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
      ) : filteredTasks.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-7 h-7 stroke-[1.8]" />
          </div>
          <h3 className="text-lg font-bold font-sans text-ink mb-1">
            {searchTerm
              ? `Nenhuma tarefa para “${searchTerm}”`
              : 'Nenhuma tarefa extraída'}
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
          {filteredTasks.map((task) => (
            <div
              key={task.id}
              className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface/30 transition-colors"
            >
              <div className="min-w-0 flex-1 space-y-1.5">
                <p className="text-sm font-semibold text-ink leading-snug">
                  {task.description}
                </p>
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
                  <Link
                    to={`/meetings/${task.meeting_id}`}
                    className="inline-flex items-center gap-1 font-medium text-brand hover:underline"
                  >
                    <MessagesSquare className="w-3.5 h-3.5" />
                    <span>{task.meeting_title}</span>
                  </Link>
                  <StatusBadge status={task.meeting_status} />
                  {task.responsible && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface text-ink-light font-medium">
                      <User className="w-3 h-3 text-brand" />
                      {task.responsible}
                    </span>
                  )}
                  {task.deadline && (
                    <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full font-medium">
                      <Calendar className="w-3 h-3" />
                      {formatDeadline(task.deadline)}
                    </span>
                  )}
                </div>
              </div>

              <Link to={`/meetings/${task.meeting_id}`} className="shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
                >
                  Ver reunião
                </Button>
              </Link>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
