import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  ChevronRight,
  FileAudio,
  Play,
  Pause,
  SlidersHorizontal,
  Share2,
  MoreHorizontal,
  Upload,
  Mic,
  X,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { RecordingPanel } from '../components/recording/RecordingPanel'
import { createMeeting, processMeeting, uploadMeetingAudio } from '../api/meetings'
import { formatBytes, formatSecondsToTime } from '../lib/utils'

const MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024 // 250MB
const ALLOWED_EXTENSIONS = [
  '.mp3',
  '.m4a',
  '.wav',
  '.mp4',
  '.webm',
  '.ogg',
  '.aac',
  '.flac',
]

type ProcessStep = 'idle' | 'creating' | 'uploading' | 'processing' | 'done' | 'failed'

export const NewMeeting: React.FC = () => {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const titleInputRef = useRef<HTMLInputElement>(null)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  const [title, setTitle] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [inputMethod, setInputMethod] = useState<'record' | 'upload'>('record')

  // Audio preview playback state
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState<number | null>(null)

  // Orchestration state machine for retry capability
  const [createdMeetingId, setCreatedMeetingId] = useState<number | null>(null)
  const [audioUploaded, setAudioUploaded] = useState(false)
  const [currentStep, setCurrentStep] = useState<ProcessStep>('idle')
  const [failedStep, setFailedStep] = useState<'create' | 'upload' | 'process' | null>(
    null
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    titleInputRef.current?.focus()
  }, [])

  // Create & clean up audio object URL
  useEffect(() => {
    if (!selectedFile) {
      setIsPlaying(false)
      setCurrentTime(0)
      setAudioDuration(null)
      return
    }

    const url = URL.createObjectURL(selectedFile)
    setAudioUrl(url)

    const audio = new Audio()
    audio.src = url
    audio.onloadedmetadata = () => {
      if (!isNaN(audio.duration) && isFinite(audio.duration)) {
        setAudioDuration(audio.duration)
      }
    }

    return () => {
      URL.revokeObjectURL(url)
      setAudioUrl(null)
    }
  }, [selectedFile])

  // Audio playback controls
  const togglePlay = () => {
    if (!audioPlayerRef.current || !audioUrl) return

    if (isPlaying) {
      audioPlayerRef.current.pause()
      setIsPlaying(false)
    } else {
      audioPlayerRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false))
    }
  }

  const handleAudioTimeUpdate = () => {
    if (audioPlayerRef.current) {
      setCurrentTime(audioPlayerRef.current.currentTime)
    }
  }

  const handleAudioEnded = () => {
    setIsPlaying(false)
    setCurrentTime(0)
  }

  // File validation
  const validateAndSetFile = (file: File) => {
    setFileError(null)
    setErrorMessage(null)

    if (file.size === 0) {
      setFileError('O arquivo selecionado está vazio (0 bytes).')
      return
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileError('O tamanho do arquivo excede o limite máximo permitido de 250 MB.')
      return
    }

    const fileNameLower = file.name.toLowerCase()
    const isValidExtension = ALLOWED_EXTENSIONS.some((ext) => fileNameLower.endsWith(ext))

    if (
      !isValidExtension &&
      !file.type.startsWith('audio/') &&
      !file.type.startsWith('video/')
    ) {
      setFileError(
        `Formato não suportado. Por favor utilize: ${ALLOWED_EXTENSIONS.join(', ')}.`
      )
      return
    }

    // Default title from file name if user hasn't typed one yet
    if (!title.trim()) {
      const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
      setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1))
    }

    setSelectedFile(file)
    // Reset pipeline state if user changes the file
    setCreatedMeetingId(null)
    setAudioUploaded(false)
    setFailedStep(null)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      validateAndSetFile(file)
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      validateAndSetFile(file)
    }
  }

  const handleRemoveFile = () => {
    setSelectedFile(null)
    setFileError(null)
    setCreatedMeetingId(null)
    setAudioUploaded(false)
    setFailedStep(null)
    setErrorMessage(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // Multi-step Orchestration & Retry Execution
  const handleStartProcess = async () => {
    if (!title.trim()) {
      setErrorMessage('Por favor, informe o título da reunião.')
      titleInputRef.current?.focus()
      return
    }

    if (!selectedFile) {
      setErrorMessage('Por favor, selecione um arquivo de áudio ou vídeo.')
      return
    }

    setErrorMessage(null)

    let meetingId = createdMeetingId

    // Etapa 1: Criar reunião (caso ainda não tenha sido criada)
    if (!meetingId) {
      try {
        setCurrentStep('creating')
        setFailedStep(null)
        const newMeeting = await createMeeting({ title: title.trim() })
        meetingId = newMeeting.id
        setCreatedMeetingId(meetingId)
      } catch (err) {
        setCurrentStep('failed')
        setFailedStep('create')
        setErrorMessage(
          err instanceof Error
            ? `Erro ao criar reunião: ${err.message}`
            : 'Erro ao criar reunião.'
        )
        return
      }
    }

    // Etapa 2: Upload do áudio (caso ainda não tenha sido feito upload com sucesso)
    if (!audioUploaded) {
      try {
        setCurrentStep('uploading')
        setFailedStep(null)
        await uploadMeetingAudio(meetingId, selectedFile)
        setAudioUploaded(true)
      } catch (err) {
        setCurrentStep('failed')
        setFailedStep('upload')
        setErrorMessage(
          err instanceof Error
            ? `Erro ao enviar áudio: ${err.message}`
            : 'Erro ao enviar arquivo de áudio.'
        )
        return
      }
    }

    // Etapa 3: Iniciar processamento assíncrono
    try {
      setCurrentStep('processing')
      setFailedStep(null)
      await processMeeting(meetingId)
      setCurrentStep('done')

      // Redireciona para a lista ou tela de detalhes da reunião
      setTimeout(() => {
        navigate(`/meetings/${meetingId}`)
      }, 700)
    } catch (err) {
      setCurrentStep('failed')
      setFailedStep('process')
      setErrorMessage(
        err instanceof Error
          ? `Erro ao disparar processamento: ${err.message}`
          : 'Erro ao iniciar o processamento da reunião.'
      )
    }
  }

  const getStepFeedbackText = () => {
    switch (currentStep) {
      case 'creating':
        return 'Criando registro da reunião...'
      case 'uploading':
        return `Enviando arquivo de áudio (${formatBytes(selectedFile?.size || 0)})...`
      case 'processing':
        return 'Iniciando pipeline de transcrição e resumo...'
      case 'done':
        return 'Processo iniciado com sucesso! Redirecionando...'
      case 'failed':
        if (failedStep === 'create') return 'Falha na criação da reunião.'
        if (failedStep === 'upload')
          return 'Falha no envio do áudio. Clique para tentar novamente.'
        if (failedStep === 'process')
          return 'Falha no agendamento do processamento. Clique para tentar novamente.'
        return 'Ocorreu um erro.'
      default:
        return null
    }
  }

  return (
    <div className="flex-1 px-8 py-10 max-w-5xl mx-auto w-full">
      {/* Hidden audio player for actual playback */}
      {audioUrl && (
        <audio
          ref={audioPlayerRef}
          src={audioUrl}
          onTimeUpdate={handleAudioTimeUpdate}
          onEnded={handleAudioEnded}
          preload="metadata"
        />
      )}

      {/* Top Header Row: Breadcrumb & Secondary Actions */}
      <div className="flex items-center justify-between mb-8">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-muted">
          <Link
            to="/meetings"
            className="hover:text-ink hover:underline transition-colors font-medium"
          >
            Reuniões
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-muted/60" />
          <span className="text-ink font-semibold">Nova reunião</span>
        </nav>

        {/* Secondary Actions (Subtly disabled in this phase) */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled
            title="Funcionalidade em desenvolvimento"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted/60 bg-transparent rounded-lg cursor-not-allowed opacity-60 hover:opacity-60"
          >
            <Share2 className="w-3.5 h-3.5" />
            <span>Compartilhar</span>
          </button>
          <button
            type="button"
            disabled
            title="Opções adicionais em desenvolvimento"
            className="p-1.5 text-muted/60 rounded-lg cursor-not-allowed opacity-60 hover:opacity-60"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Title Input */}
      <div className="mb-6">
        <input
          ref={titleInputRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Alinhamento de Produto — Sprint 04"
          disabled={currentStep !== 'idle' && currentStep !== 'failed'}
          className="w-full text-2xl sm:text-3xl font-bold font-fredoka text-ink bg-transparent border-b-2 border-transparent hover:border-slate-200 focus:border-brand focus:outline-none transition-colors pb-1 placeholder:text-muted/40"
        />
      </div>

      {/* Mode Selector Tabs (Gravar ou Enviar arquivo) */}
      {!selectedFile && (
        <div className="flex items-center gap-2 mb-6">
          <button
            type="button"
            onClick={() => setInputMethod('record')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              inputMethod === 'record'
                ? 'bg-primary-btn text-white shadow-xs'
                : 'bg-white text-muted hover:text-ink border border-slate-200'
            }`}
          >
            <Mic className="w-4 h-4 stroke-[2.2]" />
            <span>Gravar reunião</span>
          </button>

          <button
            type="button"
            onClick={() => setInputMethod('upload')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              inputMethod === 'upload'
                ? 'bg-primary-btn text-white shadow-xs'
                : 'bg-white text-muted hover:text-ink border border-slate-200'
            }`}
          >
            <Upload className="w-4 h-4 stroke-[2.2]" />
            <span>Enviar arquivo</span>
          </button>
        </div>
      )}

      {/* Main Action Area: Recording Panel or Dropzone */}
      {!selectedFile ? (
        inputMethod === 'record' ? (
          <RecordingPanel
            onRecordingComplete={(file) => validateAndSetFile(file)}
            disabled={currentStep !== 'idle' && currentStep !== 'failed'}
          />
        ) : (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer bg-white/40 hover:bg-white/80 ${
              isDragging
                ? 'border-brand bg-brand/5 scale-[1.005]'
                : 'border-slate-300 hover:border-slate-400'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,video/*,.mp3,.m4a,.wav,.mp4,.webm,.ogg,.aac,.flac"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="w-12 h-12 rounded-2xl bg-surface text-brand flex items-center justify-center mx-auto mb-4 shadow-xs">
              <Upload className="w-5 h-5 stroke-[2.2]" />
            </div>

            <p className="text-sm font-medium text-ink mb-1">
              Solte seu arquivo de áudio ou vídeo aqui, ou{' '}
              <span className="text-brand underline decoration-brand/60 underline-offset-2 hover:text-brand-dark">
                procure
              </span>
            </p>
            <p className="text-xs text-muted">MP3, M4A, WAV, MP4 ou WebM até 250 MB</p>
          </div>
        )
      ) : (
        /* Selected Audio Card Preview (Matching Figma criacao_reuniao.png) */
        <Card className="p-4 sm:p-5 mb-6 border-slate-200 shadow-xs">
          {/* Top row: Icon + Info + Actions */}
          <div className="flex items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-surface text-brand flex items-center justify-center shrink-0">
                <FileAudio className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-muted">{formatBytes(selectedFile.size)}</p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={currentStep !== 'idle' && currentStep !== 'failed'}
                title="Substituir arquivo"
                className="p-1.5 text-muted hover:text-ink hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,video/*,.mp3,.m4a,.wav,.mp4,.webm,.ogg,.aac,.flac"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={handleRemoveFile}
                disabled={currentStep !== 'idle' && currentStep !== 'failed'}
                title="Remover arquivo"
                className="p-1.5 text-muted hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Bottom row: Play/Pause button + Waveform Simulation + Duration */}
          <div className="flex items-center gap-3 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={togglePlay}
              className="w-8 h-8 rounded-full bg-ink text-white flex items-center justify-center shrink-0 hover:bg-ink-light transition-colors shadow-xs"
            >
              {isPlaying ? (
                <Pause className="w-3.5 h-3.5 fill-current" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
              )}
            </button>

            {/* Waveform graphic matching Figma design */}
            <div className="flex-1 flex items-center gap-[3px] h-6 overflow-hidden select-none">
              {[
                16, 22, 28, 20, 14, 18, 24, 12, 10, 16, 24, 20, 16, 12, 18, 22, 14, 10,
                18, 24, 28, 22, 16, 12, 20, 26, 18, 14, 10, 16, 22, 26, 18, 12, 16, 22,
                20, 14, 10, 18, 24, 26, 18, 12, 14, 20, 24, 16,
              ].map((height, i) => {
                const totalBars = 48
                const progressRatio =
                  audioDuration && audioDuration > 0 ? currentTime / audioDuration : 0
                const isPlayed = i / totalBars <= progressRatio

                return (
                  <span
                    key={i}
                    style={{ height: `${height}px` }}
                    className={`w-[2.5px] rounded-full transition-colors ${
                      isPlayed ? 'bg-primary-btn' : 'bg-slate-300'
                    }`}
                  />
                )
              })}
            </div>

            <span className="text-xs font-mono text-muted shrink-0">
              {audioDuration
                ? isPlaying
                  ? `${formatSecondsToTime(currentTime)} / ${formatSecondsToTime(audioDuration)}`
                  : formatSecondsToTime(audioDuration)
                : '48:12'}
            </span>
          </div>
        </Card>
      )}

      {/* Validation / Error alerts */}
      {fileError && (
        <div className="flex items-center gap-2 text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 mt-4">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{fileError}</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-start gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 mt-4">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">{errorMessage}</p>
            {failedStep && (
              <p className="mt-1 text-muted">
                O progresso anterior foi preservado. Ao clicar no botão abaixo, a operação
                continuará a partir desta etapa.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Step progress notification */}
      {currentStep !== 'idle' && (
        <div className="flex items-center gap-2.5 text-xs text-brand font-medium bg-surface/70 border border-[#DCE2FB] rounded-xl px-4 py-3 mt-4">
          {currentStep === 'done' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          ) : currentStep === 'failed' ? (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          ) : (
            <RefreshCw className="w-4 h-4 animate-spin shrink-0 text-brand" />
          )}
          <span>{getStepFeedbackText()}</span>
        </div>
      )}

      {/* Bottom Bar: Opções (subtly disabled) & Iniciar processo */}
      <div className="flex items-center justify-between mt-10 pt-4">
        {/* Secondary button: Opções (Disabled subtly) */}
        <button
          type="button"
          disabled
          title="Opções avançadas estarão disponíveis nas próximas fases"
          className="flex items-center gap-2 text-xs font-medium text-muted/60 cursor-not-allowed opacity-60 hover:opacity-60"
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span>Opções</span>
        </button>

        {/* Primary Action Button */}
        <Button
          onClick={handleStartProcess}
          disabled={!selectedFile || (currentStep !== 'idle' && currentStep !== 'failed')}
          isLoading={
            currentStep === 'creating' ||
            currentStep === 'uploading' ||
            currentStep === 'processing'
          }
          rightIcon={<ArrowRight className="w-4 h-4" />}
          className="h-11 px-6 font-semibold shadow-sm"
        >
          {failedStep ? 'Tentar novamente' : 'Iniciar processo'}
        </Button>
      </div>
    </div>
  )
}
