import React, { useEffect, useState } from 'react'
import {
  SlidersHorizontal,
  X,
  Globe,
  AudioLines,
  Cpu,
  CheckCircle2,
  FileText,
} from 'lucide-react'
import { Button } from '../ui/Button'
import { MeetingOptions, useRecordingContext } from '../../context/RecordingContext'

interface MeetingOptionsModalProps {
  isOpen: boolean
  onClose: () => void
}

export const MeetingOptionsModal: React.FC<MeetingOptionsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { options, updateOptions } = useRecordingContext()
  const [localOptions, setLocalOptions] = useState<MeetingOptions>(options)

  useEffect(() => {
    if (isOpen) {
      setLocalOptions(options)
    }
  }, [isOpen, options])

  if (!isOpen) return null

  const handleSave = () => {
    updateOptions(localOptions)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        className="modal-backdrop-enter absolute inset-0 bg-ink/40 backdrop-blur-xs"
      />
      <div className="modal-panel-enter relative bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-surface text-brand flex items-center justify-center">
              <SlidersHorizontal className="w-4 h-4 stroke-[2.2]" />
            </div>
            <div>
              <h3 className="font-sans text-lg font-semibold text-ink">
                Opções da reunião
              </h3>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted hover:text-ink hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* Idioma */}
          <div>
            <label className="flex items-center gap-2 text-xs font-semibold text-ink mb-2">
              <Globe className="w-4 h-4 text-brand stroke-[2]" />
              <span>Idioma principal</span>
            </label>
            <select
              value={localOptions.language}
              onChange={(e) =>
                setLocalOptions((prev) => ({
                  ...prev,
                  language: e.target.value as MeetingOptions['language'],
                }))
              }
              className="w-full text-xs font-medium text-ink bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 focus:border-brand focus:outline-none transition-colors"
            >
              <option value="pt">Português (Brasil)</option>
              <option value="en">Inglês (English)</option>
              <option value="es">Espanhol (Español)</option>
              <option value="auto">Detecção automática de idioma</option>
            </select>
          </div>

          {/* Modo de transcrição contínua por chunks */}
          <div className="flex items-start gap-2.5 p-3.5 bg-surface/60 border border-[#DCE2FB] rounded-xl">
            <AudioLines className="w-4 h-4 text-brand shrink-0 mt-0.5 stroke-[2]" />
            <div>
              <p className="text-xs font-semibold text-ink">
                Transcrição contínua por chunks
              </p>
              <p className="text-[11px] text-ink-light leading-snug mt-0.5">
                Transcreve blocos em ordem cronológica, sem identificar quem falou.
              </p>
            </div>
          </div>

          {/* Provedor de Transcrição */}
          <div>
            <label className="flex items-center gap-2 text-xs font-semibold text-ink mb-2">
              <Cpu className="w-4 h-4 text-brand stroke-[2]" />
              <span>Motor de transcrição</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setLocalOptions((prev) => ({ ...prev, provider: 'auto' }))}
                className={`p-3 text-left border rounded-xl text-xs transition-all ${
                  localOptions.provider === 'auto'
                    ? 'border-brand bg-brand/5 text-ink font-semibold'
                    : 'border-slate-200 bg-white text-muted hover:border-slate-300'
                }`}
              >
                <p className="font-semibold text-ink mb-0.5">Automático / Groq</p>
                <p className="text-[10px] text-muted">Nuvem (recomendado)</p>
              </button>

              <button
                type="button"
                onClick={() =>
                  setLocalOptions((prev) => ({ ...prev, provider: 'local' }))
                }
                className={`p-3 text-left border rounded-xl text-xs transition-all ${
                  localOptions.provider === 'local'
                    ? 'border-brand bg-brand/5 text-ink font-semibold'
                    : 'border-slate-200 bg-white text-muted hover:border-slate-300'
                }`}
              >
                <p className="font-semibold text-ink mb-0.5">Whisper Local</p>
                <p className="text-[10px] text-muted">
                  Processamento offline no servidor
                </p>
              </button>
            </div>
          </div>

          {/* Tarefas e Notion */}
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <div className="flex items-start justify-between gap-3 p-3 bg-slate-50 border border-slate-200/80 rounded-xl">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-brand shrink-0 mt-0.5 stroke-[2]" />
                <div>
                  <p className="text-xs font-semibold text-ink">
                    Extração automática de tarefas
                  </p>
                  <p className="text-[11px] text-muted">
                    Identifica responsáveis e prazos.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={localOptions.autoTasks}
                onChange={(e) =>
                  setLocalOptions((prev) => ({
                    ...prev,
                    autoTasks: e.target.checked,
                  }))
                }
                className="w-4 h-4 mt-0.5 accent-primary-btn rounded cursor-pointer"
              />
            </div>

            <div className="flex items-start justify-between gap-3 p-3 bg-slate-50 border border-slate-200/80 rounded-xl">
              <div className="flex items-start gap-2.5">
                <FileText className="w-4 h-4 text-brand shrink-0 mt-0.5 stroke-[2]" />
                <div>
                  <p className="text-xs font-semibold text-ink">
                    Enviar para integrações conectadas
                  </p>
                  <p className="text-[11px] text-muted">
                    Publica o resumo no Discord, Notion ou Obsidian, se conectados.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={localOptions.exportIntegrations}
                onChange={(e) =>
                  setLocalOptions((prev) => ({
                    ...prev,
                    exportIntegrations: e.target.checked,
                  }))
                }
                className="w-4 h-4 mt-0.5 accent-primary-btn rounded cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 bg-slate-50 border-t border-slate-100">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave}>
            Salvar opções
          </Button>
        </div>
      </div>
    </div>
  )
}
