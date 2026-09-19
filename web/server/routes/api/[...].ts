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
    const ifNoneMatch = getRequestHeader(event, 'if-none-match')
    if (cookie) headers.cookie = cookie
    if (range) headers.range = range
    if (authorization) headers.authorization = authorization
    if (ifNoneMatch) headers['if-none-match'] = ifNoneMatch

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
    if (upstream.status === 304 || !upstream.body) {
      return null
    }
    setResponseHeader(event, 'x-accel-buffering', 'no')
    return sendStream(event, upstream.body)
  }

  return proxyRequest(event, joinURL(targetBase, event.path))
})
