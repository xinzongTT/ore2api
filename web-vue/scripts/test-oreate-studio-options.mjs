import assert from 'node:assert/strict'

import {
  resolveImageSizePresets,
  supportsHighResolutionImageSizes,
} from '../src/config/imageSizes.ts'

for (const model of ['gpt-image-2', 'nano-banana-2', 'seedream', 'kling-image']) {
  assert.equal(supportsHighResolutionImageSizes(model), true, `${model} should support high resolution presets`)
  const resolutions = new Set(resolveImageSizePresets(model).map((preset) => preset.resolution))
  assert.equal(resolutions.has('2K'), true, `${model} should expose 2K`)
  assert.equal(resolutions.has('4K'), true, `${model} should expose 4K`)
}

console.log('oreate studio options ok')
