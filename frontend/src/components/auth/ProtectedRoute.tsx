import React from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

/**
 * Guard de rotas autenticadas. Use como rota de layout (sem path) envolvendo
 * tudo o que exige login: o usuário deslogado vai para /login antes de
 * qualquer tela (ou AppLayout) ser renderizada.
 */
export const ProtectedRoute: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // Só bloqueia na verificação INICIAL da sessão. Uma nova verificação com o
  // usuário já carregado não pode desmontar a tela (perderia o estado dela).
  if (isLoading && !isAuthenticated) {
    return (
      <div
        role="status"
        className="min-h-screen bg-page flex items-center justify-center"
      >
        <RefreshCw className="w-6 h-6 text-brand animate-spin" aria-hidden="true" />
        <span className="sr-only">Verificando sessão...</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: {
            pathname: location.pathname,
            search: location.search,
            hash: location.hash,
          },
        }}
      />
    )
  }

  return <Outlet />
}