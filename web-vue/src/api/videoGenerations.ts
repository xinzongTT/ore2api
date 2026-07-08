import apiClient from './client'

export const DEFAULT_VIDEO_MODEL = 'seedance-2.0-fast'
export const DEFAULT_VIDEO_DURATION = 5
export const DEFAULT_VIDEO_RATIO = '16:9'
export const DEFAULT_VIDEO_RESOLUTION = '480P'

export const VIDEO_DURATION_OPTIONS = [
  { label: '5 秒', value: 5 },
  { label: '10 秒', value: 10 },
]

export const VIDEO_RATIO_OPTIONS = [
  { label: '16:9', value: '16:9' },
  { label: '9:16', value: '9:16' },
  { label: '1:1', value: '1:1' },
  { label: '4:3', value: '4:3' },
  { label: '3:4', value: '3:4' },
  { label: '21:9', value: '21:9' },
]

export const VIDEO_RESOLUTION_OPTIONS = [
  { label: '480P', value: '480P' },
  { label: '720P', value: '720P' },
  { label: '1080P', value: '1080P' },
]

export interface VideoGenerationAsset {
  url?: string
  [key: string]: unknown
}

export interface VideoGenerationResponse {
  created?: number
  data: VideoGenerationAsset[]
}

export interface CreateVideoGenerationInput {
  prompt: string
  model?: string
  duration?: number
  aspectRatio?: string
  resolution?: string
  audio?: boolean
  image?: string
}

function cleanString(value: unknown, fallback = '') {
  const text = String(value ?? '').trim()
  return text || fallback
}

function normalizeDuration(value: unknown) {
  const duration = Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : DEFAULT_VIDEO_DURATION
  return duration >= 8 ? 10 : 5
}

function sizeFromRatio(ratio: string) {
  if (ratio === '9:16') return '576x1024'
  if (ratio === '1:1') return '1024x1024'
  if (ratio === '4:3') return '1024x768'
  if (ratio === '3:4') return '768x1024'
  if (ratio === '21:9') return '1344x576'
  return '1024x576'
}

function normalizeResponse(response: Partial<VideoGenerationResponse>): VideoGenerationResponse {
  return {
    created: Number.isFinite(Number(response.created)) ? Number(response.created) : undefined,
    data: Array.isArray(response.data) ? response.data : [],
  }
}

export const videoGenerationsApi = {
  create: async (input: CreateVideoGenerationInput) => {
    const aspectRatio = cleanString(input.aspectRatio, DEFAULT_VIDEO_RATIO)
    const response = await apiClient.post<Record<string, unknown>, VideoGenerationResponse>('/v1/video/generations', {
      prompt: input.prompt,
      model: cleanString(input.model, DEFAULT_VIDEO_MODEL),
      n: 1,
      size: sizeFromRatio(aspectRatio),
      duration: normalizeDuration(input.duration),
      aspect_ratio: aspectRatio,
      resolution: cleanString(input.resolution, DEFAULT_VIDEO_RESOLUTION),
      response_format: 'url',
      audio: Boolean(input.audio),
      image: cleanString(input.image),
    })
    return normalizeResponse(response)
  },
}
