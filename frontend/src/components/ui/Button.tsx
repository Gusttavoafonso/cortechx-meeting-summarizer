import React, { ButtonHTMLAttributes, forwardRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'ghost' | 'secondary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none'

    const sizeStyles = {
      sm: 'h-8 px-3 text-xs rounded-lg gap-1.5',
      md: 'h-10 px-4 text-sm rounded-xl gap-2',
      lg: 'h-12 px-6 text-base rounded-xl gap-2.5',
    }

    const variantStyles = {
      primary:
        'bg-primary-btn text-white hover:bg-primary-btn-hover active:bg-primary-btn-active shadow-sm',
      outline:
        'border border-slate-200 bg-white text-ink hover:bg-slate-50 active:bg-slate-100',
      ghost:
        'text-ink hover:bg-surface active:bg-surface-hover text-muted hover:text-ink',
      secondary: 'bg-surface text-brand font-semibold hover:bg-surface-hover',
      danger: 'bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800',
    }

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, sizeStyles[size], variantStyles[variant], className)}
        {...props}
      >
        {isLoading ? <Loader2 className="h-4 w-4 animate-spin text-current" /> : leftIcon}
        <span>{children}</span>
        {!isLoading && rightIcon}
      </button>
    )
  }
)

Button.displayName = 'Button'
