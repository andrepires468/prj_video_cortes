<script setup lang="ts">
import type { CutJobInfo } from '~/types/downloads'

const route = useRoute()
const router = useRouter()
const {
  mediaStreamUrl,
  getMediaInfo,
  getPlaybackUrl,
  startCuts,
  pollCutJob,
} = useDownloads()

const downloadId = computed(() => {
  const raw = route.query.id
  return typeof raw === 'string' ? raw : ''
})

const cutId = computed(() => {
  const raw = route.query.cut
  return typeof raw === 'string' ? raw : ''
})

const editingCut = computed(() => Boolean(cutId.value))

const mediaFolder = computed(() => (editingCut.value ? 'cortes' : 'downloads'))

const mediaId = computed(() => (editingCut.value ? cutId.value : downloadId.value))

const displayName = ref('')
const cutDisplayName = ref('')

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
const cutListRef = ref<{ refresh: () => Promise<void> } | null>(null)

const MAX_MARKERS = 2
const SPEED_MIN = 0.25
const SPEED_MAX = 2
const SPEED_STEP = 0.1
const SPEED_PRESETS = [0.5, 0.75, 1, 1.25, 1.5, 2]
const speed = ref(1)
const speedText = ref('1.0')

const streamUrl = ref('')

const sortedMarkerTimes = computed(() =>
  [...markers.value].sort((a, b) => a - b),
)

const canSave = computed(() => {
  if (loading.value || exporting.value || !downloadId.value || duration.value <= 0) {
    return false
  }
  const count = markers.value.length
  return count === 0 || count === MAX_MARKERS
})

const selectionRange = computed(() => {
  if (sortedMarkerTimes.value.length !== 2) return null
  const [start, end] = sortedMarkerTimes.value
  return { start, end }
})

const outputDuration = computed(() => {
  if (!duration.value) return null
  if (selectionRange.value) {
    return (selectionRange.value.end - selectionRange.value.start) / speed.value
  }
  if (markers.value.length === 0) {
    return duration.value / speed.value
  }
  return null
})

function formatSpeed(value: number): string {
  return Number.isInteger(value * 10) ? value.toFixed(1) : value.toFixed(2)
}

function clampSpeed(value: number): number {
  const rounded = Math.round(value * 100) / 100
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, rounded))
}

function applyPlaybackRate() {
  const el = videoRef.value
  if (!el) return
  el.playbackRate = speed.value
}

function commitSpeed(raw: string | number) {
  const parsed = typeof raw === 'number' ? raw : Number.parseFloat(String(raw).replace(',', '.'))
  if (!Number.isFinite(parsed)) {
    speedText.value = formatSpeed(speed.value)
    return
  }
  speed.value = clampSpeed(parsed)
  speedText.value = formatSpeed(speed.value)
  applyPlaybackRate()
}

function nudgeSpeed(delta: number) {
  commitSpeed(speed.value + delta)
}

function onSpeedTyped() {
  commitSpeed(speedText.value)
}

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
  speed.value = 1
  speedText.value = '1.0'

  if (!downloadId.value) {
    errorMsg.value = 'Nenhum arquivo selecionado.'
    streamUrl.value = ''
    displayName.value = ''
    cutDisplayName.value = ''
    loading.value = false
    return
  }

  streamUrl.value = mediaStreamUrl(mediaId.value, mediaFolder.value)
  try {
    const info = await getMediaInfo(mediaId.value, mediaFolder.value)
    duration.value = info.duration
    if (editingCut.value) {
      cutDisplayName.value = info.name
      const original = await getMediaInfo(downloadId.value, 'downloads').catch(() => null)
      displayName.value = original?.name || downloadId.value
    } else {
      displayName.value = info.name
      cutDisplayName.value = ''
    }
    void getPlaybackUrl(mediaId.value, mediaFolder.value).then((playback) => {
      if (playback && !playback.includes('/api/media/stream')) {
        streamUrl.value = playback
      }
    })
  } catch (err: unknown) {
    streamUrl.value = ''
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
  applyPlaybackRate()
}

function onVideoError() {
  if (!mediaId.value) return
  const fallback = mediaStreamUrl(mediaId.value, mediaFolder.value)
  if (streamUrl.value !== fallback) {
    streamUrl.value = fallback
  }
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
  if (!downloadId.value || duration.value <= 0) {
    errorMsg.value = 'Nenhum arquivo selecionado.'
    return
  }
  if (markers.value.length === 1) {
    errorMsg.value =
      'Com 1 linha de corte não é possível salvar. Posicione a segunda linha ou remova a linha para salvar o vídeo inteiro.'
    return
  }
  if (markers.value.length > MAX_MARKERS) {
    errorMsg.value = 'Posicione no máximo 2 linhas de corte.'
    return
  }

  let start = 0
  let end = duration.value
  if (markers.value.length === MAX_MARKERS) {
    if (!selectionRange.value) {
      errorMsg.value = 'Posicione exatamente 2 linhas de corte para salvar o trecho entre elas.'
      return
    }
    start = selectionRange.value.start
    end = selectionRange.value.end
  }

  exporting.value = true
  errorMsg.value = ''
  successMsg.value = ''
  exportJob.value = null

  try {
    const created = await startCuts(
      downloadId.value,
      markers.value,
      [{ start, end }],
      speed.value,
      cutId.value || undefined,
    )
    exportJob.value = created
    const finalJob = await pollCutJob(created.id, (job) => {
      exportJob.value = job
    })
    if (finalJob.status === 'error') {
      errorMsg.value = finalJob.error || finalJob.message || 'Falha ao exportar.'
    } else {
      successMsg.value = `Corte salvo: ${finalJob.outputs.join(', ')}`
      await cutListRef.value?.refresh()
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
  if (loading.value || !downloadId.value) return

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

watch([downloadId, cutId], load)

function pauseMainVideo() {
  videoRef.value?.pause()
}

function goHome() {
  router.push('/')
}

function editOriginal() {
  if (!downloadId.value) return
  router.push({ path: '/editor', query: { id: downloadId.value } })
}
</script>

<template>
  <div class="page-shell editor-page">
    <div class="editor-toolbar">
      <v-btn
        class="ghost-btn"
        variant="outlined"
        rounded="lg"
        prepend-icon="mdi-arrow-left"
        @click="goHome"
      >
        Voltar
      </v-btn>
      <div class="editor-title">
        <h1>Editor de cortes</h1>
        <p v-if="displayName" class="filename" :title="displayName">{{ displayName }}</p>
        <p v-if="editingCut" class="filename filename-cut" :title="cutDisplayName">
          Editando corte: {{ cutDisplayName }}
        </p>
      </div>
      <v-btn
        class="save-btn"
        color="secondary"
        rounded="lg"
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

    <v-alert
      v-if="editingCut"
      type="info"
      variant="tonal"
      density="comfortable"
      class="mb-3"
    >
      Você está editando um corte. O novo arquivo entra na lista do vídeo original.
      <div class="mt-2">
        <v-btn size="small" variant="text" @click="editOriginal">
          Voltar ao vídeo original
        </v-btn>
      </div>
    </v-alert>

    <v-progress-linear
      v-if="exporting"
      class="mb-3"
      :model-value="exportJob?.progress || 0"
      color="secondary"
      height="6"
      rounded
    />

    <div v-if="loading" class="editor-loading">
      <span class="app-spinner" role="status" aria-label="Carregando vídeo" />
      <span>Carregando vídeo…</span>
    </div>

    <template v-else-if="downloadId && streamUrl">
      <div class="preview-stage" @click="togglePlay">
        <video
          :key="streamUrl"
          ref="videoRef"
          class="preview-video"
          :src="streamUrl"
          preload="auto"
          playsinline
          @loadedmetadata="onLoadedMetadata"
          @error="onVideoError"
          @timeupdate="onTimeUpdate"
          @play="onPlay"
          @pause="onPause"
        />
      </div>

      <div class="editor-controls">
      <div class="transport">
        <div class="transport-left">
          <v-btn icon variant="text" aria-label="Voltar 5 segundos" @click="skip(-5)">
            <v-icon>mdi-skip-previous</v-icon>
          </v-btn>
          <v-btn
            class="transport-play"
            icon
            color="primary"
            size="large"
            :aria-label="playing ? 'Pausar' : 'Play/pause'"
            @click="togglePlay"
          >
            <v-icon>{{ playing ? 'mdi-pause' : 'mdi-play' }}</v-icon>
          </v-btn>
          <v-btn icon variant="text" aria-label="Avançar 5 segundos" @click="skip(5)">
            <v-icon>mdi-skip-next</v-icon>
          </v-btn>

          <span class="timecode">
            {{ formatClock(currentTime) }}
            <span class="timecode-sep">/</span>
            {{ formatClock(duration) }}
          </span>

          <div class="volume-control">
            <v-btn icon variant="text" size="small" :aria-label="muted ? 'Ativar som' : 'Silenciar'" @click="toggleMute">
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

          <v-menu location="bottom">
            <template #activator="{ props: menuProps }">
              <button
                v-bind="menuProps"
                type="button"
                class="speed-chip"
                :disabled="exporting"
              >
                Velocidade: {{ formatSpeed(speed) }}x
                <v-icon size="16">mdi-chevron-down</v-icon>
              </button>
            </template>
            <div class="speed-menu">
              <button
                v-for="preset in SPEED_PRESETS"
                :key="preset"
                type="button"
                class="speed-option"
                :class="{ active: speed === preset }"
                @click="commitSpeed(preset)"
              >
                {{ formatSpeed(preset) }}x
              </button>
              <label class="speed-custom">
                Custom
                <input
                  class="speed-input"
                  type="number"
                  min="0.25"
                  max="2"
                  step="0.01"
                  :disabled="exporting"
                  v-model="speedText"
                  aria-label="Velocidade do corte"
                  @change="onSpeedTyped"
                  @blur="onSpeedTyped"
                  @keydown.up.prevent="nudgeSpeed(SPEED_STEP)"
                  @keydown.down.prevent="nudgeSpeed(-SPEED_STEP)"
                >
              </label>
            </div>
          </v-menu>
        </div>

        <div class="transport-right">
          <v-btn
            class="cut-btn"
            variant="outlined"
            color="secondary"
            rounded="lg"
            prepend-icon="mdi-scissors-cutting"
            :disabled="markers.length >= MAX_MARKERS"
            @click="addMarkerAtPlayhead"
          >
            Linha de corte ({{ markers.length }}/{{ MAX_MARKERS }})
          </v-btn>
          <v-btn
            class="ghost-btn"
            variant="outlined"
            rounded="lg"
            :disabled="selectedMarkerIndex === null"
            prepend-icon="mdi-delete"
            @click="removeSelectedMarker"
          >
            Remover
          </v-btn>
        </div>

        <button
          type="button"
          class="clear-link"
          :disabled="markers.length === 0"
          @click="clearMarkers"
        >
          Limpar
        </button>
      </div>
      </div>

      <section class="timeline-card surface-card">
        <div class="timeline-card-title">
          <h2>Linha de edição</h2>
          <span class="marker-count">
            <template v-if="selectionRange">
              Trecho:
              {{ formatClock(selectionRange.start) }}
              →
              {{ formatClock(selectionRange.end) }}
              <template v-if="outputDuration != null && speed !== 1">
                · saída {{ formatClock(outputDuration) }} a {{ formatSpeed(speed) }}x
              </template>
            </template>
            <template v-else-if="markers.length === 1">
              1/{{ MAX_MARKERS }} linhas · adicione a segunda ou remova para salvar o vídeo inteiro
            </template>
            <template v-else>
              Vídeo inteiro
              <template v-if="outputDuration != null && speed !== 1">
                · saída {{ formatClock(outputDuration) }} a {{ formatSpeed(speed) }}x
              </template>
            </template>
          </span>
        </div>
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
      </section>

      <p class="timeline-hint">
        Espaço: play/pause · Setas ← → : −5s / +5s · Sem linhas: salva o vídeo inteiro, só mudar a velocidade. Duas linhas: salva o trecho aqui, uma linha não permite salvar.
      </p>
    </template>

    <EditorCutList
      v-if="downloadId"
      ref="cutListRef"
      :download-id="downloadId"
      :active-cut="cutId"
      @play="pauseMainVideo"
    />
  </div>
</template>

<style scoped>
.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.editor-title {
  flex: 1;
  min-width: 0;
}

.editor-title h1 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.filename {
  margin: 2px 0 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filename-cut {
  color: var(--text-primary);
}

.save-btn {
  min-height: 40px !important;
  padding-inline: 18px !important;
  font-weight: 700 !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  flex-shrink: 0;
}

.preview-stage {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: var(--radius-lg);
  background: var(--bg-video);
  min-height: 220px;
  max-height: min(58vh, 640px);
}

.preview-video {
  display: block;
  width: 100%;
  max-height: min(58vh, 640px);
  height: auto;
  cursor: pointer;
  background: var(--bg-video);
}

.editor-controls {
  margin-top: 12px;
  margin-bottom: 16px;
}

.transport {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    "left right"
    "clear right";
  align-items: center;
  column-gap: 12px;
  row-gap: 2px;
}

.transport-left {
  grid-area: left;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.transport-right {
  grid-area: right;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  align-self: start;
}

.clear-link {
  grid-area: clear;
}

.transport-play {
  background: var(--accent-blue) !important;
  color: #fff !important;
}

.timecode {
  margin-left: 6px;
  font-variant-numeric: tabular-nums;
  font-size: 0.95rem;
  color: var(--text-on-preview);
}

.timecode-sep {
  opacity: 0.5;
  margin: 0 4px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 120px;
  max-width: 180px;
  width: 160px;
}

.volume-slider {
  flex: 1;
  margin-inline: 0;
}

.speed-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
}

.speed-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.speed-menu {
  min-width: 140px;
  padding: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
}

.speed-option,
.speed-custom {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
}

.speed-option.active,
.speed-option:hover {
  background: var(--bg-elevated);
}

.speed-custom {
  gap: 8px;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: default;
}

.speed-input {
  width: 4rem;
  height: 32px;
  border: 1px solid var(--border-speed-input);
  border-radius: 8px;
  background: var(--bg-speed-input);
  color: #fff;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.speed-input:focus {
  outline: 1px solid var(--focus-ring);
  border-color: var(--focus-ring);
}

.speed-input::-webkit-outer-spin-button,
.speed-input::-webkit-inner-spin-button {
  appearance: none;
  margin: 0;
}

.speed-input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}

.cut-btn {
  min-height: 40px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em !important;
  font-weight: 700 !important;
}

.clear-link {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  margin: 0;
  padding: 0 4px;
  border: 0;
  background: none;
  color: var(--accent-pink);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
}

.clear-link:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.timeline-card {
  display: block;
  padding: 16px 18px 12px;
  margin-top: 8px;
}

.timeline-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.timeline-card-title h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.marker-count {
  font-size: 0.85rem;
  font-weight: 400;
  color: #60a5fa;
}

.timeline-hint {
  margin: 12px 0 0;
  text-align: center;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.editor-loading {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 48px;
  justify-content: center;
  color: var(--text-muted);
}

.mb-3 {
  margin-bottom: 12px;
}

.mt-2 {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .editor-toolbar {
    flex-wrap: wrap;
  }

  .save-btn {
    width: 100%;
  }
}

  @media (max-width: 720px) {
  .transport {
    grid-template-columns: 1fr;
    grid-template-areas:
      "left"
      "right"
      "clear";
  }

  .transport-left,
  .transport-right {
    width: 100%;
  }

  .transport-right .v-btn {
    flex: 1;
  }

  .volume-control {
    width: 100%;
    max-width: none;
  }

  .timeline-card-title {
    flex-direction: column;
    align-items: flex-start;
  }

  .timeline-hint {
    text-align: left;
  }
}
</style>
