// kind: 'unavailable' (service down/unreachable), 'validation' (rejected input), 'not-found', 'error' (backend failure)
export class ApiError extends Error {
  constructor(message, { status = null, kind = 'error' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
  }
}

const kindOf = (status) => {
  if ([502, 503, 504].includes(status)) return 'unavailable'
  if (status === 400 || status === 422) return 'validation'
  if (status === 404) return 'not-found'
  return 'error'
}

// A hung backend must not hold one of the browser's ~6 connections per host forever
const REQUEST_TIMEOUT_MS = 15_000

async function request(method, url, body) {
  let res
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
  } catch (err) {
    const message = err.name === 'TimeoutError' ? 'Service not responding (timeout)' : 'Service unreachable'
    throw new ApiError(message, { kind: 'unavailable' })
  }
  // 204 has no body; Bottle's own 500 page is HTML, not JSON
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(data?.error ?? `${res.status} ${res.statusText}`, { status: res.status, kind: kindOf(res.status) })
  }
  return data
}

export const getJson = (url) => request('GET', url)
export const postJson = (url, body) => request('POST', url, body)
export const putJson = (url, body) => request('PUT', url, body)
export const deleteJson = (url) => request('DELETE', url)
