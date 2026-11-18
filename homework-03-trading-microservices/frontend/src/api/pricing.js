import { getJson } from './http.js'

const BASE = '/api/pricing'

export const getTradeValuations = (tradeId, limit = 20) =>
  getJson(`${BASE}/valuations/${encodeURIComponent(tradeId)}?limit=${limit}`).then((res) => res.valuations)

// Newest persisted valuation (pushed to DB in batches, so it can lag the stream by a few seconds)
export const getLatestValuation = () => getJson(`${BASE}/valuations?limit=1`).then((res) => res.valuations[0] ?? null)

export const openValuationStream = () => new EventSource(`${BASE}/valuation-stream`)

// { benchmark_symbol, book_metrics: [{ book_id, alpha, beta, last_book_return, last_benchmark_return, updated_at }] }
export const getBookMetrics = () => getJson(`${BASE}/book-metrics`)

// alpha is a mean return per observation (one benchmark tick) - shown in basis points
export const formatAlphaBp = (alpha) => `${(alpha * 10_000).toFixed(2)} bp`

// ~3x TICK_INTERVAL of market-data-service (pricing values active trades on each tick round); only meaningful while there are active trades
export const VALUATION_STALE_AFTER_MS = 30_000
