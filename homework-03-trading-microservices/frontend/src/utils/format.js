export const shortId = (id) => String(id).slice(0, 8)

export const formatNumber = (value, digits = 2) =>
  Number(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })

// Python services send naive UTC timestamps (no offset) - read them as UTC, not local time
export const parseTimestamp = (iso) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)

export const formatDateTime = (iso) => parseTimestamp(iso).toLocaleString()

export const formatTime = (iso) => parseTimestamp(iso).toLocaleTimeString()

export const secondsSince = (iso) => Math.max(0, Math.round((Date.now() - parseTimestamp(iso)) / 1000))

export const formatAge = (seconds) =>
  seconds < 60 ? `${seconds} s ago` : seconds < 3600 ? `${Math.floor(seconds / 60)} min ago` : `${Math.floor(seconds / 3600)} h ago`
