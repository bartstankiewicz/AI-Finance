import { getJson } from './http.js'

const BASE = '/api/market-data'

export const getSnapshot = () => getJson(`${BASE}/snapshot`)

// { symbol: [{ event_id, timestamp, spot }, ...] } - persisted ticks, oldest first
export const getHistory = (limit) => getJson(`${BASE}/history?limit=${limit}`)

export const openStream = () => new EventSource(`${BASE}/stream`)
