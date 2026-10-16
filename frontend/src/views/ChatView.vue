<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ChatInput from '@/components/ChatInput.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

const currentTitle = computed(() =>
  chat.conversations.find((c) => c.id === chat.currentConvId)?.title ?? '新对话',
)

const hasSelection = computed(() => !!chat.currentConvId)

onMounted(async () => {
  // Only reload the currently-selected conversation detail — never auto-create
  // an empty placeholder. ask() will create one lazily on first send.
  if (chat.currentConvId) {
    await chat.selectConversation(chat.currentConvId)
  }
})

async function onSend(text: string) {
  try {
    await chat.ask(text)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '发送失败')
  }
}
</script>

<template>
  <div class="chat-view">
    <header class="chat-header">
      <div class="title">💬 {{ currentTitle }}</div>
      <el-button
        type="primary"
        plain
        :icon="Plus"
        @click="chat.newConversation()"
      >新建对话</el-button>
    </header>

    <ChatWindow
      :messages="chat.messages"
      :active-turn="chat.activeTurn"
      :streaming="chat.streaming"
    />

    <div v-if="!hasSelection && !chat.streaming" class="chat-empty">
      <el-empty description="输入一个问题就会自动开始新对话">
        <el-button type="primary" :icon="Plus" @click="chat.newConversation()">新建对话</el-button>
      </el-empty>
    </div>

    <ChatInput
      :streaming="chat.streaming"
      @send="onSend"
      @stop="chat.stopAsk()"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  padding: 14px 24px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-header .title {
  font-size: 16px;
  font-weight: 600;
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
