<script setup lang="ts">
import type { FileInfo } from '~/types/downloads'

const { listFiles, listCortes, mediaThumbUrl, mediaStreamUrl, deleteMedia } = useDownloads()
const { setDownloadCount } = useLibraryStats()
const swal = useSwal()

const files = ref<FileInfo[]>([])
const loading = ref(true)
const errorMsg = ref('')
const removing = ref<string | null>(null)
const playerOpen = ref(false)
const playingFile = ref<FileInfo | null>(null)

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

function thumbSrc(file: FileInfo): string | null {
  if (!file.thumb) return null
  return mediaThumbUrl(file.name)
}

function playFile(file: FileInfo) {
  playingFile.value = file
  playerOpen.value = true
}

const playingSrc = computed(() =>
  playingFile.value ? mediaStreamUrl(playingFile.value.name, 'downloads') : '',
)

async function refresh() {
  loading.value = true
  errorMsg.value = ''
  try {
    files.value = await listFiles()
    setDownloadCount(files.value.length)
  } catch (err: unknown) {
    const e = err as { message?: string }
    errorMsg.value = e?.message || 'Falha ao listar arquivos.'
  } finally {
    loading.value = false
  }
}

async function removeFile(file: FileInfo) {
  if (removing.value) return
  let cortesCount = 0
  let cortesUnknown = false
  try {
    const cortes = await listCortes(file.name)
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
    await refresh()
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
      Nenhum arquivo na pasta de downloads.
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

    <VideoPlayerModal
      v-model="playerOpen"
      :src="playingSrc"
      :title="playingFile?.name ?? ''"
    />
  </section>
</template>

<style scoped>
.mb-3 {
  margin-bottom: 12px;
}
</style>
