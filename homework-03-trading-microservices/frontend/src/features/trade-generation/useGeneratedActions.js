import { useState } from 'react'
import useSseStream from '../../hooks/useSseStream.js'
import { openGeneratedActionsStream } from '../../api/tradeGeneration.js'

// Matches RECENT_ACTIONS replayed by the backend
const MAX_ACTIONS = 50

// Newest first; replay after reconnect overlaps with what we have, so merge by client_request_id
export default function useGeneratedActions() {
  const [actions, setActions] = useState([])

  const { status, lastEventAt } = useSseStream(openGeneratedActionsStream, {
    onEvents: (batch) =>
      setActions((prev) => {
        const seen = new Set(prev.map((a) => a.client_request_id))
        const fresh = batch.filter((a) => !seen.has(a.client_request_id)).reverse()
        return fresh.length ? [...fresh, ...prev].slice(0, MAX_ACTIONS) : prev
      }),
  })

  return { actions, status, lastEventAt }
}
