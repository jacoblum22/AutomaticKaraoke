import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Optional: add ?smoke=1 to URL in dev to run API smoke test in console
if (import.meta.env.DEV && new URLSearchParams(window.location.search).has("smoke")) {
  void import("./mocks/smokeTest").then((m) => m.runMockSmokeTest());
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
