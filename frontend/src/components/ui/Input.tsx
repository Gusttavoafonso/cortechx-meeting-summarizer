import { forwardRef, InputHTMLAttributes, ReactNode } from 'react'
import { Search } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, leftIcon, rightIcon, type = 'text', ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full">
        {leftIcon && (
          <div className="absolute left-3.5 text-muted pointer-events-none flex items-center justify-center">
            {leftIcon}
          </div>
        )}
        <input
          ref={ref}
          type={type}
          className={cn(
            'w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-ink placeholder:text-muted/70 transition-colors focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-50',
            leftIcon && 'pl-10',
            rightIcon && 'pr-10',
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3.5 text-muted pointer-events-none flex items-center justify-center">
            {rightIcon}
          </div>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

export interface SearchInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'type'
> {
  onClear?: () => void
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  ({ className, ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full max-w-xl mx-auto">
        <div className="absolute left-4 text-muted/80 pointer-events-none">
          <Search className="w-4 h-4 text-ink/60" />
        </div>
        <input
          ref={ref}
          type="text"
          className={cn(
            'w-full h-11 pl-11 pr-4 rounded-xl border border-slate-200 bg-white text-sm text-ink placeholder:text-muted/70 shadow-sm transition-all focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20',
            className
          )}
          placeholder="Buscar reunião..."
          {...props}
        />
      </div>
    )
  }
)

SearchInput.displayName = 'SearchInput'
