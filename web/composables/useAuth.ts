export type AuthUser = {
  id: string
  email: string
  nome: string
}

export function useAuth() {
  const user = useState<AuthUser | null>('auth-user', () => null)
  const requestFetch = useRequestFetch()

  async function fetchMe(): Promise<AuthUser | null> {
    try {
      const me = await requestFetch<AuthUser>('/api/auth/me')
      user.value = me
      return me
    } catch {
      user.value = null
      return null
    }
  }

  async function login(email: string, senha: string): Promise<AuthUser> {
    const res = await requestFetch<{ usuario: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: { email, senha },
    })
    user.value = res.usuario
    return res.usuario
  }

  async function logout(): Promise<void> {
    try {
      await requestFetch('/api/auth/logout', { method: 'POST' })
    } finally {
      user.value = null
      await navigateTo('/login')
    }
  }

  async function ensureSession(): Promise<boolean> {
    if (user.value) return true
    const me = await fetchMe()
    return Boolean(me)
  }

  const isLoggedIn = computed(() => Boolean(user.value))

  return { user, isLoggedIn, login, logout, fetchMe, ensureSession }
}
