<script setup lang="ts">
/* "来源引用" panel — shown below the answer when RAG sources exist.

   Clicking a source row emits 'jump' with chunk content so the ChatWindow
   can highlight/focus it. (Future: open document detail page, scroll to chunk.)
*/
import type { RagSource } from '@/types'

defineProps<{ sources: RagSource[] }>()
const emit = defineEmits<{ jump: [source: RagSource] }>()
</script>

<template>
  <div class="source-panel">
    <div class="source-title">
      <el-icon><Document /></el-icon>
      引用来源 ({{ sources.length }})
    </div>
    <div
      v-for="(s, i) in sources"
      :key="i"
      class="source-item"
      @click="emit('jump', s)"
    >
      <div class="source-meta">
        <span class="source-doc">{{ s.document_filename }}</span>
        <span class="source-score">final: {{ s.final_score.toFixed(3) }}</span>
      </div>
      <div class="source-content">{{ s.content.slice(0, 160) }}{{ s.content.length > 160 ? '...' : '' }}</div>
    </div>
  </div>
</template>

<style scoped>
.source-panel {
  margin-top: 12px;
  border-top: 1px dashed var(--color-border);
  padding-top: 10px;
}
.source-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted);
  margin-bottom: 8px;
}
.source-item {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f1f5f9;
  margin-bottom: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.source-item:hover { background: #e2e8f0; }
.source-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-muted);
  margin-bottom: 4px;
}
.source-doc { font-weight: 500; color: var(--color-text); }
.source-content {
  font-size: 13px;
  line-height: 1.5;
  color: #475569;
}
</style>
