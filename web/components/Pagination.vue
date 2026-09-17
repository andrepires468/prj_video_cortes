<script setup lang="ts">
import type { PaginationMeta } from '~/types/pagination'

const props = withDefaults(
  defineProps<{
    pagination: PaginationMeta
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const WINDOW = 5

const from = computed(() => {
  if (props.pagination.total === 0) return 0
  return (props.pagination.page - 1) * props.pagination.per_page + 1
})

const to = computed(() =>
  Math.min(props.pagination.page * props.pagination.per_page, props.pagination.total),
)

const pages = computed(() => {
  const total = props.pagination.pages
  const current = props.pagination.page
  if (total <= WINDOW) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  const half = Math.floor(WINDOW / 2)
  let start = Math.max(1, current - half)
  let end = start + WINDOW - 1
  if (end > total) {
    end = total
    start = Math.max(1, end - WINDOW + 1)
  }
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})

function go(page: number) {
  if (props.disabled) return
  if (page < 1 || page > props.pagination.pages || page === props.pagination.page) return
  emit('update:page', page)
}
</script>

<template>
  <nav
    v-if="pagination.total > 0"
    class="pager"
    aria-label="Paginação"
  >
    <p class="pager__summary">
      {{ from }}–{{ to }} de {{ pagination.total }}
    </p>
    <div v-if="pagination.pages > 1" class="pager__controls">
      <v-btn
        class="pager__nav"
        variant="outlined"
        rounded="xl"
        icon
        aria-label="Página anterior"
        :disabled="disabled || !pagination.has_prev"
        @click="go(pagination.page - 1)"
      >
        <v-icon size="18">mdi-chevron-left</v-icon>
      </v-btn>
      <v-btn
        v-for="item in pages"
        :key="item"
        class="pager__page"
        :class="{ 'pager__page--current': item === pagination.page }"
        :variant="item === pagination.page ? 'flat' : 'outlined'"
        :color="item === pagination.page ? 'primary' : undefined"
        rounded="xl"
        :aria-current="item === pagination.page ? 'page' : undefined"
        :aria-label="`Página ${item}`"
        :disabled="disabled"
        @click="go(item)"
      >
        {{ item }}
      </v-btn>
      <v-btn
        class="pager__nav"
        variant="outlined"
        rounded="xl"
        icon
        aria-label="Próxima página"
        :disabled="disabled || !pagination.has_next"
        @click="go(pagination.page + 1)"
      >
        <v-icon size="18">mdi-chevron-right</v-icon>
      </v-btn>
    </div>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  flex-wrap: wrap;
}

.pager__summary {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.pager__controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.pager__nav,
.pager__page {
  min-width: 40px !important;
  min-height: 40px !important;
  border-color: var(--border-strong) !important;
  color: var(--text-muted) !important;
  font-size: 0.78rem !important;
  font-weight: 600 !important;
}

.pager__page--current {
  color: #fff !important;
  border-color: transparent !important;
}

@media (max-width: 720px) {
  .pager {
    flex-direction: column;
    align-items: stretch;
  }

  .pager__controls {
    justify-content: center;
  }
}
</style>
