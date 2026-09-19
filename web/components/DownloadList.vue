<script setup lang="ts">
import type { FileInfo } from '~/types/downloads'
import type { PaginationMeta } from '~/types/pagination'
import { DEFAULT_PER_PAGE } from '~/types/pagination'

const { listFiles, listCortes, mediaThumbUrl, mediaStreamUrl, deleteMedia } = useDownloads()
const { setDownloadCount } = useLibraryStats()
const swal = useSwal()

const files = ref<FileInfo[]>([])
const pagination = ref<PaginationMeta>({
  page: 1,
  per_page: DEFAULT_PER_PAGE,
  total: 0,
  pages: 1,
  has_next: false,
  has_prev: false,
})
const loading = ref(true)
const errorMsg = ref('')
const removing = ref<string | null>(null)
const playerOpen = ref(false)
const playingFile = ref<FileInfo | null>(null)
const playingSrc = ref('')
const thumbFallback = ref<Set<string>>(new Set())
const thumbBroken = ref<Set<string>>(new Set())

function thumbSrc(file: FileInfo): string | null {
  if (thumbBroken.value.has(file.name)) return null
  if (thumbFallback.value.has(file.name) || !file.thumb_url) {
    if (!file.thumb) return null
    return mediaThumbUrl(file.name)
  }
  return file.thumb_url
}

function onThumbError(name: string) {
  if (!thumbFallback.value.has(name)) {
    const next = new Set(thumbFallback.value)
    next.add(name)
    thumbFallback.value = next
    return
  }
  if (thumbBroken.value.has(name)) return
  const next = new Set(thumbBroken.value)
  next.add(name)
  thumbBroken.value = next
}

function playFile(file: FileInfo) {
  playingFile.value = file
  playerOpen.value = true
}

async function resolvePlayingSrc() {
  const file = playingFile.value
  if (!playerOpen.value || !file) {
    playingSrc.value = ''
    return
  }
  playingSrc.value = file.play_url || mediaStreamUrl(file.name, 'downloads')
}

function onPlayerError() {
  const file = playingFile.value
  if (!file) return
  const fallback = mediaStreamUrl(file.name, 'downloads')
  if (playingSrc.value !== fallback) {
    playingSrc.value = fallback
  }
}

watch([playingFile, playerOpen], resolvePlayingSrc)

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function editorLink(name: string): string {
  return `/editor?file=${encodeURIComponent(name)}`
}

async function load(page = pagination.value.page) {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await listFiles(page, DEFAULT_PER_PAGE)
    files.value = res.files
    pagination.value = res.pagination
    thumbFallback.value = new Set()
    thumbBroken.value = new Set()
    setDownloadCount(res.pagination.total)
  } catch (err: unknown) {
    const e = err as { message?: string }
    errorMsg.value = e?.message || 'Falha ao listar arquivos.'
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await load(1)
}

function onPageChange(page: number) {
  load(page)
}

async function removeFile(file: FileInfo) {
  if (removing.value) return
  let cortesCount = 0
  let cortesUnknown = false
  try {
    const cortes = await withSwalLoading(
      'Verificando cortes…',
      'Consultando os cortes deste vídeo.',
      () => listCortes(file.name),
    )
    cortesCount = cortes.length
  } catch {
    cortesUnknown = true
  }

  const confirmed = await confirmDangerousDelete({
    filename: file.name,
    kind: 'video',
    cortesCount,
    cortesUnknown,
  })
  if (!confirmed) return

  removing.value = file.name
  try {
    if (playingFile.value?.name === file.name) {
      playerOpen.value = false
      playingFile.value = null
    }
    await deleteMedia(file.name, 'downloads')
    const nextPage =
      files.value.length === 1 && pagination.value.page > 1
        ? pagination.value.page - 1
        : pagination.value.page
    await load(nextPage)
    await swal.fire({
      icon: 'success',
      title: 'Vídeo removido',
      timer: 1800,
      showConfirmButton: false,
      theme: swalTheme(),
    })
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    await swal.fire({
      icon: 'error',
      title: 'Não foi possível remover',
      text: e?.data?.detail || e?.message || 'Falha ao excluir o vídeo.',
      theme: swalTheme(),
    })
  } finally {
    removing.value = null
  }
}

onMounted(() => {
  refresh()
})

defineExpose({ refresh })
</script>

<template>
  <section class="page-section">
    <div class="list-toolbar">
      <h2>Arquivos baixados</h2>
      <v-btn
        class="refresh-btn"
        variant="outlined"
        rounded="xl"
        :disabled="loading"
        prepend-icon="mdi-refresh"
        @click="refresh"
      >
        Atualizar
      </v-btn>
    </div>

    <v-alert
      v-if="errorMsg"
      type="error"
      variant="tonal"
      density="comfortable"
      class="mb-3"
    >
      {{ errorMsg }}
    </v-alert>

    <div v-if="loading && files.length === 0" class="grid-loading">
      <span class="app-spinner" role="status" aria-label="Carregando arquivos" />
    </div>

    <v-alert
      v-else-if="!loading && files.length === 0"
      type="info"
      variant="tonal"
      density="comfortable"
    >
      Nenhum download na biblioteca.
    </v-alert>

    <div v-else class="files-grid">
      <article
        v-for="file in files"
        :key="file.name"
        class="file-card"
      >
        <div
          class="thumb-wrap"
          role="button"
          tabindex="0"
          :aria-label="`Assistir ${file.name}`"
          @click="playFile(file)"
          @keyup.enter="playFile(file)"
        >
          <img
            v-if="thumbSrc(file)"
            class="thumb-img"
            :src="thumbSrc(file)!"
            :alt="file.name"
            loading="lazy"
            @error="onThumbError(file.name)"
          >
          <div v-else class="thumb-placeholder">
            <v-icon size="48" color="grey">mdi-video-outline</v-icon>
          </div>
          <div class="thumb-play" aria-hidden="true">
            <span class="thumb-play-icon">
              <v-icon size="26">mdi-play</v-icon>
            </span>
          </div>
        </div>

        <div class="file-meta">
          <p class="file-name" :title="file.name">{{ file.name }}</p>
          <p class="file-sub">
            <span class="file-size">{{ formatSize(file.size) }}</span>
            <span>{{ formatDate(file.mtime) }}</span>
          </p>
        </div>

        <div class="file-actions">
          <v-btn
            class="action-cut"
            size="small"
            variant="outlined"
            rounded="lg"
            prepend-icon="mdi-content-cut"
            :to="editorLink(file.name)"
            :disabled="removing === file.name"
          >
            Cortar
          </v-btn>
          <v-btn
            class="action-remove"
            size="small"
            variant="outlined"
            rounded="lg"
            prepend-icon="mdi-delete-outline"
            :loading="removing === file.name"
            :disabled="!!removing"
            @click="removeFile(file)"
          >
            Remover
          </v-btn>
        </div>
      </article>
    </div>

    <Pagination
      :pagination="pagination"
      :disabled="loading"
      @update:page="onPageChange"
    />

    <VideoPlayerModal
      v-model="playerOpen"
      :src="playingSrc"
      :title="playingFile?.name ?? ''"
      folder="downloads"
      @error="onPlayerError"
    />
  </section>
</template>

<style scoped>
.mb-3 {
  margin-bottom: 12px;
}
</style>
