import React from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, MessagesSquare } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

export const TasksPage: React.FC = () => {
  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold font-fredoka text-ink">Tarefas</h1>
        <p className="text-sm text-muted mt-1">
          Acompanhe itens de ação e prazos identificados automaticamente pela IA.
        </p>
      </div>

      <Card className="p-12 text-center">
        <div className="w-14 h-14 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-7 h-7 stroke-[1.8]" />
        </div>
        <h3 className="text-lg font-bold font-fredoka text-ink mb-1">
          Consolidação de Tarefas
        </h3>
        <p className="text-sm text-muted max-w-md mx-auto mb-6">
          As tarefas extraídas podem ser consultadas diretamente em cada reunião gravada
          ou integradas ao Notion.
        </p>
        <Link to="/meetings">
          <Button leftIcon={<MessagesSquare className="w-4 h-4" />}>
            Ir para Reuniões
          </Button>
        </Link>
      </Card>
    </div>
  )
}
