import React from 'react'
import { cn, getStatusBadgeConfig } from '../../lib/utils'
import { MeetingStatus } from '../../types/meeting'

export interface TimeBadgeProps {
  time: string
  period?: string
  className?: string
}

export const TimeBadge: React.FC<TimeBadgeProps> = ({ time, period, className }) => {
  return (
    <div
      className={cn(
        'w-14 h-14 rounded-xl bg-[#E8F1FC] flex flex-col items-center justify-center text-primary-btn shrink-0 select-none shadow-sm',
        className
      )}
    >
      <span className="text-xs font-bold leading-tight tracking-tight">{time}</span>
      {period && (
        <span className="text-[10px] font-semibold uppercase leading-tight tracking-wider opacity-90">
          {period}
        </span>
      )}
    </div>
  )
}

export interface StatusBadgeProps {
  status: MeetingStatus
  className?: string
  showDot?: boolean
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  className,
  showDot = true,
}) => {
  const config = getStatusBadgeConfig(status)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border',
        config.bg,
        config.text,
        className
      )}
    >
      {showDot && (
        <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', config.dot)} />
      )}
      <span>{config.label}</span>
    </span>
  )
}
