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
      <span class="app-spinner" role="status" aria-label="Carregando cortes" />
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
      <article
        v-for="file in files"
        :key="file.name"
        class="file-card"
        :class="{ 'file-card--active': isEditing(file.name) }"
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
            prepend-icon="mdi-play"
            :disabled="removing === file.name"
            @click="playFile(file)"
          >
            Assistir
          </v-btn>
          <v-btn
            class="action-cut"
            size="small"
            :variant="isEditing(file.name) ? 'flat' : 'outlined'"
            :color="isEditing(file.name) ? 'primary' : undefined"
            rounded="lg"
            prepend-icon="mdi-pencil"
            :to="editLink(file.name)"
            :disabled="removing === file.name"
          >
            {{ isEditing(file.name) ? 'Editando' : 'Editar' }}
          </v-btn>
          <v-btn
            class="action-cut"
            size="small"
            variant="outlined"
            rounded="lg"
            prepend-icon="mdi-download"
            :href="downloadHref(file)"
            :disabled="removing === file.name"
          >
            Baixar
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
.cuts-section {
  margin-top: 28px;
}

.mb-3 {
  margin-bottom: 12px;
}
</style>
