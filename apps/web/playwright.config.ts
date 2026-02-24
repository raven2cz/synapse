import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  retries: 1,
  reporter: [['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'uv run uvicorn apps.api.src.main:app --port 8000',
      cwd: '../../',
      port: 8000,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'pnpm dev',
      port: 5173,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
  projects: [
    {
      name: 'tier1',
      use: { ...devices['Desktop Chrome'] },
      grepInvert: /@live/,
      fullyParallel: true,
    },
    {
      name: 'tier2-live',
      use: { ...devices['Desktop Chrome'] },
      grep: /@live/,
      fullyParallel: false,
    },
  ],
})
