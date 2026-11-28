import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Mic,
  FileText,
  Users,
  BarChart3,
  ArrowRight,
  Lock,
  Cpu,
  Zap,
  ChevronDown,
  Share2,
} from 'lucide-react'
import { LandingNavbar } from '../../components/landing/LandingNavbar'
import { HalftoneWaveCanvas } from '../../components/landing/HalftoneWaveCanvas'
import { Button } from '../../components/ui/Button'
import { ZumoLogo } from '../../components/ZumoLogo'
import { cn } from '../../lib/utils'

export const LandingPage: React.FC = () => {
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0)
  const mainRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const main = mainRef.current
    if (!main || !('IntersectionObserver' in window)) return
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (reducedMotion.matches) return

    const targets = main.querySelectorAll<HTMLElement>(
      'section:not(:first-child) > div > .text-center, section:not(:first-child) .grid > div, section:last-child > div'
    )
    let frame = 0
    const update = () => {
      frame = 0
      const viewport = window.innerHeight
      targets.forEach((element) => {
        const top = element.getBoundingClientRect().top
        const progress = reducedMotion.matches
          ? 1
          : Math.max(0, Math.min(1, (viewport * 0.92 - top) / (viewport * 0.38)))
        element.style.opacity = String(progress)
        element.style.transform = `translateY(${(1 - progress) * 32}px)`
      })
    }
    const scheduleUpdate = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', scheduleUpdate, { passive: true })
    window.addEventListener('resize', scheduleUpdate)
    reducedMotion.addEventListener('change', scheduleUpdate)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', scheduleUpdate)
      window.removeEventListener('resize', scheduleUpdate)
      reducedMotion.removeEventListener('change', scheduleUpdate)
      targets.forEach((element) => {
        element.style.removeProperty('opacity')
        element.style.removeProperty('transform')
      })
    }
  }, [])

  const faqs = [
    {
      q: 'Como o Zumo trata o áudio?',
      a: 'O Silero VAD remove silêncios, reduz custos e torna a transcrição 3 vezes mais rápida.',
    },
    {
      q: 'Como meus dados são protegidos?',
      a: 'No modo local, o áudio fica no seu computador. Na nuvem, há criptografia de ponta a ponta e não há retenção de dados.',
    },
    {
      q: 'Quais arquivos posso enviar?',
      a: 'MP3, WAV, M4A, MP4 ou WebM de até 250 MB.',
    },
    {
      q: 'O Zumo funciona em português do Brasil?',
      a: 'Sim. Os modelos reconhecem pronúncias e termos técnicos em português do Brasil, com mais de 99% de precisão.',
    },
    {
      q: 'Quais integrações estão disponíveis?',
      a: 'Sincronize notas, tarefas e transcrições com Obsidian, Discord ou Notion, ou exporte em Markdown.',
    },
  ]

  return (
    <div className="landing-page min-h-screen bg-page text-ink selection:bg-surface selection:text-brand flex flex-col">
      {/* Navigation */}
      <LandingNavbar />

      <main ref={mainRef} className="flex-1">
        {/* ================= HERO SECTION (FULL SCREEN) ================= */}
        <section className="relative min-h-[calc(100vh-4.5rem)] flex flex-col justify-between overflow-hidden">
          {/* Subtle Ambient Background Light */}
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-brand/5 blur-[120px] rounded-full pointer-events-none" />

          {/* Hero Typography Container - Centered in viewport */}
          <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto px-4 sm:px-6 text-center relative z-10 pt-16 pb-6">
            {/* Main Headline */}
            <h1 className="text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-ink font-sans leading-[1.08] mb-6">
              Transcreva suas reuniões <br />
              <span className="text-brand">e gere resumos.</span>
            </h1>
          </div>

          {/* ================= FULL-WIDTH BLUE HALFTONE WAVE ================= */}
          <div className="w-full relative mt-auto mb-12 sm:mb-20 overflow-hidden select-none">
            <HalftoneWaveCanvas height={320} className="w-full" />
          </div>
        </section>

        {/* ================= 4 PILLARS FEATURE STRIP (SEEN ON SCROLL) ================= */}
        <section className="py-16 md:py-20 bg-page border-b border-subtle-border/80 relative z-20">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Feature 1 */}
              <div className="p-5 rounded-2xl bg-white border border-subtle-border/80 hover:border-brand/30 transition-all shadow-card group">
                <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-3 group-hover:scale-105 transition-transform">
                  <Mic className="w-5 h-5 stroke-[2.2]" />
                </div>
                <h3 className="text-base font-bold text-ink mb-1 font-sans">
                  Transcrição de áudio
                </h3>
              </div>

              {/* Feature 2 */}
              <div className="p-5 rounded-2xl bg-white border border-subtle-border/80 hover:border-brand/30 transition-all shadow-card group">
                <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-3 group-hover:scale-105 transition-transform">
                  <FileText className="w-5 h-5 stroke-[2.2]" />
                </div>
                <h3 className="text-base font-bold text-ink mb-1 font-sans">
                  Resumos automáticos
                </h3>
                <p className="text-xs text-muted leading-relaxed">
                  Pontos principais, decisões e acordos.
                </p>
              </div>

              {/* Feature 3 */}
              <div className="p-5 rounded-2xl bg-white border border-subtle-border/80 hover:border-brand/30 transition-all shadow-card group">
                <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-3 group-hover:scale-105 transition-transform">
                  <Users className="w-5 h-5 stroke-[2.2]" />
                </div>
                <h3 className="text-base font-bold text-ink mb-1 font-sans">
                  Histórico de reuniões
                </h3>
                <p className="text-xs text-muted leading-relaxed">
                  Atas e gravações arquivadas.
                </p>
              </div>

              {/* Feature 4 */}
              <div className="p-5 rounded-2xl bg-white border border-subtle-border/80 hover:border-brand/30 transition-all shadow-card group">
                <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center text-brand mb-3 group-hover:scale-105 transition-transform">
                  <BarChart3 className="w-5 h-5 stroke-[2.2]" />
                </div>
                <h3 className="text-base font-bold text-ink mb-1 font-sans">
                  Tarefas e prazos
                </h3>
              </div>
            </div>
          </div>
        </section>

        {/* ================= COMO FUNCIONA (3 PASSOS) ================= */}
        <section
          id="como-funciona"
          className="py-10 bg-surface/30 border-y border-subtle-border"
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-16">
              <h2 className="text-3xl sm:text-4xl font-bold font-sans text-ink mb-4">
                Como funciona
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
              {/* Step 1 */}
              <div className="relative p-6 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface text-brand font-sans font-bold text-xl flex items-center justify-center mb-5">
                  01
                </div>
                <h3 className="text-lg font-bold text-ink mb-2 font-sans">
                  Envie ou grave o áudio
                </h3>
                <p className="text-sm text-muted leading-relaxed mb-4 flex-1">
                  MP3, WAV, M4A ou MP4 de até 250 MB.
                </p>
              </div>

              {/* Step 2 */}
              <div className="relative p-6 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface text-brand font-sans font-bold text-xl flex items-center justify-center mb-5">
                  02
                </div>
                <h3 className="text-lg font-bold text-ink mb-2 font-sans">Transcrição</h3>
                <p className="text-sm text-muted leading-relaxed mb-4 flex-1">
                  O Silero VAD separa a fala do ruído. O Whisper transcreve o áudio.
                </p>
              </div>

              {/* Step 3 */}
              <div className="relative p-6 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface text-brand font-sans font-bold text-xl flex items-center justify-center mb-5">
                  03
                </div>
                <h3 className="text-lg font-bold text-ink mb-2 font-sans">
                  Resumo e tarefas
                </h3>
                <p className="text-sm text-muted leading-relaxed mb-4 flex-1">
                  O Zumo registra as decisões e atribui tarefas aos participantes.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ================= BENTO GRID DE RECURSOS ================= */}
        <section id="recursos" className="py-20">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-16">
              <h2 className="text-3xl sm:text-4xl font-bold font-sans text-ink mb-4">
                Recursos
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Feature Large: Local vs Cloud Engine */}
              <div className="md:col-span-2 p-8 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-4">
                    <Cpu className="w-5 h-5" />
                  </div>
                  <h3 className="text-2xl font-bold font-sans text-ink mb-2">
                    Processamento local ou na nuvem
                  </h3>
                  <p className="text-sm text-muted max-w-xl leading-relaxed mb-6">
                    Escolha entre <strong>Faster-Whisper</strong> local e{' '}
                    <strong>Groq Cloud</strong>.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-subtle-border">
                  <div className="p-3 rounded-xl bg-page border border-subtle-border">
                    <span className="text-xs font-bold text-ink block mb-0.5">
                      Modo Local (Offline)
                    </span>
                    <span className="text-xs text-muted">
                      Áudio no seu computador, sem internet nem custo de API.
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-page border border-subtle-border">
                    <span className="text-xs font-bold text-brand block mb-0.5">
                      Modo Nuvem (Groq Whisper Large)
                    </span>
                    <span className="text-xs text-muted">
                      Transcrição em segundos, mesmo para arquivos de uma hora ou mais.
                    </span>
                  </div>
                </div>
              </div>

              {/* Feature 2: Voice Activity Detection */}
              <div className="p-8 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-4">
                    <Zap className="w-5 h-5" />
                  </div>
                  <h3 className="text-xl font-bold font-sans text-ink mb-2">
                    Detecção de fala (Silero VAD)
                  </h3>
                  <p className="text-sm text-muted leading-relaxed mb-4">
                    Remove silêncios e ruídos de fundo antes da transcrição.
                  </p>
                </div>
              </div>

              {/* Feature 3: Security & Privacy */}
              <div className="p-8 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-4">
                    <Lock className="w-5 h-5" />
                  </div>
                  <h3 className="text-xl font-bold font-sans text-ink mb-2">
                    Privacidade
                  </h3>
                  <p className="text-sm text-muted leading-relaxed mb-4">
                    Seus dados de reunião não são usados para treinar modelos públicos.
                  </p>
                </div>
              </div>

              {/* Feature 4: Supported Platforms (Obsidian, Discord, Notion, Markdown) */}
              <div className="md:col-span-2 p-8 rounded-2xl bg-white border border-subtle-border shadow-card flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand mb-4">
                    <Share2 className="w-5 h-5" />
                  </div>
                  <h3 className="text-2xl font-bold font-sans text-ink mb-2">
                    Integrações
                  </h3>
                  <p className="text-sm text-muted max-w-xl leading-relaxed mb-6">
                    Sincronize notas, atas e tarefas.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs font-semibold">
                  <span className="bg-surface px-4 py-2 rounded-xl text-ink border border-brand/15">
                    Obsidian
                  </span>
                  <span className="bg-surface px-4 py-2 rounded-xl text-ink border border-brand/15">
                    Discord
                  </span>
                  <span className="bg-surface px-4 py-2 rounded-xl text-ink border border-brand/15">
                    Notion
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ================= FAQ SECTION ================= */}
        <section id="faq" className="py-20 bg-surface/30 border-t border-subtle-border">
          <div className="max-w-3xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold font-sans text-ink mb-4">
                Perguntas frequentes
              </h2>
            </div>

            <div className="space-y-3">
              {faqs.map((faq, idx) => {
                const isOpen = openFaqIndex === idx
                return (
                  <div
                    key={idx}
                    className="bg-white rounded-xl border border-subtle-border overflow-hidden transition-all shadow-xs"
                  >
                    <button
                      type="button"
                      onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                      className="w-full px-5 py-4 text-left flex items-center justify-between gap-4 font-semibold text-sm text-ink hover:text-brand transition-colors"
                    >
                      <span>{faq.q}</span>
                      <ChevronDown
                        className={cn(
                          'w-4 h-4 text-muted shrink-0 transition-transform duration-200',
                          isOpen && 'rotate-180 text-brand'
                        )}
                      />
                    </button>
                    {isOpen && (
                      <div className="px-5 pb-5 pt-1 text-xs sm:text-sm text-muted leading-relaxed border-t border-subtle-border/50 bg-page/30">
                        {faq.a}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        {/* ================= FINAL CTA CALLOUT ================= */}
        <section className="py-20">
          <div className="max-w-5xl mx-auto px-4 sm:px-6">
            <div className="p-10 sm:p-14 rounded-3xl bg-primary-btn text-white text-center relative overflow-hidden shadow-xl">
              {/* Background Glow */}
              <div className="absolute top-0 right-0 w-80 h-80 bg-brand-light/20 blur-3xl rounded-full pointer-events-none" />

              <h2 className="text-3xl sm:text-5xl font-bold font-sans mb-4 relative z-10">
                Grave ou envie um áudio
              </h2>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 relative z-10">
                <Link to="/login?mode=register" className="w-full sm:w-auto">
                  <Button
                    size="lg"
                    className="w-full sm:w-auto bg-white text-primary-btn hover:bg-surface active:bg-surface-hover font-bold shadow-md"
                    rightIcon={<ArrowRight className="w-4 h-4" />}
                  >
                    Criar Primeira Reunião
                  </Button>
                </Link>
                <Link to="/login" className="w-full sm:w-auto">
                  <button
                    type="button"
                    className="w-full sm:w-auto h-12 px-6 rounded-xl text-sm font-semibold text-white/90 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    Acessar Plataforma
                  </button>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ================= FOOTER ================= */}
      <footer className="bg-white border-t border-subtle-border py-12 text-xs text-muted">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <ZumoLogo size="md" />
          </div>

          <div className="flex items-center gap-6">
            <a href="#como-funciona" className="hover:text-ink transition-colors">
              Como funciona
            </a>
            <a href="#recursos" className="hover:text-ink transition-colors">
              Recursos
            </a>
            <a href="#faq" className="hover:text-ink transition-colors">
              FAQ
            </a>
            <Link to="/login" className="hover:text-ink transition-colors">
              Acessar App
            </Link>
          </div>

          <p>
            © {new Date().getFullYear()} CortechX / Zumo. Todos os direitos reservados.
          </p>
        </div>
      </footer>
    </div>
  )
}
