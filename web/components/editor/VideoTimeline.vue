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

const waveBars = computed(() => {
  const count = 96
  const seed = Math.max(1, Math.round(props.duration * 17))
  const bars: { height: number; played: boolean }[] = []
  for (let i = 0; i < count; i++) {
    const n = Math.sin((i + 1) * 12.9898 + seed) * 43758.5453
    const frac = n - Math.floor(n)
    const height = 18 + frac * 72
    const played = props.duration
      ? (i / count) * props.duration <= props.currentTime
      : false
    bars.push({ height, played })
  }
  return bars
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

function onTrackPointer(e: PointerEvent) {
  if (e.buttons !== 1) return
  const target = e.target as HTMLElement
  if (target.closest('.marker')) return
  emit('seek', timeFromClientX(e.clientX))
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
    <div
      ref="trackRef"
      class="timeline-track"
      @click="onTrackClick"
      @dblclick="onTrackDblClick"
      @pointerdown="onTrackPointer"
      @pointermove="onTrackPointer"
    >
      <div class="wave" aria-hidden="true">
        <span
          v-for="(bar, index) in waveBars"
          :key="index"
          class="wave-bar"
          :class="{ played: bar.played }"
          :style="{ height: `${bar.height}%` }"
        />
      </div>

      <div
        v-if="selection"
        class="segment"
        :style="{ left: `${selection.left}%`, width: `${selection.width}%` }"
        :title="`Trecho: ${formatClock(selection.start)} → ${formatClock(selection.end)}`"
      />

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
  </div>
</template>

<style scoped>
.timeline {
  user-select: none;
}

.timeline-track {
  position: relative;
  height: 92px;
  background: var(--timeline-track);
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  touch-action: none;
}

.wave {
  position: absolute;
  inset: 14px 8px;
  display: flex;
  align-items: center;
  gap: 3px;
  pointer-events: none;
}

.wave-bar {
  flex: 1;
  min-width: 2px;
  border-radius: 2px;
  background: #4b5568;
  opacity: 0.85;
}

.wave-bar.played {
  background: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%);
}

.segment {
  position: absolute;
  top: 10px;
  bottom: 10px;
  background: rgb(37 99 235 / 22%);
  box-shadow: inset 0 0 0 1px rgb(96 165 250 / 45%);
  pointer-events: none;
}

.marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 3px;
  margin-left: -1.5px;
  padding: 0;
  border: none;
  background: #fb7185;
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
  border-top: 8px solid #fb7185;
}

.marker.selected,
.marker:hover {
  background: #fbbf24;
  width: 4px;
  margin-left: -2px;
}

.marker.selected::before,
.marker:hover::before {
  border-top-color: #fbbf24;
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
  top: 4px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
  width: 12px;
  height: 12px;
  background: var(--playhead);
  border-radius: 2px;
  box-shadow: 0 0 0 2px rgb(11 14 26 / 70%);
}

.playhead-line {
  position: absolute;
  top: 12px;
  bottom: 0;
  left: 50%;
  width: 2px;
  margin-left: -1px;
  background: var(--playhead);
}

.timeline-ruler {
  position: relative;
  height: 22px;
  margin-top: 8px;
  color: var(--timeline-ruler);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}

.ruler-tick {
  position: absolute;
  transform: translateX(-50%);
  white-space: nowrap;
}
</style>
