import { createContext, useContext, useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'

import { ErrorBox, Spinner } from './components/ui'
import { ApiError, api, getAccessCode, setAccessCode } from './lib/api'
import type { Meta } from './lib/types'
import CodingPage from './pages/CodingPage'
import CvPage from './pages/CvPage'
import Dashboard from './pages/Dashboard'
import JobDetail from './pages/JobDetail'
import KnowledgePage from './pages/KnowledgePage'
import NewJob from './pages/NewJob'
import PlanPage from './pages/PlanPage'
import ProblemDetail from './pages/ProblemDetail'
import QuizPage from './pages/QuizPage'
import TopicDetail from './pages/TopicDetail'

const MetaContext = createContext<Meta | null>(null)

/** Configurazione dell'istanza (AI attiva, esecuzione codice, contenuti). */
export function useMeta(): Meta | null {
  return useContext(MetaContext)
}

function AccessGate({ onUnlock }: { onUnlock: () => void }) {
  const [code, setCode] = useState(getAccessCode())
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setChecking(true)
    setError('')
    setAccessCode(code.trim())
    try {
      // Una rotta protetta qualunque: serve solo a validare il codice.
      await api.categories()
      onUnlock()
    } catch (err) {
      setAccessCode('')
      setError(
        err instanceof ApiError && err.isAuth
          ? 'Codice di accesso errato.'
          : 'Impossibile contattare l’API.',
      )
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="container" style={{ maxWidth: 420, paddingTop: 80 }}>
      <div className="card">
        <h1>Interview Prep Copilot</h1>
        <p className="muted">Questa istanza è protetta da un codice di accesso.</p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="access-code">Codice di accesso</label>
            <input
              id="access-code"
              type="password"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
              autoComplete="current-password"
            />
          </div>
          {error && <div className="alert error">{error}</div>}
          <button className="primary" type="submit" disabled={!code.trim() || checking}>
            {checking && <span className="spinner" />} Entra
          </button>
        </form>
      </div>
    </div>
  )
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [locked, setLocked] = useState(false)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    api
      .meta()
      .then(async (value) => {
        if (!alive) return
        setMeta(value)
        if (value.access_code_required) {
          // /meta è pubblica: verifichiamo il codice su una rotta protetta.
          try {
            await api.categories()
            setLocked(false)
          } catch (err) {
            setLocked(err instanceof ApiError && err.isAuth)
          }
        }
        setError('')
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [nonce])

  if (loading) return <Spinner label="Connessione all'API…" />
  if (error) {
    return (
      <div className="container" style={{ maxWidth: 560, paddingTop: 64 }}>
        <ErrorBox error={error} onRetry={() => setNonce((n) => n + 1)} />
        <p className="muted small">
          Verifica che il backend sia in esecuzione e che <code>VITE_API_BASE_URL</code> punti
          all'indirizzo giusto.
        </p>
      </div>
    )
  }
  if (locked) return <AccessGate onUnlock={() => setNonce((n) => n + 1)} />

  return (
    <MetaContext.Provider value={meta}>
      <div className="app">
        <header className="topbar">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              🎯
            </span>
            <span>Interview Prep</span>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>
              Dashboard
            </NavLink>
            <NavLink to="/jobs/new">Nuovo annuncio</NavLink>
            <NavLink to="/knowledge">Argomenti</NavLink>
            <NavLink to="/coding">Coding</NavLink>
            <NavLink to="/quiz">Quiz</NavLink>
            <NavLink to="/cv">CV</NavLink>
          </nav>
          {meta && !meta.ai_enabled && (
            <span className="badge nowrap" title="Nessun modello configurato: l'app usa le euristiche deterministiche.">
              AI non attiva
            </span>
          )}
        </header>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs/new" element={<NewJob />} />
          <Route path="/jobs/:jobId" element={<JobDetail />} />
          <Route path="/plans/:planId" element={<PlanPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/knowledge/:topicId" element={<TopicDetail />} />
          <Route path="/coding" element={<CodingPage />} />
          <Route path="/coding/:problemId" element={<ProblemDetail />} />
          <Route path="/quiz" element={<QuizPage />} />
          <Route path="/quiz/:quizId" element={<QuizPage />} />
          <Route path="/cv" element={<CvPage />} />
          <Route
            path="*"
            element={
              <div className="container">
                <div className="empty">
                  <h3>Pagina non trovata</h3>
                  <Link to="/" className="btn">
                    Torna alla dashboard
                  </Link>
                </div>
              </div>
            }
          />
        </Routes>
      </div>
    </MetaContext.Provider>
  )
}
