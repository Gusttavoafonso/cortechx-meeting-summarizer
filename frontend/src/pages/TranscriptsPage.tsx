import React from 'react'
import { Link } from 'react-router-dom'
import { AudioLines, MessagesSquare } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

export const TranscriptsPage: React.FC = () => {
  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold font-fredoka text-ink">Transcrições</h1>
        <p className="text-sm text-muted mt-1">
          Arquivo textual completo e segmentação por locutores de todas as gravações.
        </p>
      </div>

      <Card className="p-12 text-center">
        <div className="w-14 h-14 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4">
          <AudioLines className="w-7 h-7 stroke-[1.8]" />
        </div>
        <h3 className="text-lg font-bold font-fredoka text-ink mb-1">
          Transcrições Integradas
        </h3>
        <p className="text-sm text-muted max-w-md mx-auto mb-6">
          Selecione qualquer reunião para visualizar o texto integral sincronizado com as
          falas de cada participante.
        </p>
        <Link to="/meetings">
          <Button leftIcon={<MessagesSquare className="w-4 h-4" />}>
            Explorar Reuniões
          </Button>
        </Link>
      </Card>
    </div>
  )
}
