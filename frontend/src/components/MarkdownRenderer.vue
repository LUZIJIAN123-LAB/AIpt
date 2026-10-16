<script setup lang="ts">
/* Safe Markdown renderer — marked + DOMPurify + highlight.js.

  Used both for:
    1. Final answer (full content)
    2. Streaming partial content (append-only, safe per-frame — DOMPurify re-runs each render)
*/
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const props = withDefaults(defineProps<{
  content: string
  inline?: boolean
}>(), { inline: false })

marked.setOptions({
  gfm: true,
  breaks: true,
})
marked.use({
  renderer: {
    code({ text, lang }) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      const highlighted = hljs.highlight(text, { language }).value
      return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
    },
  },
})

const html = computed(() => {
  const raw = marked.parse(props.content, { async: false }) as string
  return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
})
</script>

<template>
  <div
    v-if="inline"
    class="md-content md-inline"
    v-html="html"
  />
  <div v-else class="md-content" v-html="html" />
</template>

<style scoped>
.md-inline :deep(p) { display: inline; }
</style>
