// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: false },

  modules: ['vuetify-nuxt-module'],

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    apiUrl: process.env.NUXT_API_URL || 'http://127.0.0.1:5101',
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api',
    },
  },

  vuetify: {
    moduleOptions: {
      styles: true,
    },
    vuetifyOptions: {
      theme: {
        defaultTheme: 'light',
      },
    },
  },

  app: {
    head: {
      title: 'Video Cortes',
      meta: [
        { name: 'description', content: 'Download local de vídeos do YouTube' },
      ],
    },
  },
})
