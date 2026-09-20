/** Login Microsoft (Entra ID) con MSAL.
 *
 * Il flusso e' OAuth2 Authorization Code con PKCE, gestito interamente da MSAL:
 * l'app ottiene un access token per la propria API e lo allega come Bearer.
 * La validazione avviene nell'autenticazione integrata di Container Apps, prima
 * che la richiesta raggiunga il backend.
 *
 * Se le variabili non sono configurate l'app resta in modalita' codice di
 * accesso: e' lo stesso bundle, cambia solo la configurazione di build.
 */

import type { AccountInfo, PublicClientApplication } from '@azure/msal-browser'

const CLIENT_ID = import.meta.env.VITE_ENTRA_CLIENT_ID ?? ''
const TENANT_ID = import.meta.env.VITE_ENTRA_TENANT_ID ?? ''
const API_SCOPE = import.meta.env.VITE_ENTRA_API_SCOPE ?? ''

/** True se questo bundle e' stato compilato per il login Microsoft. */
export const entraEnabled = Boolean(CLIENT_ID && TENANT_ID && API_SCOPE)

let instance: PublicClientApplication | null = null
let initializing: Promise<PublicClientApplication> | null = null

async function getInstance(): Promise<PublicClientApplication> {
  if (instance) return instance
  // MSAL viene caricato solo quando serve: chi usa il codice di accesso non
  // paga il peso della libreria.
  if (!initializing) {
    initializing = (async () => {
      const msal = await import('@azure/msal-browser')
      const pca = new msal.PublicClientApplication({
        auth: {
          clientId: CLIENT_ID,
          authority: `https://login.microsoftonline.com/${TENANT_ID}`,
          // La slash finale non è un dettaglio: Entra ID pretende che un
          // redirect URI senza path finisca con "/" al momento della
          // registrazione, e poi confronta le due stringhe esattamente. Il
          // default di MSAL è window.location.origin, che la slash non ce
          // l'ha, e il login fallirebbe con AADSTS50011.
          redirectUri: `${window.location.origin}/`,
        },
        cache: {
          // sessionStorage e non localStorage: il token non sopravvive alla
          // chiusura del browser, che e' quello che si vuole su una postazione
          // condivisa.
          cacheLocation: 'sessionStorage',
        },
      })
      await pca.initialize()
      instance = pca
      return pca
    })()
  }
  return initializing
}

export async function currentAccount(): Promise<AccountInfo | null> {
  if (!entraEnabled) return null
  const pca = await getInstance()
  const active = pca.getActiveAccount()
  if (active) return active
  const [first] = pca.getAllAccounts()
  if (first) {
    pca.setActiveAccount(first)
    return first
  }
  return null
}

export async function login(): Promise<AccountInfo> {
  const pca = await getInstance()
  const result = await pca.loginPopup({ scopes: [API_SCOPE] })
  pca.setActiveAccount(result.account)
  return result.account
}

export async function logout(): Promise<void> {
  const pca = await getInstance()
  const account = pca.getActiveAccount() ?? undefined
  await pca.logoutPopup({ account })
}

/** Access token per l'API, o null se non c'è una sessione. */
export async function getAccessToken(): Promise<string | null> {
  if (!entraEnabled) return null
  const pca = await getInstance()
  const account = await currentAccount()
  if (!account) return null

  try {
    const result = await pca.acquireTokenSilent({ scopes: [API_SCOPE], account })
    return result.accessToken
  } catch (error) {
    // Token scaduto o consenso da rinnovare: serve l'interazione dell'utente.
    const msal = await import('@azure/msal-browser')
    if (error instanceof msal.InteractionRequiredAuthError) {
      const result = await pca.acquireTokenPopup({ scopes: [API_SCOPE], account })
      return result.accessToken
    }
    throw error
  }
}
