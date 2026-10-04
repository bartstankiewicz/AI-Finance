import DataTable from '../../components/DataTable.jsx'
import DetailsList from '../../components/DetailsList.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import { formatAge, formatDateTime, secondsSince } from '../../utils/format.js'

// Expected per service in monitoring-service /status (missing fields render as "—"):
//   error_count, last_error { at, message }, streams { name: CONNECTED|DISCONNECTED }, history [{ at, from, to }]

function StreamBadges({ streams }) {
  const entries = Object.entries(streams)
  if (entries.length === 0) return 'No SSE connections'
  return (
    <span className="stream-badges">
      {entries.map(([name, state]) => (
        <StatusBadge key={name} status={state === 'CONNECTED' ? 'UP' : 'DOWN'}>{`${name}: ${state}`}</StatusBadge>
      ))}
    </span>
  )
}

const FIELDS = [
  { key: 'status', label: 'Status', format: (v) => <StatusBadge status={v} /> },
  {
    key: 'last_checked',
    label: 'Last check',
    format: (v) => `${formatDateTime(v)} (${formatAge(secondsSince(v))})`,
  },
  { key: 'response_time_ms', label: 'Response time', format: (v) => `${Math.round(v)} ms` },
  { key: 'error_count', label: 'Error counter' },
  { key: 'last_error', label: 'Last error', format: (e) => `${formatDateTime(e.at)} – ${e.message}` },
  { key: 'streams', label: 'SSE connections', format: (streams) => <StreamBadges streams={streams} /> },
]

const HISTORY_COLUMNS = [
  { key: 'at', label: 'Time', format: formatDateTime },
  { key: 'from', label: 'From', format: (v) => <StatusBadge status={v} /> },
  { key: 'to', label: 'To', format: (v) => <StatusBadge status={v} /> },
]

export default function ServiceDetails({ service }) {
  return (
    <>
      <DetailsList fields={FIELDS} data={service} />

      <h3 className="service-details__title">Status history</h3>
      {service.history
        ? <DataTable columns={HISTORY_COLUMNS} rows={[...service.history].reverse()} rowKey="at" />
        : <p className="muted">Not reported by monitoring-service yet.</p>}
    </>
  )
}
