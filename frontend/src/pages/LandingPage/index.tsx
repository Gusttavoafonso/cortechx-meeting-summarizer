import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Mic, FileText, ArrowRight, Cpu, ChevronDown, Share2 } from 'lucide-react'
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
              Nenhuma decisão perdida no <br />
              <span className="text-brand">meio da call.</span>
            </h1>
          </div>

          {/* ================= FULL-WIDTH BLUE HALFTONE WAVE ================= */}
          <div className="w-full relative mt-auto mb-12 sm:mb-20 overflow-hidden select-none">
            <HalftoneWaveCanvas height={320} className="w-full" />
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
            <div className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold font-sans text-ink">
                Recursos
              </h2>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
              {[
                {
                  icon: Cpu,
                  title: 'Transcrição durante a reunião',
                  description:
                    'Acompanhe o texto enquanto grava. Processe a gravação no seu computador ou na nuvem.',
                },
                {
                  icon: FileText,
                  title: 'Resumos com LLM',
                  description:
                    'Gere resumos, decisões e tarefas a partir da transcrição.',
                },
                {
                  icon: Share2,
                  title: 'Integrações externas',
                  description: 'Envie resumos e tarefas ao Obsidian, Discord e Notion.',
                },
                {
                  icon: Mic,
                  title: 'Sem bots na chamada',
                  description:
                    'Com sua permissão, grave pelo microfone e, quando disponível, pelo áudio do sistema.',
                },
              ].map(({ icon: Icon, title, description }) => (
                <div
                  key={title}
                  className="min-w-0 rounded-2xl border border-subtle-border bg-white p-5 shadow-card sm:p-7 lg:p-8"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-surface text-brand">
                    <Icon aria-hidden="true" className="h-5 w-5" />
                  </div>
                  <h3 className="mb-2 font-sans text-lg font-bold text-ink sm:text-xl">
                    {title}
                  </h3>
                  <p className="max-w-prose text-sm leading-relaxed text-muted">
                    {description}
                  </p>
                </div>
              ))}
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
                Pronto para transformar suas reuniões em decisões e tarefas?
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
