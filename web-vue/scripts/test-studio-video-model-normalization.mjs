import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const studio = readFileSync(resolve(root, 'src/views/Studio.vue'), 'utf8')

assert.match(studio, /function normalizeVideoModel\(/, 'Studio should normalize saved video model preferences')
assert.match(studio, /if\s*\(\s*model\s*===\s*'seedance-2\.0'\s*\)\s*return\s+DEFAULT_VIDEO_MODEL/, 'legacy seedance-2.0 should migrate to the verified default model')
assert.match(studio, /model:\s*normalizeVideoModel\(\s*getStringPreference\(preferenceKeys\.studioVideoModel,\s*DEFAULT_VIDEO_MODEL\)\s*\)/, 'video form should normalize stored model on load')
assert.match(studio, /videoModels\.value\.map\(normalizeVideoModel\)/, 'video model options should hide legacy seedance-2.0 by normalizing catalog values')
assert.match(studio, /const\s+normalizedVideoModel\s*=\s*normalizeVideoModel\(videoForm\.model\)/, 'sendVideoMessage should normalize the selected model before building the assistant message and request')
assert.match(studio, /model:\s*normalizedVideoModel/, 'video request should submit the normalized video model')
assert.match(studio, /videoForm\.model\s*=\s*normalized/, 'video model watcher should write normalized values back to form state')
assert.match(studio, /setStringPreference\(preferenceKeys\.studioVideoModel,\s*normalized\)/, 'video model watcher should persist the normalized model')

console.log('studio video model normalization ok')
