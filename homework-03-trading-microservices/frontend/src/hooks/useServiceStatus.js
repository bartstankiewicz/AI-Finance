import { useState } from 'react'
import useSseStream from './useSseStream.js'
import { openStatusStream } from '../api/monitoring.js'

const SERVICES = [
  { id: 'market-data-service', label: 'Market Data' },
  { id: 'pricing-service', label: 'Pricing' },
  { id: 'monitoring-service', label: 'Monitoring' },
  { id: 'blotter-service', label: 'Blotter' },
  { id: 'books-service', label: 'Books' },
  { id: 'trade-action-service', label: 'Trade Action' },
  { id: 'trade-generation-service', label: 'Trade Generator' },
]

// Each SSE event is a full snapshot, so only the newest one in a batch matters
const STREAM_TO_STATUS = { CONNECTED: 'UP', RECONNECTING: 'DOWN', CLOSED: 'DOWN' }

// [{ id, label, status, response_time_ms, ... }] for every known service
export default function useServiceStatus() {
  const [snapshot, setSnapshot] = useState({})
  const streamStatus = useSseStream(openStatusStream, { onEvents: (batch) => setSnapshot(batch.at(-1)) })

  // Without a live stream the last snapshot is stale, so show only monitoring-service itself
  const statuses = {
    ...(streamStatus === 'CONNECTED' ? snapshot : {}),
    'monitoring-service': { status: STREAM_TO_STATUS[streamStatus] },
  }
  return SERVICES.map((service) => ({ ...service, ...statuses[service.id] }))
}
