const THEME_STORAGE_KEY = 'video-cortes-theme'

export default defineNuxtPlugin({
  name: 'color-mode',
  enforce: 'pre',
  setup() {
    try {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
      const theme = saved === 'dark' || saved === 'light' ? saved : 'light'
      document.documentElement.setAttribute('data-theme', theme)
      document.documentElement.style.colorScheme = theme
    } catch {
      /* ignore */
    }
  },
})
