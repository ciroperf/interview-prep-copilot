/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base dell'API. Vuoto in sviluppo: ci pensa il proxy di Vite. */
  readonly VITE_API_BASE_URL?: string

  /** Login Microsoft. Se mancano, l'app usa il codice di accesso condiviso.
   *  I valori li stampa `terraform output entra_client_id` e affini. */
  readonly VITE_ENTRA_CLIENT_ID?: string
  readonly VITE_ENTRA_TENANT_ID?: string
  readonly VITE_ENTRA_API_SCOPE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
