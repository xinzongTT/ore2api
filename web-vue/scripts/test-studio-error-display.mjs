import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const messageList = readFileSync(resolve(root, 'src/components/studio/StudioMessageList.vue'), 'utf8')

assert.match(messageList, /displayErrorMessage:\s*string/, 'message view should carry the exact error text to render')
assert.match(messageList, /function messageErrorText\(/, 'message list should centralize image/video error text resolution')
assert.match(messageList, /messageErrorText\(message,\s*task\)/, 'buildMessageView should compute display error text from the message and task')
assert.match(messageList, /message\.displayErrorMessage\s*\|\|/, 'error card should prefer displayErrorMessage before generic fallback text')

const helperStart = messageList.indexOf('function messageErrorText(')
assert.notEqual(helperStart, -1, 'messageErrorText helper should exist')
const helperEnd = messageList.indexOf('\nfunction ', helperStart + 1)
const helper = messageList.slice(helperStart, helperEnd === -1 ? undefined : helperEnd)
assert.ok(helper.indexOf('message.error') < helper.indexOf('message.content'), 'message.error should have priority over message.content')
assert.ok(helper.indexOf('message.content') < helper.indexOf('taskPrimaryMessage(task)'), 'message.content should have priority over task primary message')

console.log('studio error display ok')
