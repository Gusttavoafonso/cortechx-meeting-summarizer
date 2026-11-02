import React from 'react'
import { cn } from '../lib/utils'

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
    sm: 'text-xl',
    md: 'text-2xl',
    lg: 'text-3xl',
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
    <div
      className={cn(
        'flex items-baseline select-none tracking-tight font-fredoka font-bold leading-none',
        sizeClasses[size],
        className
      )}
    >
      <span className="text-ink">zumo</span>
      <span className="inline-block w-2 h-2 rounded-full bg-brand ml-0.5" />
    </div>
  )
}
