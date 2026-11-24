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
import {
  createLiveTranscriptionTransport,
  INITIAL_LIVE_TRANSCRIPTION_STATE,
  LiveTranscriptionState,
  LiveTranscriptionTransport,
} from '../lib/liveTranscription'

export interface MeetingOptions {
  language: 'pt' | 'en' | 'es' | 'auto'
  provider: 'auto' | 'groq' | 'local'
  autoTasks: boolean
  exportIntegrations: boolean
}

export const DEFAULT_MEETING_OPTIONS: MeetingOptions = {
  language: 'pt',
  provider: 'auto',
  autoTasks: true,
  exportIntegrations: true,
}

interface RecordingContextValue {
  recordedFile: File | null
  durationMs: number | null
  title: string
  options: MeetingOptions
  isRecording: boolean
  isStartingRecording: boolean
  isPaused: boolean
  elapsedMs: number
  captureMode: CaptureMode
  recordingError: string | null
  liveTranscription: LiveTranscriptionState
  setCaptureMode: (mode: CaptureMode) => void
  setRecordingData: (file: File, durationMs: number, customTitle?: string) => void
  setTitle: (title: string) => void
  clearRecording: () => void
  clearLiveTranscription: () => void
  updateOptions: (newOptions: Partial<MeetingOptions>) => void
  startRecording: (mode?: CaptureMode) => Promise<void>
  pauseRecording: () => void
  resumeRecording: () => void
  stopRecording: (userId?: number | string) => Promise<RecordingResult>
  cancelRecording: () => void
  getAudioLevels: () => AudioLevels
  clearRecordingError: () => void
}

const RecordingContext = createContext<RecordingContextValue | undefined>(undefined)

export const RecordingProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const engineRef = useRef<AudioRecorderEngine | null>(null)
  const transportRef = useRef<LiveTranscriptionTransport | null>(null)
  const unsubscribeTransportRef = useRef<(() => void) | null>(null)
  const startingRef = useRef(false)
  const [recordedFile, setRecordedFile] = useState<File | null>(null)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [options, setOptions] = useState<MeetingOptions>(DEFAULT_MEETING_OPTIONS)

  const [isRecording, setIsRecording] = useState(false)
  const [isStartingRecording, setIsStartingRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [captureMode, setCaptureMode] = useState<CaptureMode>('both')
  const [recordingError, setRecordingError] = useState<string | null>(null)
  const [liveTranscription, setLiveTranscription] = useState<LiveTranscriptionState>(
    INITIAL_LIVE_TRANSCRIPTION_STATE
  )

  const setupTransport = useCallback((language: MeetingOptions['language']) => {
    unsubscribeTransportRef.current?.()
    transportRef.current?.cancel()
    const transport = createLiveTranscriptionTransport({ language })
    transportRef.current = transport
    unsubscribeTransportRef.current = transport.subscribe((nextState) => {
      setLiveTranscription(nextState)
    })
    return transport
  }, [])

  useEffect(() => {
    engineRef.current = new AudioRecorderEngine()
    const transport = setupTransport(DEFAULT_MEETING_OPTIONS.language)

    return () => {
      unsubscribeTransportRef.current?.()
      transport.cancel()
      transportRef.current?.cancel()
      engineRef.current?.cleanup()
    }
  }, [setupTransport])

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
    setTitle('')
    transportRef.current?.cancel()
  }, [])

  const clearLiveTranscription = useCallback(() => {
    transportRef.current?.cancel()
  }, [])

  const updateOptions = useCallback((newOptions: Partial<MeetingOptions>) => {
    setOptions((prev) => ({ ...prev, ...newOptions }))
  }, [])

  const clearRecordingError = useCallback(() => {
    setRecordingError(null)
  }, [])

  const startRecording = useCallback(
    async (mode?: CaptureMode) => {
      if (startingRef.current || engineRef.current?.isRecording) return
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

      startingRef.current = true
      setIsStartingRecording(true)
      const transport = setupTransport(options.language)

      try {
        await engineRef.current.start({
          mode: targetMode,
          onTick: (ms) => setElapsedMs(ms),
          onChunk: (chunk) => transportRef.current?.pushChunk(chunk),
          onPartialSegmentEnd: (epochId) => transportRef.current?.endSegment?.(epochId),
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
              transportRef.current?.pause()
              engineRef.current?.pause()
              setIsPaused(true)
              setRecordingError(
                'O compartilhamento de áudio da aba foi encerrado no navegador. A gravação foi pausada.'
              )
            }
          },
        })
        transport.start()
        setCaptureMode(targetMode)
        setIsRecording(true)
        setIsPaused(false)
      } catch (err) {
        transport.cancel()
        const msg = err instanceof Error ? err.message : String(err)
        setRecordingError(msg)
        setIsRecording(false)
        setIsPaused(false)
        throw err
      } finally {
        startingRef.current = false
        setIsStartingRecording(false)
      }
    },
    [captureMode, options.language, setupTransport]
  )

  const pauseRecording = useCallback(() => {
    transportRef.current?.pause()
    engineRef.current?.pause()
    setIsPaused(true)
  }, [])

  const resumeRecording = useCallback(() => {
    transportRef.current?.resume()
    engineRef.current?.resume()
    setIsPaused(false)
  }, [])

  const stopRecording = useCallback(
    async (userId: number | string = 1): Promise<RecordingResult> => {
      if (!engineRef.current) {
        throw new Error('Gravador não inicializado.')
      }
      const result = await engineRef.current.stop({ userId })
      await transportRef.current?.finalize()
      setIsRecording(false)
      setIsPaused(false)
      setElapsedMs(0)
      return result
    },
    []
  )

  const cancelRecording = useCallback(() => {
    engineRef.current?.cleanup()
    transportRef.current?.cancel()
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
        isStartingRecording,
        isPaused,
        elapsedMs,
        captureMode,
        recordingError,
        liveTranscription,
        setCaptureMode,
        setRecordingData,
        setTitle,
        clearRecording,
        clearLiveTranscription,
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
