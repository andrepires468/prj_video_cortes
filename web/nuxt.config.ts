// https://nuxt.com/docs/api/configuration/nuxt-config
const dockerDev = process.env.NUXT_DOCKER_DEV === '1'
const hmrClientPort = Number(process.env.NUXT_HMR_CLIENT_PORT || 3101)

export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: false },

  devServer: dockerDev
    ? {
        host: '0.0.0.0',
        port: 3000,
      }
    : undefined,

  vite: dockerDev
    ? {
        server: {
          watch: {
            usePolling: true,
            interval: 300,
          },
          hmr: {
            protocol: 'ws',
            host: 'localhost',
            clientPort: hmrClientPort,
          },
        },
      }
    : undefined,

  modules: ['vuetify-nuxt-module'],

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    // NUXT_API_URL e NUXT_PUBLIC_API_BASE vêm de web/.env (Compose sobrescreve no Docker)
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
        defaultTheme: 'dark',
        themes: {
          dark: {
            dark: true,
            colors: {
              background: '#0B0E1A',
              surface: '#16192B',
              primary: '#2563EB',
              secondary: '#EC4899',
              error: '#F43F5E',
              info: '#3B82F6',
              success: '#22C55E',
              warning: '#F59E0B',
              'on-background': '#F4F6FB',
              'on-surface': '#F4F6FB',
            },
          },
        },
      },
    },
  },

  app: {
    head: {
      htmlAttrs: {
        lang: 'pt-BR',
        'data-theme': 'dark',
      },
      title: 'Video Cortes',
      meta: [
        { name: 'description', content: 'Download local de vídeos do YouTube, X, TikTok, Instagram e Angel' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
        { name: 'theme-color', content: '#0B0E1A' },
        { name: 'color-scheme', content: 'dark' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
      ],
    },
  },
})
