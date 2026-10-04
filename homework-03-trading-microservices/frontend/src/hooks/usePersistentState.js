import { useState } from 'react'

// useState that survives unmounting (page switches) and refresh, kept per browser tab
export default function usePersistentState(key, initialValue) {
  const [value, setValue] = useState(() => {
    const stored = sessionStorage.getItem(key)
    return stored === null ? initialValue : JSON.parse(stored)
  })

  const setPersistentValue = (next) => {
    setValue(next)
    sessionStorage.setItem(key, JSON.stringify(next))
  }

  return [value, setPersistentValue]
}
