import React from 'react'
import { Link } from 'react-router-dom'
import { LayoutGrid, MessagesSquare, Plus } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

export const DashboardPage: React.FC = () => {
  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold font-fredoka text-ink">Dashboard</h1>
        <p className="text-sm text-muted mt-1">
          Visão geral das suas reuniões e atividades recentes.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Reuniões Transcritas
          </p>
          <p className="text-3xl font-bold font-fredoka text-ink">--</p>
        </Card>
        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Horas Processadas
          </p>
          <p className="text-3xl font-bold font-fredoka text-ink">--</p>
        </Card>
        <Card className="p-6">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
            Tarefas Extraídas
          </p>
          <p className="text-3xl font-bold font-fredoka text-ink">--</p>
        </Card>
      </div>

      <Card className="p-10 text-center">
        <div className="w-12 h-12 rounded-xl bg-surface text-brand flex items-center justify-center mx-auto mb-3">
          <LayoutGrid className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold font-fredoka text-ink mb-1">
          Acesse a lista completa de reuniões
        </h3>
        <p className="text-sm text-muted max-w-sm mx-auto mb-6">
          Acompanhe todos os áudios processados, transcrições e resumos na aba de
          Reuniões.
        </p>
        <div className="flex justify-center gap-3">
          <Link to="/meetings">
            <Button variant="outline" leftIcon={<MessagesSquare className="w-4 h-4" />}>
              Ver Reuniões
            </Button>
          </Link>
          <Link to="/meetings/new">
            <Button leftIcon={<Plus className="w-4 h-4" />}>Nova Reunião</Button>
          </Link>
        </div>
      </Card>
    </div>
  )
}
