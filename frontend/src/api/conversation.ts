/* Conversation API — CRUD. */
import { apiClient, unwrap } from './index'
import type { ConversationDetail, ConversationListResponse } from '@/types'

export const conversationApi = {
  async create(title?: string | null, created_by?: string | null) {
    return unwrap<{ id: string; title: string; created_by: string | null; message_count: number; created_at: string }>(
      await apiClient.post('/conversations', { title, created_by }),
    )
  },
  async list(page = 1, page_size = 20) {
    return unwrap<ConversationListResponse>(
      await apiClient.get('/conversations', { params: { page, page_size } }),
    )
  },
  async get(id: string) {
    return unwrap<ConversationDetail>(await apiClient.get(`/conversations/${id}`))
  },
  async remove(id: string) {
    return unwrap<{ id: string }>(await apiClient.delete(`/conversations/${id}`))
  },
}
