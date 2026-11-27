import { API_BASE_URL, request } from './client'
import {
  AudioMetadata,
  GlobalTaskItem,
  IntegrationRetryResponse,
  Meeting,
  MeetingCreate,
  MeetingIntegrationsResponse,
  MeetingProcessOptions,
  MeetingProcessResponse,
  MeetingStats,
  MeetingStatusResponse,
  SummaryResponse,
  TranscriptResponse,
} from '../types/meeting'

export async function fetchMeetings(): Promise<Meeting[]> {
  return request<Meeting[]>('/meetings')
}

export async function fetchMeetingById(id: number): Promise<Meeting> {
  return request<Meeting>(`/meetings/${id}`)
}

export async function createMeeting(data: MeetingCreate): Promise<Meeting> {
  return request<Meeting>('/meetings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function uploadMeetingAudio(
  meetingId: number,
  file: File
): Promise<AudioMetadata> {
  const formData = new FormData()
  formData.append('file', file)

  return request<AudioMetadata>(`/meetings/${meetingId}/audio`, {
    method: 'POST',
    body: formData,
  })
}

export async function processMeeting(
  meetingId: number,
  options?: MeetingProcessOptions
): Promise<MeetingProcessResponse> {
  return request<MeetingProcessResponse>(`/meetings/${meetingId}/process`, {
    method: 'POST',
    ...(options ? { body: JSON.stringify(options) } : {}),
  })
}

export async function fetchMeetingStatus(
  meetingId: number
): Promise<MeetingStatusResponse> {
  return request<MeetingStatusResponse>(`/meetings/${meetingId}/status`)
}

export async function fetchMeetingTranscript(
  meetingId: number
): Promise<TranscriptResponse> {
  return request<TranscriptResponse>(`/meetings/${meetingId}/transcript`)
}

export async function fetchMeetingSummary(meetingId: number): Promise<SummaryResponse> {
  return request<SummaryResponse>(`/meetings/${meetingId}/summary`)
}

export async function retryMeeting(meetingId: number): Promise<Meeting> {
  return request<Meeting>(`/meetings/${meetingId}/retry`, {
    method: 'POST',
  })
}

export async function fetchMeetingStats(): Promise<MeetingStats> {
  return request<MeetingStats>('/meetings/stats')
}

export async function fetchAllTasks(): Promise<GlobalTaskItem[]> {
  return request<GlobalTaskItem[]>('/meetings/tasks')
}

export async function deleteMeeting(meetingId: number): Promise<void> {
  await request<void>(`/meetings/${meetingId}`, {
    method: 'DELETE',
  })
}

export function getMeetingAudioUrl(meetingId: number): string {
  return `${API_BASE_URL}/meetings/${meetingId}/audio/file`
}

export async function fetchMeetingIntegrations(
  meetingId: number
): Promise<MeetingIntegrationsResponse> {
  return request<MeetingIntegrationsResponse>(`/meetings/${meetingId}/integrations`)
}

export async function retryMeetingIntegrations(
  meetingId: number,
  providers?: string[]
): Promise<IntegrationRetryResponse> {
  return request<IntegrationRetryResponse>(`/meetings/${meetingId}/integrations/retry`, {
    method: 'POST',
    ...(providers ? { body: JSON.stringify({ providers }) } : {}),
  })
}
