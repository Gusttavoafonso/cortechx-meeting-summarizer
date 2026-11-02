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
              'pb-3 transition-colors flex items-center gap-2 relative',
              activeTab === 'perfil'
                ? 'text-ink border-b-2 border-brand font-bold'
                : 'text-muted hover:text-ink'
            )}
          >
            {activeTab === 'perfil' && (
              <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
            )}
            <span>Perfil</span>
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
            {activeTab === 'integracoes' && (
              <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
            )}
            <span>Integrações</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('notificacoes')}
            className={cn(
              'pb-3 transition-colors flex items-center gap-2 relative',
              activeTab === 'notificacoes'
                ? 'text-ink border-b-2 border-brand font-bold'
                : 'text-muted hover:text-ink'
            )}
          >
            {activeTab === 'notificacoes' && (
              <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
            )}
            <span>Notificações</span>
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
                    {/* Official Notion SVG icon */}
                    <svg
                      className="w-7 h-7"
                      viewBox="0 0 57 57"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M33.9551 0.111328L39.7704 0.149625C39.88 0.23468 39.9686 0.290344 40.0625 0.332203C41.1166 0.808688 42.2593 1.1498 43.2091 1.78303C45.9629 3.61327 48.6522 5.54191 51.3396 7.46967C52.5887 8.36341 53.82 9.29412 54.9716 10.3063C55.8275 11.058 56.2118 12.1245 56.214 13.2619L56.2118 49.0521C56.2105 49.5513 56.125 50.0647 55.986 50.5448C55.3546 52.733 53.9541 54.2306 51.7502 54.8153C50.5879 55.123 49.3602 55.2188 48.1548 55.3181C46.2742 55.4744 44.387 55.551 42.5028 55.6641L38.9386 55.8867L33.2314 56.2225L29.7228 56.4416L23.96 56.7756L20.9818 56.8976C20.886 56.9025 20.7974 57.0365 20.707 57.1113C18.4404 57.1113 16.1755 57.1113 13.8897 57.0748C13.7802 56.988 13.6969 56.9181 13.5994 56.8905C12.218 56.4901 11.0598 55.7269 10.1692 54.6185C8.93564 53.0861 7.76358 51.5066 6.57726 49.9378C5.11931 48.01 3.62351 46.1108 2.24571 44.1278C1.43588 42.9691 1.00212 41.5893 1.00329 40.1756C0.999405 29.6053 1.00074 19.0349 1.0073 8.4645C1.0073 8.15991 1.06073 7.85219 1.11328 7.54938C1.66636 4.29504 4.0755 2.55877 6.94064 2.2368C8.42798 2.06981 9.92557 1.995 11.42 1.89614L15.37 1.66814L17.0679 1.55681L22.189 1.11506L25.0279 0.892406L29.73 0.558422L33.6799 0.325078C33.7761 0.318398 33.8647 0.186141 33.9551 0.111328ZM11.5536 50.8476C11.7905 51.1553 12.0546 51.4474 12.2617 51.7747C13.2654 53.3453 14.7042 53.9158 16.5322 53.7942L28.9159 53.0568L42.8524 52.2147L49.7913 51.7676C51.8477 51.6024 52.8408 50.4909 52.8809 48.4277V47.9824L52.8964 14.1997C52.8982 13.1821 52.5469 12.4705 51.7328 11.9019L41.9253 4.99062C40.3475 3.8426 38.6727 3.30689 36.7329 3.46008L25.7498 4.27233L14.2656 5.11931L7.05731 5.6813C5.60114 5.81489 4.69849 6.70552 4.43754 8.13408C4.37409 8.49874 4.34324 8.86832 4.34536 9.23845L4.31552 38.7368C4.30528 40.6695 4.89665 42.2771 6.05358 43.7555L11.5536 50.8476Z"
                        fill="white"
                      />
                      <path
                        d="M11.5278 50.8177L6.05358 43.7551C4.89666 42.2767 4.30528 40.6695 4.31552 38.7369L4.34536 9.23848C4.34536 8.86976 4.37297 8.4957 4.43754 8.1341C4.69849 6.70599 5.60114 5.81536 7.05731 5.68132L14.2656 5.11934L25.7502 4.27235L36.7329 3.4601C38.6727 3.30691 40.3475 3.84263 41.9253 4.99064C45.1591 7.34412 48.4536 9.61432 51.7328 11.9019C52.5469 12.4706 52.8982 13.1822 52.8964 14.1997L52.8809 47.9842V48.4295C52.8408 50.4909 51.8477 51.6024 49.7913 51.7676C47.4814 51.9537 45.1663 52.074 42.8524 52.2147L28.9159 53.0563L16.5322 53.7942C14.7042 53.9158 13.2654 53.3453 12.2617 51.7747C12.0546 51.4474 11.7905 51.1553 11.5278 50.8177ZM14.3805 30.3369V45.2496L14.384 48.031C14.4081 49.2783 15.0191 49.8995 16.2659 49.9708C16.579 49.9881 16.8956 49.9774 17.2104 49.9583L27.6495 49.3429L47.5839 48.2033C48.8263 48.1339 49.4003 47.5892 49.5165 46.3579C49.5392 46.1366 49.5321 45.9126 49.5321 45.69L49.5339 16.9776C49.5339 16.8106 49.5392 16.6436 49.529 16.4766C49.4542 15.3339 48.9634 14.8677 47.8279 14.9282L37.5541 15.5201C32.7419 15.8 27.9299 16.0817 23.118 16.3653L15.9008 16.7985C14.9808 16.8573 14.5648 17.2541 14.4259 18.1536C14.393 18.3922 14.3784 18.6329 14.3823 18.8737L14.3805 30.3369ZM39.8399 6.85695C38.9684 6.38402 38.0221 6.22727 37.0478 6.28116C35.5502 6.36309 34.0526 6.48645 32.5546 6.59466L11.2023 8.14613C10.557 8.19288 9.9082 8.23964 9.27141 8.35498C9.05765 8.39327 8.7878 8.60881 8.72189 8.80385C8.67291 8.94101 8.88888 9.21799 9.04697 9.3694C9.33954 9.64906 9.67664 9.88373 9.99548 10.1362C10.7521 10.7329 11.5572 11.2771 12.2514 11.9366C13.5682 13.1871 15.1005 13.4761 16.856 13.3492L30.6762 12.4826L45.5541 11.5902C45.69 11.5835 45.8258 11.5416 46.1246 11.486C45.8516 11.2023 45.6931 10.985 45.4864 10.8318C44.7576 10.2935 44.0217 9.76472 43.279 9.2456C42.138 8.44167 40.9916 7.64543 39.8399 6.85695Z"
                        fill="black"
                      />
                      <path
                        d="M14.3805 30.2813L14.3823 18.8737C14.3823 18.6332 14.3894 18.3901 14.4259 18.1536C14.5648 17.2541 14.9808 16.8578 15.9008 16.7986L23.118 16.3653L37.5541 15.5201L47.8274 14.9282C48.9634 14.8677 49.4542 15.3353 49.5285 16.4766C49.5392 16.6436 49.5339 16.8106 49.5339 16.9776L49.5321 45.69L49.5165 46.358C49.4003 47.5892 48.8263 48.1339 47.5839 48.2033L27.6495 49.3429L17.2104 49.9583L16.2664 49.9708C15.0191 49.8995 14.4081 49.2783 14.384 48.0328L14.3805 45.2496V30.2813ZM34.7606 30.3107L29.0304 21.5803C28.8304 21.2757 28.634 21.1751 28.2653 21.2152L25.8228 21.3799L21.3296 21.709C20.2252 21.8101 19.5572 22.8486 19.8632 23.9253L22.2429 24.1288V43.4078L20.622 43.8651C19.9032 44.0771 19.5955 44.6827 19.8373 45.4566L25.3182 45.1418L27.4771 44.9646C28.4078 44.8114 28.9088 44.2409 29.0339 43.3102L26.037 42.6267V28.126L26.2596 28.4377L33.1477 39.1929C34.1602 40.7635 35.2 42.3164 36.2667 43.8508C37.0268 44.9419 38.1472 45.2758 39.4066 45.0042C40.1948 44.8359 40.9514 44.5157 41.7235 44.2668C42.1257 44.1363 42.2628 43.8963 42.261 43.4456L42.2477 23.6292C42.2477 22.4709 42.2477 22.4709 43.3935 22.2398C44.5522 22.0065 44.8425 21.5438 44.578 20.3054L37.6534 20.7262C36.8999 20.7801 36.3295 21.4098 36.215 22.1423C36.1589 22.4954 36.232 22.69 36.6546 22.7145L38.7511 22.9461V36.3852C37.4232 34.3595 36.093 32.3352 34.7606 30.3125V30.3107ZM39.8777 6.8761C41.0145 7.66109 42.1479 8.45078 43.2781 9.24516C44.021 9.76442 44.757 10.2933 45.486 10.8318C45.6926 10.985 45.8512 11.2023 46.1241 11.486L45.5537 11.5902L30.6758 12.4826L16.8555 13.3492C15.1001 13.4761 13.5678 13.1871 12.251 11.9366C11.5567 11.2776 10.7516 10.733 9.99459 10.1362C9.67619 9.88374 9.33909 9.64906 9.04652 9.36896C8.88843 9.21755 8.67246 8.94146 8.72144 8.80341C8.78735 8.60881 9.05899 8.39328 9.27096 8.35498C9.90776 8.24009 10.5566 8.19289 11.2018 8.14613L32.5546 6.59466L37.0478 6.28116C38.0217 6.22772 38.968 6.38358 39.8777 6.8761Z"
                        fill="white"
                      />
                      <path
                        d="M34.7847 30.3436L38.7511 36.3851V22.9456L36.655 22.7141C36.232 22.69 36.1589 22.4954 36.2146 22.1423C36.3295 21.4097 36.9004 20.7801 37.653 20.7262L44.578 20.3054C44.8425 21.5433 44.5522 22.0065 43.3935 22.2394C42.2472 22.4691 42.2472 22.4691 42.2472 23.6292L42.261 43.4456C42.2628 43.8962 42.1257 44.1363 41.7236 44.2667L39.4066 45.0042C38.1473 45.274 37.0268 44.9418 36.2671 43.8508C35.2009 42.3161 34.1611 40.7632 33.1482 39.1928L26.2592 28.4372C26.2106 28.3606 26.155 28.2894 26.0365 28.1259V42.6266L29.0339 43.3102C28.9088 44.2409 28.4078 44.8109 27.4771 44.9645C26.7673 45.0808 26.0388 45.0981 25.3182 45.1418L19.8373 45.4566C19.5955 44.6827 19.9032 44.077 20.622 43.8651L22.2429 43.4077V24.1288L19.8632 23.9253C19.5572 22.8485 20.2252 21.8101 21.3296 21.709C22.824 21.5696 24.3252 21.4845 25.8228 21.3803C26.6368 21.3247 27.4544 21.3037 28.2653 21.2151C28.634 21.1751 28.8309 21.2757 29.0304 21.5803L34.7847 30.3436Z"
                        fill="black"
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
