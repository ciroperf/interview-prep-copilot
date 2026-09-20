/** Hook per caricare dati dall'API tenendo insieme stato, errore e ricarica. */

import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../lib/api'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string
  reload: () => void
  setData: (value: T) => void
}

export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    run()
      .then((value) => {
        if (alive) setData(value)
      })
      .catch((err: unknown) => {
        if (!alive) return
        setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [run, nonce])

  return {
    data,
    loading,
    error,
    reload: () => setNonce((n) => n + 1),
    setData,
  }
}
