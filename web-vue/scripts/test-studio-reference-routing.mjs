import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const studio = readFileSync(resolve(root, 'src/views/Studio.vue'), 'utf8')
const composer = readFileSync(resolve(root, 'src/components/studio/StudioComposer.vue'), 'utf8')
const start = studio.indexOf('async function sendImageMessage')
const end = studio.indexOf('async function sendVideoMessage')
assert.notEqual(start, -1, 'sendImageMessage should exist')
assert.notEqual(end, -1, 'sendVideoMessage should exist')
assert.ok(end > start, 'sendVideoMessage should follow sendImageMessage')
const sendImageMessage = studio.slice(start, end)

assert.match(sendImageMessage, /imageTasksApi\.createEdit/, 'image messages with reference files should use the image edit task API')
assert.match(sendImageMessage, /files\.length\s*\?/, 'image task routing should branch on uploaded reference files')
assert.match(sendImageMessage, /imageTasksApi\.createGeneration/, 'image messages without reference files should keep using the generation task API')
assert.match(composer, /referenceStatusOutputLabel/, 'reference status should use a mode-aware output label')
assert.match(composer, /submitAriaLabel/, 'submit button aria label should be mode-aware')

console.log('studio reference routing ok')
