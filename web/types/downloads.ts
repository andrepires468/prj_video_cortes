import type { PaginationMeta } from '~/types/pagination'

export type JobStatus = 'queued' | 'running' | 'done' | 'error' | 'cancelled'

export type MediaFolder = 'downloads' | 'cortes'

export type JobStage = 'download' | 'upload'

export interface JobInfo {
  id: string
  status: JobStatus
  progress: number
  message: string
  url: string
  filename?: string | null
  error?: string | null
  created_at?: string
  updated_at?: string
  stage?: JobStage
  download_progress?: number
  upload_progress?: number
}

export interface FileInfo {
  name: string
  size: number
  mtime: string
  thumb?: string | null
  play_url?: string | null
  thumb_url?: string | null
}

export interface FileListResponse {
  files: FileInfo[]
  pagination: PaginationMeta
}

export interface MediaInfo {
  name: string
  duration: number
  width?: number | null
  height?: number | null
  size: number
}

export interface CutJobInfo {
  id: string
  status: JobStatus
  progress: number
  message: string
  filename: string
  outputs: string[]
  error?: string | null
  created_at?: string
  updated_at?: string
}

export interface DeleteMediaResponse {
  deleted: string
  cortes_deleted: number
}
