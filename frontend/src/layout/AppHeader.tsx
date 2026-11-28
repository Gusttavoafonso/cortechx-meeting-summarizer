import React, { useEffect, useId, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogIn, LogOut, Menu, X } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { useAuth } from '../contexts/AuthContext'
import { AppNavigation } from './Sidebar'

export const AppHeader: React.FC = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const menuId = useId()
  const menuRef = useRef<HTMLDialogElement>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const logoutDialogId = useId()
  const logoutRef = useRef<HTMLDialogElement>(null)
  const logoutCancelRef = useRef<HTMLButtonElement>(null)
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  useEffect(() => {
    menuRef.current?.close()
    logoutRef.current?.close()
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
          <Link
            to="/settings?tab=perfil"
            aria-label={`Perfil de ${user.name}`}
            className="flex min-w-0 items-center gap-2 rounded-full px-2 py-1 hover:bg-brand/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-safe:transition-colors"
          >
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
            <span className="truncate font-semibold leading-tight text-ink">
              {user.name}
            </span>
          </Link>
          <button
            type="button"
            aria-label="Sair da conta"
            title="Sair da conta"
            aria-haspopup="dialog"
            aria-controls={logoutDialogId}
            disabled={isLoggingOut}
            onClick={(event) => {
              const dialog = logoutRef.current
              if (!dialog || dialog.open) return
              event.currentTarget.focus()
              dialog.showModal()
              logoutCancelRef.current?.focus()
            }}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-rose-50 hover:text-rose-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50 motion-safe:transition-colors"
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

      <dialog
        id={logoutDialogId}
        ref={logoutRef}
        aria-labelledby={`${logoutDialogId}-title`}
        aria-describedby={`${logoutDialogId}-description`}
        className="modal-dialog-enter m-auto w-11/12 max-w-sm rounded-2xl border border-subtle-border bg-white p-6 text-ink shadow-xl backdrop:bg-ink/40"
      >
        <h2 id={`${logoutDialogId}-title`} className="font-sans text-lg font-semibold">
          Sair da conta?
        </h2>
        <p id={`${logoutDialogId}-description`} className="mt-2 text-sm text-muted">
          Sua sessão será encerrada neste dispositivo.
        </p>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button
            ref={logoutCancelRef}
            type="button"
            variant="outline"
            onClick={() => logoutRef.current?.close()}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            variant="danger"
            onClick={async () => {
              logoutRef.current?.close()
              setIsLoggingOut(true)
              try {
                await logout()
              } catch {
                // AuthContext clears the local session even if the request fails.
              } finally {
                setIsLoggingOut(false)
                navigate('/login')
              }
            }}
          >
            Sair
          </Button>
        </div>
      </dialog>
    </header>
  )
}
