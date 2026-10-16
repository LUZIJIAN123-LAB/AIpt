<script setup lang="ts">
import { ref, watch } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import SourceCitations from './SourceCitations.vue'
import type { ChatTurn, MessageItem, RagSource } from '@/types'

const props = defineProps<{
  messages: MessageItem[]
  activeTurn: ChatTurn | null
  streaming: boolean
}>()
const emit = defineEmits<{ jump: [source: RagSource] }>()

const scrollRef = ref<HTMLDivElement | null>(null)

// Auto-scroll to bottom on every content change (streaming tokens included).
function scrollToBottom() {
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(() => props.messages.length, scrollToBottom)
watch(() => props.activeTurn?.answer, scrollToBottom)
</script>

<template>
  <div class="chat-window" ref="scrollRef">
    <!-- Empty state -->
    <div v-if="messages.length === 0 && !activeTurn" class="empty">
      <div class="empty-title">你好，我是 AIpt 知识库问答助手 👋</div>
      <div class="empty-sub">上传文档后，在这里直接提问，我会基于资料回答。</div>
    </div>

    <!-- Historical messages -->
    <template v-for="m in messages" :key="m.id">
      <div v-if="m.role === 'user'" class="msg user">
        <div class="bubble user-bubble">{{ m.content }}</div>
        <div v-if="m.rewritten_query" class="rewrite-hint">改写为：{{ m.rewritten_query }}</div>
      </div>
      <div v-else-if="m.role === 'assistant'" class="msg assistant">
        <div class="avatar">🤖</div>
        <div class="bubble">
          <MarkdownRenderer :content="m.content" />
          <SourceCitations
            v-if="m.rag_sources && m.rag_sources.length"
            :sources="m.rag_sources as RagSource[]"
            @jump="emit('jump', $event)"
          />
        </div>
      </div>
    </template>

    <!-- Active streaming turn -->
    <div v-if="activeTurn" class="msg user">
      <div class="bubble user-bubble">{{ activeTurn.query }}</div>
      <div v-if="activeTurn.rewritten_query" class="rewrite-hint">改写为：{{ activeTurn.rewritten_query }}</div>
    </div>

    <div v-if="activeTurn" class="msg assistant">
      <div class="avatar">🤖</div>
      <div class="bubble">
        <MarkdownRenderer :content="activeTurn.answer || ''" />
        <div v-if="!activeTurn.answer && streaming" class="typing">
          <span></span><span></span><span></span>
        </div>
        <SourceCitations
          v-if="activeTurn.sources.length"
          :sources="activeTurn.sources"
          @jump="emit('jump', $event)"
        />
        <div v-if="activeTurn.done" class="latency">
          首字 {{ activeTurn.first_token_ms?.toFixed(0) ?? '-' }} ms
          · 共 {{ activeTurn.total_ms?.toFixed(0) ?? '-' }} ms
        </div>
        <div v-if="activeTurn.error" class="error">⚠️ {{ activeTurn.error }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.empty {
  text-align: center;
  margin-top: 120px;
  color: var(--color-muted);
}
.empty-title { font-size: 22px; font-weight: 600; color: var(--color-text); margin-bottom: 6px; }
.empty-sub { font-size: 14px; }

.msg { display: flex; gap: 12px; }
.msg.user { justify-content: flex-end; flex-direction: column; align-items: flex-end; }
.msg.user .bubble {
  background: var(--color-primary); color: #fff;
  padding: 10px 14px; border-radius: 14px 14px 2px 14px;
  max-width: 70%; white-space: pre-wrap; line-height: 1.6;
}
.msg.assistant { align-items: flex-start; }
.avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: #e2e8f0; display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
}
.msg.assistant .bubble {
  background: var(--color-surface);
  padding: 12px 16px; border-radius: 14px 14px 14px 2px;
  max-width: 80%; min-width: 200px;
  border: 1px solid var(--color-border);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.rewrite-hint {
  font-size: 12px;
  color: var(--color-muted);
  margin-top: 4px;
  font-style: italic;
}
.typing { display: flex; gap: 4px; padding: 4px 0; }
.typing span {
  width: 8px; height: 8px; border-radius: 50%; background: #94a3b8;
  animation: blink 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity: 0.3; } 40% { opacity: 1; } }

.latency {
  margin-top: 10px;
  font-size: 12px;
  color: var(--color-muted);
  border-top: 1px solid var(--color-border);
  padding-top: 8px;
}
.error {
  margin-top: 8px;
  color: #dc2626;
  font-size: 13px;
}
</style>
