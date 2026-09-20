/** Lacune del catalogo per un annuncio, con l'azione per colmarle. */

import { useState } from 'react'

import { useMeta } from '../App'
import { ApiError, api } from '../lib/api'
import type { TopicGap } from '../lib/types'
import { ErrorBox } from './ui'

export default function GapPanel({ jobId }: { jobId: string }) {
  const meta = useMeta()
  const [gaps, setGaps] = useState<TopicGap[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyTerm, setBusyTerm] = useState('')
  const [error, setError] = useState('')
  const [added, setAdded] = useState<Record<string, string>>({})

  async function analizza() {
    setLoading(true)
    setError('')
    try {
      const response = await api.findGaps(jobId)
      setGaps(response.gaps)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setLoading(false)
    }
  }

  async function aggiungi(gap: TopicGap) {
    setBusyTerm(gap.term)
    setError('')
    try {
      const { topic, question_count } = await api.createTopic({
        term: gap.term,
        job_id: jobId,
        num_questions: 3,
      })
      setAdded((prev) => ({
        ...prev,
        [gap.term]: `${topic.title} (${question_count} domande)`,
      }))
      setGaps((prev) =>
        prev ? prev.map((g) => (g.term === gap.term ? { ...g, covered: true } : g)) : prev,
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusyTerm('')
    }
  }

  const missing = gaps?.filter((g) => !g.covered) ?? []

  return (
    <div className="card">
      <div className="card-title">
        <h2>Copertura del catalogo</h2>
        <button className="sm" onClick={analizza} disabled={loading}>
          {loading && <span className="spinner" />}
          {gaps ? 'Ricontrolla' : 'Verifica'}
        </button>
      </div>
      <p className="muted small">
        Controlla quali competenze richieste dall'annuncio hanno già un argomento dedicato e
        quali no. Le lacune si possono colmare: l'argomento generato entra subito nei piani,
        nei quiz e nella ricerca.
      </p>

      {error && <ErrorBox error={error} />}

      {gaps && gaps.length === 0 && (
        <p className="muted small">
          Nessuna competenza specifica da valutare in questo annuncio.
        </p>
      )}

      {gaps && gaps.length > 0 && (
        <>
          <p className="small">
            {missing.length === 0
              ? 'Tutte le competenze rilevate hanno un argomento dedicato.'
              : `${missing.length} competenz${missing.length === 1 ? 'a' : 'e'} senza argomento dedicato.`}
          </p>
          <ul className="list-reset">
            {gaps.map((gap) => (
              <li key={gap.term} className="row between" style={{ padding: '8px 0' }}>
                <div style={{ minWidth: 0 }}>
                  <span className={`badge ${gap.covered ? 'ok' : 'ko'}`}>
                    {gap.covered ? 'coperto' : 'lacuna'}
                  </span>{' '}
                  <strong>{gap.term}</strong>{' '}
                  <span className="badge accent">{gap.importance}/5</span>
                  <div className="faint">
                    {added[gap.term]
                      ? `Aggiunto: ${added[gap.term]}`
                      : gap.best_topic_title
                        ? `Più vicino: ${gap.best_topic_title}`
                        : 'Nessun argomento correlato nel catalogo'}
                  </div>
                </div>
                {!gap.covered && (
                  <button
                    className="sm"
                    onClick={() => aggiungi(gap)}
                    disabled={Boolean(busyTerm) || !meta?.ai_enabled}
                    title={
                      meta?.ai_enabled
                        ? 'Genera un argomento dedicato e aggiungilo al catalogo'
                        : 'Serve un modello AI configurato'
                    }
                  >
                    {busyTerm === gap.term && <span className="spinner" />}
                    Aggiungi al catalogo
                  </button>
                )}
              </li>
            ))}
          </ul>
          {!meta?.ai_enabled && missing.length > 0 && (
            <div className="alert warn small">
              La generazione automatica richiede un modello AI configurato. Senza, puoi
              aggiungere un argomento scrivendone tu il contenuto dalla pagina Argomenti.
            </div>
          )}
        </>
      )}
    </div>
  )
}
