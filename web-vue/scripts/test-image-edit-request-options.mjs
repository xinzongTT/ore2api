import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const imageTasks = readFileSync(resolve(root, 'src/api/imageTasks.ts'), 'utf8')
const start = imageTasks.indexOf('function createEditForm')
const end = imageTasks.indexOf('export function isImageTaskTerminal')
assert.notEqual(start, -1, 'createEditForm should exist')
assert.notEqual(end, -1, 'isImageTaskTerminal should follow createEditForm')
const createEditForm = imageTasks.slice(start, end)

assert.match(createEditForm, /resolveImageRequestPreset/, 'image edit requests should resolve size presets')
assert.match(createEditForm, /form\.append\('aspect_ratio',\s*preset\.aspectRatio\)/, 'image edit requests should send aspect_ratio')
assert.match(createEditForm, /form\.append\('resolution',\s*preset\.resolution\)/, 'image edit requests should send resolution')

console.log('image edit request options ok')
