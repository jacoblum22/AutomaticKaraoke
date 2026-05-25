import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const apiKey = process.env.VITE_API_KEY ?? ''
  if (mode === 'production' && !apiKey) {
    console.warn(
      '[build] VITE_API_KEY is empty — production will get 401 from Modal API'
    )
  }

  return {
    plugins: [react()],
    // Explicit inject so Vercel build always bakes the key into the client bundle.
    define: {
      'import.meta.env.VITE_API_KEY': JSON.stringify(apiKey),
    },
  }
})
