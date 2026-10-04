async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  // 204 has no body; Bottle's own 500 page is HTML, not JSON
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.error ?? `${res.status} ${res.statusText}`)
  return data
}

export const getJson = (url) => request('GET', url)
export const postJson = (url, body) => request('POST', url, body)
export const putJson = (url, body) => request('PUT', url, body)
export const deleteJson = (url) => request('DELETE', url)
