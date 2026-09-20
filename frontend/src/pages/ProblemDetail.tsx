import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useMeta } from '../App'
import { useAsync } from '../components/useAsync'
import {
  Bullets,
  DifficultyBadge,
  ErrorBox,
  Prose,
  Spinner,
  formatMinutes,
} from '../components/ui'
import { ApiError, api } from '../lib/api'
import type { CodeReview } from '../lib/types'

function ReviewPanel({ review }: { review: CodeReview }) {
  const allPassed = review.executed && review.tests_passed === review.tests_total
  return (
    <div className="card">
      <div className="card-title">
        <h2>Revisione</h2>
        {review.ai_generated && <span className="badge accent">AI</span>}
      </div>

      {review.executed && (
        <div className={`alert ${allPassed ? 'info' : 'error'}`}>
          {review.tests_passed}/{review.tests_total} test superati
        </div>
      )}

      {review.verdict && (
        <p>
          <strong>{review.verdict}</strong>
        </p>
      )}
      {review.correctness && (
        <>
          <h3>Correttezza</h3>
          <Prose text={review.correctness} />
        </>
      )}
      {review.complexity && (
        <>
          <h3>Complessità</h3>
          <p>{review.complexity}</p>
        </>
      )}

      {review.outcomes.length > 0 && (
        <>
          <h3>Dettaglio dei test</h3>
          <ul className="list-reset">
            {review.outcomes.map((outcome, i) => (
              <li key={i} className="row" style={{ marginBottom: 5 }}>
                <span className={`badge ${outcome.passed ? 'ok' : 'ko'}`}>
                  {outcome.passed ? 'ok' : 'ko'}
                </span>
                <span className="small">{outcome.name}</span>
                {!outcome.passed && (
                  <span className="faint">
                    {outcome.error || `atteso ${outcome.expected}, ottenuto ${outcome.actual}`}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <Bullets items={review.strengths} title="Punti di forza" />
      <Bullets items={review.improvements} title="Da migliorare" />
      {review.interview_notes && (
        <>
          <h3>Come lo vedrebbe un intervistatore</h3>
          <Prose text={review.interview_notes} />
        </>
      )}
    </div>
  )
}

export default function ProblemDetail() {
  const { problemId = '' } = useParams()
  const meta = useMeta()
  const { data, loading, error, reload } = useAsync(() => api.getProblem(problemId), [problemId])

  const [code, setCode] = useState('')
  const [review, setReview] = useState<CodeReview | null>(null)
  const [busy, setBusy] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [hintsShown, setHintsShown] = useState(0)
  const [solution, setSolution] = useState('')

  useEffect(() => {
    if (data) setCode(data.problem.starter_code)
  }, [data])

  if (loading) return <Spinner />
  if (error) return <div className="container"><ErrorBox error={error} onRetry={reload} /></div>
  if (!data) return null

  const problem = data.problem

  async function submit() {
    setBusy(true)
    setSubmitError('')
    try {
      const response = await api.submitCode(problemId, code)
      setReview(response.review)
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  async function reveal() {
    if (!confirm('Vuoi davvero vedere la soluzione? Prova prima con tutti i suggerimenti.')) return
    const response = await api.getSolution(problemId)
    setSolution(response.solution)
  }

  return (
    <main className="container wide">
      <div className="page-header row between">
        <div>
          <h1>{problem.title}</h1>
          <p>
            {formatMinutes(problem.estimated_minutes)}
            {problem.target_complexity && ` · obiettivo: ${problem.target_complexity}`}
          </p>
        </div>
        <div className="row">
          <DifficultyBadge level={problem.difficulty} />
          <Link className="btn sm" to="/coding">
            Tutti i problemi
          </Link>
        </div>
      </div>

      <div className="grid cols-2">
        <div>
          <div className="card">
            <h2>Consegna</h2>
            <Prose text={problem.statement} />
            {problem.examples.length > 0 && (
              <>
                <h3>Esempi</h3>
                <pre>{problem.examples.join('\n')}</pre>
              </>
            )}
            {problem.topic_ids.length > 0 && (
              <div className="faint">
                Argomenti:{' '}
                {problem.topic_ids.map((id, i) => (
                  <span key={id}>
                    {i > 0 && ', '}
                    <Link to={`/knowledge/${id}`}>{id}</Link>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">
              <h2>Suggerimenti</h2>
              <span className="badge">
                {hintsShown}/{problem.hints.length}
              </span>
            </div>
            {problem.hints.slice(0, hintsShown).map((hint, i) => (
              <p key={i} className="small">
                <strong>{i + 1}.</strong> {hint}
              </p>
            ))}
            <div className="row">
              {hintsShown < problem.hints.length && (
                <button className="sm" onClick={() => setHintsShown((n) => n + 1)}>
                  Mostra il prossimo
                </button>
              )}
              <button className="ghost sm" onClick={reveal}>
                Vedi la soluzione
              </button>
            </div>
            {solution && <pre style={{ marginTop: 12 }}>{solution}</pre>}
          </div>
        </div>

        <div>
          <div className="card">
            <div className="card-title">
              <h2>La tua soluzione</h2>
              <span className="badge">Python</span>
            </div>
            <textarea
              className="code-editor"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              spellCheck={false}
              aria-label="Editor della soluzione"
            />
            {submitError && <ErrorBox error={submitError} />}
            <div className="row between" style={{ marginTop: 12 }}>
              <span className="faint">
                {meta?.code_execution_enabled
                  ? 'I test verranno eseguiti sul server.'
                  : "Esecuzione disattivata: la soluzione viene valutata senza eseguirla."}
              </span>
              <button className="primary" onClick={submit} disabled={busy || !code.trim()}>
                {busy && <span className="spinner" />} Invia
              </button>
            </div>
          </div>

          {review && <ReviewPanel review={review} />}
        </div>
      </div>
    </main>
  )
}
