import { request } from './client'

export interface SystemStatus {
  status: string
  stt_mode: 'groq' | 'local'
  stt_source: 'user' | 'server' | 'local'
  whisper_model: string
  llm_configured: boolean
  llm_provider: string | null
  llm_model: string | null
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  return request<SystemStatus>('/system/status')
}
