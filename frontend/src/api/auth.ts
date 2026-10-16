/* Auth API — mirror backend /api/v1/auth/* */
import { apiClient, unwrap } from '@/api'
import type { ApiEnvelope } from '@/types'

export interface UserPublic {
  id: string
  username: string
  display_name: string | null
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface AuthResponse {
  token: TokenResponse
  user: UserPublic
}

export const authApi = {
  login(username: string, password: string) {
    return apiClient
      .post<ApiEnvelope<AuthResponse>>('/auth/login', { username, password })
      .then(unwrap<AuthResponse>)
  },

  register(username: string, password: string, display_name?: string) {
    return apiClient
      .post<ApiEnvelope<AuthResponse>>('/auth/register', {
        username,
        password,
        display_name: display_name ?? null,
      })
      .then(unwrap<AuthResponse>)
  },

  me() {
    return apiClient
      .get<ApiEnvelope<UserPublic>>('/auth/me')
      .then(unwrap<UserPublic>)
  },
}
