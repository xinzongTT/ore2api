export const DEFAULT_IMAGE_SIZE = 'auto'

export interface ImageSizeOption {
  label: string
  value: string
}

export type ImageSizeResolution = 'auto' | '1K' | '2K' | '4K'

export interface ImageSizePreset extends ImageSizeOption {
  ratio: string
  resolution: ImageSizeResolution
  width?: number
  height?: number
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b)
}

export function parseImageSize(value: string) {
  if (!value || value === DEFAULT_IMAGE_SIZE) return null
  const match = value.match(/^(\d+)\s*x\s*(\d+)$/i)
  if (!match) return null
  const width = Number(match[1])
  const height = Number(match[2])
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null
  return { width, height }
}

function imageResolutionTier(width: number, height: number): ImageSizeResolution {
  const maxEdge = Math.max(width, height)
  if (maxEdge >= 3840) return '4K'
  if (maxEdge > 1920) return '2K'
  return '1K'
}

export function formatImageSizeLabel(value: string, autoLabel = '自动') {
  if (!value || value === DEFAULT_IMAGE_SIZE) return autoLabel
  const parsed = parseImageSize(value)
  if (!parsed) return value
  const { width, height } = parsed
  const divisor = gcd(width, height)
  const ratio = `${width / divisor}:${height / divisor}`
  return [ratio, imageResolutionTier(width, height), `${width}x${height}`].join(' · ')
}

function createSizePreset(value: string, ratio: string, resolution: ImageSizeResolution): ImageSizePreset {
  const parsed = parseImageSize(value)
  return {
    label: formatImageSizeLabel(value),
    value,
    ratio,
    resolution,
    width: parsed?.width,
    height: parsed?.height,
  }
}

export const STANDARD_IMAGE_SIZE_PRESETS: ImageSizePreset[] = [
  { label: '自动', value: 'auto', ratio: 'auto', resolution: 'auto' },
  createSizePreset('1024x1024', '1:1', '1K'),
  createSizePreset('1024x1536', '2:3', '1K'),
  createSizePreset('1536x1024', '3:2', '1K'),
  createSizePreset('1024x1365', '3:4', '1K'),
  createSizePreset('1365x1024', '4:3', '1K'),
  createSizePreset('1088x1920', '9:16', '1K'),
  createSizePreset('1920x1088', '16:9', '1K'),
]

export const HIGH_RES_IMAGE_SIZE_PRESETS: ImageSizePreset[] = [
  createSizePreset('2048x2048', '1:1', '2K'),
  createSizePreset('2560x1440', '16:9', '2K'),
  createSizePreset('1440x2560', '9:16', '2K'),
  createSizePreset('3840x2160', '16:9', '4K'),
  createSizePreset('2160x3840', '9:16', '4K'),
]

export const IMAGE_SIZE_PRESETS: ImageSizePreset[] = [
  ...STANDARD_IMAGE_SIZE_PRESETS,
  ...HIGH_RES_IMAGE_SIZE_PRESETS,
]

export const STANDARD_IMAGE_SIZE_OPTIONS: ImageSizeOption[] = STANDARD_IMAGE_SIZE_PRESETS
export const HIGH_RES_IMAGE_SIZE_OPTIONS: ImageSizeOption[] = HIGH_RES_IMAGE_SIZE_PRESETS
export const IMAGE_SIZE_OPTIONS: ImageSizeOption[] = IMAGE_SIZE_PRESETS

const OREATE_HIGH_RES_IMAGE_MODELS = new Set([
  'gpt-image-2',
  'gpt-image',
  'nano-banana-2',
  'nano-banana',
  'seedream',
  'kling-image',
])

export function supportsHighResolutionImageSizes(model: string) {
  const value = String(model || '').trim().toLowerCase()
  if (OREATE_HIGH_RES_IMAGE_MODELS.has(value)) return true
  return value.includes('codex-gpt-image-2') || value.includes('gpt-image-2-codex')
}

export function resolveImageSizePresets(model: string): ImageSizePreset[] {
  return supportsHighResolutionImageSizes(model)
    ? IMAGE_SIZE_PRESETS
    : STANDARD_IMAGE_SIZE_PRESETS
}

export function resolveImageSizeOptions(model: string): ImageSizeOption[] {
  return resolveImageSizePresets(model)
}

export function isImageSizeSupportedByModel(size: string, model: string) {
  if (!size || size === DEFAULT_IMAGE_SIZE) return true
  return resolveImageSizeOptions(model).some((option) => option.value === size)
}

export function resolveImageRequestSize(size: string | undefined) {
  const value = String(size || DEFAULT_IMAGE_SIZE).trim()
  return value === DEFAULT_IMAGE_SIZE ? undefined : value
}

export function resolveImageRequestPreset(size: string | undefined, model: string) {
  const value = String(size || DEFAULT_IMAGE_SIZE).trim()
  const presets = resolveImageSizePresets(model)
  const preset = presets.find((item) => item.value === value)
    || presets.find((item) => item.value === DEFAULT_IMAGE_SIZE)
  return {
    size: resolveImageRequestSize(value),
    aspectRatio: preset && preset.ratio !== 'auto' ? preset.ratio : '1:1',
    resolution: preset && preset.resolution !== 'auto' ? preset.resolution : '1K',
  }
}
