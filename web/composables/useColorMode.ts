import { useTheme } from 'vuetify'

export const THEME_STORAGE_KEY = 'video-cortes-theme'

export type ColorMode = 'light' | 'dark'

function readStored(): ColorMode {
  if (!import.meta.client) return 'light'
  try {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    /* private mode / blocked storage */
  }
  return 'light'
}

function writeStored(mode: ColorMode) {
  if (!import.meta.client) return
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    /* ignore */
  }
  document.documentElement.setAttribute('data-theme', mode)
  document.documentElement.style.colorScheme = mode
}

export function useColorMode() {
  const mode = ref<ColorMode>('light')
  const isDark = computed(() => mode.value === 'dark')
  const theme = import.meta.client ? useTheme() : null

  function apply(next: ColorMode) {
    mode.value = next
    writeStored(next)
    if (theme) {
      theme.global.name.value = next
    }
  }

  function toggle() {
    apply(mode.value === 'dark' ? 'light' : 'dark')
  }

  function init() {
    apply(readStored())
  }

  onMounted(() => {
    init()
  })

  return { mode, isDark, toggle, apply, init }
}
