import React from 'react'
import { cn } from '../lib/utils'
import zumoLogo from '../assets/zumo-logo-extended.png'

interface ZumoLogoProps {
  className?: string
  showIconOnly?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export const ZumoLogo: React.FC<ZumoLogoProps> = ({
  className,
  showIconOnly = false,
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'w-14',
    md: 'w-16',
    lg: 'w-20',
  }

  if (showIconOnly) {
    return (
      <svg
        className={cn('w-7 h-7 shrink-0', className)}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="40" height="40" rx="10" fill="#EAEDFF" />
        <rect x="9" y="14" width="4" height="12" rx="2" fill="#006EB9" />
        <rect x="18" y="10" width="4" height="20" rx="2" fill="#006EB9" />
        <rect x="27" y="14" width="4" height="12" rx="2" fill="#006EB9" />
      </svg>
    )
  }

  return (
    <img
      src={zumoLogo}
      alt="Zumo"
      className={cn('block h-auto shrink-0 select-none', sizeClasses[size], className)}
    />
  )
}
