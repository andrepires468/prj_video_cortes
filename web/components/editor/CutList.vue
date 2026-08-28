<script setup lang="ts">
import type { FileInfo } from '~/types/downloads'

const props = defineProps<{
  filename: string
  activeCut?: string
}>()

const emit = defineEmits<{
  play: []
}>()

const { listCortes, mediaThumbUrl, mediaStreamUrl, deleteMedia } = useDownloads()
const swal = useSwal()

const files = ref<FileInfo[]>([])
const loading = ref(false)
const errorMsg = ref('')
const brokenThumbs = ref<Set<string>>(new Set())
const playerOpen = ref(false)
const playingFile = ref<FileInfo | null>(null)
const removing = ref<string | null>(null)

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR')
  } catch {
    return iso
  }
}

function thumbSrc(file: FileInfo): string {
  return mediaThumbUrl(file.name, 'cortes')
}

function showThumb(file: FileInfo): boolean {
  return !brokenThumbs.value.has(file.name)
}

function onThumbError(name: string) {
  const next = new Set(brokenThumbs.value)
  next.add(name)
  brokenThumbs.value = next
}

function playFile(file: FileInfo) {
  emit('play')
  playingFile.value = file
  playerOpen.value = true
}

function downloadHref(file: FileInfo): string {
  return mediaStreamUrl(file.name, 'cortes', true)
}

function editLink(cutName: string) {
  return {
    path: '/editor',
    query: {
      file: props.filename,
      cut: cutName,
    },
  }
}

function isEditing(cutName: string) {
  return Boolean(props.activeCut) && props.activeCut === cutName
}

const playingSrc = computed(() =>
  playingFile.value ? mediaStreamUrl(playingFile.value.name, 'cortes') : '',
)

async function refresh() {
  if (!props.filename) {
    files.value = []
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    files.value = await listCortes(props.filename)
    brokenThumbs.value = new Set()
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    errorMsg.value = e?.data?.detail || e?.message || 'Falha ao listar cortes.'
  } finally {
    loading.value = false
  }
}

watch(() => props.filename, refresh, { immediate: true })

async function removeFile(file: FileInfo) {
  if (removing.value) return

  const confirmed = await confirmDangerousDelete({
    filename: file.name,
    kind: 'corte',
  })
  if (!confirmed) return

  removing.value = file.name
  try {
    if (playingFile.value?.name === file.name) {
      playerOpen.value = false
      playingFile.value = null
    }
    await deleteMedia(file.name, 'cortes')
    await refresh()
    await swal.fire({
      icon: 'success',
      title: 'Corte removido',
      timer: 1800,
      showConfirmButton: false,
      theme: swalTheme(),
    })
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    await swal.fire({
      icon: 'error',
      title: 'Não foi possível remover',
      text: e?.data?.detail || e?.message || 'Falha ao excluir o corte.',
      theme: swalTheme(),
    })
  } finally {
    removing.value = null
  }
}

defineExpose({ refresh })
</script>

<template>
  <section class="page-section cuts-section">
    <div class="list-toolbar">
      <h2>Cortes deste vídeo</h2>
      <v-btn
        variant="outlined"
        :loading="loading"
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
      <v-progress-circular indeterminate color="primary" />
    </div>

    <v-alert
      v-else-if="!loading && files.length === 0"
      type="info"
      variant="tonal"
      density="comfortable"
    >
      Nenhum corte deste vídeo ainda. Salve um trecho para vê-lo aqui.
    </v-alert>

    <div v-else class="files-grid">
      <v-card
        v-for="file in files"
        :key="file.name"
        class="file-card"
        :class="{ 'file-card--active': isEditing(file.name) }"
        variant="outlined"
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
            v-if="showThumb(file)"
            class="thumb-img"
            :src="thumbSrc(file)"
            :alt="file.name"
            loading="lazy"
            @error="onThumbError(file.name)"
          >
          <div v-else class="thumb-placeholder">
            <v-icon size="48" color="grey">mdi-video-outline</v-icon>
          </div>
          <div class="thumb-play" aria-hidden="true">
            <v-icon size="52">mdi-play-circle</v-icon>
          </div>
        </div>

        <v-card-text class="file-meta">
          <p class="file-name" :title="file.name">{{ file.name }}</p>
          <p class="file-sub">
            <span class="file-size">{{ formatSize(file.size) }}</span>
            <span class="file-dot">·</span>
            <span>{{ formatDate(file.mtime) }}</span>
          </p>
        </v-card-text>

        <v-card-actions class="file-actions">
          <v-btn
            size="small"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-play"
            :disabled="removing === file.name"
            block
            @click="playFile(file)"
          >
            Assistir
          </v-btn>
          <v-btn
            size="small"
            color="primary"
            :variant="isEditing(file.name) ? 'flat' : 'tonal'"
            prepend-icon="mdi-pencil"
            :to="editLink(file.name)"
            :disabled="removing === file.name"
            block
          >
            {{ isEditing(file.name) ? 'Editando' : 'Editar' }}
          </v-btn>
          <v-btn
            size="small"
            variant="text"
            prepend-icon="mdi-download"
            :href="downloadHref(file)"
            :disabled="removing === file.name"
            block
          >
            Baixar
          </v-btn>
          <v-btn
            size="small"
            color="error"
            variant="tonal"
            prepend-icon="mdi-delete-outline"
            :loading="removing === file.name"
            :disabled="!!removing"
            block
            @click="removeFile(file)"
          >
            Remover
          </v-btn>
        </v-card-actions>
      </v-card>
    </div>

    <VideoPlayerModal
      v-model="playerOpen"
      :src="playingSrc"
      :title="playingFile?.name ?? ''"
    />
  </section>
</template>

<style scoped>
.cuts-section {
  margin-top: 24px;
}

.mb-3 {
  margin-bottom: 12px;
}

.grid-loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.file-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-card);
}

.file-card--active {
  outline: 2px solid rgb(var(--v-theme-primary));
}

.thumb-wrap {
  position: relative;
  aspect-ratio: 16 / 9;
  background: var(--bg-thumb);
  overflow: hidden;
  cursor: pointer;
}

.thumb-play {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: rgb(0 0 0 / 28%);
  opacity: 0;
  transition: opacity 0.15s ease;
  pointer-events: none;
}

.thumb-wrap:hover .thumb-play,
.thumb-wrap:focus .thumb-play,
.thumb-wrap:focus-visible .thumb-play {
  opacity: 1;
}

.thumb-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: var(--bg-thumb-placeholder);
}

.file-meta {
  padding-top: 12px;
  padding-bottom: 4px;
}

.file-name {
  margin: 0 0 6px;
  font-size: 0.9rem;
  font-weight: 500;
  line-height: 1.3;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.file-sub {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.file-dot {
  margin: 0 4px;
}

.file-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px 12px;
  margin-top: auto;
}
</style>
