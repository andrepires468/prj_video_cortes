import type { CutJobInfo, DeleteMediaResponse, FileInfo, FileListResponse, JobInfo, MediaFolder, MediaInfo } from '~/types/downloads'
import { DEFAULT_PER_PAGE } from '~/types/pagination'

export function useDownloads() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase as string

  async function startDownload(url: string): Promise<JobInfo> {
    return await $fetch<JobInfo>(`${base}/downloads`, {
      method: 'POST',
      body: { url },
    })
  }

  async function getJob(id: string): Promise<JobInfo> {
    return await $fetch<JobInfo>(`${base}/downloads/jobs/${id}`)
  }

  async function cancelDownload(id: string): Promise<JobInfo> {
    return await $fetch<JobInfo>(`${base}/downloads/jobs/${id}/cancel`, {
      method: 'POST',
    })
  }

  async function listFiles(page = 1, perPage = DEFAULT_PER_PAGE): Promise<FileListResponse> {
    return await $fetch<FileListResponse>(`${base}/downloads/files`, {
      query: { page, per_page: perPage },
    })
  }

  async function listCortes(downloadId: string): Promise<FileInfo[]> {
    const res = await $fetch<{ files: FileInfo[] }>(`${base}/editor/cortes`, {
      query: { id: downloadId },
    })
    return res.files
  }

  async function pollJob(
    id: string,
    onUpdate: (job: JobInfo) => void,
    intervalMs = 1000,
  ): Promise<JobInfo> {
    return await new Promise((resolve, reject) => {
      const tick = async () => {
        try {
          const job = await getJob(id)
          onUpdate(job)
          if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') {
            resolve(job)
            return
          }
          setTimeout(tick, intervalMs)
        } catch (err) {
          reject(err)
        }
      }
      tick()
    })
  }

  function mediaQuery(id: string, folder: MediaFolder, extra?: Record<string, string>) {
    const params = new URLSearchParams({ id, folder, ...extra })
    return params.toString()
  }

  function mediaStreamUrl(
    id: string,
    folder: MediaFolder = 'downloads',
    download = false,
  ): string {
    const extra = download ? { download: '1' } : undefined
    return `${base}/media/stream?${mediaQuery(id, folder, extra)}`
  }

  function mediaThumbUrl(id: string, folder: MediaFolder = 'downloads'): string {
    return `${base}/media/thumb?${mediaQuery(id, folder)}`
  }

  async function getPlaybackUrl(
    id: string,
    folder: MediaFolder = 'downloads',
    download = false,
  ): Promise<string> {
    try {
      const res = await $fetch<{ url: string }>(`${base}/media/playback`, {
        query: { id, folder, download: download ? '1' : '0' },
      })
      if (res?.url) return res.url
    } catch {
      /* cai no stream autenticado */
    }
    return mediaStreamUrl(id, folder, download)
  }

  async function getMediaInfo(
    id: string,
    folder: MediaFolder = 'downloads',
  ): Promise<MediaInfo> {
    return await $fetch<MediaInfo>(`${base}/media/info`, {
      query: { id, folder },
    })
  }

  async function deleteMedia(
    id: string,
    folder: MediaFolder = 'downloads',
  ): Promise<DeleteMediaResponse> {
    return await $fetch<DeleteMediaResponse>(`${base}/media`, {
      method: 'DELETE',
      query: { id, folder },
    })
  }

  async function startCuts(
    downloadId: string,
    markers: number[],
    segments?: { start: number; end: number }[],
    speed = 1,
    sourceCorteId?: string,
  ): Promise<CutJobInfo> {
    return await $fetch<CutJobInfo>(`${base}/editor/cuts`, {
      method: 'POST',
      body: {
        download_id: downloadId,
        markers,
        segments,
        speed,
        source_corte_id: sourceCorteId || undefined,
      },
    })
  }

  async function getCutJob(id: string): Promise<CutJobInfo> {
    return await $fetch<CutJobInfo>(`${base}/editor/cuts/${id}`)
  }

  async function pollCutJob(
    id: string,
    onUpdate: (job: CutJobInfo) => void,
    intervalMs = 800,
  ): Promise<CutJobInfo> {
    return await new Promise((resolve, reject) => {
      const tick = async () => {
        try {
          const job = await getCutJob(id)
          onUpdate(job)
          if (job.status === 'done' || job.status === 'error') {
            resolve(job)
            return
          }
          setTimeout(tick, intervalMs)
        } catch (err) {
          reject(err)
        }
      }
      tick()
    })
  }

  return {
    startDownload,
    getJob,
    cancelDownload,
    listFiles,
    listCortes,
    pollJob,
    mediaStreamUrl,
    mediaThumbUrl,
    getPlaybackUrl,
    getMediaInfo,
    deleteMedia,
    startCuts,
    getCutJob,
    pollCutJob,
  }
}
