/* Chat store — conversations list + current conversation's messages + active ask stream. */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { conversationApi } from '@/api/conversation'
import { streamAsk } from '@/api/ask'
import type { ChatTurn, ConversationItem, MessageItem, RagSource } from '@/types'

export const useChatStore = defineStore('chat', () => {
  // --- conversations sidebar ---
  const conversations = ref<ConversationItem[]>([])
  const currentConvId = ref<string | null>(null)
  const messages = ref<MessageItem[]>([]) // populated from /conversations/{id}

  // --- active streaming state ---
  const activeTurn = ref<ChatTurn | null>(null)
  const streaming = ref(false)
  let abortCtrl: AbortController | null = null

  async function loadConversations() {
    const res = await conversationApi.list(1, 50)
    conversations.value = res.items
  }

  async function selectConversation(id: string) {
    currentConvId.value = id
    const detail = await conversationApi.get(id)
    messages.value = detail.messages
    // Ensure title sync if sidebar item missing
    const idx = conversations.value.findIndex((c) => c.id === id)
    if (idx >= 0) conversations.value[idx].title = detail.title
    else conversations.value.unshift({
      id: detail.id, title: detail.title,
      created_by: detail.created_by, message_count: detail.message_count,
      created_at: detail.created_at,
    })
  }

  async function newConversation(title?: string) {
    const c = await conversationApi.create(title)
    conversations.value.unshift(c)
    await selectConversation(c.id)
    return c.id
  }

  async function deleteConversation(id: string) {
    await conversationApi.remove(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentConvId.value === id) {
      currentConvId.value = null
      messages.value = []
    }
  }

  /** Stream an ask request and update activeTurn incrementally. */
  async function ask(query: string, top_k = 6) {
    if (streaming.value) return
    streaming.value = true
    abortCtrl = new AbortController()

    activeTurn.value = {
      id: crypto.randomUUID?.() ?? String(Date.now()),
      query,
      answer: '',
      sources: [],
      done: false,
    }

    try {
      const convId = currentConvId.value
      const finalConvId = convId ?? (await newConversation())

      for await (const ev of streamAsk({
        query,
        conversation_id: finalConvId,
        top_k,
        stream: true,
      }, abortCtrl.signal)) {
        if (!activeTurn.value) break

        if (ev.type === 'rewrite') {
          activeTurn.value.rewritten_query = ev.data.rewritten_query
        } else if (ev.type === 'source') {
          activeTurn.value.sources.push(ev.data as RagSource)
        } else if (ev.type === 'generating') {
          activeTurn.value.answer += ev.data.content
        } else if (ev.type === 'done') {
          activeTurn.value.first_token_ms = ev.data.first_token_ms
          activeTurn.value.total_ms = ev.data.total_ms
          activeTurn.value.done = true
        }
      }

      // Stream done. Clear activeTurn BEFORE reloading messages, otherwise
      // ChatWindow will render both the streaming bubble AND the server-persisted
      // assistant/user pair from messages → duplicate.
      activeTurn.value = null

      await selectConversation(finalConvId)
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        if (activeTurn.value) activeTurn.value.error = (e as Error).message
      }
    } finally {
      streaming.value = false
      abortCtrl = null
    }
  }

  function stopAsk() {
    abortCtrl?.abort()
  }

  return {
    conversations, currentConvId, messages, activeTurn, streaming,
    loadConversations, selectConversation, newConversation, deleteConversation,
    ask, stopAsk,
  }
})
