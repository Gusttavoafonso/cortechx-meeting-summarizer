import React from 'react'
import { cn } from '../lib/utils'
import zumoLogo from '../assets/zumo-logo-extended.png'

interface ZumoLogoProps {
  alt?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
  showIconOnly?: boolean
}

export const ZumoLogo: React.FC<ZumoLogoProps> = ({
  alt = 'Zumo',
  className,
  size = 'md',
  showIconOnly = false,
}) => {
  const sizeClasses = {
    sm: 'w-14',
    md: 'w-16',
    lg: 'w-20',
  }

  if (showIconOnly) {
    return (
      <div
        className={cn(
          'w-8 h-8 rounded-xl bg-brand text-white flex items-center justify-center font-bold text-sm tracking-tight select-none shadow-xs',
          className
        )}
      >
        <span>Z</span>
      </div>
    )
  }

  return (
    <img
      src={zumoLogo}
      alt={alt}
      width={1395}
      height={424}
      className={cn('block h-auto shrink-0 select-none', sizeClasses[size], className)}
    />
  )
}
