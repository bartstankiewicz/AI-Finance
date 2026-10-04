import { useEffect, useState } from 'react'
import { flushSync } from 'react-dom'

const STORAGE_KEY = 'theme'

export const getStoredTheme = () => (localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark')

// Theme = data-theme attribute on <html>; CSS variables in styles/_themes.scss do the rest
export default function useTheme() {
  const [theme, setTheme] = useState(getStoredTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (!document.startViewTransition || reduceMotion) {
      setTheme(next)
      return
    }

    // Browser snapshots the old page, runs the callback, then animates old -> new (see main.scss).
    // DOM must be updated synchronously inside the callback, hence flushSync.
    document.startViewTransition(() => {
      document.documentElement.dataset.theme = next
      flushSync(() => setTheme(next))
    })
  }

  return { theme, toggleTheme }
}
