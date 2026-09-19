<script setup lang="ts">
import type { MediaFolder } from '~/types/downloads'

const PLAYER_VOLUME_KEY = 'video-cortes-player-volume'

type StoredVolume = {
  volume: number
  muted: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    src: string
    title?: string
    mediaId?: string
    folder?: MediaFolder
  }>(),
  { folder: 'downloads' },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  error: []
}>()

const { mediaStreamUrl } = useDownloads()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const downloadHref = computed(() => {
  const id = props.mediaId?.trim()
  if (!id) return ''
  return mediaStreamUrl(id, props.folder, true)
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
  <v-dialog
    v-model="open"
    class="player-dialog"
    max-width="920"
    scrim
    opacity="1"
  >
    <v-card class="player-card surface-card">
      <v-card-title class="player-title">
        <span class="player-name" :title="title">{{ title }}</span>
        <div class="player-actions">
          <v-btn
            v-if="downloadHref"
            class="player-download"
            :href="downloadHref"
            :download="title || 'video.mp4'"
            variant="outlined"
            rounded="lg"
            size="small"
            prepend-icon="mdi-download"
          >
            Baixar
          </v-btn>
          <v-btn icon variant="text" aria-label="Fechar" @click="close">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </div>
      </v-card-title>
      <video
        v-if="open && src"
        :ref="bindVideo"
        class="player-video"
        :src="src"
        controls
        autoplay
        playsinline
        preload="auto"
        @error="emit('error')"
        @volumechange="onVolumeChange"
      />
    </v-card>
  </v-dialog>
</template>

<style scoped>
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

.player-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.player-download {
  text-transform: none !important;
  letter-spacing: 0.02em !important;
  border-color: var(--border-strong) !important;
  color: var(--text-primary) !important;
}

.player-video {
  display: block;
  width: 100%;
  max-height: min(70vh, 720px);
  background: var(--bg-video);
}

@media (max-width: 520px) {
  .player-download {
    min-width: 40px;
    padding-inline: 10px !important;
  }

  .player-download :deep(.v-btn__content) {
    display: none;
  }
}
</style>

<style>
.v-overlay.player-dialog > .v-overlay__scrim {
  background:
    radial-gradient(120% 80% at 50% 40%, rgb(37 99 235 / 12%), transparent 55%),
    rgb(8 10 22 / 52%) !important;
  opacity: 1 !important;
  backdrop-filter: blur(22px) saturate(160%);
  -webkit-backdrop-filter: blur(22px) saturate(160%);
}
</style>
