import React, { useEffect, useId, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogIn, LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { AppNavigation } from './Sidebar'

export const AppHeader: React.FC = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const menuId = useId()
  const menuRef = useRef<HTMLDialogElement>(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    menuRef.current?.close()
  }, [location])

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 768px)')
    const closeOnDesktop = () => {
      if (desktop.matches) menuRef.current?.close()
    }

    desktop.addEventListener('change', closeOnDesktop)
    return () => desktop.removeEventListener('change', closeOnDesktop)
  }, [])

  return (
    <header className="flex min-h-14 items-center justify-between gap-3 border-b border-subtle-border bg-white px-4 py-2 md:justify-end md:px-6">
      <button
        type="button"
        aria-label="Abrir menu de navegação"
        aria-haspopup="dialog"
        aria-controls={menuId}
        aria-expanded={menuOpen}
        onClick={(event) => {
          const menu = menuRef.current
          if (!menu || menu.open) return
          event.currentTarget.focus()
          menu.showModal()
          setMenuOpen(true)
        }}
        className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-ink-light hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand md:hidden"
      >
        <Menu aria-hidden="true" className="h-5 w-5" />
      </button>

      {user ? (
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted">
          {user.picture_url ? (
            <img
              src={user.picture_url}
              alt=""
              className="h-7 w-7 shrink-0 rounded-full border border-slate-200 object-cover"
            />
          ) : (
            <span
              aria-hidden="true"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand/10 text-[11px] font-bold text-brand"
            >
              {user.name.charAt(0).toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate font-semibold leading-tight text-ink">{user.name}</p>
          </div>
          <button
            type="button"
            aria-label="Sair da conta"
            title="Sair da conta"
            onClick={async () => {
              await logout()
              navigate('/login')
            }}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-rose-50 hover:text-rose-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand motion-safe:transition-colors"
          >
            <LogOut aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <Link
          to="/login"
          className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold text-brand hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          Fazer login
          <LogIn aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      )}

      <dialog
        id={menuId}
        ref={menuRef}
        aria-label="Navegação"
        onClose={() => setMenuOpen(false)}
        className="modal-dialog-enter m-auto max-h-[calc(100dvh_-_2rem)] w-11/12 max-w-sm overflow-y-auto rounded-2xl border border-subtle-border bg-surface p-4 text-ink shadow-xl backdrop:bg-ink/40 md:hidden"
      >
        <button
          type="button"
          aria-label="Fechar menu de navegação"
          onClick={() => menuRef.current?.close()}
          className="mb-3 ml-auto grid h-10 w-10 place-items-center rounded-lg text-ink-light hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          <X aria-hidden="true" className="h-5 w-5" />
        </button>
        <AppNavigation onNavigate={() => menuRef.current?.close()} />
      </dialog>
    </header>
  )
}
