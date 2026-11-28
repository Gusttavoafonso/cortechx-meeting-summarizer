import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Menu, X } from 'lucide-react'
import { ZumoLogo } from '../ZumoLogo'
import { SlidingNav } from '../ui/SlidingNav'
import { cn } from '../../lib/utils'

const navLinks = [
  { label: 'Como funciona', href: '#como-funciona' },
  { label: 'Recursos', href: '#recursos' },
  { label: 'FAQ', href: '#faq' },
]

const registrationLinkClass =
  'inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary-btn px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-primary-btn-hover active:bg-primary-btn-active focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-safe:transition-colors'

export const LandingNavbar: React.FC = () => {
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = useState('')
  const [isScrolled, setIsScrolled] = useState(false)
  const [compactLogoLoaded, setCompactLogoLoaded] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const sections = [...navLinks].reverse().map(({ href }) => ({
      href,
      element: document.getElementById(href.slice(1)),
    }))
    let frame = 0

    const update = () => {
      frame = 0
      const { scrollY, innerHeight } = window
      setIsScrolled((floating) => scrollY > (floating ? 8 : 24))

      // A fixed reading line keeps the active section stable as sections enter the viewport.
      const readingLine = Math.min(240, Math.max(96, innerHeight * 0.3), innerHeight - 1)
      const atBottom =
        Math.ceil(scrollY + innerHeight) >= document.documentElement.scrollHeight
      const visible = sections.find(({ element }) => {
        if (!element) return false
        const { top, bottom } = element.getBoundingClientRect()
        return bottom > readingLine && (atBottom ? top < innerHeight : top <= readingLine)
      })

      setActiveSection(visible?.href ?? '')
    }

    const scheduleUpdate = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }

    scheduleUpdate()
    window.addEventListener('scroll', scheduleUpdate, { passive: true })
    window.addEventListener('resize', scheduleUpdate)
    window.addEventListener('hashchange', scheduleUpdate)
    window.addEventListener('load', scheduleUpdate)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', scheduleUpdate)
      window.removeEventListener('resize', scheduleUpdate)
      window.removeEventListener('hashchange', scheduleUpdate)
      window.removeEventListener('load', scheduleUpdate)
    }
  }, [])

  return (
    <header
      className="landing-header pointer-events-none sticky top-0 z-50 h-[76px] w-full"
      data-floating={isScrolled}
    >
      <div className="landing-header-bar pointer-events-auto relative">
        <div className="landing-header-row grid grid-cols-[minmax(0,1fr)_auto] items-center px-4 lg:px-8 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
          {/* Brand Logo */}
          <Link
            to="/"
            onClick={(event) => {
              if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
              event.preventDefault()
              if (window.location.hash) {
                navigate('/', { replace: true })
              }
              window.scrollTo({
                top: 0,
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                  ? 'instant'
                  : 'smooth',
              })
              setMobileMenuOpen(false)
            }}
            aria-label="Zumo, início"
            data-compact={isScrolled && compactLogoLoaded}
            className="landing-header-brand relative h-8 w-20 justify-self-start rounded-md hover:opacity-95 motion-safe:transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            <ZumoLogo
              alt=""
              size="lg"
              className="landing-header-wordmark absolute left-0 top-1/2 -translate-y-1/2"
            />
            <img
              src={import.meta.env.BASE_URL + 'zumo-favicon.png'}
              alt=""
              width={601}
              height={590}
              onLoad={() => setCompactLogoLoaded(true)}
              className="landing-header-symbol absolute left-0 top-1/2 h-7 w-auto -translate-y-1/2"
            />
          </Link>

          {/* Desktop Navigation Links */}
          <SlidingNav
            label="Seções do site"
            locationKey={activeSection}
            className="hidden items-center gap-2 whitespace-nowrap md:flex"
            indicatorClassName="bg-surface-hover"
          >
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                aria-current={activeSection === link.href ? 'location' : undefined}
                className="rounded-xl px-3 py-2 text-sm font-medium text-muted hover:text-ink active:bg-surface-hover aria-[current=location]:text-brand-dark motion-safe:transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
              >
                {link.label}
              </a>
            ))}
          </SlidingNav>

          {/* Desktop Action Buttons */}
          <div className="hidden items-center gap-3 justify-self-end whitespace-nowrap md:flex">
            <Link
              to="/login"
              className="rounded-lg px-3 py-2 text-sm font-medium text-ink-light hover:bg-surface/50 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand motion-safe:transition-colors"
            >
              Entrar
            </Link>
            <Link to="/login?mode=register" className={cn(registrationLinkClass, 'h-9')}>
              Começar agora
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-ink-light hover:text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
            aria-label={mobileMenuOpen ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Drawer */}
        {mobileMenuOpen && (
          <div className="absolute inset-x-0 top-full mt-2 max-h-[calc(100dvh-88px)] space-y-3 overflow-y-auto rounded-2xl border border-subtle-border bg-page px-4 pb-6 pt-3 shadow-card md:hidden">
            <SlidingNav
              label="Seções do site"
              locationKey={activeSection}
              className="flex flex-col gap-2"
              indicatorClassName="bg-surface-hover"
            >
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  aria-current={activeSection === link.href ? 'location' : undefined}
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-xl px-3 py-2 text-base font-medium text-ink-light hover:bg-surface hover:text-brand active:bg-surface-hover aria-[current=location]:text-brand-dark motion-safe:transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                >
                  {link.label}
                </a>
              ))}
            </SlidingNav>
            <div className="pt-3 border-t border-subtle-border flex flex-col gap-2">
              <Link
                to="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 text-sm font-semibold text-ink hover:bg-surface rounded-lg"
              >
                Entrar
              </Link>
              <Link
                to="/login?mode=register"
                onClick={() => setMobileMenuOpen(false)}
                className={cn(registrationLinkClass, 'w-full py-2.5')}
              >
                Começar agora
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
