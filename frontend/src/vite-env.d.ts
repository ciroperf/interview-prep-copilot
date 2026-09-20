/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base dell'API. Vuoto in sviluppo: ci pensa il proxy di Vite. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
