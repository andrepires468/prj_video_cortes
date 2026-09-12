<script setup lang="ts">
const route = useRoute()
const { listFiles } = useDownloads()
const { downloadCount, setDownloadCount } = useLibraryStats()

async function refreshCount() {
  try {
    const files = await listFiles()
    setDownloadCount(files.length)
  } catch {
    /* lista ainda pode estar vazia / API offline */
  }
}

onMounted(() => {
  refreshCount()
})

watch(() => route.path, () => {
  if (route.path === '/') refreshCount()
})
</script>

<template>
  <v-app class="app-root" theme="dark">
    <header class="app-header">
      <div class="app-header__inner">
        <NuxtLink to="/" class="brand" aria-label="Video Cortes — início">
          <span class="brand-mark" aria-hidden="true">
            <v-icon size="22">mdi-play</v-icon>
          </span>
          <span class="brand-name">Video Cortes</span>
        </NuxtLink>
        <div class="app-header__actions">
          <v-btn
            class="downloads-btn"
            variant="outlined"
            rounded="xl"
            to="/"
          >
            <v-icon size="18">mdi-download</v-icon>
            <span class="downloads-label">Downloads</span>
            <span class="count-badge">{{ downloadCount }}</span>
          </v-btn>
        </div>
      </div>
    </header>
    <v-main class="app-main">
      <NuxtPage />
    </v-main>
  </v-app>
</template>
