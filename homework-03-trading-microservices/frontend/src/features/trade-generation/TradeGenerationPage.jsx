import { useEffect, useState } from 'react'
import DataTable from '../../components/DataTable.jsx'
import Panel from '../../components/Panel.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import StreamNotice from '../../components/StreamNotice.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import usePolling from '../../hooks/usePolling.js'
import {
  generateOnce,
  getGeneratorConfigs,
  getGeneratorStatus,
  startGenerator,
  stopGenerator,
  updateGeneratorConfigs,
} from '../../api/tradeGeneration.js'
import { formatNumber, formatTime, shortId } from '../../utils/format.js'
import useGeneratedActions from './useGeneratedActions.js'
import './TradeGenerationPage.scss'

const POLL_INTERVAL_MS = 2000

const CONFIG_FIELDS = [
  { key: 'frequency', label: 'Frequency [s]', min: 0.1, step: 'any' },
  { key: 'trade_out_probability', label: 'Trade Out Probability [%]', min: 0, max: 100, step: 'any' },
  { key: 'max_active_trades', label: 'Max Active Trades', min: 1, step: 1, placeholder: 'no limit' },
]

const toForm = (configs) =>
  Object.fromEntries(CONFIG_FIELDS.map(({ key }) => [key, configs[key] == null ? '' : String(configs[key])]))

// Empty inputs are sent as null so the backend keeps the current value
const toPayload = (form) =>
  Object.fromEntries(CONFIG_FIELDS.map(({ key }) => [key, form[key] === '' ? null : Number(form[key])]))

const errorMessage = (err) =>
  err.kind === 'unavailable' ? 'Trade Generation Service is down or unreachable.'
    : err.kind === 'validation' ? `Invalid config: ${err.message}`
      : `Backend error: ${err.message}`

const OUTCOME_TONES = { SENT: 'UP', FAILED: 'DOWN' }

// CLOSE_TRADE carries only trade_id + close_price, instrument fields stay empty
const ACTION_COLUMNS = [
  { key: 'pushed_at', label: 'Time', format: formatTime },
  { key: 'action_type', label: 'Action' },
  { key: 'outcome', label: 'Outcome', format: (v) => <StatusBadge status={OUTCOME_TONES[v]}>{v}</StatusBadge> },
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'symbol', label: 'Symbol' },
  { key: 'side', label: 'Side' },
  { key: 'quantity', label: 'Qty', numeric: true },
  {
    key: 'price',
    label: 'Price',
    numeric: true,
    render: (row) => {
      const price = row.trade_price ?? row.close_price
      return price == null ? '—' : formatNumber(price, 4)
    },
  },
  { key: 'book_id', label: 'Book Id', format: shortId },
  { key: 'trade_id', label: 'Trade Id', format: shortId },
  { key: 'error', label: 'Error' },
]

export default function TradeGenerationPage() {
  const { data: status, error: statusError, reload: reloadStatus } = usePolling(getGeneratorStatus, POLL_INTERVAL_MS)
  const actions = useGeneratedActions()
  const [actionError, setActionError] = useState(null)
  const [configForm, setConfigForm] = useState(null)
  const [configError, setConfigError] = useState(null)
  const [configSaved, setConfigSaved] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)

  const running = status?.status === 'running'

  const loadConfigs = async () => {
    setConfigError(null)
    try {
      const { configs } = await getGeneratorConfigs()
      setConfigForm(toForm(configs))
    } catch (err) {
      setConfigError(errorMessage(err))
    }
  }

  useEffect(() => {
    loadConfigs()
  }, [])

  const changeConfig = (key) => (e) => {
    setConfigSaved(false)
    setConfigForm((form) => ({ ...form, [key]: e.target.value }))
  }

  const saveConfigs = async (e) => {
    e.preventDefault()
    setConfigError(null)
    setConfigSaved(false)
    setSavingConfig(true)
    try {
      const { configs } = await updateGeneratorConfigs(toPayload(configForm))
      setConfigForm(toForm(configs))
      setConfigSaved(true)
    } catch (err) {
      setConfigError(errorMessage(err))
    } finally {
      setSavingConfig(false)
    }
  }

  const run = async (action) => {
    setActionError(null)
    try {
      await action()
      reloadStatus()
    } catch (err) {
      setActionError(errorMessage(err))
    }
  }

  return (
    <>
      <div className="panels">
        <Panel title="Trade Generator Action">
          <p className="muted">
            Status:{' '}
            {statusError
              ? <StatusBadge status="DOWN">UNREACHABLE</StatusBadge>
              : <StatusBadge status={status && (running ? 'UP' : 'DOWN')}>{status?.status.toUpperCase()}</StatusBadge>}
          </p>
          <div className="generator-actions">
            <button className="btn generator-actions__btn" disabled={!status || running} onClick={() => run(startGenerator)}>
              Start
            </button>
            <button className="btn generator-actions__btn" disabled={!status || !running} onClick={() => run(stopGenerator)}>
              Stop
            </button>
            <button className="btn generator-actions__btn" disabled={!status} onClick={() => run(generateOnce)}>
              Generate Once
            </button>
          </div>
          {actionError && <p className="error">{actionError}</p>}
        </Panel>

        <Panel title="Trade Generator Config">
          <form className="form" onSubmit={saveConfigs}>
            {CONFIG_FIELDS.map(({ key, label, min, max, step, placeholder }) => (
              <label key={key}>
                {label}
                <input
                  className="input"
                  type="number"
                  min={min}
                  max={max}
                  step={step}
                  placeholder={placeholder ?? '—'}
                  disabled={!configForm || savingConfig}
                  value={configForm?.[key] ?? ''}
                  onChange={changeConfig(key)}
                />
              </label>
            ))}
            <button type="submit" className="btn btn--primary" disabled={!configForm || savingConfig}>
              {savingConfig ? 'Saving…' : 'Save'}
            </button>
          </form>
          {configSaved && <p className="muted">Config saved.</p>}
          {configError && <p className="error">{configError}</p>}
        </Panel>
      </div>

      <section className="section">
        <h2>
          Generated Trade Actions
          <StreamStatusBadge status={actions.status} />
        </h2>
        <StreamNotice
          name="Trade action stream"
          status={actions.status}
          lastEventAt={actions.lastEventAt}
          impact="New generated actions are not shown"
        />
        <DataTable
          columns={ACTION_COLUMNS}
          rows={actions.actions}
          rowKey="client_request_id"
          loading={actions.status === 'CONNECTING'}
          emptyMessage={
            actions.status === 'RECONNECTING' ? 'Trade action stream unavailable'
              : 'No actions yet – press Start or Generate once.'
          }
        />
      </section>
    </>
  )
}
