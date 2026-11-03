import React, { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'

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
  const [gisLoaded, setGisLoaded] = useState(false)
  const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) || ''

  useEffect(() => {
    if (!clientId) return

    let intervalId: NodeJS.Timeout | null = null

    const checkGis = () => {
      if (window.google?.accounts?.id) {
        setGisLoaded(true)
        if (intervalId) clearInterval(intervalId)
      }
    }

    if (window.google?.accounts?.id) {
      setGisLoaded(true)
    } else {
      intervalId = setInterval(checkGis, 200)
    }

    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [clientId])

  useEffect(() => {
    if (!clientId || !gisLoaded || !containerRef.current || disabled) return

    try {
      window.google?.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          if (response?.credential) {
            onSuccess(response.credential)
          } else {
            onError?.(new Error('Credencial do Google não recebida'))
          }
        },
      })

      containerRef.current.innerHTML = ''
      window.google?.accounts.id.renderButton(containerRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: text,
        shape: 'rectangular',
        logo_alignment: 'left',
        width: '100%',
      })
    } catch (e) {
      onError?.(e instanceof Error ? e : new Error(String(e)))
    }
  }, [clientId, gisLoaded, disabled, onSuccess, onError, text])

  // Custom Google Button when Client ID is not configured or GIS is loading
  const handleSimulatedOrMissing = () => {
    if (!clientId) {
      const msg =
        'VITE_GOOGLE_CLIENT_ID não está configurado no arquivo .env. Configure sua chave OAuth do Google para autenticar.'
      onError?.(new Error(msg))
    }
  }

  return (
    <div className="w-full">
      {clientId ? (
        <div ref={containerRef} className="w-full min-h-[44px] flex justify-center" />
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={handleSimulatedOrMissing}
            disabled={disabled}
            className="w-full h-11 px-4 flex items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 active:bg-slate-100 text-ink text-sm font-medium transition-colors shadow-xs group"
          >
            {/* Google SVG Logo */}
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
