import { useState } from 'react'
import useSseStream from '../../hooks/useSseStream.js'
import { openValuationStream, VALUATION_STALE_AFTER_MS } from '../../api/pricing.js'

// trade_id -> latest valuation + how it moves since the page was opened (updates, value changes, last PnL change)
export default function useValuationStream() {
  const [byTrade, setByTrade] = useState({})

  const { status, lastEventAt } = useSseStream(openValuationStream, {
    staleAfterMs: VALUATION_STALE_AFTER_MS,
    onEvents: (valuations) =>
      setByTrade((prev) => {
        const next = { ...prev }
        const receivedAt = Date.now()
        for (const v of valuations) {
          if (!v.trade_id) continue
          const old = next[v.trade_id]
          const changed = Boolean(old) && (v.fair_value !== old.fair_value || v.total_pnl !== old.total_pnl)
          next[v.trade_id] = {
            ...v,
            first_seen_at: old?.first_seen_at ?? receivedAt,
            updates: (old?.updates ?? 0) + 1,
            changes: (old?.changes ?? 0) + (changed ? 1 : 0),
            last_pnl_change: old ? v.total_pnl - old.total_pnl : null,
          }
        }
        return next
      }),
  })

  return { byTrade, status, lastEventAt }
}
