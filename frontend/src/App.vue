<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const chat = useChatStore()
const auth = useAuthStore()

const isLoginPage = computed(() => route.name === 'login')

onMounted(async () => {
  if (!isLoginPage.value) {
    try { await chat.loadConversations() } catch {}
  }
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  auth.logout()
  router.replace('/login')
}

async function handleDeleteConv(id: string, title: string) {
  try {
    await ElMessageBox.confirm(`确定要删除对话「${title}」吗？关联的消息也会一起删除。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await chat.deleteConversation(id)
  // 删的是当前正在看的 → 直接清空状态，不自动造新的
  if (chat.currentConvId === null && route.name === 'chat') {
    // 让 ChatView 知道：没有选中任何对话，它会显示空态提示
    // ask() 里会在首次提问时按需 newConversation()
  }
}
</script>

<template>
  <!-- Login page — no sidebar, no topbar -->
  <router-view v-if="isLoginPage" />

  <!-- App shell for authenticated pages -->
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-header">🤖 AIpt 知识库</div>

      <div class="sidebar-label">导航</div>
      <router-link
        to="/chat"
        class="sidebar-item"
        :class="{ active: route.name === 'chat' }"
      >💬 智能问答</router-link>
      <router-link
        to="/documents"
        class="sidebar-item"
        :class="{ active: route.name === 'documents' }"
      >📚 知识库管理</router-link>

      <div class="sidebar-label">会话历史</div>
      <div
        v-for="c in chat.conversations"
        :key="c.id"
        class="sidebar-item conv-item"
        :class="{ active: chat.currentConvId === c.id }"
        @click="async () => { await chat.selectConversation(c.id); router.push('/chat') }"
      >
        <span class="conv-title">{{ c.title }}</span>
        <el-icon
          class="conv-del"
          title="删除"
          @click.stop="handleDeleteConv(c.id, c.title)"
        ><Delete /></el-icon>
      </div>
    </aside>

    <section class="main">
      <header class="topbar">
        <div class="topbar-title">{{ route.meta.title ?? 'AIpt' }}</div>
        <div class="topbar-user">
          <el-dropdown trigger="click">
            <button class="user-chip">
              <span class="avatar">{{ (auth.user?.display_name ?? auth.user?.username ?? '?').slice(0, 1).toUpperCase() }}</span>
              <span class="username">{{ auth.user?.display_name ?? auth.user?.username ?? '未登录' }}</span>
              <el-icon><CaretBottom /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  ID: {{ auth.user?.id }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="main-area">
        <router-view />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 48px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
  flex-shrink: 0;
}

.topbar-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.topbar-user {
  display: flex;
  align-items: center;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border: 1px solid #e4e7ed;
  border-radius: 20px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #303133;
  transition: border-color 0.2s;
}

.user-chip:hover {
  border-color: #409eff;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.username {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-area {
  flex: 1;
  overflow: hidden;
}

/* --- conversation item with delete button --- */
.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-del {
  opacity: 0;
  color: #94a3b8;
  font-size: 14px;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
}

.conv-item:hover .conv-del,
.conv-item.active .conv-del {
  opacity: 1;
}

.conv-del:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
}
</style>
