import React from 'react'
import { NavLink, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutGrid,
  MessagesSquare,
  CheckSquare,
  AudioLines,
  Settings,
  Plus,
  LogOut,
  LogIn,
} from 'lucide-react'
import { ZumoLogo } from '../components/ZumoLogo'
import { Button } from '../components/ui/Button'
import { useAuth } from '../contexts/AuthContext'
import { fetchSystemStatus } from '../api/system'
import { cn } from '../lib/utils'

interface NavItem {
  name: string
  to: string
  icon: React.ElementType
}

const navItems: NavItem[] = [
  { name: 'Dashboard', to: '/dashboard', icon: LayoutGrid },
  { name: 'Reuniões', to: '/meetings', icon: MessagesSquare },
  { name: 'Tarefas', to: '/tasks', icon: CheckSquare },
  { name: 'Transcrições', to: '/transcripts', icon: AudioLines },
  { name: 'Configurações', to: '/settings', icon: Settings },
]

export const Sidebar: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { data: systemStatus, isError: isSystemError } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    retry: 1,
    staleTime: 30_000,
  })

  return (
    <aside className="w-56 bg-surface shrink-0 min-h-screen flex flex-col px-3.5 py-4 select-none border-r border-[#DCE2FB]">
      {/* Brand Header */}
      <div className="flex items-center justify-between mb-5 px-2">
        <NavLink
          to="/meetings"
          className="hover:opacity-90 transition-opacity focus:outline-hidden"
        >
          <ZumoLogo size="sm" />
        </NavLink>
      </div>

      {/* Main Action Button */}
      <div className="mb-4">
        <Button
          onClick={() => navigate('/meetings/new')}
          leftIcon={<Plus className="w-3.5 h-3.5 stroke-[2.5]" />}
          className="w-full h-9 justify-center font-semibold text-xs shadow-sm"
        >
          Nova Reunião
        </Button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-semibold transition-all duration-150',
                  isActive
                    ? 'bg-primary-btn text-white shadow-xs'
                    : 'text-ink-light hover:text-ink hover:bg-slate-200/50'
                )
              }
            >
              <Icon className="w-4 h-4 stroke-[2]" />
              <span>{item.name}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom Shortcuts / Status */}
      <div className="pt-3 border-t border-slate-200/60 mb-2.5 px-1">
        <Link
          to="/settings?tab=integrations"
          className="block bg-white/60 hover:bg-white border border-slate-200/80 rounded-xl p-2.5 transition-colors"
        >
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                'w-2 h-2 rounded-full shrink-0',
                isSystemError
                  ? 'bg-rose-500'
                  : systemStatus?.stt_mode === 'groq'
                    ? 'bg-emerald-500'
                    : 'bg-brand'
              )}
            />
            <p className="text-[11px] font-semibold text-ink truncate">
              {isSystemError
                ? 'Backend Indisponível'
                : systemStatus?.stt_mode === 'groq'
                  ? 'Groq Cloud Ativo'
                  : 'Whisper Local Ativo'}
            </p>
          </div>
          <p className="text-[10px] text-muted mt-0.5 leading-snug">
            {isSystemError
              ? 'Verifique o servidor na porta 8000.'
              : systemStatus?.stt_mode === 'groq'
                ? systemStatus.stt_source === 'user'
                  ? 'Usando sua chave API pessoal.'
                  : 'Usando chave configurada no servidor.'
                : `Modelo ${systemStatus?.whisper_model || 'small'} local.`}
          </p>
        </Link>
      </div>

      {/* User / Workspace Footer */}
      <div className="pt-3 border-t border-slate-200/40 px-1.5 flex items-center justify-between gap-2 text-xs text-muted">
        {user ? (
          <>
            <div className="flex items-center gap-2 min-w-0 flex-1">
              {user.picture_url ? (
                <img
                  src={user.picture_url}
                  alt={user.name}
                  className="w-7 h-7 rounded-full object-cover shrink-0 border border-slate-200"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-brand/10 text-brand flex items-center justify-center font-bold text-[11px] shrink-0">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="truncate font-semibold text-ink leading-tight">
                  {user.name}
                </p>
                <p className="text-[10px] text-muted truncate">Conectado</p>
              </div>
            </div>
            <button
              type="button"
              onClick={async () => {
                await logout()
                navigate('/login')
              }}
              title="Sair da conta"
              className="p-1.5 rounded-lg text-muted hover:text-rose-600 hover:bg-rose-50 transition-colors shrink-0 cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </>
        ) : (
          <Link
            to="/login"
            className="flex items-center justify-between w-full p-1 rounded-lg text-xs font-semibold text-brand hover:underline"
          >
            <span>Fazer login</span>
            <LogIn className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </aside>
  )
}
