/* Document API — upload / list / detail / delete. */
import { apiClient, unwrap } from './index'
import type { DocumentDetail, DocumentListResponse } from '@/types'

export const documentApi = {
  async upload(file: File, title?: string | null) {
    const fd = new FormData()
    fd.append('file', file)
    if (title) fd.append('title', title)
    return unwrap<{ document_id: string; chunk_count: number; word_count: number; file_type: string; skipped: boolean }>(
      await apiClient.post('/documents/upload', fd),
    )
  },
  async list(page = 1, page_size = 20) {
    return unwrap<DocumentListResponse>(
      await apiClient.get('/documents', { params: { page, page_size } }),
    )
  },
  async get(id: string) {
    return unwrap<DocumentDetail>(await apiClient.get(`/documents/${id}`))
  },
  async remove(id: string) {
    return unwrap<{ id: string }>(await apiClient.delete(`/documents/${id}`))
  },
}
