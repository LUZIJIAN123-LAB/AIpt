/* Shared TypeScript interfaces — mirror the backend /api/v1 response shapes. */

// --- generic envelope ---
export interface ApiEnvelope<T> {
  code: 'OK' | string
  message: string
  data: T
}
export interface ErrorEnvelope {
  code: string
  message: string
  detail?: unknown
}

// --- document ---
export interface DocumentItem {
  id: string
  filename: string
  file_type: string
  parse_status: string
  chunk_count?: number
  title?: string | null
  created_at?: string
}
export interface DocumentChunk {
  index: number
  content: string
  chunk_type: string
  start_offset?: number | null
  end_offset?: number | null
}
export interface DocumentDetail extends DocumentItem {
  chunks: DocumentChunk[]
}
export interface DocumentListResponse {
  items: DocumentItem[]
  total: number
  page: number
  page_size: number
}

// --- conversation / message ---
export interface ConversationItem {
  id: string
  title: string
  created_by: string | null
  message_count: number
  created_at: string
}
export interface MessageItem {
  id: string
  role: 'system' | 'user' | 'assistant'
  content: string
  rag_sources?: RagSource[] | null
  rewritten_query?: string | null
  created_at: string
}
export interface ConversationDetail extends ConversationItem {
  messages: MessageItem[]
}
export interface ConversationListResponse {
  items: ConversationItem[]
  total: number
  page: number
  page_size: number
}

// --- RAG sources (returned both by /search and SSE "source" events) ---
export interface RagSource {
  content: string
  document_id: string
  document_filename: string
  chunk_index: number
  vector_score?: number
  bm25_score?: number
  final_score: number
  source?: string
}

// --- ask / SSE ---
export interface AskRequest {
  query: string
  conversation_id?: string | null
  top_k?: number
  stream?: boolean
}

// SSE event payloads (each `event:` type has its own data shape)
export type SseEvent =
  | { type: 'start'; data: { query: string; query_used?: string; top_k: number; source_count?: number } }
  | { type: 'rewrite'; data: { rewritten_query: string } }
  | { type: 'source'; data: RagSource }
  | { type: 'generating'; data: { content: string } }
  | { type: 'usage'; data: { prompt_tokens?: number; completion_tokens?: number } }
  | { type: 'done'; data: { first_token_ms?: number | null; total_ms?: number; retrieval_ms?: number; provider?: string; query_used?: string } }

// Full assembled chat turn — what Pinia stores
export interface ChatTurn {
  id: string
  query: string            // what user typed
  rewritten_query?: string // populated when multi-turn rewrite fired
  answer: string           // streamed content assembled
  sources: RagSource[]     // from "source" events
  done: boolean            // SSE "done" received
  first_token_ms?: number | null
  total_ms?: number
  error?: string
}
