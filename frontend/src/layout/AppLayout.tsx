import React from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useTauriMeetingDetector } from '../hooks/useTauriMeetingDetector'
import { TauriMeetingBanner } from '../components/desktop/TauriMeetingBanner'

export const AppLayout: React.FC = () => {
  const { detectedMeeting, dismiss, recordNow } = useTauriMeetingDetector()

  return (
    <div className="flex min-h-screen bg-page text-ink">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto relative">
        {detectedMeeting && (
          <TauriMeetingBanner
            meeting={detectedMeeting}
            onRecordNow={recordNow}
            onDismiss={dismiss}
          />
        )}
        <Outlet />
      </main>
    </div>
  )
}
