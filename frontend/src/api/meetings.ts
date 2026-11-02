import { request } from './client'
import {
  AudioMetadata,
  Meeting,
  MeetingCreate,
  MeetingProcessResponse,
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

export async function processMeeting(meetingId: number): Promise<MeetingProcessResponse> {
  return request<MeetingProcessResponse>(`/meetings/${meetingId}/process`, {
    method: 'POST',
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
