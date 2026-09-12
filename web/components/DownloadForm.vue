<script setup lang="ts">
import type { JobInfo } from '~/types/downloads'

const emit = defineEmits<{
  completed: []
}>()

const { startDownload, pollJob } = useDownloads()

const url = ref('')
const loading = ref(false)
const job = ref<JobInfo | null>(null)
const errorMsg = ref('')

const platforms = [
  { name: 'YouTube', icon: 'mdi-youtube' },
  { name: 'X (Twitter)', icon: 'mdi-twitter' },
  { name: 'TikTok', icon: 'mdi-music-note' },
  { name: 'Instagram', icon: 'mdi-instagram' },
  { name: 'Angel', icon: 'mdi-movie-open' },
]

async function onSubmit() {
  errorMsg.value = ''
  job.value = null
  const trimmed = url.value.trim()
  if (!trimmed) {
    errorMsg.value = 'Informe a URL do vídeo (YouTube, X, TikTok, Instagram ou Angel).'
    return
  }

  loading.value = true
  try {
    const created = await startDownload(trimmed)
    job.value = created
    const finalJob = await pollJob(created.id, (update) => {
      job.value = update
    })
    if (finalJob.status === 'error') {
      errorMsg.value = finalJob.error || finalJob.message || 'Falha no download.'
    } else {
      emit('completed')
      url.value = ''
    }
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    errorMsg.value =
      e?.data?.detail || e?.message || 'Não foi possível iniciar o download.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="download-card surface-card">
    <h1 class="download-card__title">Baixar vídeo</h1>

    <label class="url-field">
      <v-icon class="url-field__icon" size="20">mdi-link-variant</v-icon>
      <input
        v-model="url"
        class="url-field__input"
        type="url"
        inputmode="url"
        autocomplete="off"
        spellcheck="false"
        placeholder="Cole a URL do vídeo aqui (YouTube, X, TikTok, Instagram...)"
        :disabled="loading"
        @keyup.enter="onSubmit"
      >
    </label>

    <div class="download-card__row">
      <div class="platform-chips">
        <span
          v-for="platform in platforms"
          :key="platform.name"
          class="platform-chip"
        >
          <v-icon size="15">{{ platform.icon }}</v-icon>
          {{ platform.name }}
        </span>
      </div>
      <v-btn
        class="download-btn"
        color="primary"
        rounded="lg"
        :loading="loading"
        :disabled="loading"
        @click="onSubmit"
      >
        Baixar
      </v-btn>
    </div>

    <div v-if="job && loading" class="progress-block">
      <div class="progress-msg">{{ job.message || 'Baixando…' }}</div>
      <v-progress-linear
        class="mt-2"
        :model-value="job.progress"
        height="8"
        color="primary"
        rounded
      />
      <div class="progress-pct">{{ job.progress.toFixed(0) }}%</div>
    </div>

    <v-alert
      v-if="errorMsg"
      class="mt-4"
      type="error"
      variant="tonal"
      density="comfortable"
    >
      {{ errorMsg }}
    </v-alert>

    <v-alert
      v-if="job?.status === 'done' && !loading"
      class="mt-4"
      type="success"
      variant="tonal"
      density="comfortable"
    >
      Download concluído
      <span v-if="job.filename">: {{ job.filename }}</span>
    </v-alert>
  </section>
</template>

<style scoped>
.download-card {
  padding: 22px 22px 20px;
}

.download-card__title {
  margin: 0 0 16px;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.url-field {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 14px;
  border-radius: 12px;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
}

.url-field__icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.url-field__input {
  flex: 1;
  min-width: 0;
  height: 48px;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  outline: none;
}

.url-field__input::placeholder {
  color: var(--text-muted);
}

.url-field:focus-within {
  border-color: rgb(37 99 235 / 55%);
  box-shadow: 0 0 0 3px rgb(37 99 235 / 18%);
}

.download-card__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
}

.platform-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 10px;
  border-radius: var(--radius-pill);
  background: var(--bg-chip);
  color: var(--text-muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

.download-btn {
  min-height: 44px !important;
  min-width: 120px;
  padding-inline: 22px !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  flex-shrink: 0;
}

.progress-msg,
.progress-pct {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.progress-pct {
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}

.mt-2 {
  margin-top: 8px;
}

.mt-4 {
  margin-top: 16px;
}

@media (max-width: 720px) {
  .download-card {
    padding: 18px 16px 16px;
  }

  .download-card__row {
    flex-direction: column;
    align-items: stretch;
  }

  .download-btn {
    width: 100%;
  }
}
</style>
