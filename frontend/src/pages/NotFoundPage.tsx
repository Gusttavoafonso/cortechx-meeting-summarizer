import React from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <Card className="p-12 text-center max-w-md w-full">
        <h1 className="text-4xl font-bold font-fredoka text-ink mb-2">404</h1>
        <p className="text-sm text-muted mb-6">Página não encontrada no Zumo.</p>
        <Link to="/meetings">
          <Button>Voltar para o início</Button>
        </Link>
      </Card>
    </div>
  )
}
