<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" flat>
      <v-app-bar-title>
        <NuxtLink to="/" class="brand-link">Video Cortes</NuxtLink>
      </v-app-bar-title>
      <template #append>
        <v-btn variant="text" to="/">Downloads</v-btn>
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
