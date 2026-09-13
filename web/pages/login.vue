<script setup lang="ts">
definePageMeta({
  public: true,
})

const route = useRoute()
const { login, ensureSession } = useAuth()

const email = ref('')
const senha = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const errorMsg = ref('')

onMounted(async () => {
  const ok = await ensureSession()
  if (ok) {
    await navigateTo(safeRedirect())
  }
})

function safeRedirect(): string {
  const raw = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/login')) {
    return '/'
  }
  return raw
}

async function onSubmit() {
  if (submitting.value) return
  errorMsg.value = ''
  submitting.value = true
  try {
    await login(email.value.trim(), senha.value)
    await navigateTo(safeRedirect())
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }; message?: string }
    errorMsg.value = e?.data?.detail || 'E-mail ou senha inválidos.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card surface-card">
      <div class="login-brand">
        <span class="brand-mark" aria-hidden="true">
          <v-icon size="22">mdi-play</v-icon>
        </span>
        <h1>Video Cortes</h1>
        <p>Entre para gerenciar downloads e cortes.</p>
      </div>

      <v-alert
        v-if="errorMsg"
        type="error"
        variant="tonal"
        class="mb-4"
      >
        {{ errorMsg }}
      </v-alert>

      <v-form @submit.prevent="onSubmit">
        <v-text-field
          v-model="email"
          label="E-mail"
          type="email"
          autocomplete="username"
          variant="outlined"
          hide-details="auto"
          class="mb-3"
          :disabled="submitting"
        />
        <v-text-field
          v-model="senha"
          label="Senha"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          variant="outlined"
          hide-details="auto"
          class="mb-4"
          :disabled="submitting"
          :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
          @click:append-inner="showPassword = !showPassword"
        />
        <v-btn
          type="submit"
          color="primary"
          size="large"
          block
          rounded="xl"
          class="login-submit"
          :disabled="submitting || !email || !senha"
        >
          {{ submitting ? 'Entrando…' : 'Entrar' }}
        </v-btn>
      </v-form>
    </div>
  </div>
</template>
