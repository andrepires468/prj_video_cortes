<script setup lang="ts">
const { isDark, toggle } = useColorMode()
</script>

<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" flat>
      <v-app-bar-title>
        <NuxtLink to="/" class="brand-link">Video Cortes</NuxtLink>
      </v-app-bar-title>
      <template #append>
        <v-btn variant="text" to="/">Downloads</v-btn>
        <ClientOnly>
          <v-btn
            icon
            variant="text"
            :aria-label="isDark ? 'Ativar modo claro' : 'Ativar modo escuro'"
            :title="isDark ? 'Modo claro' : 'Modo escuro'"
            @click="toggle"
          >
            <v-icon>{{ isDark ? 'mdi-white-balance-sunny' : 'mdi-weather-night' }}</v-icon>
          </v-btn>
          <template #fallback>
            <v-btn icon variant="text" aria-label="Tema" disabled>
              <v-icon>mdi-theme-light-dark</v-icon>
            </v-btn>
          </template>
        </ClientOnly>
      </template>
    </v-app-bar>
    <v-main>
      <NuxtPage />
    </v-main>
  </v-app>
</template>

<style>
.brand-link {
  color: inherit;
  text-decoration: none;
}
</style>
