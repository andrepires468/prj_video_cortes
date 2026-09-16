import { joinURL } from 'ufo'
import { getRequestHeader, getRequestURL, sendStream, setResponseHeader, setResponseStatus } from 'h3'

const STREAM_PATH = /^\/api\/media\/(stream|thumb)$/

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const targetBase = (config.apiUrl as string).replace(/\/$/, '')
  const reqUrl = getRequestURL(event)
  const target = joinURL(targetBase, reqUrl.pathname) + reqUrl.search

  if (STREAM_PATH.test(reqUrl.pathname) && event.method === 'GET') {
    const headers: Record<string, string> = {}
    const cookie = getRequestHeader(event, 'cookie')
    const range = getRequestHeader(event, 'range')
    const authorization = getRequestHeader(event, 'authorization')
    if (cookie) headers.cookie = cookie
    if (range) headers.range = range
    if (authorization) headers.authorization = authorization

    const upstream = await fetch(target, { method: 'GET', headers })
    setResponseStatus(event, upstream.status)
    for (const key of [
      'content-type',
      'content-length',
      'content-range',
      'accept-ranges',
      'content-disposition',
      'cache-control',
      'etag',
    ]) {
      const value = upstream.headers.get(key)
      if (value) setResponseHeader(event, key, value)
    }
    setResponseHeader(event, 'x-accel-buffering', 'no')
    if (!upstream.body) {
      return null
    }
    return sendStream(event, upstream.body)
  }

  return proxyRequest(event, joinURL(targetBase, event.path))
})
