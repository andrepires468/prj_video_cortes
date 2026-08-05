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

async function onSubmit() {
  errorMsg.value = ''
  job.value = null
  const trimmed = url.value.trim()
  if (!trimmed) {
    errorMsg.value = 'Informe a URL do vídeo (YouTube ou X).'
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
  <v-card class="page-section" variant="outlined">
    <v-card-title>Baixar vídeo</v-card-title>
    <v-card-text>
      <v-text-field
        v-model="url"
        label="URL do vídeo"
        placeholder="YouTube ou X (ex.: https://x.com/.../status/...)"
        variant="outlined"
        density="comfortable"
        hide-details="auto"
        :disabled="loading"
        clearable
        @keyup.enter="onSubmit"
      />

      <div class="form-actions">
        <v-btn
          color="primary"
          :loading="loading"
          :disabled="loading"
          @click="onSubmit"
        >
          Baixar
        </v-btn>
      </div>

      <div v-if="job && loading" class="progress-block">
        <div>{{ job.message || 'Baixando…' }}</div>
        <v-progress-linear
          class="mt-2"
          :model-value="job.progress"
          height="8"
          color="primary"
          rounded
        />
        <div class="text-caption mt-1">{{ job.progress.toFixed(0) }}%</div>
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
    </v-card-text>
  </v-card>
</template>

<style scoped>
.mt-2 {
  margin-top: 8px;
}

.mt-1 {
  margin-top: 4px;
}

.mt-4 {
  margin-top: 16px;
}

.text-caption {
  font-size: 0.75rem;
  opacity: 0.7;
}
</style>
