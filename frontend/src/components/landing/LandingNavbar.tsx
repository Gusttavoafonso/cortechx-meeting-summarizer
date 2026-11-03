import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Menu, X } from 'lucide-react'
import { ZumoLogo } from '../ZumoLogo'
import { Button } from '../ui/Button'
import { cn } from '../../lib/utils'

export const LandingNavbar: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 16)
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const navLinks = [
    { label: 'Como funciona', href: '#como-funciona' },
    { label: 'Recursos', href: '#recursos' },
    { label: 'FAQ', href: '#faq' },
  ]

  return (
    <header
      className={cn(
        'sticky top-0 z-50 w-full transition-all duration-200',
        isScrolled
          ? 'bg-page/85 backdrop-blur-md border-b border-subtle-border/80 shadow-xs'
          : 'bg-transparent border-b border-transparent'
      )}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-4 flex items-center justify-between">
        {/* Brand Logo */}
        <Link
          to="/"
          onClick={(event) => {
            event.preventDefault()
            window.scrollTo({
              top: 0,
              behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                ? 'instant'
                : 'smooth',
            })
            setMobileMenuOpen(false)
          }}
          className="flex items-center gap-2 group hover:opacity-95 transition-opacity"
        >
          <ZumoLogo size="lg" />
        </Link>

        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-muted hover:text-ink transition-colors"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Desktop Action Buttons */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-medium text-ink-light hover:text-ink px-3 py-2 rounded-lg hover:bg-surface/50 transition-colors"
          >
            Entrar
          </Link>
          <Link to="/login?mode=register">
            <Button
              size="sm"
              className="h-9 px-4 text-xs font-semibold rounded-lg shadow-sm group"
              rightIcon={
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              }
            >
              Começar agora
            </Button>
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 text-ink-light hover:text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
          aria-label="Abrir menu"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-page border-b border-subtle-border px-4 pt-3 pb-6 space-y-3 animate-in slide-in-from-top duration-200">
          <nav className="flex flex-col space-y-2">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="text-base font-medium text-ink-light hover:text-brand px-3 py-2 rounded-lg hover:bg-surface"
              >
                {link.label}
              </a>
            ))}
          </nav>
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
              className="w-full"
            >
              <Button
                className="w-full justify-center"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Começar agora
              </Button>
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}
