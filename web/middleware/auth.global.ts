export default defineNuxtRouteMiddleware(async (to) => {
  const isPublic = to.meta.public === true || to.path === '/login'
  const { ensureSession } = useAuth()
  const ok = await ensureSession()

  if (isPublic) {
    if (ok && to.path === '/login') {
      const raw = typeof to.query.redirect === 'string' ? to.query.redirect : '/'
      const dest =
        raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/login') ? raw : '/'
      return navigateTo(dest)
    }
    return
  }

  if (!ok) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }
})
