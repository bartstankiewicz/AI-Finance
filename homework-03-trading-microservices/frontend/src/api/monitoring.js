import { getJson } from './http.js'

const BASE = '/api/monitoring'

export const getServiceStatus = () => getJson(`${BASE}/status`)

export const openStatusStream = () => new EventSource(`${BASE}/stream`)
