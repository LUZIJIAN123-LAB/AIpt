<template>
  <div class="login-wrap">
    <div class="login-card">
      <h1 class="title">AIpt RAG</h1>
      <p class="subtitle">{{ activeTab === 'login' ? '登录你的账号' : '创建新账号' }}</p>

      <el-tabs v-model="activeTab" stretch class="auth-tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="admin" autocomplete="username" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="activeTab === 'login' ? '••••••' : '至少 6 位'"
            autocomplete="current-password"
          />
        </el-form-item>

        <el-form-item v-if="activeTab === 'register'" label="显示名（可选）" prop="display_name">
          <el-input v-model="form.display_name" placeholder="给自己起个昵称" />
        </el-form-item>

        <el-button
          type="primary"
          class="submit-btn"
          :loading="loading"
          native-type="submit"
        >
          {{ activeTab === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </el-form>

      <p v-if="errMsg" class="err">{{ errMsg }}</p>

      <p class="hint">
        预置账号：<code>admin / admin</code>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeTab = ref<'login' | 'register'>('login')
const loading = ref(false)
const errMsg = ref('')
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
  display_name: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '2-64 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
}

async function submit() {
  errMsg.value = ''
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    if (activeTab.value === 'login') {
      await auth.login(form.username.trim(), form.password)
    } else {
      await auth.register(
        form.username.trim(),
        form.password,
        form.display_name.trim() || undefined,
      )
    }
    ElMessage.success(activeTab.value === 'login' ? '登录成功' : '注册成功')
    // bounce back to where they were going, or /chat
    const redirect = (route.query.redirect as string) || '/chat'
    router.replace(redirect)
  } catch (e) {
    errMsg.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 12px;
  padding: 40px 36px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.title {
  margin: 0 0 4px;
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.subtitle {
  margin: 0 0 24px;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.auth-tabs {
  margin-bottom: 12px;
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
}

.err {
  color: #f56c6c;
  font-size: 13px;
  text-align: center;
  margin: 12px 0 0;
}

.hint {
  margin: 16px 0 0;
  text-align: center;
  color: #909399;
  font-size: 12px;
}

.hint code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
