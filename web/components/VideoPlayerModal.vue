<script setup lang="ts">
const PLAYER_VOLUME_KEY = 'video-cortes-player-volume'

type StoredVolume = {
  volume: number
  muted: boolean
}

const props = defineProps<{
  modelValue: boolean
  src: string
  title?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

function close() {
  open.value = false
}

function readStoredVolume(): StoredVolume {
  if (!import.meta.client) return { volume: 1, muted: false }
  try {
    const raw = window.localStorage.getItem(PLAYER_VOLUME_KEY)
    if (!raw) return { volume: 1, muted: false }
    const parsed = JSON.parse(raw) as Partial<StoredVolume>
    const volume =
      typeof parsed.volume === 'number' && Number.isFinite(parsed.volume)
        ? Math.min(1, Math.max(0, parsed.volume))
        : 1
    return { volume, muted: Boolean(parsed.muted) }
  } catch {
    return { volume: 1, muted: false }
  }
}

function writeStoredVolume(next: StoredVolume) {
  if (!import.meta.client) return
  try {
    window.localStorage.setItem(PLAYER_VOLUME_KEY, JSON.stringify(next))
  } catch {
    /* private mode / blocked storage */
  }
}

function applyStoredVolume(el: HTMLVideoElement) {
  const saved = readStoredVolume()
  el.volume = saved.volume
  el.muted = saved.muted
}

function bindVideo(el: Element | null) {
  if (el instanceof HTMLVideoElement) {
    applyStoredVolume(el)
  }
}

function onVolumeChange(event: Event) {
  const el = event.target
  if (!(el instanceof HTMLVideoElement)) return
  writeStoredVolume({ volume: el.volume, muted: el.muted })
}
</script>

<template>
  <v-dialog v-model="open" max-width="920">
    <v-card class="player-card">
      <v-card-title class="player-title">
        <span class="player-name" :title="title">{{ title }}</span>
        <v-btn icon variant="text" aria-label="Fechar" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <video
        v-if="open && src"
        :ref="bindVideo"
        class="player-video"
        :src="src"
        controls
        autoplay
        @volumechange="onVolumeChange"
      />
    </v-card>
  </v-dialog>
</template>

<style scoped>
.player-card {
  background: var(--bg-card);
}

.player-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.player-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 1rem;
  color: var(--text-primary);
}

.player-video {
  display: block;
  width: 100%;
  max-height: 70vh;
  background: var(--bg-video);
}
</style>
