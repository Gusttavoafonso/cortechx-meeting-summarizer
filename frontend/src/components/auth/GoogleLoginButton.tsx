import React, { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'

const gisFailureMessage =
  'O botão do Google não carregou. Verifique a conexão, os bloqueadores de anúncios ou a origem autorizada no Google Cloud.'

// Typing for Google Identity Services
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
            auto_select?: boolean
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: 'standard' | 'icon'
              theme?: 'outline' | 'filled_blue' | 'filled_black'
              size?: 'large' | 'medium' | 'small'
              text?: 'signin_with' | 'signup_with' | 'continue_with'
              shape?: 'rectangular' | 'pill' | 'circle'
              logo_alignment?: 'left' | 'center'
              width?: string | number
            }
          ) => void
          prompt?: () => void
        }
      }
    }
  }
}

interface GoogleLoginButtonProps {
  onSuccess: (credential: string) => void
  onError?: (err: Error) => void
  disabled?: boolean
  text?: 'continue_with' | 'signin_with' | 'signup_with'
}

export const GoogleLoginButton: React.FC<GoogleLoginButtonProps> = ({
  onSuccess,
  onError,
  disabled = false,
  text = 'continue_with',
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const onSuccessRef = useRef(onSuccess)
  const onErrorRef = useRef(onError)

  const [gisLoaded, setGisLoaded] = useState(false)
  const [gisTimedOut, setGisTimedOut] = useState(false)
  const showGisWarning = gisTimedOut && !gisLoaded
  const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) || ''

  useEffect(() => {
    onSuccessRef.current = onSuccess
    onErrorRef.current = onError
  }, [onSuccess, onError])

  useEffect(() => {
    if (!clientId) return

    let intervalId: ReturnType<typeof setInterval> | null = null
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    if (window.google?.accounts?.id) {
      setGisLoaded(true)
      setGisTimedOut(false)
      return
    }

    intervalId = setInterval(() => {
      if (window.google?.accounts?.id) {
        setGisLoaded(true)
        setGisTimedOut(false)
        if (intervalId) clearInterval(intervalId)
        if (timeoutId) clearTimeout(timeoutId)
      }
    }, 200)

    timeoutId = setTimeout(() => {
      if (!window.google?.accounts?.id) {
        setGisTimedOut(true)
        if (intervalId) clearInterval(intervalId)
      }
    }, 6000)

    return () => {
      if (intervalId) clearInterval(intervalId)
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [clientId])

  useEffect(() => {
    if (!clientId || !gisLoaded || !containerRef.current) return

    try {
      window.google?.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          if (response?.credential) {
            onSuccessRef.current(response.credential)
          } else {
            onErrorRef.current?.(new Error('Credencial do Google não recebida'))
          }
        },
      })

      const containerWidth = containerRef.current.clientWidth || 384
      const buttonWidth = Math.min(400, Math.max(240, containerWidth))

      containerRef.current.innerHTML = ''
      window.google?.accounts.id.renderButton(containerRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text,
        shape: 'rectangular',
        logo_alignment: 'center',
        width: buttonWidth,
      })
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e : new Error(String(e)))
    }
  }, [clientId, gisLoaded, text])

  const handleMissingClientId = () => {
    if (!clientId) {
      onErrorRef.current?.(
        new Error(
          'Configure VITE_GOOGLE_CLIENT_ID no .env com o ID do cliente OAuth do Google.'
        )
      )
    }
  }

  return (
    <div className="w-full">
      {clientId ? (
        <div className="space-y-2">
          <div
            ref={containerRef}
            className={`flex h-11 w-full flex-none items-center justify-center overflow-y-clip transition-opacity ${
              disabled ? 'pointer-events-none opacity-60' : ''
            }`}
          />
          <div>
            <p
              aria-hidden="true"
              className={`text-[11px] text-amber-700 bg-amber-50 border border-amber-200/80 rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 ${showGisWarning ? '' : 'invisible'}`}
            >
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span className="min-w-0 break-words">{gisFailureMessage}</span>
            </p>
            <div role="status" className="sr-only">
              {showGisWarning ? gisFailureMessage : ''}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={handleMissingClientId}
            disabled={disabled}
            className="w-full h-11 px-4 flex items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 active:bg-slate-100 text-ink text-sm font-medium transition-colors shadow-xs group"
          >
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                fill="#EA4335"
              />
            </svg>
            <span>Continuar com o Google</span>
          </button>

          <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200/80 rounded-lg px-2.5 py-1.5 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>
              Adicione <code>VITE_GOOGLE_CLIENT_ID</code> ao <code>.env</code> para login
              do Google
            </span>
          </p>
        </div>
      )}
    </div>
  )
}
