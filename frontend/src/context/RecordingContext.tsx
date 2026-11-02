/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState } from 'react'

export interface MeetingOptions {
  language: 'pt' | 'en' | 'es' | 'auto'
  diarization: boolean
  provider: 'auto' | 'groq' | 'local'
  autoTasks: boolean
  exportNotion: boolean
}

export const DEFAULT_MEETING_OPTIONS: MeetingOptions = {
  language: 'pt',
  diarization: true,
  provider: 'auto',
  autoTasks: true,
  exportNotion: false,
}

interface RecordingContextValue {
  recordedFile: File | null
  durationMs: number | null
  title: string
  options: MeetingOptions
  setRecordingData: (file: File, durationMs: number, customTitle?: string) => void
  setTitle: (title: string) => void
  clearRecording: () => void
  updateOptions: (newOptions: Partial<MeetingOptions>) => void
}

const RecordingContext = createContext<RecordingContextValue | undefined>(undefined)

export const RecordingProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [recordedFile, setRecordedFile] = useState<File | null>(null)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [options, setOptions] = useState<MeetingOptions>(DEFAULT_MEETING_OPTIONS)

  const setRecordingData = (
    file: File,
    duration: number,
    customTitle?: string
  ) => {
    setRecordedFile(file)
    setDurationMs(duration)
    if (customTitle && !title.trim()) {
      setTitle(customTitle)
    }
  }

  const clearRecording = () => {
    setRecordedFile(null)
    setDurationMs(null)
  }

  const updateOptions = (newOptions: Partial<MeetingOptions>) => {
    setOptions((prev) => ({ ...prev, ...newOptions }))
  }

  return (
    <RecordingContext.Provider
      value={{
        recordedFile,
        durationMs,
        title,
        options,
        setRecordingData,
        setTitle,
        clearRecording,
        updateOptions,
      }}
    >
      {children}
    </RecordingContext.Provider>
  )
}

export const useRecordingContext = (): RecordingContextValue => {
  const ctx = useContext(RecordingContext)
  if (!ctx) {
    throw new Error('useRecordingContext deve ser utilizado dentro de RecordingProvider.')
  }
  return ctx
}
