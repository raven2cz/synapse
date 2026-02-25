/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** E2E test model override — set by Playwright webServer command */
  readonly VITE_E2E_MODEL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
