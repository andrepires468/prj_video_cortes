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
        themes: {
          light: {
            dark: false,
            colors: {
              background: '#f5f5f5',
              surface: '#ffffff',
            },
          },
          dark: {
            dark: true,
            colors: {
              background: '#0e0e0e',
              surface: '#1e1e1e',
            },
          },
        },
      },
    },
  },

  app: {
    head: {
      title: 'Video Cortes',
      meta: [
        { name: 'description', content: 'Download local de vídeos do YouTube, X, TikTok e Instagram' },
      ],
      script: [
        {
          src: '/theme-init.js',
          tagPosition: 'head',
          tagPriority: 'critical',
        },
      ],
    },
  },
})
