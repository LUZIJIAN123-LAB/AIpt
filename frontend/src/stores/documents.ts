/* Documents store — for the "知识库管理" page. */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { documentApi } from '@/api/document'
import type { DocumentItem } from '@/types'

export const useDocumentsStore = defineStore('documents', () => {
  const items = ref<DocumentItem[]>([])
  const loading = ref(false)
  const uploading = ref(false)
  const uploadProgress = ref(0) // 0..100 (informational only — real progress needs XHR)

  async function load() {
    loading.value = true
    try {
      const res = await documentApi.list(1, 100)
      items.value = res.items
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File, title?: string | null) {
    uploading.value = true
    uploadProgress.value = 0
    try {
      const result = await documentApi.upload(file, title)
      uploadProgress.value = 100
      items.value.unshift({
        id: result.document_id,
        filename: file.name,
        file_type: result.file_type,
        parse_status: result.skipped ? 'existing' : 'done',
        chunk_count: result.chunk_count,
        title: title ?? null,
      })
      return result
    } finally {
      uploading.value = false
    }
  }

  async function remove(id: string) {
    await documentApi.remove(id)
    items.value = items.value.filter((d) => d.id !== id)
  }

  return { items, loading, uploading, uploadProgress, load, upload, remove }
})
