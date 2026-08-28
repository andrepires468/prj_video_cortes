export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export type MediaFolder = 'downloads' | 'cortes'

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
}

export interface FileInfo {
  name: string
  size: number
  mtime: string
  thumb?: string | null
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
