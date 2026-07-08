export type DebugSearchSource = {
  title?: string
  url?: string
  snippet?: string
  source_type?: string
}

export type DebugSearchImageGroup = {
  queries?: string[]
  aspect_ratio?: string
  num_per_query?: number
}

export type DebugSearchResult = {
  conversation_id?: string
  status?: string
  answer?: string
  sources?: DebugSearchSource[]
  image_groups?: DebugSearchImageGroup[]
}

export type DebugChatMessage = {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export type DebugChatCompletion = {
  choices?: Array<{ message?: { role?: string; content?: string } }>
  [key: string]: unknown
}

export type DebugEditableKind = 'ppt' | 'psd'

export type DebugEditableFileTask = {
  id?: string
  taskId?: string
  status?: 'queued' | 'running' | 'success' | 'error' | string
  kind?: DebugEditableKind | string
  created_at?: string
  updated_at?: string
  elapsed_seconds?: number
  prompt_preview?: string
  error?: string
  result?: {
    conversation_id?: string
    primary_url?: string
    zip_url?: string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export type DebugEditableTasksResponse = {
  items: DebugEditableFileTask[]
  missing_ids?: string[]
}

export function createDebugClientTaskId(prefix = 'debug') {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function endpointForEditableKind(kind: DebugEditableKind) {
  return kind === 'psd' ? '/v1/psd/generations' : '/v1/ppt/generations'
}

function removedEndpoint<T>(path: string): Promise<T> {
  return Promise.reject(new Error(`${path} has been removed in this oreate-only build`))
}

export const debugApi = {
  search: async (_prompt: string) => removedEndpoint<DebugSearchResult>('/v1/search'),

  chat: async (_model: string, _messages: DebugChatMessage[], _reasoningEffort = '') => (
    removedEndpoint<DebugChatCompletion>('/v1/chat/completions')
  ),

  createEditableFileTask: async (kind: DebugEditableKind, _input: { prompt: string; base64_images?: string[] }) => (
    removedEndpoint<DebugEditableFileTask>(endpointForEditableKind(kind))
  ),

  listEditableFileTasks: async (_ids?: string[]) => removedEndpoint<DebugEditableTasksResponse>('/v1/editable-file-tasks'),
}
