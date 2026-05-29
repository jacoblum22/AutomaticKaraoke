import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  const apiKey = env.VITE_API_KEY ?? ''
  if (mode === 'production' && !apiKey) {
    console.warn(
      '[build] VITE_API_KEY is empty — production will get 401 from Modal API'
    )
  }

  return {
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    plugins: [react(), tailwindcss()],
    // Only override when set — empty define would wipe Vite's .env.local injection in dev.
    define: apiKey
      ? { 'import.meta.env.VITE_API_KEY': JSON.stringify(apiKey) }
      : {},
  }
})
