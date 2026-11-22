import React from 'react'
import ReactDOM from 'react-dom/client'
// Global styles first: component styles imported later must be able to override them
import './styles/main.scss'
import App from './App.jsx'
import { getStoredTheme } from './hooks/useTheme.js'

// Apply the saved theme before the first paint, so light users don't see a dark flash
document.documentElement.dataset.theme = getStoredTheme()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
