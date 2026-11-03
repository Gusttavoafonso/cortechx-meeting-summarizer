import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Mail,
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowLeft,
} from 'lucide-react'
import { ZumoLogo } from '../components/ZumoLogo'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { GoogleLoginButton } from '../components/auth/GoogleLoginButton'
import { useAuth } from '../contexts/AuthContext'
import { ApiError } from '../api/client'

export const LoginPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialMode = searchParams.get('mode') === 'register' ? 'register' : 'login'
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { login, register, loginWithGoogle, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/meetings', { replace: true })
    }
  }, [isAuthenticated, navigate])

  // Sync mode with query parameter
  const handleSwitchMode = (newMode: 'login' | 'register') => {
    setMode(newMode)
    setError(null)
    setSearchParams(newMode === 'register' ? { mode: 'register' } : {})
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!email || !password) {
      setError('Por favor, preencha todos os campos obrigatórios.')
      return
    }

    if (mode === 'register' && !name.trim()) {
      setError('Por favor, informe seu nome completo.')
      return
    }

    if (password.length < 8) {
      setError('A senha deve conter no mínimo 8 caracteres.')
      return
    }

    try {
      setIsSubmitting(true)
      if (mode === 'register') {
        await register({ email, password, name: name.trim() })
      } else {
        await login({ email, password })
      }
      navigate('/meetings')
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const detail = (err.data as { detail?: string })?.detail
        setError(detail || err.message || 'Erro ao realizar autenticação.')
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Ocorreu um erro inesperado ao conectar ao servidor.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoogleSuccess = async (credential: string) => {
    setError(null)
    try {
      setIsSubmitting(true)
      await loginWithGoogle(credential)
      navigate('/meetings')
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const detail = (err.data as { detail?: string })?.detail
        setError(detail || err.message)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Falha ao autenticar com a conta do Google.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-page flex flex-col justify-center py-12 sm:px-6 lg:px-8 selection:bg-surface selection:text-brand relative overflow-hidden">
      {/* Subtle Ambient Light Glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-brand/5 blur-[120px] rounded-full pointer-events-none" />

      {/* Return to Home Link */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4 mb-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Voltar para o site</span>
        </Link>
      </div>

      {/* Main Card Container */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4 relative z-10">
        <div className="bg-white py-8 px-6 sm:px-10 rounded-3xl border border-subtle-border shadow-card">
          {/* Logo & Headline */}
          <div className="text-center mb-6">
            <Link
              to="/"
              className="inline-block hover:opacity-90 transition-opacity mb-3"
            >
              <ZumoLogo size="lg" />
            </Link>
            <h1 className="text-2xl font-bold font-fredoka text-ink">
              {mode === 'login' ? 'Bem-vindo de volta' : 'Crie sua conta'}
            </h1>
            <p className="text-xs text-muted mt-1">
              {mode === 'login'
                ? 'Acesse suas reuniões e resumos inteligentes.'
                : 'Comece a transcrever e resumir conversas com IA.'}
            </p>
          </div>

          {/* Mode Switch Tabs */}
          <div className="flex rounded-xl bg-surface/60 p-1 mb-6 border border-[#DCE2FB]">
            <button
              type="button"
              onClick={() => handleSwitchMode('login')}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                mode === 'login'
                  ? 'bg-white text-ink shadow-xs'
                  : 'text-muted hover:text-ink'
              }`}
            >
              Entrar
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('register')}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                mode === 'register'
                  ? 'bg-white text-ink shadow-xs'
                  : 'text-muted hover:text-ink'
              }`}
            >
              Criar Conta
            </button>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2 animate-in fade-in duration-200">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          {/* Google Sign-In */}
          <div className="mb-6">
            <GoogleLoginButton
              onSuccess={handleGoogleSuccess}
              onError={(err) => setError(err.message)}
              disabled={isSubmitting}
              text={mode === 'login' ? 'continue_with' : 'signup_with'}
            />
          </div>

          {/* Or Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-subtle-border" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-3 text-muted">ou continue com e-mail</span>
            </div>
          </div>

          {/* Email/Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-ink-light mb-1.5">
                  Nome Completo
                </label>
                <Input
                  type="text"
                  placeholder="Seu nome"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  leftIcon={<UserIcon className="w-4 h-4" />}
                  required={mode === 'register'}
                  disabled={isSubmitting}
                  autoComplete="name"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-ink-light mb-1.5">
                E-mail
              </label>
              <Input
                type="email"
                placeholder="seu.email@exemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                leftIcon={<Mail className="w-4 h-4" />}
                required
                disabled={isSubmitting}
                autoComplete="email"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-ink-light">
                  Senha
                </label>
                {mode === 'login' && (
                  <span className="text-[11px] text-muted hover:text-brand cursor-pointer transition-colors">
                    Esqueceu?
                  </span>
                )}
              </div>
              <Input
                type={showPassword ? 'text' : 'password'}
                placeholder="Mínimo de 8 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                leftIcon={<Lock className="w-4 h-4" />}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-muted hover:text-ink focus:outline-none transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                }
                required
                disabled={isSubmitting}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            <Button
              type="submit"
              className="w-full h-11 justify-center font-bold text-sm shadow-sm mt-2"
              isLoading={isSubmitting}
            >
              {mode === 'login' ? 'Entrar no Zumo' : 'Criar minha conta'}
            </Button>
          </form>

          {/* Footer Note */}
          <div className="mt-6 text-center text-xs text-muted">
            {mode === 'login' ? (
              <p>
                Não tem uma conta?{' '}
                <button
                  type="button"
                  onClick={() => handleSwitchMode('register')}
                  className="font-semibold text-brand hover:underline"
                >
                  Cadastre-se gratuitamente
                </button>
              </p>
            ) : (
              <p>
                Já tem uma conta?{' '}
                <button
                  type="button"
                  onClick={() => handleSwitchMode('login')}
                  className="font-semibold text-brand hover:underline"
                >
                  Faça login
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
