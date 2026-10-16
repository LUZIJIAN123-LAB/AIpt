<script setup lang="ts">
import { ref } from 'vue'
import { Promotion, VideoPause } from '@element-plus/icons-vue'

const props = defineProps<{ streaming: boolean }>()
const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const text = ref('')

function handleSend() {
  const q = text.value.trim()
  if (!q || props.streaming) return
  emit('send', q)
  text.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="chat-input">
    <el-input
      v-model="text"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 5 }"
      :rows="1"
      :disabled="streaming"
      placeholder="提问...（Enter 发送，Shift+Enter 换行）"
      resize="none"
      @keydown="onKeydown"
    />
    <el-button
      v-if="!streaming"
      type="primary"
      :icon="Promotion"
      :disabled="!text.trim()"
      @click="handleSend"
    >发送</el-button>
    <el-button
      v-else
      type="danger"
      :icon="VideoPause"
      @click="emit('stop')"
    >停止</el-button>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 12px 20px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
</style>
