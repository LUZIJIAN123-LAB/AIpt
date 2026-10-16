/**
 * Auth state — holds JWT + current user, persisted to localStorage.
 *
 * Usage:
 *   const auth = useAuthStore()
 *   await auth.login('admin', 'admin')
 *   await auth.fetchMe()           // verify token still valid
 *   auth.logout()
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type UserPublic } from '@/api/auth'

const TOKEN_KEY = 'aipt.auth.token'
const USER_KEY = 'aipt.auth.user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserPublic | null>(
    (() => {
      const raw = localStorage.getItem(USER_KEY)
      if (!raw) return null
      try {
        return JSON.parse(raw) as UserPublic
      } catch {
        return null
      }
    })(),
  )

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function _persist() {
    if (token.value) localStorage.setItem(TOKEN_KEY, token.value)
    else localStorage.removeItem(TOKEN_KEY)

    if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(USER_KEY)
  }

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    token.value = res.token.access_token
    user.value = res.user
    _persist()
    return user.value
  }

  async function register(username: string, password: string, display_name?: string) {
    const res = await authApi.register(username, password, display_name)
    token.value = res.token.access_token
    user.value = res.user
    _persist()
    return user.value
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const u = await authApi.me()
      user.value = u
      _persist()
      return u
    } catch {
      // token expired / bad — clear everything
      logout()
      return null
    }
  }

  function logout() {
    token.value = null
    user.value = null
    _persist()
  }

  return {
    token,
    user,
    isLoggedIn,
    login,
    register,
    fetchMe,
    logout,
  }
})
