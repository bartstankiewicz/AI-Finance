import { useEffect, useRef, useState } from 'react'

const FLUSH_INTERVAL_MS = 250

// status: CONNECTING -> CONNECTED; on error RECONNECTING (EventSource retries itself) or CLOSED (gave up).
// Events are buffered and passed to onEvents(batch) every FLUSH_INTERVAL_MS: one render per burst, not per event.
export default function useSseStream(openSource, { onEvents, onOpen }) {
  const [status, setStatus] = useState('CONNECTING')

  // Latest callbacks without reopening the stream when they change
  const handlers = useRef({ onEvents, onOpen })
  useEffect(() => {
    handlers.current = { onEvents, onOpen }
  })

  useEffect(() => {
    const source = openSource()
    let buffer = []
    let timer = null

    const flush = () => {
      timer = null
      const batch = buffer
      buffer = []
      handlers.current.onEvents(batch)
    }

    source.onopen = () => {
      setStatus('CONNECTED')
      handlers.current.onOpen?.()
    }
    source.onmessage = (message) => {
      buffer.push(JSON.parse(message.data))
      timer ??= setTimeout(flush, FLUSH_INTERVAL_MS)
    }
    source.onerror = () => setStatus(source.readyState === EventSource.CLOSED ? 'CLOSED' : 'RECONNECTING')

    return () => {
      clearTimeout(timer)
      source.close()
    }
  }, [openSource])

  return status
}
