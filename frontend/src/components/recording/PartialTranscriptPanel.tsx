import React from 'react'
import { PartialState } from '../../lib/partialTranscription'

const LABELS: Record<PartialState['state'], string> = {
  idle: '', starting: 'Iniciando sessão', recording: 'Recebendo áudio',
  finishing: 'Enviando últimos chunks e finalizando', completed: 'Prévia concluída',
  failed: 'Prévia indisponível',
}

export const PartialTranscriptPanel: React.FC<{ partial: PartialState }> = ({ partial }) => {
  if (partial.state === 'idle') return null
  const lag = Math.max(0, partial.capturedSeconds - partial.processedSeconds)
  return (
    <section className="mt-5 border border-slate-200 rounded-xl p-4 text-left" aria-label="Transcrição parcial">
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <h3 className="font-semibold text-ink">Transcrição parcial local</h3>
        <span className="text-muted" role="status">{LABELS[partial.state]}</span>
      </div>
      <p className="text-xs text-muted mt-2 tabular-nums">
        Atraso aproximado: {lag.toFixed(0)}s · {partial.uploadedChunks} chunks enviados
        {' '}· {partial.pendingChunks} pendentes · Revisão {Math.max(0, partial.revision)}
      </p>
      <p className="text-xs text-muted mt-1">Prévia sem falantes. O trecho final pode ser revisto; a transcrição definitiva será gerada no processamento final.</p>
      <div className="h-44 overflow-y-auto [overflow-anchor:none] whitespace-pre-wrap break-words mt-3 text-sm leading-relaxed" tabIndex={0} aria-label="Texto parcial; rolagem manual">
        {partial.text || 'Aguardando a primeira janela de áudio (cerca de 10s, mais o tempo do transcritor local)…'}
      </div>
      <p className="text-xs text-amber-800 min-h-8 mt-2" role={partial.error ? 'alert' : undefined}>{partial.error || ''}</p>
    </section>
  )
}
