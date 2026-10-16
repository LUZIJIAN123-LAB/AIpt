import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp)
}

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus)

// Rehydrate auth state from localStorage + validate token against backend.
// Silently clears local creds if expired — router guard will bounce to login.
import { useAuthStore } from '@/stores/auth'
void useAuthStore().fetchMe()

app.mount('#app')
