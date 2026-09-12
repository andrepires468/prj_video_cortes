<script setup lang="ts">
const listRef = ref<{ refresh: () => Promise<void> } | null>(null)

function onCompleted() {
  listRef.value?.refresh()
}
</script>

<template>
  <div class="page-shell home-page">
    <DownloadForm @completed="onCompleted" />
    <DownloadList ref="listRef" />
  </div>
</template>
