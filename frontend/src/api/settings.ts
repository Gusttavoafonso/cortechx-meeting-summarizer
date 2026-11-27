import { request } from './client'

export type ProviderName = 'discord' | 'notion' | 'obsidian' | 'groq' | 'llm'
export type LLMProviderName = 'gemini' | 'openai' | 'groq' | 'anthropic'

export interface LLMProviderConfigItem {
  llm_provider: LLMProviderName
  llm_model?: string | null
  api_key_masked?: string | null
  is_configured: boolean
}

export interface IntegrationStatusItem {
  provider: ProviderName
  enabled: boolean
  is_configured: boolean
  source: 'user' | 'env' | 'none'
  webhook_preview: string | null
  api_key_masked: string | null
  database_id: string | null
  vault_path: string | null
  notes_folder: string | null
  llm_provider?: string | null
  llm_model?: string | null
  llm_providers?: Record<string, LLMProviderConfigItem> | null
}

export interface IntegrationsSettingsResponse {
  discord: IntegrationStatusItem
  notion: IntegrationStatusItem
  obsidian: IntegrationStatusItem
  groq: IntegrationStatusItem
  llm: IntegrationStatusItem
}

export interface IntegrationTestResponse {
  ok: boolean
  detail: string
}

export async function fetchIntegrationsSettings(): Promise<IntegrationsSettingsResponse> {
  return request<IntegrationsSettingsResponse>('/settings/integrations')
}

export async function updateDiscordIntegration(payload: {
  enabled: boolean
  webhook_url?: string
}): Promise<IntegrationStatusItem> {
  return request<IntegrationStatusItem>('/settings/integrations/discord', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function updateNotionIntegration(payload: {
  enabled: boolean
  api_key?: string
  database_id?: string
}): Promise<IntegrationStatusItem> {
  return request<IntegrationStatusItem>('/settings/integrations/notion', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function updateObsidianIntegration(payload: {
  enabled: boolean
  vault_path?: string
  notes_folder?: string
}): Promise<IntegrationStatusItem> {
  return request<IntegrationStatusItem>('/settings/integrations/obsidian', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function updateGroqIntegration(payload: {
  enabled: boolean
  api_key?: string
}): Promise<IntegrationStatusItem> {
  return request<IntegrationStatusItem>('/settings/integrations/groq', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function updateLlmIntegration(payload: {
  enabled: boolean
  llm_provider?: LLMProviderName
  llm_model?: string
  api_key?: string
}): Promise<IntegrationStatusItem> {
  return request<IntegrationStatusItem>('/settings/integrations/llm', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteIntegration(
  provider: ProviderName,
  llmProvider?: LLMProviderName
): Promise<void> {
  const query =
    provider === 'llm' && llmProvider
      ? `?llm_provider=${encodeURIComponent(llmProvider)}`
      : ''
  await request<void>(`/settings/integrations/${provider}${query}`, {
    method: 'DELETE',
  })
}

export async function testIntegration(
  provider: ProviderName,
  llmProvider?: LLMProviderName
): Promise<IntegrationTestResponse> {
  const query =
    provider === 'llm' && llmProvider
      ? `?llm_provider=${encodeURIComponent(llmProvider)}`
      : ''
  return request<IntegrationTestResponse>(`/settings/integrations/${provider}/test${query}`, {
    method: 'POST',
  })
}
