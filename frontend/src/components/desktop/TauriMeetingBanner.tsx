import React from 'react'
import { Video, Mic, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { DetectedMeeting, getPlatformDisplayName } from '../../hooks/useTauriMeetingDetector'

interface TauriMeetingBannerProps {
  meeting: DetectedMeeting
  onRecordNow: () => void
  onDismiss: () => void
}

export const TauriMeetingBanner: React.FC<TauriMeetingBannerProps> = ({
  meeting,
  onRecordNow,
  onDismiss,
}) => {
  const platformName = getPlatformDisplayName(meeting.platform)

  return (
    <div
      role="alert"
      className="fixed top-4 right-4 z-50 max-w-md w-[calc(100%-2rem)] sm:w-auto sm:min-w-[360px] bg-white border border-[#DCE2FB] rounded-2xl p-4 shadow-xl backdrop-blur-md animate-in fade-in slide-in-from-top-4 duration-300"
    >
      <div className="flex items-start gap-3">
        {/* Platform / Mic Icon */}
        <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center text-brand shrink-0">
          <Video className="w-5 h-5" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pr-1">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600" />
            </span>
            <span className="text-xs font-bold text-ink uppercase tracking-wider">
              {platformName}
            </span>
          </div>

          <p className="text-xs font-semibold text-ink truncate mb-1" title={meeting.title}>
            {meeting.title || 'Chamada em andamento'}
          </p>

          <p className="text-[11px] text-muted leading-tight mb-3">
            Deseja gravar e transcrever esta reunião agora?
          </p>

          {/* Action Button */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={onRecordNow}
              leftIcon={<Mic className="w-3.5 h-3.5" />}
              className="h-8 px-3.5 text-xs font-bold shadow-xs"
            >
              Gravar Agora
            </Button>
            <button
              type="button"
              onClick={onDismiss}
              className="px-2.5 py-1.5 text-xs font-medium text-muted hover:text-ink rounded-lg transition-colors cursor-pointer"
            >
              Agora não
            </button>
          </div>
        </div>

        {/* Close button */}
        <button
          type="button"
          onClick={onDismiss}
          title="Fechar"
          className="text-muted hover:text-ink p-1 rounded-lg hover:bg-slate-100 transition-colors shrink-0 cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
