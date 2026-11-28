import React from 'react'
import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'
import { Sidebar } from './Sidebar'
import { useTauriMeetingDetector } from '../hooks/useTauriMeetingDetector'
import { TauriMeetingBanner } from '../components/desktop/TauriMeetingBanner'

export const AppLayout: React.FC = () => {
  const { detectedMeeting, dismiss, recordNow } = useTauriMeetingDetector()

  return (
    <div className="flex min-h-screen bg-page text-ink">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="relative flex min-w-0 flex-1 flex-col overflow-y-auto">
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
    </div>
  )
}
