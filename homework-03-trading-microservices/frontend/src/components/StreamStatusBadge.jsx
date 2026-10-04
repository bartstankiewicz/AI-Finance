import StatusBadge from './StatusBadge.jsx'

// useSseStream status -> badge tone + label
const BADGES = {
  CONNECTING: { tone: undefined, label: 'CONNECTING' },
  CONNECTED: { tone: 'UP', label: 'LIVE' },
  RECONNECTING: { tone: 'DOWN', label: 'RECONNECTING' },
  CLOSED: { tone: 'DOWN', label: 'CLOSED' },
}

export default function StreamStatusBadge({ status }) {
  const { tone, label } = BADGES[status]
  return <StatusBadge status={tone}>{label}</StatusBadge>
}
