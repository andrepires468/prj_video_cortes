import type { CutJobInfo, DeleteMediaResponse, FileInfo, JobInfo, MediaFolder, MediaInfo } from '~/types/downloads'

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

  async function listFiles(): Promise<FileInfo[]> {
    const res = await $fetch<{ files: FileInfo[] }>(`${base}/downloads/files`)
    return res.files
  }

  async function listCortes(filename: string): Promise<FileInfo[]> {
    const res = await $fetch<{ files: FileInfo[] }>(`${base}/editor/cortes`, {
      query: { filename },
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

  function mediaQuery(filename: string, folder: MediaFolder, extra?: Record<string, string>) {
    const params = new URLSearchParams({ name: filename, folder, ...extra })
    return params.toString()
  }

  function mediaStreamUrl(
    filename: string,
    folder: MediaFolder = 'downloads',
    download = false,
  ): string {
    const extra = download ? { download: '1' } : undefined
    return `${base}/media/stream?${mediaQuery(filename, folder, extra)}`
  }

  function mediaThumbUrl(filename: string, folder: MediaFolder = 'downloads'): string {
    return `${base}/media/thumb?${mediaQuery(filename, folder)}`
  }

  async function getMediaInfo(
    filename: string,
    folder: MediaFolder = 'downloads',
  ): Promise<MediaInfo> {
    return await $fetch<MediaInfo>(`${base}/media/info`, {
      query: { name: filename, folder },
    })
  }

  async function deleteMedia(
    filename: string,
    folder: MediaFolder = 'downloads',
  ): Promise<DeleteMediaResponse> {
    return await $fetch<DeleteMediaResponse>(`${base}/media`, {
      method: 'DELETE',
      query: { name: filename, folder },
    })
  }

  async function startCuts(
    filename: string,
    markers: number[],
    segments?: { start: number; end: number }[],
    speed = 1,
    sourceFilename?: string,
  ): Promise<CutJobInfo> {
    return await $fetch<CutJobInfo>(`${base}/editor/cuts`, {
      method: 'POST',
      body: {
        filename,
        markers,
        segments,
        speed,
        source_filename: sourceFilename || undefined,
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
    listFiles,
    listCortes,
    pollJob,
    mediaStreamUrl,
    mediaThumbUrl,
    getMediaInfo,
    deleteMedia,
    startCuts,
    getCutJob,
    pollCutJob,
  }
}
