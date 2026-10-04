import { useState } from 'react'
import useSseStream from '../../hooks/useSseStream.js'
import { openValuationStream } from '../../api/pricing.js'

// Latest valuation per symbol; pricing-service sends one event per trade in bursts, so batching matters here
export default function useValuationStream() {
  const [latestBySymbol, setLatestBySymbol] = useState({})

  const status = useSseStream(openValuationStream, {
    onEvents: (valuations) =>
      setLatestBySymbol((prev) => ({ ...prev, ...Object.fromEntries(valuations.map((v) => [v.symbol, v])) })),
  })

  return { latestBySymbol, status }
}
