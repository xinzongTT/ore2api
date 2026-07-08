import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const debugCenter = readFileSync(resolve(root, 'src/views/DebugCenter.vue'), 'utf8')
const settings = readFileSync(resolve(root, 'src/views/Settings.vue'), 'utf8')

const availableStart = debugCenter.indexOf('const availableEndpoints = [')
const removedStart = debugCenter.indexOf('const removedEndpoints = [')
const scriptEnd = debugCenter.indexOf('</script>', removedStart)
assert.notEqual(availableStart, -1, 'availableEndpoints should exist')
assert.notEqual(removedStart, -1, 'removedEndpoints should exist')
assert.ok(removedStart > availableStart, 'removedEndpoints should follow availableEndpoints')
assert.notEqual(scriptEnd, -1, 'script block should close after removedEndpoints')
const availableSection = debugCenter.slice(availableStart, removedStart)
const removedSection = debugCenter.slice(removedStart, scriptEnd)

assert.match(availableSection, /\/v1\/images\/edits/, 'image edits endpoint should be listed as available')
assert.doesNotMatch(removedSection, /\/v1\/images\/edits/, 'image edits endpoint should not be listed as removed')
assert.doesNotMatch(settings, /ChatGPT 生图 SSE/, 'settings help text should use OreateAI branding')

console.log('debug center endpoints ok')
