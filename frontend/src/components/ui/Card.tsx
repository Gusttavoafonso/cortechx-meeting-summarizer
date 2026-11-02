import React, { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export const Card: React.FC<HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        'bg-white rounded-2xl border border-slate-100 shadow-card transition-shadow',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
