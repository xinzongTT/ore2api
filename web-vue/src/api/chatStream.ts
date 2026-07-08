import type { DebugChatMessage } from './debug'

export interface ChatStreamInput {
  model: string
  messages: DebugChatMessage[]
  reasoningEffort?: string
  signal?: AbortSignal
  onDelta?: (delta: string) => void
}

export interface ChatStreamResult {
  content: string
  rawChunks: number
}

export async function streamChatCompletion(_input: ChatStreamInput): Promise<ChatStreamResult> {
  throw new Error('/v1/chat/completions has been removed in this oreate-only build')
}
