const RAW_API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(
  /\/+$/,
  ''
)

function isTauriRuntime(): boolean {
  if (typeof window === 'undefined') return false
  return (
    '__TAURI_INTERNALS__' in window ||
    window.location.protocol === 'tauri:' ||
    window.location.hostname === 'tauri.localhost'
  )
}

function isLocalLoopbackUrl(url: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(url)
}

const USE_VITE_PROXY =
  import.meta.env.DEV &&
  !isTauriRuntime() &&
  import.meta.env.VITE_DISABLE_PROXY !== 'true' &&
  (!RAW_API_URL || isLocalLoopbackUrl(RAW_API_URL))

export const API_BASE_URL = USE_VITE_PROXY
  ? ''
  : RAW_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  data?: unknown

  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  const headers = new Headers(options.headers || {})
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(url, {
      credentials: options.credentials || 'include',
      ...options,
      headers,
    })
  } catch {
    throw new ApiError(
      'Não foi possível conectar ao servidor da API. Verifique se o backend está em execução.',
      0
    )
  }

  let responseData: unknown = null
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    try {
      responseData = await response.json()
    } catch {
      responseData = null
    }
  } else {
    try {
      responseData = await response.text()
    } catch {
      responseData = null
    }
  }

  if (!response.ok) {
    let detailMessage = `Erro na requisição (${response.status})`
    let hasJsonDetail = false

    if (
      responseData &&
      typeof responseData === 'object' &&
      'detail' in (responseData as Record<string, unknown>)
    ) {
      const detail = (responseData as Record<string, unknown>).detail
      if (typeof detail === 'string' && detail.trim()) {
        detailMessage = detail
        hasJsonDetail = true
      } else if (Array.isArray(detail) && detail.length > 0) {
        detailMessage = detail
          .map((d) =>
            d && typeof d === 'object' && 'msg' in d
              ? String((d as Record<string, unknown>).msg)
              : JSON.stringify(d)
          )
          .join('; ')
        hasJsonDetail = true
      } else if (detail != null) {
        detailMessage = JSON.stringify(detail)
        hasJsonDetail = true
      }
    }

    if (
      !hasJsonDetail &&
      (response.status === 502 || response.status === 503 || response.status === 504)
    ) {
      detailMessage =
        'Servidor da API indisponível no momento. Verifique se o backend e o banco de dados estão ativos.'
    }

    throw new ApiError(detailMessage, response.status, responseData)
  }

  return responseData as T
}
