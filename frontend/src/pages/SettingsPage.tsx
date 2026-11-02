import React, { useState } from 'react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { cn } from '../lib/utils'

type TabType = 'perfil' | 'integracoes' | 'notificacoes'

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('integracoes')

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      {/* Page Title */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold font-fredoka text-ink">Settings</h1>
        <p className="text-sm text-muted mt-1">
          Ajuste sua conta e escolha para onde os resumos das reuniões vão.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 mb-10">
        <div className="flex gap-8 text-sm font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab('perfil')}
            className={cn(
              'pb-3 transition-colors relative',
              activeTab === 'perfil'
                ? 'text-ink border-b-2 border-brand font-bold'
                : 'text-muted hover:text-ink'
            )}
          >
            Perfil
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('integracoes')}
            className={cn(
              'pb-3 transition-colors flex items-center gap-2 relative',
              activeTab === 'integracoes'
                ? 'text-ink border-b-2 border-brand font-bold'
                : 'text-muted hover:text-ink'
            )}
          >
            <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
            <span>Integrações</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('notificacoes')}
            className={cn(
              'pb-3 transition-colors relative',
              activeTab === 'notificacoes'
                ? 'text-ink border-b-2 border-brand font-bold'
                : 'text-muted hover:text-ink'
            )}
          >
            Notificações
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'integracoes' && (
        <div>
          <div className="mb-8">
            <h2 className="text-xl font-bold font-fredoka text-ink mb-1">
              Conecte suas ferramentas
            </h2>
            <p className="text-sm text-muted max-w-xl">
              Quando uma reunião termina, o Zumo envia o resumo e as tarefas para onde seu
              time já trabalha.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Notion Card */}
            <div className="bg-surface rounded-2xl p-6 flex flex-col justify-between border border-[#DCE2FB] shadow-xs">
              <div>
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-white border border-slate-200 flex items-center justify-center shrink-0 shadow-xs">
                    {/* Notion SVG icon */}
                    <svg
                      className="w-7 h-7"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M4.459 4.208c.55.458.733.458 1.833.367l11.458-.917c.459 0 .275-.458.184-.55L16.29 1.642A2.08 2.08 0 0 0 14.823 1L3.909 1.825c-.458 0-.55.275-.367.55l.917 1.833zm.917 3.575v13.567c0 .733.367 1.008 1.192.917l12.741-.734c.825-.091.917-.641.917-1.191V6.958c0-.55-.183-.825-.733-.825l-13.2.825c-.642.092-.917.367-.917.825zm11.366 1.467c.092.458 0 .916-.458.916l-.825.092v8.892c-.367.366-.825.55-1.192.55-.458 0-.733-.184-1.192-.642l-4.583-7.242v6.692l1.375.275c.092.458 0 .917-.458.917l-3.3.183c-.092-.458 0-.917.458-.917l.917-.092V9.975l-1.1-.092c-.092-.458 0-.916.458-.916l3.392-.275 4.767 7.333V9.608l-1.1-.091c-.091-.459 0-.917.458-.917l3.242-.275.092.917z"
                        fill="#1D1A2B"
                      />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold font-fredoka text-ink">Notion</h3>
                    <p className="text-xs text-muted mt-1 leading-relaxed">
                      Salve cada resumo como uma página no database que você escolher.
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex justify-end mt-4">
                <Button size="sm" className="px-5 font-semibold">
                  Conectar
                </Button>
              </div>
            </div>

            {/* Discord Card */}
            <div className="bg-surface rounded-2xl p-6 flex flex-col justify-between border border-[#DCE2FB] shadow-xs">
              <div>
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-[#5865F2] flex items-center justify-center shrink-0 shadow-xs">
                    {/* Discord SVG icon */}
                    <svg
                      className="w-7 h-7 text-white"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.893.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold font-fredoka text-ink">Discord</h3>
                    <p className="text-xs text-muted mt-1 leading-relaxed">
                      Publique o resumo em um canal para todo mundo ficar por dentro.
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex justify-end mt-4">
                <Button size="sm" className="px-5 font-semibold">
                  Conectar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'perfil' && (
        <Card className="p-8">
          <h3 className="text-lg font-bold font-fredoka text-ink mb-2">
            Perfil do Usuário
          </h3>
          <p className="text-sm text-muted mb-6">
            Gerencie seu nome, endereço de e-mail e preferências gerais da conta.
          </p>
          <div className="max-w-md space-y-4">
            <div>
              <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                Nome
              </label>
              <input
                type="text"
                defaultValue="Sergio"
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink uppercase tracking-wider mb-1">
                Email
              </label>
              <input
                type="email"
                defaultValue="sergio@cortechx.ai"
                className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-ink bg-white focus:outline-none focus:border-brand"
              />
            </div>
          </div>
        </Card>
      )}

      {activeTab === 'notificacoes' && (
        <Card className="p-8">
          <h3 className="text-lg font-bold font-fredoka text-ink mb-2">
            Preferências de Notificação
          </h3>
          <p className="text-sm text-muted mb-4">
            Escolha quando e como você deseja receber avisos sobre conclusões de
            processamento.
          </p>
          <div className="space-y-3">
            <label className="flex items-center gap-3 text-sm text-ink cursor-pointer">
              <input type="checkbox" defaultChecked className="rounded text-brand" />
              <span>Notificar no navegador quando uma reunião for concluída</span>
            </label>
            <label className="flex items-center gap-3 text-sm text-ink cursor-pointer">
              <input type="checkbox" defaultChecked className="rounded text-brand" />
              <span>Enviar cópia do resumo executivo por e-mail</span>
            </label>
          </div>
        </Card>
      )}
    </div>
  )
}
