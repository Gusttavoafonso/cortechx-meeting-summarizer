/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'
import {
  AudioLevels,
  AudioRecorderEngine,
  CaptureMode,
  RecordingResult,
} from '../lib/audioRecorder'

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
  isRecording: boolean
  isPaused: boolean
  elapsedMs: number
  captureMode: CaptureMode
  recordingError: string | null
  setCaptureMode: (mode: CaptureMode) => void
  setRecordingData: (file: File, durationMs: number, customTitle?: string) => void
  setTitle: (title: string) => void
  clearRecording: () => void
  updateOptions: (newOptions: Partial<MeetingOptions>) => void
  startRecording: (mode?: CaptureMode) => Promise<void>
  pauseRecording: () => void
  resumeRecording: () => void
  stopRecording: (userId: number | string) => Promise<RecordingResult>
  cancelRecording: () => void
  getAudioLevels: () => AudioLevels
  clearRecordingError: () => void
}

const RecordingContext = createContext<RecordingContextValue | undefined>(undefined)

export const RecordingProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const engineRef = useRef<AudioRecorderEngine | null>(null)
  const [recordedFile, setRecordedFile] = useState<File | null>(null)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [options, setOptions] = useState<MeetingOptions>(DEFAULT_MEETING_OPTIONS)

  const [isRecording, setIsRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [captureMode, setCaptureMode] = useState<CaptureMode>('both')
  const [recordingError, setRecordingError] = useState<string | null>(null)

  useEffect(() => {
    engineRef.current = new AudioRecorderEngine()
    return () => {
      engineRef.current?.cleanup()
    }
  }, [])

  // Protege contra fechamento/recarregamento acidental da aba durante gravação ativa
  useEffect(() => {
    if (!isRecording) return
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isRecording])

  const setRecordingData = useCallback(
    (file: File, duration: number, customTitle?: string) => {
      setRecordedFile(file)
      setDurationMs(duration)
      if (customTitle) {
        setTitle((prev) => (prev.trim() ? prev : customTitle))
      }
    },
    []
  )

  const clearRecording = useCallback(() => {
    setRecordedFile(null)
    setDurationMs(null)
  }, [])

  const updateOptions = useCallback((newOptions: Partial<MeetingOptions>) => {
    setOptions((prev) => ({ ...prev, ...newOptions }))
  }, [])

  const clearRecordingError = useCallback(() => {
    setRecordingError(null)
  }, [])

  const startRecording = useCallback(
    async (mode?: CaptureMode) => {
      const targetMode = mode ?? captureMode
      setRecordingError(null)

      if (!AudioRecorderEngine.isSupported()) {
        const msg =
          'Seu navegador não possui suporte para gravação com Web Audio API / MediaRecorder.'
        setRecordingError(msg)
        throw new Error(msg)
      }

      if (!engineRef.current) {
        engineRef.current = new AudioRecorderEngine()
      }

      try {
        await engineRef.current.start({
          mode: targetMode,
          onTick: (ms) => setElapsedMs(ms),
          onStateChange: (state) => {
            if (state === 'paused') {
              setIsPaused(true)
            } else if (state === 'recording') {
              setIsPaused(false)
              setIsRecording(true)
            } else if (state === 'stopped') {
              setIsRecording(false)
              setIsPaused(false)
            }
          },
          onSourceEnded: (src) => {
            if (src === 'system') {
              engineRef.current?.pause()
              setIsPaused(true)
              setRecordingError(
                'O compartilhamento de áudio da aba foi encerrado no navegador. A gravação foi pausada.'
              )
            }
          },
        })
        setCaptureMode(targetMode)
        setIsRecording(true)
        setIsPaused(false)
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        setRecordingError(msg)
        setIsRecording(false)
        setIsPaused(false)
        throw err
      }
    },
    [captureMode]
  )

  const pauseRecording = useCallback(() => {
    engineRef.current?.pause()
    setIsPaused(true)
  }, [])

  const resumeRecording = useCallback(() => {
    engineRef.current?.resume()
    setIsPaused(false)
  }, [])

  const stopRecording = useCallback(
    async (userId: number | string): Promise<RecordingResult> => {
      if (
        userId === undefined ||
        userId === null ||
        String(userId).trim() === ''
      ) {
        const msg =
          'É necessário informar o ID do usuário para finalizar a gravação.'
        setRecordingError(msg)
        throw new Error(msg)
      }

      if (!engineRef.current) {
        throw new Error('Gravador não inicializado.')
      }

      const result = await engineRef.current.stop({ userId })

      setIsRecording(false)
      setIsPaused(false)
      setElapsedMs(0)
      setRecordingError(null)

      return result
    },
    []
  )

  const cancelRecording = useCallback(() => {
    engineRef.current?.cleanup()
    setIsRecording(false)
    setIsPaused(false)
    setElapsedMs(0)
    setRecordingError(null)
  }, [])

  const getAudioLevels = useCallback((): AudioLevels => {
    if (!engineRef.current?.isRecording || engineRef.current.isPaused) {
      return { micLevel: 0, systemLevel: 0 }
    }
    return engineRef.current.getAudioLevels()
  }, [])

  return (
    <RecordingContext.Provider
      value={{
        recordedFile,
        durationMs,
        title,
        options,
        isRecording,
        isPaused,
        elapsedMs,
        captureMode,
        recordingError,
        setCaptureMode,
        setRecordingData,
        setTitle,
        clearRecording,
        updateOptions,
        startRecording,
        pauseRecording,
        resumeRecording,
        stopRecording,
        cancelRecording,
        getAudioLevels,
        clearRecordingError,
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