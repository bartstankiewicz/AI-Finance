import DataTable from '../../components/DataTable.jsx'
import Panel from '../../components/Panel.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import ServiceStatusCards from '../../components/ServiceStatusCards.jsx'
import useServiceStatus from '../../hooks/useServiceStatus.js'
import usePersistentState from '../../hooks/usePersistentState.js'
import ServiceDetails from './ServiceDetails.jsx'
import './MonitoringPage.scss'

export default function MonitoringPage() {
  const rows = useServiceStatus()
  const [selectedId, setSelectedId] = usePersistentState('monitoring.selectedService', null)
  const selected = rows.find((row) => row.id === selectedId)

  const columns = [
    { key: 'label', label: 'Service' },
    { key: 'status', label: 'Status', format: (v) => <StatusBadge status={v} /> },
    { key: 'response_time_ms', label: 'Response Time', format: (v) => `${Math.round(v)} ms` },
    {
      key: 'details',
      label: 'Details',
      render: (row) => (
        <button
          className={row.id === selectedId ? 'btn btn--primary' : 'btn'}
          onClick={() => setSelectedId(row.id)}
        >
          Details
        </button>
      ),
    },
  ]

  return (
    <>
      <ServiceStatusCards services={rows} />

      <div className="panels">
        <DataTable columns={columns} rows={rows} rowKey="id" />

        <Panel title={selected ? `${selected.label} Service – Details` : 'Details'}>
          {selected ? <ServiceDetails service={selected} /> : <p className="muted">Click „Details” on a service.</p>}
        </Panel>
      </div>
    </>
  )
}
