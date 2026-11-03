import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { AppLayout } from './layout/AppLayout'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MeetingsList } from './pages/MeetingsList'
import { NewMeeting } from './pages/NewMeeting'
import { MeetingDetails } from './pages/MeetingDetails'
import { SettingsPage } from './pages/SettingsPage'
import { DashboardPage } from './pages/DashboardPage'
import { TasksPage } from './pages/TasksPage'
import { TranscriptsPage } from './pages/TranscriptsPage'
import { NotFoundPage } from './pages/NotFoundPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Landing Page */}
            <Route path="/" element={<LandingPage />} />

            {/* Authentication Page */}
            <Route path="/login" element={<LoginPage />} />

            {/* Authenticated / App Workspace */}
            <Route element={<AppLayout />}>
              <Route path="meetings" element={<MeetingsList />} />
              <Route path="meetings/new" element={<NewMeeting />} />
              <Route path="meetings/:id" element={<MeetingDetails />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="tasks" element={<TasksPage />} />
              <Route path="transcripts" element={<TranscriptsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
