<script setup lang="ts">
import type { JobInfo } from '~/types/downloads'

const emit = defineEmits<{
  completed: []
}>()

const { startDownload, pollJob, cancelDownload } = useDownloads()

const url = ref('')
const loading = ref(false)
const cancelling = ref(false)
const job = ref<JobInfo | null>(null)
const errorMsg = ref('')
const cancelMsg = ref('')

const platforms = [
  { name: 'YouTube', icon: 'mdi-youtube' },
  { name: 'X (Twitter)', icon: 'mdi-twitter' },
  { name: 'TikTok', icon: 'mdi-music-note' },
  { name: 'Instagram', icon: 'mdi-instagram' },
  { name: 'Angel', icon: 'mdi-movie-open' },
]

const downloadPct = computed(() => {
  const n = Number(job.value?.download_progress ?? 0)
  return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 0
})
const uploadPct = computed(() => {
  const n = Number(job.value?.upload_progress ?? 0)
  return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 0
})
const stage = computed(() => job.value?.stage || 'download')
const downloadDone = computed(() => downloadPct.value >= 100 || stage.value === 'upload' || job.value?.status === 'done')
const uploadActive = computed(() => stage.value === 'upload' || job.value?.status === 'done')
const processActive = computed(() => loading.value && Boolean(job.value))

function downloadHint(): string {
  if (job.value?.status === 'done') return 'Arquivo salvo na pasta local'
  if (downloadDone.value) return 'Download local concluído'
  return job.value?.stage === 'download'
    ? (job.value.message || 'Baixando o vídeo para a pasta local…')
    : 'Aguardando início…'
}

function uploadHint(): string {
  if (job.value?.status === 'done') return 'Banco e storage atualizados'
  if (!uploadActive.value) return 'Começa depois do download local'
  return job.value?.message || 'Gravando no banco e enviando ao storage…'
}

async function onSubmit() {
  errorMsg.value = ''
  cancelMsg.value = ''
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
    }, 400)
    job.value = finalJob
    if (finalJob.status === 'error') {
      errorMsg.value = finalJob.error || finalJob.message || 'Falha no download.'
    } else if (finalJob.status === 'cancelled') {
      cancelMsg.value = 'Processo cancelado. Os arquivos gerados até aqui foram apagados.'
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
    cancelling.value = false
  }
}

async function onCancel() {
  const id = job.value?.id
  if (!id || cancelling.value) return
  cancelling.value = true
  cancelMsg.value = ''
  errorMsg.value = ''
  try {
    const updated = await cancelDownload(id)
    job.value = updated
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    if (e?.data?.detail) {
      errorMsg.value = e.data.detail
    }
    cancelling.value = false
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

    <div v-if="job && (processActive || job.status === 'cancelled' || job.status === 'done' || job.status === 'error')" class="process">
      <div class="process__header">
        <div>
          <p class="process__kicker">Mesmo processo</p>
          <p class="process__title">Download local e envio ao storage</p>
        </div>
        <v-btn
          v-if="processActive"
          class="cancel-btn"
          variant="outlined"
          color="error"
          rounded="lg"
          size="small"
          prepend-icon="mdi-close-circle-outline"
          :loading="cancelling"
          :disabled="cancelling"
          @click="onCancel"
        >
          Cancelar
        </v-btn>
      </div>

      <ol class="steps">
        <li
          class="step"
          :class="{
            'step--active': processActive && stage === 'download',
            'step--done': downloadDone,
          }"
        >
          <div class="step__rail">
            <span class="step__badge" aria-hidden="true">
              <v-icon v-if="downloadDone" size="16">mdi-check</v-icon>
              <span v-else>1</span>
            </span>
            <span class="step__line" />
          </div>
          <div class="step__body">
            <div class="step__meta">
              <strong>Download</strong>
              <span class="step__pct">{{ downloadPct.toFixed(0) }}%</span>
            </div>
            <p class="step__hint">{{ downloadHint() }}</p>
            <v-progress-linear
              class="step__bar"
              :model-value="downloadPct"
              height="8"
              color="primary"
              rounded
            />
          </div>
        </li>
        <li
          class="step"
          :class="{
            'step--active': processActive && stage === 'upload',
            'step--done': job.status === 'done' || uploadPct >= 100,
            'step--wait': !uploadActive,
          }"
        >
          <div class="step__rail">
            <span class="step__badge" aria-hidden="true">
              <v-icon v-if="job.status === 'done' || uploadPct >= 100" size="16">mdi-check</v-icon>
              <span v-else>2</span>
            </span>
          </div>
          <div class="step__body">
            <div class="step__meta">
              <strong>Upload</strong>
              <span class="step__pct">{{ uploadPct.toFixed(0) }}%</span>
            </div>
            <p class="step__hint">{{ uploadHint() }}</p>
            <v-progress-linear
              class="step__bar"
              :model-value="uploadPct"
              height="8"
              :color="uploadActive ? 'secondary' : 'primary'"
              rounded
            />
          </div>
        </li>
      </ol>
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
      v-if="cancelMsg"
      class="mt-4"
      type="warning"
      variant="tonal"
      density="comfortable"
    >
      {{ cancelMsg }}
    </v-alert>

    <v-alert
      v-if="job?.status === 'done' && !loading"
      class="mt-4"
      type="success"
      variant="tonal"
      density="comfortable"
    >
      Download e upload concluídos
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

.process {
  margin-top: 18px;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.process__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.process__kicker {
  margin: 0 0 2px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-blue);
}

.process__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.cancel-btn {
  flex-shrink: 0;
  text-transform: none !important;
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
}

.step {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 12px;
  opacity: 0.55;
}

.step--active,
.step--done {
  opacity: 1;
}

.step + .step {
  margin-top: 4px;
}

.step__rail {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.step__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-chip);
  border: 1px solid var(--border-strong);
  font-size: 0.78rem;
  font-weight: 700;
}

.step--active .step__badge {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
}

.step--done .step__badge {
  background: #15803d;
  border-color: #15803d;
}

.step__line {
  flex: 1;
  width: 2px;
  min-height: 22px;
  margin: 6px 0 2px;
  background: var(--border-strong);
}

.step--done .step__line {
  background: #15803d;
}

.step__meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.step__pct {
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.step__hint {
  margin: 4px 0 8px;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.step__bar {
  margin-bottom: 10px;
}

.mt-4 {
  margin-top: 16px;
}

@media (max-width: 720px) {
  .download-card {
    padding: 18px 16px 16px;
  }

  .download-card__row,
  .process__header {
    flex-direction: column;
    align-items: stretch;
  }

  .download-btn,
  .cancel-btn {
    width: 100%;
  }
}
</style>
