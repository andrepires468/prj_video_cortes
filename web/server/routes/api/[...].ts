import { joinURL } from 'ufo'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const targetBase = (config.apiUrl as string).replace(/\/$/, '')

  // event.path is like /api/downloads/... — forward as-is to FastAPI
  const target = joinURL(targetBase, event.path)

  return proxyRequest(event, target)
})
