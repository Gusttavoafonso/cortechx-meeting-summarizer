import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Bell,
  CheckCircle2,
  KeyRound,
  Lock,
  ShieldCheck,
  Sparkles,
  Trash2,
  User as UserIcon,
} from 'lucide-react'
import {
  DiscordIcon,
  GroqIcon,
  NotionIcon,
  ObsidianIcon,
} from '../components/icons/IntegrationIcons'
import {
  deleteIntegration,
  fetchIntegrationsSettings,
  IntegrationStatusItem,
  IntegrationTestResponse,
  LLMProviderName,
  ProviderName,
  testIntegration,
  updateDiscordIntegration,
  updateGroqIntegration,
  updateLlmIntegration,
  updateNotionIntegration,
  updateObsidianIntegration,
} from '../api/settings'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { useAuth } from '../contexts/AuthContext'
import { cn } from '../lib/utils'

type TabType = 'perfil' | 'integracoes' | 'notificacoes'

const NOTIFICATIONS_STORAGE_KEY = 'zumo_browser_notifications'

function resolveTabParam(raw: string | null): TabType {
  if (raw === 'profile' || raw === 'perfil') return 'perfil'
  if (raw === 'notifications' || raw === 'notificacoes') return 'notificacoes'
  return 'integracoes'
}

interface ProviderFeedback {
  ok: boolean
  message: string
}

const LLM_PROVIDER_META: Record<
  LLMProviderName,
  { label: string; defaultModel: string; keyPlaceholder: string; models: string[] }
> = {
  gemini: {
    label: 'Google Gemini',
    defaultModel: 'gemini-2.5-flash',
    keyPlaceholder: 'AIza...',
    models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
  },
  openai: {
    label: 'OpenAI',
    defaultModel: 'gpt-4o-mini',
    keyPlaceholder: 'sk-...',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
  },
  groq: {
    label: 'Groq',
    defaultModel: 'llama-3.3-70b-versatile',
    keyPlaceholder: 'gsk_...',
    models: [
      'llama-3.3-70b-versatile',
      'llama-3.1-8b-instant',
      'meta-llama/llama-4-scout-17b-16e-instruct',
    ],
  },
  anthropic: {
    label: 'Anthropic Claude',
    defaultModel: 'claude-sonnet-4-20250514',
    keyPlaceholder: 'sk-ant-...',
    models: [
      'claude-sonnet-4-20250514',
      'claude-3-5-haiku-latest',
      'claude-3-7-sonnet-latest',
    ],
  },
}

function normalizeLlmProvider(raw?: string | null): LLMProviderName {
  const val = (raw || '').toLowerCase()
  if (val === 'openai' || val === 'groq' || val === 'anthropic') {
    return val
  }
  return 'gemini'
}

export const SettingsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabType>(() =>
    resolveTabParam(searchParams.get('tab'))
  )
  const queryClient = useQueryClient()
  const { user, updateProfile, changePassword } = useAuth()

  useEffect(() => {
    const param = searchParams.get('tab')
    if (param) {
      setActiveTab(resolveTabParam(param))
    }
  }, [searchParams])

  const handleSelectTab = (tab: TabType) => {
    setActiveTab(tab)
    setSearchParams(tab === 'integracoes' ? {} : { tab })
  }

  // ---------------- Integrations state ----------------
  const {
    data: integrationsData,
    isLoading: isLoadingIntegrations,
    isError: isIntegrationsError,
    refetch: refetchIntegrations,
  } = useQuery({
    queryKey: ['settings-integrations'],
    queryFn: fetchIntegrationsSettings,
    staleTime: 15_000,
  })

  const [discordEnabled, setDiscordEnabled] = useState(false)
  const [discordWebhook, setDiscordWebhook] = useState('')

  const [notionEnabled, setNotionEnabled] = useState(false)
  const [notionApiKey, setNotionApiKey] = useState('')
  const [notionDatabaseId, setNotionDatabaseId] = useState('')

  const [obsidianEnabled, setObsidianEnabled] = useState(false)
  const [obsidianVaultPath, setObsidianVaultPath] = useState('')
  const [obsidianNotesFolder, setObsidianNotesFolder] = useState('Reuniões')

  const [groqEnabled, setGroqEnabled] = useState(false)
  const [groqApiKey, setGroqApiKey] = useState('')

  const [llmEnabled, setLlmEnabled] = useState(false)
  const [llmProvider, setLlmProvider] = useState<LLMProviderName>('gemini')
  const [llmModel, setLlmModel] = useState('gemini-2.5-flash')
  const [llmApiKey, setLlmApiKey] = useState('')

  const [busyProvider, setBusyProvider] = useState<ProviderName | null>(null)
  const [providerFeedback, setProviderFeedback] = useState<
    Partial<Record<ProviderName, ProviderFeedback>>
  >({})

  useEffect(() => {
    if (!integrationsData) return
    setDiscordEnabled(integrationsData.discord.enabled)
    setNotionEnabled(integrationsData.notion.enabled)
    setNotionDatabaseId(integrationsData.notion.database_id ?? '')
    setObsidianEnabled(integrationsData.obsidian.enabled)
    setObsidianVaultPath(integrationsData.obsidian.vault_path ?? '')
    setObsidianNotesFolder(integrationsData.obsidian.notes_folder || 'Reuniões')
    setGroqEnabled(integrationsData.groq.enabled)
    if (integrationsData.llm) {
      const activeSub = normalizeLlmProvider(integrationsData.llm.llm_provider)
      setLlmEnabled(integrationsData.llm.enabled)
      setLlmProvider(activeSub)
      setLlmModel(
        integrationsData.llm.llm_model || LLM_PROVIDER_META[activeSub].defaultModel
      )
    }
  }, [integrationsData])

  const handleSelectLlmProvider = (nextProvider: LLMProviderName) => {
    setLlmProvider(nextProvider)
    setLlmApiKey('')
    const savedSub = integrationsData?.llm?.llm_providers?.[nextProvider]
    setLlmModel(savedSub?.llm_model || LLM_PROVIDER_META[nextProvider].defaultModel)
  }

  const refreshIntegrationsAndSystem = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings-integrations'] }),
      queryClient.invalidateQueries({ queryKey: ['system-status'] }),
    ])
  }

  const extractErrMessage = (err: unknown, fallback: string) => {
    if (err instanceof ApiError) return err.message || fallback
    if (err instanceof Error) return err.message || fallback
    return fallback
  }

  const runProviderAction = async (provider: ProviderName, fn: () => Promise<string>) => {
    setBusyProvider(provider)
    setProviderFeedback((prev) => ({ ...prev, [provider]: undefined }))
    try {
      const msg = await fn()
      setProviderFeedback((prev) => ({
        ...prev,
        [provider]: { ok: true, message: msg },
      }))
    } catch (err) {
      setProviderFeedback((prev) => ({
        ...prev,
        [provider]: {
          ok: false,
          message: extractErrMessage(err, 'Falha ao processar solicitação.'),
        },
      }))
    } finally {
      setBusyProvider(null)
    }
  }

  const handleSaveDiscord = () =>
    runProviderAction('discord', async () => {
      await updateDiscordIntegration({
        enabled: discordEnabled,
        ...(discordWebhook.trim() ? { webhook_url: discordWebhook.trim() } : {}),
      })
      setDiscordWebhook('')
      await refreshIntegrationsAndSystem()
      return 'Configuração do Discord salva.'
    })

  const handleSaveNotion = () =>
    runProviderAction('notion', async () => {
      await updateNotionIntegration({
        enabled: notionEnabled,
        ...(notionApiKey.trim() ? { api_key: notionApiKey.trim() } : {}),
        ...(notionDatabaseId.trim() ? { database_id: notionDatabaseId.trim() } : {}),
      })
      setNotionApiKey('')
      await refreshIntegrationsAndSystem()
      return 'Configuração do Notion salva.'
    })

  const handleSaveObsidian = () =>
    runProviderAction('obsidian', async () => {
      await updateObsidianIntegration({
        enabled: obsidianEnabled,
        ...(obsidianVaultPath.trim() ? { vault_path: obsidianVaultPath.trim() } : {}),
        notes_folder: obsidianNotesFolder.trim() || 'Reuniões',
      })
      await refreshIntegrationsAndSystem()
      return 'Configuração do Obsidian salva.'
    })

  const handleSaveGroq = () =>
    runProviderAction('groq', async () => {
      await updateGroqIntegration({
        enabled: groqEnabled,
        ...(groqApiKey.trim() ? { api_key: groqApiKey.trim() } : {}),
      })
      setGroqApiKey('')
      await refreshIntegrationsAndSystem()
      return 'Configuração da chave Groq atualizada.'
    })

  const handleSaveLlm = () =>
    runProviderAction('llm', async () => {
      await updateLlmIntegration({
        enabled: llmEnabled,
        llm_provider: llmProvider,
        llm_model: llmModel.trim() || LLM_PROVIDER_META[llmProvider].defaultModel,
        ...(llmApiKey.trim() ? { api_key: llmApiKey.trim() } : {}),
      })
      setLlmApiKey('')
      await refreshIntegrationsAndSystem()
      return `Configuração de ${LLM_PROVIDER_META[llmProvider].label} atualizada.`
    })

  const handleTestProvider = (provider: ProviderName) =>
    runProviderAction(provider, async () => {
      const res: IntegrationTestResponse = await testIntegration(
        provider,
        provider === 'llm' ? llmProvider : undefined
      )
      if (!res.ok) {
        throw new Error(res.detail)
      }
      return res.detail
    })

  const handleDeleteProvider = (provider: ProviderName, subProvider?: LLMProviderName) =>
    runProviderAction(provider, async () => {
      await deleteIntegration(provider, subProvider)
      if (provider === 'discord') setDiscordWebhook('')
      if (provider === 'notion') {
        setNotionApiKey('')
        setNotionDatabaseId('')
      }
      if (provider === 'obsidian') {
        setObsidianVaultPath('')
        setObsidianNotesFolder('Reuniões')
      }
      if (provider === 'groq') setGroqApiKey('')
      if (provider === 'llm') setLlmApiKey('')
      await refreshIntegrationsAndSystem()
      return 'Configuração pessoal removida.'
    })

  // ---------------- Profile state ----------------
  const [profileName, setProfileName] = useState(user?.name ?? '')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileFeedback, setProfileFeedback] = useState<ProviderFeedback | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordFeedback, setPasswordFeedback] = useState<ProviderFeedback | null>(null)

  useEffect(() => {
    if (user?.name) {
      setProfileName(user.name)
    }
  }, [user?.name])

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileFeedback(null)
    if (!profileName.trim()) {
      setProfileFeedback({ ok: false, message: 'O nome não pode ficar vazio.' })
      return
    }
    try {
      setProfileSaving(true)
      await updateProfile(profileName.trim())
      setProfileFeedback({ ok: true, message: 'Perfil atualizado com sucesso.' })
    } catch (err) {
      setProfileFeedback({
        ok: false,
        message: extractErrMessage(err, 'Erro ao atualizar perfil.'),
      })
    } finally {
      setProfileSaving(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordFeedback(null)
    if (!currentPassword || !newPassword) {
      setPasswordFeedback({
        ok: false,
        message: 'Preencha a senha atual e a nova senha.',
      })
      return
    }
    if (newPassword.length < 8) {
      setPasswordFeedback({
        ok: false,
        message: 'A nova senha deve ter pelo menos 8 caracteres.',
      })
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordFeedback({
        ok: false,
        message: 'A confirmação da nova senha não confere.',
      })
      return
    }
    try {
      setPasswordSaving(true)
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordFeedback({ ok: true, message: 'Senha alterada com sucesso.' })
    } catch (err) {
      setPasswordFeedback({
        ok: false,
        message: extractErrMessage(err, 'Não foi possível alterar a senha.'),
      })
    } finally {
      setPasswordSaving(false)
    }
  }

  // ---------------- Browser Notifications state ----------------
  const [browserNotifications, setBrowserNotifications] = useState<boolean>(() => {
    return localStorage.getItem(NOTIFICATIONS_STORAGE_KEY) === 'true'
  })
  const [permissionState, setPermissionState] = useState<string>(() =>
    typeof window !== 'undefined' && 'Notification' in window
      ? Notification.permission
      : 'unsupported'
  )

  const handleToggleBrowserNotifications = async (checked: boolean) => {
    setBrowserNotifications(checked)
    localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, String(checked))
    if (checked && typeof window !== 'undefined' && 'Notification' in window) {
      try {
        const perm = await Notification.requestPermission()
        setPermissionState(perm)
        if (perm === 'denied') {
          setBrowserNotifications(false)
          localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, 'false')
        }
      } catch {
        // Ignora caso ambiente não suporte requestPermission
      }
    }
  }

  const renderSourceBadge = (item?: IntegrationStatusItem) => {
    if (!item) return null
    if (item.source === 'user') {
      return (
        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
          Conta pessoal
        </span>
      )
    }
    if (item.source === 'env') {
      return (
        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          Configurado no servidor
        </span>
      )
    }
    return (
      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-muted border border-slate-200">
        Não configurado
      </span>
    )
  }

  const renderFeedback = (fb?: ProviderFeedback | null) => {
    if (!fb) return null
    return (
      <div
        className={cn(
          'mt-3 p-2.5 rounded-xl border text-xs flex items-start gap-2',
          fb.ok
            ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
            : 'bg-rose-50 border-rose-200 text-rose-700'
        )}
      >
        {fb.ok ? (
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
        ) : (
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
        )}
        <span>{fb.message}</span>
      </div>
    )
  }

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-3xl font-bold font-sans text-ink">Configurações</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 mb-8">
        <div className="flex gap-8 text-sm font-semibold">
          {(
            [
              { id: 'perfil', label: 'Perfil' },
              { id: 'integracoes', label: 'Integrações' },
              { id: 'notificacoes', label: 'Notificações' },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleSelectTab(tab.id)}
              className={cn(
                'pb-3 transition-colors flex items-center gap-2 relative cursor-pointer',
                activeTab === tab.id
                  ? 'text-ink border-b-2 border-brand font-bold'
                  : 'text-muted hover:text-ink'
              )}
            >
              {activeTab === tab.id && (
                <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
              )}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'integracoes' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold font-sans text-ink mb-1">
              Provedores e integrações
            </h2>
            <p className="text-sm text-muted max-w-2xl">
              As credenciais são salvas por conta e exibidas de forma mascarada. Os
              provedores ativos recebem o resumo ao fim do processamento.
            </p>
          </div>

          {isIntegrationsError && (
            <Card className="p-6 border-rose-200 bg-rose-50/40 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2.5 text-sm text-rose-700">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Não foi possível carregar suas integrações.</span>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetchIntegrations()}>
                Tentar novamente
              </Button>
            </Card>
          )}

          <div
            className={cn(
              'grid grid-cols-1 md:grid-cols-2 gap-6',
              isLoadingIntegrations && 'opacity-70 pointer-events-none'
            )}
          >
            {/* Sumarização com IA (LLM) Card */}
            <Card className="p-6 bg-surface/60 border-[#DCE2FB] md:col-span-2 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-brand text-white flex items-center justify-center shrink-0">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-sans text-ink">
                        Sumarização com IA (LLM)
                      </h3>
                      {renderSourceBadge(integrationsData?.llm)}
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={llmEnabled}
                      onChange={(e) => setLlmEnabled(e.target.checked)}
                      className="w-4 h-4 accent-primary-btn rounded cursor-pointer"
                    />
                    <span>Ativo</span>
                  </label>
                </div>

                {integrationsData?.llm?.llm_providers &&
                  Object.keys(integrationsData.llm.llm_providers).length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 mb-4">
                      <span className="text-[11px] font-semibold text-muted">
                        Cadastrados:
                      </span>
                      {(
                        Object.keys(
                          integrationsData.llm.llm_providers
                        ) as LLMProviderName[]
                      ).map((subKey) => {
                        const meta = LLM_PROVIDER_META[subKey]
                        if (!meta) return null
                        const isActive = integrationsData.llm.llm_provider === subKey
                        const isSelected = llmProvider === subKey
                        return (
                          <button
                            key={subKey}
                            type="button"
                            onClick={() => handleSelectLlmProvider(subKey)}
                            className={cn(
                              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors cursor-pointer',
                              isSelected
                                ? 'bg-primary-btn text-white border-primary-btn'
                                : 'bg-white text-ink border-slate-200 hover:border-brand'
                            )}
                          >
                            <span>{meta.label}</span>
                            {isActive && (
                              <span
                                className={cn(
                                  'text-[10px] px-1.5 py-0.2 rounded-full',
                                  isSelected
                                    ? 'bg-white/20 text-white'
                                    : 'bg-emerald-50 text-emerald-700'
                                )}
                              >
                                Ativo
                              </span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Provedor
                    </label>
                    <select
                      value={llmProvider}
                      onChange={(e) =>
                        handleSelectLlmProvider(normalizeLlmProvider(e.target.value))
                      }
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand"
                    >
                      <option value="gemini">Google Gemini</option>
                      <option value="openai">OpenAI</option>
                      <option value="groq">Groq</option>
                      <option value="anthropic">Anthropic Claude</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Modelo
                    </label>
                    <input
                      type="text"
                      list={`llm-models-${llmProvider}`}
                      value={llmModel}
                      onChange={(e) => setLlmModel(e.target.value)}
                      placeholder={LLM_PROVIDER_META[llmProvider].defaultModel}
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand font-mono"
                    />
                    <datalist id={`llm-models-${llmProvider}`}>
                      {LLM_PROVIDER_META[llmProvider].models.map((m) => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Chave da API ({LLM_PROVIDER_META[llmProvider].label})
                    </label>
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={llmApiKey}
                      onChange={(e) => setLlmApiKey(e.target.value)}
                      placeholder={
                        integrationsData?.llm?.llm_providers?.[llmProvider]
                          ?.api_key_masked ||
                        (integrationsData?.llm?.llm_provider === llmProvider
                          ? integrationsData.llm.api_key_masked
                          : null) ||
                        LLM_PROVIDER_META[llmProvider].keyPlaceholder
                      }
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand font-mono"
                    />
                    {(integrationsData?.llm?.llm_providers?.[llmProvider]
                      ?.api_key_masked ||
                      (integrationsData?.llm?.llm_provider === llmProvider &&
                        integrationsData.llm.api_key_masked)) && (
                      <p className="text-[11px] text-muted mt-1 font-mono">
                        Chave salva:{' '}
                        {integrationsData?.llm?.llm_providers?.[llmProvider]
                          ?.api_key_masked || integrationsData?.llm?.api_key_masked}
                      </p>
                    )}
                  </div>
                </div>

                {renderFeedback(providerFeedback.llm)}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 mt-5 pt-4 border-t border-slate-200/70">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveLlm}
                    isLoading={busyProvider === 'llm'}
                  >
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTestProvider('llm')}
                    disabled={busyProvider !== null}
                  >
                    Testar chave
                  </Button>
                </div>
                {integrationsData?.llm?.source === 'user' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      handleDeleteProvider(
                        'llm',
                        integrationsData?.llm?.llm_providers?.[llmProvider]
                          ? llmProvider
                          : undefined
                      )
                    }
                    disabled={busyProvider !== null}
                    leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-600" />}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Remover chave
                  </Button>
                )}
              </div>
            </Card>

            {/* Discord Card */}
            <Card className="p-6 bg-surface/60 border-[#DCE2FB] flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-[#5865F2] text-white flex items-center justify-center shrink-0">
                      <DiscordIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-sans text-ink">Discord</h3>
                      {renderSourceBadge(integrationsData?.discord)}
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={discordEnabled}
                      onChange={(e) => setDiscordEnabled(e.target.checked)}
                      className="w-4 h-4 accent-primary-btn rounded cursor-pointer"
                    />
                    <span>Ativo</span>
                  </label>
                </div>

                <p className="text-xs text-muted mb-4">
                  Envia o resumo e as tarefas a um canal via webhook.
                </p>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Webhook URL
                    </label>
                    <input
                      type="url"
                      value={discordWebhook}
                      onChange={(e) => setDiscordWebhook(e.target.value)}
                      placeholder={
                        integrationsData?.discord.webhook_preview ||
                        'https://discord.com/api/webhooks/...'
                      }
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand"
                    />
                    {integrationsData?.discord.webhook_preview && (
                      <p className="text-[11px] text-muted mt-1 font-mono truncate">
                        Salvo: {integrationsData.discord.webhook_preview}
                      </p>
                    )}
                  </div>
                </div>

                {renderFeedback(providerFeedback.discord)}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 mt-5 pt-4 border-t border-slate-200/70">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveDiscord}
                    isLoading={busyProvider === 'discord'}
                  >
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTestProvider('discord')}
                    disabled={busyProvider !== null}
                  >
                    Testar envio
                  </Button>
                </div>
                {integrationsData?.discord.source === 'user' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteProvider('discord')}
                    disabled={busyProvider !== null}
                    leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-600" />}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Desconectar
                  </Button>
                )}
              </div>
            </Card>

            {/* Notion Card */}
            <Card className="p-6 bg-surface/60 border-[#DCE2FB] flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-white border border-slate-200 flex items-center justify-center shrink-0">
                      <NotionIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-sans text-ink">Notion</h3>
                      {renderSourceBadge(integrationsData?.notion)}
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={notionEnabled}
                      onChange={(e) => setNotionEnabled(e.target.checked)}
                      className="w-4 h-4 accent-primary-btn rounded cursor-pointer"
                    />
                    <span>Ativo</span>
                  </label>
                </div>

                <p className="text-xs text-muted mb-4">
                  Cria uma página com resumo, decisões e tarefas na base escolhida.
                </p>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Token de Integração (secret_...)
                    </label>
                    <input
                      type="password"
                      value={notionApiKey}
                      onChange={(e) => setNotionApiKey(e.target.value)}
                      placeholder={
                        integrationsData?.notion.api_key_masked || 'secret_...'
                      }
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Database ID
                    </label>
                    <input
                      type="text"
                      value={notionDatabaseId}
                      onChange={(e) => setNotionDatabaseId(e.target.value)}
                      placeholder="UUID da database no Notion"
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand font-mono"
                    />
                  </div>
                </div>

                {renderFeedback(providerFeedback.notion)}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 mt-5 pt-4 border-t border-slate-200/70">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveNotion}
                    isLoading={busyProvider === 'notion'}
                  >
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTestProvider('notion')}
                    disabled={busyProvider !== null}
                  >
                    Testar conexão
                  </Button>
                </div>
                {integrationsData?.notion.source === 'user' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteProvider('notion')}
                    disabled={busyProvider !== null}
                    leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-600" />}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Desconectar
                  </Button>
                )}
              </div>
            </Card>

            {/* Obsidian Card */}
            <Card className="p-6 bg-surface/60 border-[#DCE2FB] flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-[#7C3AED] text-white flex items-center justify-center shrink-0">
                      <ObsidianIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-sans text-ink">Obsidian</h3>
                      {renderSourceBadge(integrationsData?.obsidian)}
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={obsidianEnabled}
                      onChange={(e) => setObsidianEnabled(e.target.checked)}
                      className="w-4 h-4 accent-primary-btn rounded cursor-pointer"
                    />
                    <span>Ativo</span>
                  </label>
                </div>

                <p className="text-xs text-muted mb-4">
                  Salva arquivos Markdown no vault local.
                </p>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Caminho do Vault (visto pelo backend)
                    </label>
                    <input
                      type="text"
                      value={obsidianVaultPath}
                      onChange={(e) => setObsidianVaultPath(e.target.value)}
                      placeholder="/caminho/para/seu/vault"
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-ink-light mb-1">
                      Pasta de Notas (relativa ao vault)
                    </label>
                    <input
                      type="text"
                      value={obsidianNotesFolder}
                      onChange={(e) => setObsidianNotesFolder(e.target.value)}
                      placeholder="Reuniões"
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand"
                    />
                  </div>
                </div>

                {renderFeedback(providerFeedback.obsidian)}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 mt-5 pt-4 border-t border-slate-200/70">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveObsidian}
                    isLoading={busyProvider === 'obsidian'}
                  >
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTestProvider('obsidian')}
                    disabled={busyProvider !== null}
                  >
                    Testar vault
                  </Button>
                </div>
                {integrationsData?.obsidian.source === 'user' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteProvider('obsidian')}
                    disabled={busyProvider !== null}
                    leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-600" />}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Desconectar
                  </Button>
                )}
              </div>
            </Card>

            {/* Groq Cloud Card */}
            <Card className="p-6 bg-surface/60 border-[#DCE2FB] flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-[#F55036] text-white flex items-center justify-center shrink-0">
                      <GroqIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-sans text-ink">
                        Groq Cloud (STT Opcional)
                      </h3>
                      {renderSourceBadge(integrationsData?.groq)}
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={groqEnabled}
                      onChange={(e) => setGroqEnabled(e.target.checked)}
                      className="w-4 h-4 accent-primary-btn rounded cursor-pointer"
                    />
                    <span>Ativo</span>
                  </label>
                </div>

                <p className="text-xs text-muted mb-4 leading-relaxed">
                  Use uma chave Groq (<code className="font-mono">gsk_...</code>) para
                  transcrever na nuvem. Sem ela, o Zumo usa o Whisper local.
                </p>

                <div>
                  <label className="block text-xs font-semibold text-ink-light mb-1">
                    GROQ_API_KEY pessoal
                  </label>
                  <input
                    type="password"
                    value={groqApiKey}
                    onChange={(e) => setGroqApiKey(e.target.value)}
                    placeholder={integrationsData?.groq.api_key_masked || 'gsk_...'}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-ink bg-white focus:outline-none focus:border-brand font-mono"
                  />
                  {integrationsData?.groq.api_key_masked && (
                    <p className="text-[11px] text-muted mt-1 font-mono">
                      Chave salva: {integrationsData.groq.api_key_masked}
                    </p>
                  )}
                </div>

                {renderFeedback(providerFeedback.groq)}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 mt-5 pt-4 border-t border-slate-200/70">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleSaveGroq}
                    isLoading={busyProvider === 'groq'}
                  >
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTestProvider('groq')}
                    disabled={busyProvider !== null}
                  >
                    Testar chave
                  </Button>
                </div>
                {integrationsData?.groq.source === 'user' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteProvider('groq')}
                    disabled={busyProvider !== null}
                    leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-600" />}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Remover chave
                  </Button>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'perfil' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-7">
            <div className="flex items-center gap-3 mb-5">
              {user?.picture_url ? (
                <img
                  src={user.picture_url}
                  alt={user.name}
                  className="w-12 h-12 rounded-full object-cover border border-slate-200"
                />
              ) : (
                <div className="w-12 h-12 rounded-full bg-surface text-brand flex items-center justify-center font-bold text-lg">
                  {user?.name?.charAt(0).toUpperCase() || (
                    <UserIcon className="w-5 h-5" />
                  )}
                </div>
              )}
              <div>
                <h3 className="text-lg font-bold font-sans text-ink">Dados do Perfil</h3>
              </div>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                  Nome
                </label>
                <input
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  required
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                  E-mail
                </label>
                <input
                  type="email"
                  value={user?.email ?? ''}
                  readOnly
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-muted bg-slate-50 cursor-not-allowed"
                />
              </div>

              {renderFeedback(profileFeedback)}

              <div className="pt-2">
                <Button type="submit" isLoading={profileSaving}>
                  Salvar alterações
                </Button>
              </div>
            </form>
          </Card>

          <Card className="p-7">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-surface text-brand flex items-center justify-center">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold font-sans text-ink">Alterar senha</h3>
              </div>
            </div>

            {user?.has_password === false ? (
              <div className="p-4 rounded-xl bg-surface/70 border border-[#DCE2FB] text-xs text-ink-light flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  Sua conta usa apenas o login do Google e não tem senha local.
                </p>
              </div>
            ) : (
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                    Senha atual
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                      className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                    Nova senha
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    maxLength={128}
                    autoComplete="new-password"
                    placeholder="Mínimo de 8 caracteres"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                    Confirmar nova senha
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={8}
                    maxLength={128}
                    autoComplete="new-password"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
                  />
                </div>

                {renderFeedback(passwordFeedback)}

                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="outline"
                    leftIcon={<Lock className="w-4 h-4" />}
                    isLoading={passwordSaving}
                  >
                    Alterar senha
                  </Button>
                </div>
              </form>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'notificacoes' && (
        <Card className="p-8 max-w-2xl">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-surface text-brand flex items-center justify-center">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold font-sans text-ink">
                Preferências de Notificação
              </h3>
            </div>
          </div>

          <div className="space-y-4 mt-6">
            <label className="flex items-start justify-between gap-4 p-4 rounded-xl bg-surface/50 border border-[#DCE2FB] cursor-pointer">
              <div>
                <p className="text-sm font-semibold text-ink">
                  Notificar no navegador quando uma reunião for concluída
                </p>
                <p className="text-xs text-muted mt-0.5">
                  Preferência salva neste dispositivo.
                </p>
              </div>
              <input
                type="checkbox"
                checked={browserNotifications}
                onChange={(e) => handleToggleBrowserNotifications(e.target.checked)}
                className="w-4 h-4 mt-1 accent-primary-btn rounded cursor-pointer"
              />
            </label>

            <div className="text-xs text-muted flex items-center justify-between px-1">
              <span>
                Permissão do navegador:{' '}
                <strong className="text-ink">
                  {permissionState === 'granted'
                    ? 'Permitida'
                    : permissionState === 'denied'
                      ? 'Bloqueada no navegador'
                      : permissionState === 'default'
                        ? 'Aguardando solicitação'
                        : 'Não suportada neste ambiente'}
                </strong>
              </span>
              {permissionState === 'granted' && browserNotifications && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    new Notification('CortechX Zumo', {
                      body: 'As notificações no navegador estão ativas.',
                    })
                  }
                >
                  Testar notificação
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
