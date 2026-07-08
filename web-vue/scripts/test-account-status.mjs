import assert from 'node:assert/strict'

import { backendStatusToFrontend } from '../src/api/accountStatus.ts'

const historicalOreateAuthError = {
  status: '正常',
  source_type: 'oreateai',
  quota: 228,
  invalid_count: 1,
  last_refresh_error: 'token invalidated (/backend-api/me)',
}

const mapped = backendStatusToFrontend(historicalOreateAuthError)

assert.equal(mapped.status, 'ready')
assert.equal(mapped.enabled, true)
assert.equal(mapped.status_reason_code, '')
assert.equal(mapped.last_error_kind, '')

const invalid = backendStatusToFrontend({
  status: '异常',
  last_refresh_error: 'token invalidated (/backend-api/me)',
})

assert.equal(invalid.status, 'invalid')
assert.equal(invalid.status_reason_code, 'account_invalid')

console.log('account status mapping ok')
