import { getJson, postJson } from './http.js'

const BASE = '/api/trade-generation'

export const getGeneratorStatus = () => getJson(`${BASE}/status`)

export const startGenerator = () => postJson(`${BASE}/start`)

export const stopGenerator = () => postJson(`${BASE}/stop`)

export const generateOnce = () => postJson(`${BASE}/generate-once`)
