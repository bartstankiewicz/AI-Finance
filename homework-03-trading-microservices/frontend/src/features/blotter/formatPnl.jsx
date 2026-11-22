import { formatNumber } from '../../utils/format.js'

export const formatPnl = (value) => (
  <span className={value < 0 ? 'pnl pnl--down' : 'pnl'}>{formatNumber(value)}</span>
)
