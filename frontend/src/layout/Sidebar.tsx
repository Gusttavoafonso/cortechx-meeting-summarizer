import React, { useId, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutGrid,
  MessagesSquare,
  CheckSquare,
  AudioLines,
  Settings,
  Plus,
  Menu,
} from 'lucide-react'
import { ZumoLogo } from '../components/ZumoLogo'
import { Button } from '../components/ui/Button'
import { SlidingNav } from '../components/ui/SlidingNav'
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

interface AppNavigationProps {
  onNavigate?: () => void
  compact?: boolean
  headerAction?: React.ReactNode
}

export const AppNavigation: React.FC<AppNavigationProps> = ({
  onNavigate,
  compact = false,
  headerAction,
}) => {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const handleLinkClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (
      !event.defaultPrevented &&
      event.button === 0 &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    ) {
      onNavigate?.()
    }
  }

  return (
    <>
      {/* Brand Header */}
      <div
        className={cn(
          'mb-5 flex items-center gap-2',
          compact ? 'flex-col' : 'justify-between'
        )}
      >
        <Link
          to="/dashboard"
          onClick={handleLinkClick}
          aria-label="Zumo, Dashboard"
          title={compact ? 'Zumo, Dashboard' : undefined}
          className="min-w-0 rounded-md hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-safe:transition-opacity"
        >
          {compact ? (
            <img
              src={import.meta.env.BASE_URL + 'zumo-favicon.png'}
              alt=""
              width={601}
              height={590}
              className="block h-7 w-auto"
            />
          ) : (
            <ZumoLogo size="sm" alt="" />
          )}
        </Link>
        {headerAction}
      </div>

      {/* Main Action Button */}
      <div className="mb-4">
        <Button
          onClick={() => {
            navigate('/meetings/new')
            onNavigate?.()
          }}
          aria-label={compact ? 'Nova Reunião' : undefined}
          title={compact ? 'Nova Reunião' : undefined}
          leftIcon={
            <Plus aria-hidden="true" className="h-3.5 w-3.5 shrink-0 stroke-[2.5]" />
          }
          className={cn(
            'h-9 w-full justify-center text-xs font-semibold shadow-sm',
            compact ? 'gap-0 px-0' : 'px-2 [&>span]:truncate'
          )}
        >
          {compact ? null : 'Nova Reunião'}
        </Button>
      </div>

      {/* Navigation Links */}
      <SlidingNav
        label="Navegação do aplicativo"
        locationKey={pathname}
        className="flex flex-1 flex-col gap-0.5 [&>.sliding-nav-indicator]:max-w-full"
        indicatorClassName="bg-brand/15"
      >
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={handleLinkClick}
              title={compact ? item.name : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center rounded-xl py-2 text-[13px] font-semibold motion-safe:transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-btn',
                  compact ? 'justify-center' : 'gap-3 px-3',
                  isActive
                    ? 'text-brand-dark hover:bg-brand/5 active:bg-brand/10'
                    : 'text-ink-light hover:text-ink hover:bg-slate-200/50 active:bg-surface-hover'
                )
              }
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0 stroke-[2]" />
              <span className={compact ? 'sr-only' : 'truncate'}>{item.name}</span>
            </NavLink>
          )
        })}
      </SlidingNav>
    </>
  )
}

export const Sidebar: React.FC = () => {
  const sidebarId = useId()
  const [expanded, setExpanded] = useState(true)
  const toggleLabel = expanded ? 'Recolher barra lateral' : 'Expandir barra lateral'

  return (
    <aside
      id={sidebarId}
      className={cn(
        'hidden min-h-screen shrink-0 select-none flex-col border-r border-[#DCE2FB] bg-surface px-3.5 py-4 motion-safe:transition-[width] motion-safe:duration-200 motion-safe:ease-out md:flex',
        expanded ? 'w-56' : 'w-16'
      )}
    >
      <AppNavigation
        compact={!expanded}
        headerAction={
          <button
            type="button"
            aria-label={toggleLabel}
            title={toggleLabel}
            aria-expanded={expanded}
            aria-controls={sidebarId}
            onClick={() => setExpanded((current) => !current)}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-light hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand motion-safe:transition-colors"
          >
            <Menu aria-hidden="true" className="h-4 w-4" />
          </button>
        }
      />
    </aside>
  )
}
