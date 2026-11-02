import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutGrid,
  MessagesSquare,
  CheckCircle2,
  AudioLines,
  Settings,
  Plus,
} from 'lucide-react'
import { ZumoLogo } from '../components/ZumoLogo'
import { Button } from '../components/ui/Button'
import { cn } from '../lib/utils'

interface NavItem {
  name: string
  to: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const navItems: NavItem[] = [
  { name: 'Dashboard', to: '/dashboard', icon: LayoutGrid },
  { name: 'Reuniões', to: '/meetings', icon: MessagesSquare },
  { name: 'Tarefas', to: '/tasks', icon: CheckCircle2 },
  { name: 'Transcrições', to: '/transcripts', icon: AudioLines },
  { name: 'Settings', to: '/settings', icon: Settings },
]

export const Sidebar: React.FC = () => {
  const navigate = useNavigate()

  return (
    <aside className="w-64 bg-surface shrink-0 min-h-screen flex flex-col px-5 py-6 select-none border-r border-[#DCE2FB]">
      {/* Brand Logo */}
      <div className="px-2 mb-8 flex items-center">
        <NavLink
          to="/dashboard"
          className="inline-block hover:opacity-90 transition-opacity"
        >
          <ZumoLogo size="lg" />
        </NavLink>
      </div>

      {/* Main Action: + Nova Reunião */}
      <div className="mb-8">
        <Button
          onClick={() => navigate('/meetings/new')}
          className="w-full justify-center shadow-sm text-sm font-semibold h-11"
          leftIcon={<Plus className="w-4 h-4 stroke-[2.5]" />}
        >
          Nova Reunião
        </Button>
      </div>

      {/* Workspace Navigation */}
      <div className="flex-1">
        <p className="px-3 text-[11px] font-semibold text-muted/80 tracking-wider uppercase mb-3">
          Workspace
        </p>
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group',
                    isActive
                      ? 'text-ink font-semibold bg-white/60 shadow-xs'
                      : 'text-muted hover:text-ink hover:bg-white/30'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? (
                      <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
                    ) : (
                      <span className="w-2 h-2 shrink-0" />
                    )}
                    <Icon
                      className={cn(
                        'w-4 h-4 transition-colors',
                        isActive ? 'text-brand' : 'text-muted group-hover:text-ink'
                      )}
                    />
                    <span className="flex-1">{item.name}</span>
                    {item.badge && (
                      <span className="text-[10px] bg-white/70 text-muted px-1.5 py-0.5 rounded-md font-semibold">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* User / Workspace Footer */}
      <div className="pt-4 border-t border-slate-200/40 px-2 flex items-center gap-2.5 text-xs text-muted">
        <div className="w-7 h-7 rounded-full bg-brand/10 text-brand flex items-center justify-center font-bold text-[11px]">
          Z
        </div>
        <div className="flex-1 min-w-0">
          <p className="truncate font-medium text-ink">CortechX Workspace</p>
          <p className="text-[10px] text-muted truncate">Free plan</p>
        </div>
      </div>
    </aside>
  )
}
