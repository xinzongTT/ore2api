type BackendAccountLike = Record<string, any>

export type FrontendAccountStatus = {
  enabled: boolean
  status?: 'ready' | 'incomplete' | 'disabled' | 'invalid' | 'auto_disabled' | 'cooling' | 'backoff'
  status_reason?: string
  status_reason_code?:
    | 'disabled'
    | 'snlm0e_refresh_failed'
    | 'account_invalid'
    | 'pro_cooldown'
    | 'video_cooldown'
    | 'lane_backoff'
    | 'lane_degraded'
    | 'image_generation_unavailable'
    | 'image_degraded_to_fast'
    | 'parse_failure'
    | 'text_pending'
    | 'upstream_error'
    | 'image_quota_exhausted'
    | ''
  last_error_kind?:
    | 'quota_exhausted'
    | 'media_pending'
    | 'media_generation_unavailable'
    | 'media_degraded'
    | 'lane_degraded'
    | 'parse_failure'
    | 'text_pending'
    | 'upstream_error'
    | 'auth_invalid'
    | ''
}

const STATUS_DISABLED = '禁用'
const STATUS_LIMITED = '限流'
const STATUS_INVALID = '异常'

function cleanString(value: unknown): string {
  return String(value || '').trim()
}

export function backendStatusToFrontend(item: BackendAccountLike): FrontendAccountStatus {
  const rawStatus = cleanString(item.status)
  const quota = Number(item.quota ?? 0)
  const imageQuotaUnknown = Boolean(item.image_quota_unknown)
  const lastRefreshError = cleanString(item.last_refresh_error || item.last_token_refresh_error)

  if (rawStatus === STATUS_DISABLED || rawStatus.toLowerCase() === 'disabled') {
    return {
      enabled: false,
      status: 'disabled',
      status_reason: '账号已禁用',
      status_reason_code: 'disabled',
      last_error_kind: '',
    }
  }

  if (rawStatus === STATUS_INVALID || rawStatus.toLowerCase() === 'invalid') {
    return {
      enabled: true,
      status: 'invalid',
      status_reason: lastRefreshError || '账号鉴权异常',
      status_reason_code: 'account_invalid',
      last_error_kind: 'auth_invalid',
    }
  }

  if (rawStatus === STATUS_LIMITED) {
    return {
      enabled: true,
      status: 'cooling',
      status_reason: '远程确认图片额度已用完',
      status_reason_code: 'image_quota_exhausted',
      last_error_kind: 'quota_exhausted',
    }
  }

  return {
    enabled: true,
    status: 'ready',
    status_reason: !imageQuotaUnknown && quota <= 0 ? '本地额度待远程刷新，以请求前预检结果为准' : '',
    status_reason_code: '',
    last_error_kind: '',
  }
}
