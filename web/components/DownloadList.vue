<script setup lang="ts">
import type { FileInfo } from '~/types/downloads'

const { listFiles, mediaThumbUrl } = useDownloads()

const files = ref<FileInfo[]>([])
const loading = ref(false)
const errorMsg = ref('')

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

function editorLink(name: string): string {
  return `/editor?file=${encodeURIComponent(name)}`
}

function thumbSrc(file: FileInfo): string | null {
  if (!file.thumb) return null
  return mediaThumbUrl(file.name)
}

async function refresh() {
  loading.value = true
  errorMsg.value = ''
  try {
    files.value = await listFiles()
  } catch (err: unknown) {
    const e = err as { message?: string }
    errorMsg.value = e?.message || 'Falha ao listar arquivos.'
  } finally {
    loading.value = false
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
      Nenhum arquivo na pasta de downloads.
    </v-alert>

    <div v-else class="files-grid">
      <v-card
        v-for="file in files"
        :key="file.name"
        class="file-card"
        variant="outlined"
      >
        <div class="thumb-wrap">
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
            prepend-icon="mdi-content-cut"
            :to="editorLink(file.name)"
            block
          >
            Cortar
          </v-btn>
        </v-card-actions>
      </v-card>
    </div>
  </section>
</template>

<style scoped>
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
  background: #fff;
}

.thumb-wrap {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #1e1e1e;
  overflow: hidden;
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
  background: #eceff1;
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
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.file-sub {
  margin: 0;
  font-size: 0.75rem;
  color: #666;
}

.file-dot {
  margin: 0 4px;
}

.file-actions {
  padding: 8px 12px 12px;
  margin-top: auto;
}
</style>
