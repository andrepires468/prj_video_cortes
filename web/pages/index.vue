<script setup lang="ts">
const listRef = ref<{ refresh: () => Promise<void> } | null>(null)

function onCompleted() {
  listRef.value?.refresh()
}
</script>

<template>
  <v-container class="py-6" max-width="960">
    <DownloadForm @completed="onCompleted" />
    <DownloadList ref="listRef" />
  </v-container>
</template>

<style scoped>
.py-6 {
  padding-top: 24px;
  padding-bottom: 24px;
}
</style>
