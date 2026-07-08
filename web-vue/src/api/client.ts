import axios, { type AxiosError, type AxiosInstance } from 'axios'

export const AUTH_TOKEN_STORAGE_KEY = 'oreate2api.adminKey'
const LEGACY_AUTH_TOKEN_STORAGE_KEY = 'chatgpt2api.adminKey'

export function getAuthToken() {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  if (token) return token
  const legacyToken = window.localStorage.getItem(LEGACY_AUTH_TOKEN_STORAGE_KEY) || ''
  if (legacyToken) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, legacyToken)
    window.localStorage.removeItem(LEGACY_AUTH_TOKEN_STORAGE_KEY)
  }
  return legacyToken
}

export function setAuthToken(token: string) {
  const cleanToken = token.trim()
  if (cleanToken) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, cleanToken)
    window.localStorage.removeItem(LEGACY_AUTH_TOKEN_STORAGE_KEY)
    return
  }
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  window.localStorage.removeItem(LEGACY_AUTH_TOKEN_STORAGE_KEY)
}

export function clearAuthToken() {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  window.localStorage.removeItem(LEGACY_AUTH_TOKEN_STORAGE_KEY)
}

type UnauthorizedHandler = () => void | Promise<void>

let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
})

let isRedirectingToLogin = false

function normalizeGenericServerError(message: string, status?: number) {
  const raw = String(message || '').trim()
  if (
    status
    && status >= 500
    && (
      !raw
      || /^internal server error$/i.test(raw)
      || /^request failed with status code 5\d\d$/i.test(raw)
    )
  ) {
    return `服务器内部错误（HTTP ${status}），请查看后端日志`
  }
  return raw || 'Request failed'
}

function extractErrorMessage(data: unknown, fallback: string, status?: number) {
  if (typeof data === 'string') return normalizeGenericServerError(data, status)
  if (!data || typeof data !== 'object') return normalizeGenericServerError(fallback, status)

  const payload = data as Record<string, any>
  const detail = payload.detail
  if (typeof detail === 'string') return normalizeGenericServerError(detail, status)
  if (detail && typeof detail === 'object') {
    if (typeof detail.error === 'string') return normalizeGenericServerError(detail.error, status)
    if (typeof detail.message === 'string') return normalizeGenericServerError(detail.message, status)
  }
  if (payload.error && typeof payload.error === 'object' && typeof payload.error.message === 'string') {
    return normalizeGenericServerError(payload.error.message, status)
  }
  if (typeof payload.error === 'string') return normalizeGenericServerError(payload.error, status)
  if (typeof payload.message === 'string') return normalizeGenericServerError(payload.message, status)
  return normalizeGenericServerError(fallback, status)
}

function routeAvailabilityHint(status: number | undefined, requestUrl: string) {
  if (status !== 404 && status !== 405) return ''
  if (requestUrl.includes('/api/register')) {
    return '后端未加载注册账号接口，请重启 oreate2api 后端并确认已部署最新代码'
  }
  if (requestUrl.includes('/api/accounts/import-cleanup')) {
    return '后端未加载导入异常清理接口，请重启 oreate2api 后端后再试'
  }
  return ''
}

apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    const status = error.response?.status
    const requestUrl = String(error.config?.url || '')
    const isAuthProbe = requestUrl.includes('/auth/status')
    const isLoginRequest = requestUrl.includes('/auth/login')

    if (status === 401 && !isLoginRequest && !isAuthProbe) {
      const onLoginPage = window.location.hash.startsWith('#/login')
      if (!onLoginPage && !isRedirectingToLogin) {
        isRedirectingToLogin = true
        clearAuthToken()
        Promise.resolve(unauthorizedHandler?.())
          .catch(() => {})
          .finally(() => {
            window.setTimeout(() => {
              isRedirectingToLogin = false
            }, 200)
          })
      }
    }

    const errorMessage = routeAvailabilityHint(status, requestUrl)
      || extractErrorMessage(error.response?.data, error.message, status)

    const wrapped = new Error(errorMessage || 'Request failed') as Error & {
      status?: number
      data?: unknown
    }
    wrapped.status = error.response?.status
    wrapped.data = error.response?.data
    return Promise.reject(wrapped)
  },
)

export default apiClient
