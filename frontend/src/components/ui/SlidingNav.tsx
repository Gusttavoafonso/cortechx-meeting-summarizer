import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface SlidingNavProps {
  label: string
  /** Location key that changes whenever the current link may change. */
  locationKey: string
  className?: string
  indicatorClassName?: string
  children: ReactNode
}

/** Position a shared background under the direct link marked with aria-current. */
export function SlidingNav({
  label,
  locationKey,
  className,
  indicatorClassName,
  children,
}: SlidingNavProps) {
  const navRef = useRef<HTMLElement>(null)
  const indicatorRef = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    const nav = navRef.current
    const indicator = indicatorRef.current
    if (!nav || !indicator) return

    const measure = () => {
      const current = nav.querySelector<HTMLAnchorElement>(
        ':scope > a[aria-current="page"], :scope > a[aria-current="location"]'
      )
      if (!current || current.offsetWidth === 0) {
        indicator.hidden = true
        return
      }

      indicator.style.width = `${current.offsetWidth}px`
      indicator.style.height = `${current.offsetHeight}px`
      indicator.style.transform = `translate(${current.offsetLeft}px, ${current.offsetTop}px)`
      indicator.hidden = false
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(nav)
    nav.querySelectorAll(':scope > a').forEach((link) => observer.observe(link))
    return () => observer.disconnect()
  }, [locationKey, children])

  return (
    <nav ref={navRef} aria-label={label} className={cn('sliding-nav', className)}>
      <span
        ref={indicatorRef}
        aria-hidden="true"
        hidden
        className={cn('sliding-nav-indicator rounded-xl', indicatorClassName)}
      />
      {children}
    </nav>
  )
}
