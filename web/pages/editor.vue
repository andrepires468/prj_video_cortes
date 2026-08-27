<script setup lang="ts">
import type { CutJobInfo } from '~/types/downloads'

const route = useRoute()
const router = useRouter()
const {
  mediaStreamUrl,
  getMediaInfo,
  startCuts,
  pollCutJob,
} = useDownloads()

const filename = computed(() => {
  const raw = route.query.file
  return typeof raw === 'string' ? raw : ''
})

const videoRef = ref<HTMLVideoElement | null>(null)
const duration = ref(0)
const currentTime = ref(0)
const playing = ref(false)
const volume = ref(0.6)
const muted = ref(false)
const loading = ref(true)
const errorMsg = ref('')
const markers = ref<number[]>([])
const selectedMarkerIndex = ref<number | null>(null)
const exporting = ref(false)
const exportJob = ref<CutJobInfo | null>(null)
const successMsg = ref('')

const MAX_MARKERS = 2

const streamUrl = computed(() =>
  filename.value ? mediaStreamUrl(filename.value) : '',
)

const sortedMarkerTimes = computed(() =>
  [...markers.value].sort((a, b) => a - b),
)

const canSave = computed(
  () => markers.value.length === MAX_MARKERS && !loading.value && !exporting.value,
)

const selectionRange = computed(() => {
  if (sortedMarkerTimes.value.length !== 2) return null
  const [start, end] = sortedMarkerTimes.value
  return { start, end }
})

function formatClock(seconds: number): string {
  const total = Math.max(0, seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = Math.floor(total % 60)
  const ms = Math.floor((total % 1) * 10)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${ms}`
  }
  return `${m}:${String(s).padStart(2, '0')}.${ms}`
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  markers.value = []
  selectedMarkerIndex.value = null

  if (!filename.value) {
    errorMsg.value = 'Nenhum arquivo selecionado.'
    loading.value = false
    return
  }

  try {
    const info = await getMediaInfo(filename.value)
    duration.value = info.duration
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    errorMsg.value = e?.data?.detail || e?.message || 'Falha ao carregar o vídeo.'
  } finally {
    loading.value = false
  }
}

function onLoadedMetadata() {
  const el = videoRef.value
  if (!el) return
  if (el.duration && Number.isFinite(el.duration)) {
    duration.value = el.duration
  }
  applyVolume()
}

function applyVolume() {
  const el = videoRef.value
  if (!el) return
  el.volume = volume.value
  el.muted = muted.value
}

function onVolumeInput(value: number | number[]) {
  const next = Array.isArray(value) ? value[0] : value
  volume.value = Math.min(1, Math.max(0, Number(next) || 0))
  if (volume.value > 0 && muted.value) {
    muted.value = false
  }
  applyVolume()
}

function toggleMute() {
  if (!muted.value && volume.value === 0) {
    volume.value = 0.6
    muted.value = false
  } else {
    muted.value = !muted.value
  }
  applyVolume()
}

const volumeIcon = computed(() => {
  if (muted.value || volume.value === 0) return 'mdi-volume-off'
  if (volume.value < 0.4) return 'mdi-volume-low'
  if (volume.value < 0.75) return 'mdi-volume-medium'
  return 'mdi-volume-high'
})

function onTimeUpdate() {
  const el = videoRef.value
  if (el) currentTime.value = el.currentTime
}

function onPlay() {
  playing.value = true
}

function onPause() {
  playing.value = false
}

function togglePlay() {
  const el = videoRef.value
  if (!el) return
  if (el.paused) el.play()
  else el.pause()
}

function seekTo(time: number) {
  const el = videoRef.value
  if (!el) return
  const t = Math.min(duration.value || el.duration || 0, Math.max(0, time))
  el.currentTime = t
  currentTime.value = t
}

function skip(delta: number) {
  seekTo(currentTime.value + delta)
}

function addMarkerAt(time: number) {
  if (!duration.value) return
  if (markers.value.length >= MAX_MARKERS) {
    errorMsg.value = 'Só é possível ter 2 linhas de corte. Remova uma para reposicionar.'
    return
  }
  const t = Math.min(duration.value - 0.05, Math.max(0.05, time))
  const exists = markers.value.some((m) => Math.abs(m - t) < 0.05)
  if (exists) return
  errorMsg.value = ''
  markers.value = [...markers.value, t]
  selectedMarkerIndex.value = markers.value.length - 1
}

function addMarkerAtPlayhead() {
  addMarkerAt(currentTime.value)
}

function removeSelectedMarker() {
  if (selectedMarkerIndex.value === null) return
  markers.value = markers.value.filter((_, i) => i !== selectedMarkerIndex.value)
  selectedMarkerIndex.value = null
}

function clearMarkers() {
  markers.value = []
  selectedMarkerIndex.value = null
}

function selectMarker(index: number) {
  selectedMarkerIndex.value = index
  seekTo(markers.value[index])
}

async function exportCuts() {
  if (!filename.value || markers.value.length !== MAX_MARKERS || !selectionRange.value) {
    errorMsg.value = 'Posicione exatamente 2 linhas de corte para salvar o trecho entre elas.'
    return
  }

  exporting.value = true
  errorMsg.value = ''
  successMsg.value = ''
  exportJob.value = null

  try {
    const { start, end } = selectionRange.value
    const created = await startCuts(filename.value, markers.value, [{ start, end }])
    exportJob.value = created
    const finalJob = await pollCutJob(created.id, (job) => {
      exportJob.value = job
    })
    if (finalJob.status === 'error') {
      errorMsg.value = finalJob.error || finalJob.message || 'Falha ao exportar.'
    } else {
      successMsg.value = `Arquivo salvo em data/cortes: ${finalJob.outputs.join(', ')}`
    }
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    errorMsg.value = e?.data?.detail || e?.message || 'Não foi possível exportar os cortes.'
  } finally {
    exporting.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  const tag = target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) {
    return
  }
  if (loading.value || !filename.value) return

  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    skip(-5)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    skip(5)
  } else if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault()
    togglePlay()
  }
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})

watch(filename, load)

function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="editor-page">
    <v-container fluid class="editor-container">
      <div class="editor-toolbar">
        <v-btn variant="text" prepend-icon="mdi-arrow-left" @click="goHome">
          Voltar
        </v-btn>
        <div class="editor-title">
          <h1>Editor de cortes</h1>
          <p v-if="filename" class="filename" :title="filename">{{ filename }}</p>
        </div>
        <v-spacer />
        <v-btn
          color="primary"
          prepend-icon="mdi-content-save"
          :loading="exporting"
          :disabled="!canSave"
          @click="exportCuts"
        >
          Salvar trecho
        </v-btn>
      </div>

      <v-alert
        v-if="errorMsg"
        type="error"
        variant="tonal"
        density="comfortable"
        class="mb-3"
        closable
        @click:close="errorMsg = ''"
      >
        {{ errorMsg }}
      </v-alert>

      <v-alert
        v-if="successMsg"
        type="success"
        variant="tonal"
        density="comfortable"
        class="mb-3"
        closable
        @click:close="successMsg = ''"
      >
        {{ successMsg }}
        <div class="mt-2">
          <NuxtLink to="/">Ver na lista de arquivos</NuxtLink>
        </div>
      </v-alert>

      <v-progress-linear
        v-if="exporting"
        class="mb-3"
        :model-value="exportJob?.progress || 0"
        color="primary"
        height="6"
        rounded
      />

      <div v-if="loading" class="editor-loading">
        <v-progress-circular indeterminate color="primary" />
        <span>Carregando vídeo…</span>
      </div>

      <template v-else-if="filename && streamUrl">
        <v-card class="preview-card" variant="flat">
          <div class="preview-stage">
            <video
              ref="videoRef"
              class="preview-video"
              :src="streamUrl"
              preload="metadata"
              @loadedmetadata="onLoadedMetadata"
              @timeupdate="onTimeUpdate"
              @play="onPlay"
              @pause="onPause"
              @click="togglePlay"
            />
          </div>

          <div class="transport">
            <v-btn icon variant="text" @click="skip(-5)">
              <v-icon>mdi-rewind-5</v-icon>
            </v-btn>
            <v-btn icon variant="tonal" color="primary" size="large" @click="togglePlay">
              <v-icon>{{ playing ? 'mdi-pause' : 'mdi-play' }}</v-icon>
            </v-btn>
            <v-btn icon variant="text" @click="skip(5)">
              <v-icon>mdi-fast-forward-5</v-icon>
            </v-btn>

            <span class="timecode">
              {{ formatClock(currentTime) }}
              <span class="timecode-sep">/</span>
              {{ formatClock(duration) }}
            </span>

            <div class="volume-control">
              <v-btn icon variant="text" size="small" @click="toggleMute">
                <v-icon>{{ volumeIcon }}</v-icon>
              </v-btn>
              <v-slider
                class="volume-slider"
                :model-value="muted ? 0 : volume"
                :min="0"
                :max="1"
                :step="0.01"
                hide-details
                density="compact"
                color="primary"
                thumb-size="14"
                track-size="3"
                @update:model-value="onVolumeInput"
              />
            </div>

            <v-spacer />

            <v-btn
              variant="tonal"
              color="error"
              prepend-icon="mdi-scissors-cutting"
              :disabled="markers.length >= MAX_MARKERS"
              @click="addMarkerAtPlayhead"
            >
              Linha de corte ({{ markers.length }}/{{ MAX_MARKERS }})
            </v-btn>
            <v-btn
              variant="text"
              :disabled="selectedMarkerIndex === null"
              prepend-icon="mdi-delete"
              @click="removeSelectedMarker"
            >
              Remover
            </v-btn>
            <v-btn
              variant="text"
              :disabled="markers.length === 0"
              @click="clearMarkers"
            >
              Limpar
            </v-btn>
          </div>
        </v-card>

        <v-card class="timeline-card" variant="outlined">
          <v-card-title class="timeline-card-title">
            Linha de edição
            <span class="marker-count">
              <template v-if="selectionRange">
                Trecho:
                {{ formatClock(selectionRange.start) }}
                →
                {{ formatClock(selectionRange.end) }}
              </template>
              <template v-else>
                {{ markers.length }}/{{ MAX_MARKERS }} linhas · posicione 2 para salvar
              </template>
            </span>
          </v-card-title>
          <v-card-text>
            <EditorVideoTimeline
              :duration="duration"
              :current-time="currentTime"
              :markers="markers"
              :selected-marker-index="selectedMarkerIndex"
              :max-markers="MAX_MARKERS"
              @seek="seekTo"
              @select-marker="selectMarker"
              @add-marker="addMarkerAt"
            />
          </v-card-text>
        </v-card>
      </template>
    </v-container>
  </div>
</template>

<style scoped>
.editor-page {
  min-height: 100%;
  background: #eceff1;
}

.editor-container {
  max-width: 1200px;
  padding-top: 16px;
  padding-bottom: 32px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.editor-title h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 500;
}

.filename {
  margin: 2px 0 0;
  font-size: 0.8rem;
  color: #666;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-card {
  background: #121212;
  color: #fff;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
}

.preview-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  min-height: 320px;
  max-height: 52vh;
}

.preview-video {
  display: block;
  width: 100%;
  max-height: 52vh;
  height: auto;
  cursor: pointer;
  background: #000;
}

.transport {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  flex-wrap: wrap;
  background: #1a1a1a;
}

.timecode {
  margin-left: 8px;
  font-variant-numeric: tabular-nums;
  font-size: 0.95rem;
  color: #e0e0e0;
}

.timecode-sep {
  opacity: 0.5;
  margin: 0 4px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 140px;
  max-width: 180px;
  margin-left: 8px;
}

.volume-slider {
  flex: 1;
  margin-inline: 0;
}

.timeline-card {
  background: #fff;
}

.timeline-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.marker-count {
  font-size: 0.85rem;
  font-weight: 400;
  color: #666;
}

.editor-loading {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 48px;
  justify-content: center;
  color: #666;
}

.mb-3 {
  margin-bottom: 12px;
}

.mt-2 {
  margin-top: 8px;
}
</style>
