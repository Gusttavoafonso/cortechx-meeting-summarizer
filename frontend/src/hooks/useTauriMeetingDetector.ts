import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRecordingContext } from '../context/RecordingContext'

export interface DetectedMeeting {
  platform: 'GoogleMeet' | 'Discord' | 'Zoom' | 'MicrosoftTeams' | 'Generic' | string
  title: string
  identifier: string
}

export interface TauriEvent<T> {
  event: string
  id: number
  payload: T
}

export interface TauriApi {
  event?: {
    listen: <T>(
      event: string,
      handler: (event: TauriEvent<T>) => void
    ) => Promise<() => void>
    emit?: (event: string, payload?: unknown) => Promise<void>
  }
}

export function getPlatformDisplayName(platform: string): string {
  switch (platform) {
    case 'GoogleMeet':
      return 'Google Meet'
    case 'Discord':
      return 'Discord'
    case 'Zoom':
      return 'Zoom'
    case 'MicrosoftTeams':
      return 'Microsoft Teams'
    case 'Generic':
    default:
      return 'Chamada Detectada'
  }
}

export interface UseTauriMeetingDetectorResult {
  detectedMeeting: DetectedMeeting | null
  dismiss: () => void
  recordNow: () => void
}

export const useTauriMeetingDetector = (): UseTauriMeetingDetectorResult => {
  const navigate = useNavigate()
  const { setTitle } = useRecordingContext()
  const [detectedMeeting, setDetectedMeeting] = useState<DetectedMeeting | null>(null)

  useEffect(() => {
    // Safely retrieve Tauri global object (no-op in regular browser)
    const tauri = (window as unknown as { __TAURI__?: TauriApi }).__TAURI__
    if (!tauri?.event?.listen) {
      return
    }

    let unlistenMeeting: (() => void) | undefined
    let unlistenAction: (() => void) | undefined
    let isMounted = true

    const setupListeners = async () => {
      try {
        if (!tauri.event) return

        unlistenMeeting = await tauri.event.listen<DetectedMeeting>(
          'meeting-detected',
          (event: TauriEvent<DetectedMeeting>) => {
            if (!isMounted) return
            setDetectedMeeting(event.payload)
          }
        )

        unlistenAction = await tauri.event.listen<void>(
          'start-recording-action',
          () => {
            if (!isMounted) return
            navigate('/meetings/new?tab=record')
          }
        )
      } catch (err) {
        console.warn('[TauriMeetingDetector] Falha ao registrar listeners do Tauri:', err)
      }
    }

    setupListeners()

    return () => {
      isMounted = false
      if (unlistenMeeting) {
        try {
          unlistenMeeting()
        } catch {
          // ignore cleanup error
        }
      }
      if (unlistenAction) {
        try {
          unlistenAction()
        } catch {
          // ignore cleanup error
        }
      }
    }
  }, [navigate])

  const dismiss = useCallback(() => {
    setDetectedMeeting(null)
  }, [])

  const recordNow = useCallback(() => {
    if (detectedMeeting) {
      if (detectedMeeting.title) {
        setTitle(detectedMeeting.title)
      }
      setDetectedMeeting(null)
    }
    navigate('/meetings/new?tab=record')
  }, [detectedMeeting, navigate, setTitle])

  return {
    detectedMeeting,
    dismiss,
    recordNow,
  }
}
