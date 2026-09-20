import { useRef, useState } from 'react'

import { useMeta } from '../App'
import { useAsync } from '../components/useAsync'
import { Bullets, ErrorBox, Prose, Spinner, Stat } from '../components/ui'
import { ApiError, api } from '../lib/api'
import type { CvReview } from '../lib/types'

function ReviewResult({ review }: { review: CvReview }) {
  const tone =
    review.overall_score >= 70 ? 'good' : review.overall_score >= 45 ? 'mid' : 'bad'

  return (
    <>
      <div className="card center">
        <div className={`score-ring ${tone}`}>{review.overall_score}</div>
        <h2 style={{ marginTop: 14 }}>Allineamento con la posizione</h2>
        {!review.ai_generated && (
          <p className="muted small">
            Analisi deterministica: copertura delle parole chiave e qualità delle voci.
            Con un modello AI configurato la revisione diventa molto più specifica.
          </p>
        )}
        {review.summary && <Prose text={review.summary} />}
      </div>

      {(review.matched_keywords.length > 0 || review.missing_keywords.length > 0) && (
        <div className="card">
          <h2>Parole chiave dell'annuncio</h2>
          <div className="grid cols-2">
            <div>
              <h3>Presenti nel CV ({review.matched_keywords.length})</h3>
              <div>
                {review.matched_keywords.map((keyword) => (
                  <span key={keyword} className="keyword-chip has">
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h3>Assenti ({review.missing_keywords.length})</h3>
              <div>
                {review.missing_keywords.map((keyword) => (
                  <span key={keyword} className="keyword-chip missing">
                    {keyword}
                  </span>
                ))}
              </div>
              <p className="faint">
                Aggiungile solo se corrispondono a esperienza reale: in colloquio ti verrà
                chiesto di raccontarle.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="grid cols-2">
        {review.strengths.length > 0 && (
          <div className="card">
            <Bullets items={review.strengths} title="Punti di forza" />
          </div>
        )}
        {review.weaknesses.length > 0 && (
          <div className="card">
            <Bullets items={review.weaknesses} title="Punti deboli" />
          </div>
        )}
      </div>

      {review.suggestions.length > 0 && (
        <div className="card">
          <Bullets items={review.suggestions} title="Cosa cambiare, in ordine di impatto" />
        </div>
      )}

      {review.bullet_rewrites.length > 0 && (
        <div className="card">
          <h2>Riscritture proposte</h2>
          {review.bullet_rewrites.map((rewrite, i) => (
            <div key={i} style={{ marginBottom: 18 }}>
              <div className="small muted" style={{ textDecoration: 'line-through' }}>
                {rewrite.original}
              </div>
              <div className="answer-box" style={{ marginTop: 6, marginBottom: 6 }}>
                {rewrite.improved}
              </div>
              {rewrite.why && <div className="faint">{rewrite.why}</div>}
            </div>
          ))}
        </div>
      )}

      {review.tailored_summary && (
        <div className="card">
          <h2>Profilo calibrato sull'annuncio</h2>
          <div className="answer-box">
            <Prose text={review.tailored_summary} />
          </div>
        </div>
      )}

      {review.likely_questions.length > 0 && (
        <div className="card">
          <Bullets items={review.likely_questions} title="Domande che il CV provoca" />
        </div>
      )}
    </>
  )
}

export default function CvPage() {
  const meta = useMeta()
  const jobs = useAsync(() => api.listJobs(), [])
  const [file, setFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState('')
  const [review, setReview] = useState<CvReview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const response = await api.reviewCv(file, jobId || undefined)
      setReview(response.review)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setReview(null)
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <main className="container" style={{ maxWidth: 860 }}>
      <div className="page-header row between">
        <div>
          <h1>Revisione del CV</h1>
          <p>
            Carica il CV e scegli l'annuncio: l'analisi confronta le due cose e dice cosa
            cambiare.
          </p>
        </div>
        {review && (
          <button className="sm" onClick={reset}>
            Nuova revisione
          </button>
        )}
      </div>

      {error && <ErrorBox error={error} />}

      {!review && (
        <form className="card" onSubmit={submit}>
          <div className="field">
            <label htmlFor="cv">File del CV *</label>
            <input
              id="cv"
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
            <div className="field-hint">
              PDF, DOCX, TXT o Markdown, fino a{' '}
              {meta ? Math.round(5) : 5} MB. Un PDF scansionato non contiene testo
              estraibile: esportalo come PDF testuale.
            </div>
          </div>

          <div className="field">
            <label htmlFor="job">Posizione target</label>
            <select id="job" value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">Valutazione generica</option>
              {jobs.data?.jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.role_title || 'Annuncio'} {job.company_name && `— ${job.company_name}`}
                </option>
              ))}
            </select>
            <div className="field-hint">
              Senza un annuncio la revisione resta generica: il valore sta nel confronto.
            </div>
          </div>

          <div className="alert info small">
            Il file non viene conservato a meno che non sia attivata esplicitamente
            l'archiviazione: di default viene letto, analizzato e scartato.
          </div>

          <div className="row end">
            <button className="primary" type="submit" disabled={!file || busy}>
              {busy && <span className="spinner" />}
              {busy ? 'Analisi in corso…' : 'Analizza il CV'}
            </button>
          </div>
        </form>
      )}

      {jobs.loading && !review && <Spinner label="Carico gli annunci…" />}
      {review && <ReviewResult review={review} />}

      {review && (
        <div className="grid cols-3" style={{ marginTop: 16 }}>
          <Stat value={review.matched_keywords.length} label="Keyword presenti" />
          <Stat value={review.missing_keywords.length} label="Keyword mancanti" />
          <Stat value={review.suggestions.length} label="Suggerimenti" />
        </div>
      )}
    </main>
  )
}
