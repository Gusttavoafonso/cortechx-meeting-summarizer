import React, { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Mail,
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  KeyRound,
} from 'lucide-react'
import { ZumoLogo } from '../../components/ZumoLogo'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { GoogleLoginButton } from '../../components/auth/GoogleLoginButton'
import { useAuth } from '../../contexts/AuthContext'
import { ApiError } from '../../api/client'

export const LoginPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialMode = searchParams.get('mode') === 'register' ? 'register' : 'login'
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Password recovery 2-step state
  const [recoveryStep, setRecoveryStep] = useState<'closed' | 'request' | 'confirm'>(
    'closed'
  )
  const [recoveryEmail, setRecoveryEmail] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [debugTokenHint, setDebugTokenHint] = useState<string | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const {
    login,
    register,
    loginWithGoogle,
    forgotPassword,
    resetPassword,
    isAuthenticated,
  } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const fromLocation = (
    location.state as { from?: { pathname?: string; search?: string } } | null
  )?.from
  const redirectTarget = fromLocation?.pathname
    ? `${fromLocation.pathname}${fromLocation.search ?? ''}`
    : '/meetings'

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectTarget, { replace: true })
    }
  }, [isAuthenticated, navigate, redirectTarget])

  // Sync mode with query parameter
  const handleSwitchMode = (newMode: 'login' | 'register') => {
    setMode(newMode)
    setRecoveryStep('closed')
    setError(null)
    setSuccessMessage(null)
    setSearchParams(newMode === 'register' ? { mode: 'register' } : {})
  }

  const openForgotPassword = () => {
    setError(null)
    setSuccessMessage(null)
    setDebugTokenHint(null)
    setRecoveryEmail(email)
    setResetToken('')
    setNewPassword('')
    setConfirmPassword('')
    setRecoveryStep('request')
  }

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMessage(null)
    if (!recoveryEmail.trim()) {
      setError('Informe seu e-mail cadastrado.')
      return
    }
    try {
      setIsSubmitting(true)
      const res = await forgotPassword(recoveryEmail.trim())
      setSuccessMessage(res.message)
      if (res.reset_token) {
        setDebugTokenHint(res.reset_token)
        setResetToken(res.reset_token)
      }
      setRecoveryStep('confirm')
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message || 'Erro ao solicitar recuperação de senha.')
      } else {
        setError('Erro ao solicitar recuperação de senha.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMessage(null)
    if (!resetToken.trim()) {
      setError('Informe o token de recuperação.')
      return
    }
    if (newPassword.length < 8) {
      setError('A nova senha deve conter no mínimo 8 caracteres.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('A confirmação de senha não confere.')
      return
    }
    try {
      setIsSubmitting(true)
      const res = await resetPassword(resetToken.trim(), newPassword)
      setRecoveryStep('closed')
      setMode('login')
      setEmail(recoveryEmail.trim())
      setPassword('')
      setSuccessMessage(res.message || 'Senha redefinida com sucesso. Faça login.')
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message || 'Token inválido ou expirado.')
      } else {
        setError('Não foi possível redefinir a senha.')
      }
    } finally {
      setIsSubmitting(false)
    }
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
      navigate(redirectTarget, { replace: true })
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const detail = (err.data as { detail?: unknown })?.detail
        setError(
          typeof detail === 'string' && detail
            ? detail
            : err.message || 'Erro ao realizar autenticação.'
        )
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Ocorreu um erro inesperado ao conectar ao servidor.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoogleSuccess = useCallback(
    async (credential: string) => {
      setError(null)
      try {
        setIsSubmitting(true)
        await loginWithGoogle(credential)
        navigate(redirectTarget, { replace: true })
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          const detail = (err.data as { detail?: unknown })?.detail
          setError(typeof detail === 'string' && detail ? detail : err.message)
        } else if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('Falha ao autenticar com a conta do Google.')
        }
      } finally {
        setIsSubmitting(false)
      }
    },
    [loginWithGoogle, navigate, redirectTarget]
  )

  const handleGoogleError = useCallback((err: Error) => {
    setError(err.message)
  }, [])

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
            <h1 className="text-2xl font-bold font-sans text-ink">
              {recoveryStep !== 'closed'
                ? 'Recuperar senha'
                : mode === 'login'
                  ? 'Bem-vindo de volta'
                  : 'Crie sua conta'}
            </h1>
            <p className="text-xs text-muted mt-1">
              {recoveryStep === 'request'
                ? 'Informe seu e-mail para gerar um token de redefinição.'
                : recoveryStep === 'confirm'
                  ? 'Informe o token de recuperação e defina uma nova senha.'
                  : mode === 'login'
                    ? 'Acesse suas reuniões e resumos inteligentes.'
                    : 'Comece a transcrever e resumir conversas com IA.'}
            </p>
          </div>

          {/* Mode Switch Tabs */}
          {recoveryStep === 'closed' && (
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
          )}

          {/* Success Alert */}
          {successMessage && (
            <div className="mb-5 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2 animate-in fade-in duration-200">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{successMessage}</span>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2 animate-in fade-in duration-200">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          {recoveryStep === 'request' ? (
            <form onSubmit={handleRequestReset} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink-light mb-1.5">
                  E-mail da conta
                </label>
                <Input
                  type="email"
                  placeholder="seu.email@exemplo.com"
                  value={recoveryEmail}
                  onChange={(e) => setRecoveryEmail(e.target.value)}
                  leftIcon={<Mail className="w-4 h-4" />}
                  required
                  disabled={isSubmitting}
                  autoComplete="email"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-11 justify-center font-bold text-sm shadow-sm"
                isLoading={isSubmitting}
              >
                Gerar token de recuperação
              </Button>

              <div className="flex items-center justify-between text-xs pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    setRecoveryStep('confirm')
                  }}
                  className="text-brand font-semibold hover:underline"
                >
                  Já tenho um token
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    setSuccessMessage(null)
                    setRecoveryStep('closed')
                  }}
                  className="text-muted hover:text-ink"
                >
                  Voltar ao login
                </button>
              </div>
            </form>
          ) : recoveryStep === 'confirm' ? (
            <form onSubmit={handleConfirmReset} className="space-y-4">
              {debugTokenHint && (
                <div className="p-3 rounded-xl bg-surface/80 border border-[#DCE2FB] text-[11px] text-ink">
                  <p className="font-semibold mb-1">Token local gerado (DEBUG):</p>
                  <p className="font-mono break-all select-all text-brand">
                    {debugTokenHint}
                  </p>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-ink-light mb-1.5">
                  Token de recuperação
                </label>
                <Input
                  type="text"
                  placeholder="Cole o token de recuperação"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  leftIcon={<KeyRound className="w-4 h-4" />}
                  required
                  disabled={isSubmitting}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-light mb-1.5">
                  Nova senha
                </label>
                <Input
                  type="password"
                  placeholder="Mínimo de 8 caracteres"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  leftIcon={<Lock className="w-4 h-4" />}
                  required
                  disabled={isSubmitting}
                  autoComplete="new-password"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-light mb-1.5">
                  Confirmar nova senha
                </label>
                <Input
                  type="password"
                  placeholder="Repita a nova senha"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  leftIcon={<Lock className="w-4 h-4" />}
                  required
                  disabled={isSubmitting}
                  autoComplete="new-password"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-11 justify-center font-bold text-sm shadow-sm"
                isLoading={isSubmitting}
              >
                Redefinir senha
              </Button>

              <div className="flex items-center justify-between text-xs pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    setRecoveryStep('request')
                  }}
                  className="text-brand font-semibold hover:underline"
                >
                  Solicitar novo token
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    setSuccessMessage(null)
                    setRecoveryStep('closed')
                  }}
                  className="text-muted hover:text-ink"
                >
                  Voltar ao login
                </button>
              </div>
            </form>
          ) : (
            <>
              {/* Google Sign-In */}
              <div className="mb-6">
                <GoogleLoginButton
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
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
                  <span className="bg-white px-3 text-muted">
                    ou continue com e-mail
                  </span>
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
                      <button
                        type="button"
                        onClick={openForgotPassword}
                        className="text-[11px] text-muted hover:text-brand cursor-pointer transition-colors"
                      >
                        Esqueceu?
                      </button>
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
                    autoComplete={
                      mode === 'login' ? 'current-password' : 'new-password'
                    }
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
            </>
          )}
        </div>
      </div>
    </div>
  )
}
