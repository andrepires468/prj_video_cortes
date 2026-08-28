<script setup lang="ts">
const props = defineProps<{
  duration: number
  currentTime: number
  markers: number[]
  selectedMarkerIndex: number | null
  maxMarkers?: number
}>()

const emit = defineEmits<{
  seek: [time: number]
  'select-marker': [index: number]
  'add-marker': [time: number]
}>()

const trackRef = ref<HTMLElement | null>(null)
const limit = computed(() => props.maxMarkers ?? 2)

const sortedMarkers = computed(() =>
  [...props.markers]
    .map((time, index) => ({ time, index }))
    .sort((a, b) => a.time - b.time),
)

/** Destaca somente o trecho entre as 2 linhas de corte */
const selection = computed(() => {
  if (sortedMarkers.value.length !== 2 || !props.duration) return null
  const start = sortedMarkers.value[0].time
  const end = sortedMarkers.value[1].time
  return {
    start,
    end,
    left: (start / props.duration) * 100,
    width: ((end - start) / props.duration) * 100,
  }
})

const playheadLeft = computed(() => {
  if (!props.duration) return 0
  return Math.min(100, Math.max(0, (props.currentTime / props.duration) * 100))
})

function timeFromClientX(clientX: number): number {
  const el = trackRef.value
  if (!el || !props.duration) return 0
  const rect = el.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
  return ratio * props.duration
}

function onTrackClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('.marker')) return
  const time = timeFromClientX(e.clientX)
  emit('seek', time)
}

function onTrackDblClick(e: MouseEvent) {
  if (props.markers.length >= limit.value) return
  const time = timeFromClientX(e.clientX)
  emit('add-marker', time)
  emit('seek', time)
}

function markerLeft(time: number): string {
  if (!props.duration) return '0%'
  return `${(time / props.duration) * 100}%`
}

const rulerTicks = computed(() => {
  if (!props.duration) return []
  const step = props.duration > 600 ? 60 : props.duration > 120 ? 30 : props.duration > 30 ? 10 : 5
  const ticks: { time: number; label: string }[] = []
  for (let t = 0; t <= props.duration; t += step) {
    ticks.push({ time: t, label: formatClock(t) })
  }
  if (ticks[ticks.length - 1]?.time < props.duration - 0.5) {
    ticks.push({ time: props.duration, label: formatClock(props.duration) })
  }
  return ticks
})

function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }
  return `${m}:${String(sec).padStart(2, '0')}`
}
</script>

<template>
  <div class="timeline">
    <div class="timeline-ruler">
      <span
        v-for="tick in rulerTicks"
        :key="tick.time"
        class="ruler-tick"
        :style="{ left: markerLeft(tick.time) }"
      >
        {{ tick.label }}
      </span>
    </div>

    <div
      ref="trackRef"
      class="timeline-track"
      @click="onTrackClick"
      @dblclick="onTrackDblClick"
    >
      <div
        v-if="selection"
        class="segment"
        :style="{ left: `${selection.left}%`, width: `${selection.width}%` }"
        :title="`Trecho: ${formatClock(selection.start)} → ${formatClock(selection.end)}`"
      >
        <span class="segment-label">Seleção</span>
      </div>

      <button
        v-for="marker in sortedMarkers"
        :key="marker.index"
        type="button"
        class="marker"
        :class="{ selected: selectedMarkerIndex === marker.index }"
        :style="{ left: markerLeft(marker.time) }"
        :title="`Linha ${formatClock(marker.time)}`"
        @click.stop="emit('select-marker', marker.index)"
      />

      <div class="playhead" :style="{ left: `${playheadLeft}%` }">
        <div class="playhead-head" />
        <div class="playhead-line" />
      </div>
    </div>

    <p class="timeline-hint">
      Espaço: play/pause · Setas ← → : ±5s · Sem linhas: salva o vídeo inteiro (ex.: só mudar a velocidade). Duas linhas: salva o trecho azul. Uma linha não permite salvar.
    </p>
  </div>
</template>

<style scoped>
.timeline {
  user-select: none;
}

.timeline-ruler {
  position: relative;
  height: 20px;
  margin-bottom: 4px;
  color: var(--timeline-ruler);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
}

.ruler-tick {
  position: absolute;
  transform: translateX(-50%);
  white-space: nowrap;
}

.timeline-track {
  position: relative;
  height: 72px;
  background: var(--timeline-track);
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--timeline-border);
}

.segment {
  position: absolute;
  top: 12px;
  bottom: 12px;
  background: linear-gradient(180deg, #3d7eff 0%, #2563eb 100%);
  opacity: 0.85;
  box-sizing: border-box;
}

.segment-label {
  position: absolute;
  left: 6px;
  top: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 3px;
  margin-left: -1.5px;
  padding: 0;
  border: none;
  background: #ff5252;
  cursor: pointer;
  z-index: 3;
}

.marker::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid #ff5252;
}

.marker.selected,
.marker:hover {
  background: #ffeb3b;
  width: 4px;
  margin-left: -2px;
}

.marker.selected::before,
.marker:hover::before {
  border-top-color: #ffeb3b;
}

.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 0;
  z-index: 4;
  pointer-events: none;
}

.playhead-head {
  position: absolute;
  top: -2px;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 12px;
  background: var(--playhead);
  border-radius: 2px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4);
}

.playhead-line {
  position: absolute;
  top: 10px;
  bottom: 0;
  left: 50%;
  width: 2px;
  margin-left: -1px;
  background: var(--playhead);
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
}

.timeline-hint {
  margin: 8px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
