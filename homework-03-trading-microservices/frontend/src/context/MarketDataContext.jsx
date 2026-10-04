import { createContext, useContext, useEffect, useState } from 'react'
import useSseStream from '../hooks/useSseStream.js'
import { getHistory, getSnapshot, openStream } from '../api/marketData.js'

const HISTORY_LENGTH = 500

const MarketDataContext = createContext(null)

// seq = backend event_id: unique and increasing, also across service restarts
const toPoint = (tick) => ({ seq: tick.event_id, time: tick.timestamp.slice(11, 19), price: tick.spot })

// DB history and live ticks overlap (stream replays last ticks), so merge by seq
const mergePoints = (series, points) => {
  const bySeq = new Map([...series, ...points].map((p) => [p.seq, p]))
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq).slice(-HISTORY_LENGTH)
}

// pointsBySymbol: { symbol: [point, ...] }
const mergeHistory = (history, pointsBySymbol) => {
  const next = { ...history }
  for (const [symbol, points] of Object.entries(pointsBySymbol)) {
    next[symbol] = mergePoints(history[symbol] ?? [], points)
  }
  return next
}

// Lives above the pages (in App), so the stream and price history survive page switches
export function MarketDataProvider({ children }) {
  const [latest, setLatest] = useState({})   // symbol -> last tick
  const [history, setHistory] = useState({}) // symbol -> [{ seq, time, price }, ...]

  useEffect(() => {
    getSnapshot()
      .then((snapshot) => setLatest((prev) => ({ ...snapshot, ...prev })))
      .catch((err) => console.error('snapshot failed', err))
  }, [])

  const loadHistory = () =>
    getHistory(HISTORY_LENGTH)
      .then((stored) => {
        const points = Object.fromEntries(Object.entries(stored).map(([symbol, ticks]) => [symbol, ticks.map(toPoint)]))
        setHistory((prev) => mergeHistory(prev, points))
      })
      .catch((err) => console.error('history failed', err))

  const status = useSseStream(openStream, {
    // Also fires after an automatic reconnect (e.g. service restart) - refill what we missed
    onOpen: loadHistory,
    onEvents: (events) => {
      const ticks = events.filter((e) => e.event_type !== 'CURVE')
      if (ticks.length === 0) return

      const points = {}
      for (const tick of ticks) {
        if (tick.spot !== undefined) (points[tick.symbol] ??= []).push(toPoint(tick))
      }
      setLatest((prev) => ({ ...prev, ...Object.fromEntries(ticks.map((t) => [t.symbol, t])) }))
      setHistory((prev) => mergeHistory(prev, points))
    },
  })

  return (
    <MarketDataContext.Provider value={{ latest, history, status }}>
      {children}
    </MarketDataContext.Provider>
  )
}

export const useMarketData = () => useContext(MarketDataContext)
