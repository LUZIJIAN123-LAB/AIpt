/* Axios instance — pointed at backend; vite proxy /api → :8000 in dev. */
import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import type { ApiEnvelope, ErrorEnvelope } from '@/types'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
})

// ---------------------------------------------------------------------------
// Request interceptor — attach JWT if present
// ---------------------------------------------------------------------------
apiClient.interceptors.request.use((config) => {
  // Lazy import to avoid circular dependency during store init
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  } else {
    delete config.headers.Authorization
  }
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor — unwrap envelope + handle 401 centrally
// ---------------------------------------------------------------------------
apiClient.interceptors.response.use(
  (r) => r,
  (err: AxiosError<ErrorEnvelope>) => {
    // 401 from backend → clear local auth + bounce to login
    if (err.response?.status === 401) {
      try {
        const auth = useAuthStore()
        if (auth.isLoggedIn) {
          auth.logout()
          // router might not be loaded yet during init; use path string
          const current = window.location.pathname
          if (current !== '/login') {
            // preserve destination so we can come back after login
            window.location.replace(`/login?redirect=${encodeURIComponent(current)}`)
          }
        }
      } catch {
        // store not ready yet — ignore
      }
    }
    const msg = err.response?.data?.message ?? err.message ?? '请求失败'
    return Promise.reject(new Error(msg))
  },
)

/* ---- Generic envelope unwrapper ---- */
export function unwrap<T>(r: { data: ApiEnvelope<T> }): T {
  return r.data.data
}
