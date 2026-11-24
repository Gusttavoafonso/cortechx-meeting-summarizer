export type MeetingStatus =
  | 'received'
  | 'audio_uploaded'
  | 'transcribing'
  | 'transcribed'
  | 'processing'
  | 'completed'
  | 'failed'

export interface AudioMetadata {
  meeting_id: number
  filename: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  duration_seconds?: number | null
  file_path: string
  uploaded_at: string
}

export interface MeetingProcessOptions {
  language?: 'pt' | 'en' | 'es' | 'auto'
  provider?: 'auto' | 'groq' | 'local'
  auto_tasks?: boolean
  export_notion?: boolean
  integrations?: string[]
  skip_integrations?: boolean
}

export interface TranscriptSegment {
  id?: number
  start_time: number
  end_time: number
  text: string
  speaker?: string | null
}

export interface TranscriptResponse {
  id: number
  meeting_id: number
  content: string
  created_at: string
  segments: TranscriptSegment[]
}

export interface TaskItem {
  id: number
  meeting_id: number
  description: string
  responsible: string | null
  deadline: string | null
  created_at: string
}

export interface SummaryResponse {
  id: number
  meeting_id: number
  objective: string | null
  summary: string | null
  key_points: string[]
  decisions: string[]
  tasks: TaskItem[]
  created_at: string
  updated_at: string
}

export interface Meeting {
  id: number
  title: string
  status: MeetingStatus
  created_at: string
  updated_at: string
  processing_started_at: string | null
  processing_completed_at: string | null
  last_error: string | null
  audio: AudioMetadata | null
  transcript: TranscriptResponse | null
  summary?: SummaryResponse | null
}

export interface MeetingCreate {
  title: string
}

export interface MeetingProcessResponse {
  meeting_id: number
  status: MeetingStatus
}

export interface MeetingStatusResponse {
  meeting_id: number
  status: MeetingStatus
  updated_at: string
  last_error: string | null
}

export interface MeetingStats {
  total_meetings: number
  completed_meetings: number
  processing_meetings: number
  failed_meetings: number
  total_audio_seconds: number
  total_tasks: number
  recent_meetings: Meeting[]
}

export interface GlobalTaskItem {
  id: number
  meeting_id: number
  meeting_title: string
  meeting_status: MeetingStatus
  description: string
  responsible: string | null
  deadline: string | null
  created_at: string
}
