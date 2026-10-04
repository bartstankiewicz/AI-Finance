import './StatusBadge.scss'

// status: 'UP' | 'DOWN' | undefined (unknown)
export default function StatusBadge({ status, children }) {
  const modifier = (status ?? 'unknown').toLowerCase()
  return <span className={`status-badge status-badge--${modifier}`}>{children ?? status ?? '?'}</span>
}
