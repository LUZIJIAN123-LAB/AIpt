import { createRouter, createWebHistory } from 'vue-router'

// Lazy-load auth store only inside guard to avoid circular deps
function _isLoggedIn(): boolean {
  // Fastest check: localStorage has token → trust it (frontend-side only;
  // backend validates JWT on every protected request anyway).
  return !!localStorage.getItem('aipt.auth.token')
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', requiresAuth: false },
    },
    {
      path: '/',
      redirect: '/chat',
      meta: { requiresAuth: true },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { title: '对话', requiresAuth: true },
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('@/views/DocumentsView.vue'),
      meta: { title: '知识库管理', requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  const logged = _isLoggedIn()
  const needsAuth = (to.meta.requiresAuth ?? true) as boolean

  if (to.path === '/login') {
    // Already logged in — no point showing login, bounce away
    if (logged) {
      const redirect = (to.query.redirect as string) || '/chat'
      return { path: redirect, replace: true }
    }
    return true
  }

  if (needsAuth && !logged) {
    // Kick to login, remember where we were going
    return {
      path: '/login',
      query: { redirect: to.fullPath },
      replace: true,
    }
  }

  return true
})

export default router
