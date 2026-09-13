<script setup lang="ts">
const route = useRoute()
const { downloadCount, setDownloadCount } = useLibraryStats()
const { user, isLoggedIn, logout } = useAuth()

const isLogin = computed(() => route.path === '/login')

watch(isLoggedIn, (ok) => {
  if (!ok) setDownloadCount(0)
})
</script>

<template>
  <v-app class="app-root" theme="dark">
    <header v-if="!isLogin" class="app-header">
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
          <span v-if="user" class="header-user">{{ user.nome }}</span>
          <v-btn
            class="logout-btn"
            variant="text"
            rounded="xl"
            @click="logout"
          >
            Sair
          </v-btn>
        </div>
      </div>
    </header>
    <v-main class="app-main" :class="{ 'app-main--login': isLogin }">
      <NuxtPage />
    </v-main>
  </v-app>
</template>
