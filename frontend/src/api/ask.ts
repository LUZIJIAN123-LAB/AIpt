/* SSE ask client — fetch-based (NOT EventSource, because our ask endpoint is POST with JSON body).

Backend protocol (see app/api/v1/ask.py):
    event: start      { query, top_k, source_count }
    event: rewrite    { rewritten_query }
    event: source     RagSource
    event: generating { content }        ← streamed delta
    event: usage      { prompt_tokens, completion_tokens }
    event: done       { first_token_ms, total_ms, retrieval_ms, provider }

Usage:
    const abort = new AbortController()
    const stream = streamAsk({ query: '...', conversation_id: '...', top_k: 3 }, abort.signal)
    for await (const ev of stream) {
      if (ev.type === 'generating') append(ev.data.content)
      if (ev.type === 'done') finish(ev.data)
    }
*/
import type { AskRequest, SseEvent } from '@/types'

export async function* streamAsk(
  body: AskRequest,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent, void, unknown> {
  const res = await fetch('/api/v1/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  })

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '')
    throw new Error(`Ask SSE failed: ${res.status} ${text}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // Split on double-newline (SSE event separator).
    let sepIdx: number
    while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sepIdx)
      buffer = buffer.slice(sepIdx + 2)
      const ev = parseSse(raw)
      if (ev) yield ev
    }
  }

  // Flush tail.
  const tail = buffer.trim()
  if (tail) {
    const ev = parseSse(tail)
    if (ev) yield ev
  }
}

/* ---- Parser ---- */

function parseSse(raw: string): SseEvent | null {
  let event = ''
  const dataLines: string[] = []

  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (!event || dataLines.length === 0) return null

  let data: unknown
  try {
    data = JSON.parse(dataLines.join(''))
  } catch {
    return null
  }

  return { type: event, data } as SseEvent
}
