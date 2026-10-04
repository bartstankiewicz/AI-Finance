import { getJson } from './http.js'

const BASE = '/api/trade-action'

export const getQueueStatus = () => getJson(`${BASE}/queue/status`)
