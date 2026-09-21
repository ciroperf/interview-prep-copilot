import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useMeta } from '../App'
import { useAsync } from '../components/useAsync'
import {
  DifficultyBadge,
  Empty,
  ErrorBox,
  Spinner,
  TrackBadge,
  categoryLabel,
  formatMinutes,
} from '../components/ui'
import { ApiError, api } from '../lib/api'
import type { TopicDraft } from '../lib/types'

/** Aggiunta manuale di un argomento: funziona anche senza AI configurata. */
function ManualTopicForm({
  onCreated,
  onClose,
}: {
  onCreated: () => void
  onClose: () => void
}) {
  const [term, setTerm] = useState('')
  const [draft, setDraft] = useState<TopicDraft>({ title: '', summary: '' })
  const [keyPoints, setKeyPoints] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Il pulsante resta spento finche' i tre campi obbligatori non ci sono: piu'
  // onesto di lasciarlo attivo e far fallire la richiesta.
  const pronto = Boolean(term.trim() && draft.title.trim() && draft.summary.trim())

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.createTopic({
        term: term.trim(),
        num_questions: 0,
        draft: {
          ...draft,
          tags: [term.trim().toLowerCase()],
          key_points: keyPoints
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
        },
      })
      setTerm('')
      setDraft({ title: '', summary: '' })
      setKeyPoints('')
      onCreated()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card composer" onSubmit={submit}>
      <header className="composer-head">
        <div>
          <h2>Scrivi un argomento</h2>
          <p className="small muted">
            Entra subito nel catalogo, nei piani e nei quiz. I campi con * bastano: il resto
            puoi aggiungerlo dopo modificando il file YAML esportato.
          </p>
        </div>
        <button type="button" className="ghost sm" onClick={onClose}>
          Chiudi
        </button>
      </header>

      {error && <ErrorBox error={error} />}

      <div className="composer-body">
        <section className="composer-group">
          <h3>Identità</h3>
          <div className="grid cols-2">
            <div className="field">
              <label htmlFor="term">Termine *</label>
              <input
                id="term"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                placeholder="Kubernetes"
                required
              />
              <div className="field-hint">
                È la parola che gli annunci useranno per agganciarlo.
              </div>
            </div>
            <div className="field">
              <label htmlFor="title">Titolo *</label>
              <input
                id="title"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="Kubernetes per il colloquio"
                required
              />
              <div className="field-hint">Come comparirà nell&apos;elenco e nel piano.</div>
            </div>
          </div>
        </section>

        <section className="composer-group">
          <h3>Contenuto</h3>
          <div className="field">
            <label htmlFor="summary">Sintesi *</label>
            <textarea
              id="summary"
              rows={3}
              value={draft.summary}
              onChange={(e) => setDraft({ ...draft, summary: e.target.value })}
              placeholder="Cos'è e quale problema risolve, in 2-4 frasi."
              required
            />
          </div>
          <div className="field">
            <label htmlFor="points">Punti chiave</label>
            <textarea
              id="points"
              rows={5}
              value={keyPoints}
              onChange={(e) => setKeyPoints(e.target.value)}
              placeholder={'Uno per riga.\nQuello che un intervistatore si aspetta di sentire.'}
            />
            <div className="field-hint">{contaRighe(keyPoints)}</div>
          </div>
          <div className="field">
            <label htmlFor="answer">Risposta da dare al colloquio</label>
            <textarea
              id="answer"
              rows={4}
              value={draft.interview_answer ?? ''}
              onChange={(e) => setDraft({ ...draft, interview_answer: e.target.value })}
              placeholder="In prima persona, come la diresti a voce."
            />
            <div className="field-hint">
              È la sezione che conta di più: i compromessi espliciti, non la definizione.
            </div>
          </div>
        </section>
      </div>

      <footer className="composer-foot">
        <button type="button" className="ghost" onClick={onClose}>
          Annulla
        </button>
        <button className="primary" type="submit" disabled={busy || !pronto}>
          {busy && <span className="spinner" />} Aggiungi al catalogo
        </button>
      </footer>
    </form>
  )
}

/** Conta le righe non vuote: un promemoria discreto mentre si scrive. */
function contaRighe(testo: string): string {
  const n = testo.split('\n').filter((r) => r.trim()).length
  if (!n) return 'Uno per riga. Sei o più rendono la scheda davvero utile.'
  return n < 6 ? `${n} punti — sotto i sei la scheda resta magra.` : `${n} punti.`
}

export default function KnowledgePage() {
  const meta = useMeta()
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const categories = useAsync(() => api.categories(), [])
  const topics = useAsync(
    () => api.listTopics({ category: category || undefined, q: query || undefined }),
    [category, query],
  )
  const [exportBusy, setExportBusy] = useState(false)
  const [exportMsg, setExportMsg] = useState('')
  const [formOpen, setFormOpen] = useState(false)

  async function esporta() {
    setExportBusy(true)
    setExportMsg('')
    try {
      const data = await api.exportCustom()
      if (!data.count) {
        setExportMsg('Nessun argomento aggiunto da esportare.')
        return
      }
      for (const [name, content] of [
        ['topics_custom.yaml', data.topics_yaml],
        ['questions_custom.yaml', data.questions_yaml],
      ] as const) {
        const blob = new Blob([content], { type: 'text/yaml' })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = name
        link.click()
        URL.revokeObjectURL(link.href)
      }
      setExportMsg(
        `Scaricati ${data.count} argomenti e ${data.question_count} domande. ` +
          'Mettili in backend/app/content/ e committali per renderli permanenti.',
      )
    } catch (err) {
      setExportMsg(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setExportBusy(false)
    }
  }

  return (
    <main className="container">
      <div className="page-header row between">
        <div>
          <h1>Argomenti</h1>
          <p>
            {meta?.content.topics ?? 0} argomenti, {meta?.content.questions ?? 0} domande,{' '}
            {meta?.content.problems ?? 0} problemi di coding. Per studiare in ordine, parti dai{' '}
            <Link to="/percorsi">percorsi</Link>.
          </p>
        </div>
        <div className="row">
          <button className="sm" onClick={() => setFormOpen((v) => !v)}>
            {formOpen ? 'Chiudi' : '+ Scrivi un argomento'}
          </button>
          <button className="sm" onClick={esporta} disabled={exportBusy}>
            {exportBusy && <span className="spinner" />} Esporta aggiunti
          </button>
        </div>
      </div>

      {exportMsg && <div className="alert info small">{exportMsg}</div>}

      {/* Fuori dalla riga dell'intestazione: dentro, essendo un flex, il form
          si schiacciava in una colonna stretta mentre la pagina restava larga. */}
      {formOpen && (
        <ManualTopicForm onCreated={topics.reload} onClose={() => setFormOpen(false)} />
      )}

      <div className="card row">
        <div style={{ flex: 2, minWidth: 220 }}>
          <label htmlFor="search">Cerca</label>
          <input
            id="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="kafka, idempotenza, repository…"
          />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label htmlFor="category">Categoria</label>
          <select
            id="category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">Tutte</option>
            {categories.data?.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {categoryLabel(c.id)} ({c.count})
              </option>
            ))}
          </select>
        </div>
      </div>

      {topics.loading && <Spinner />}
      {topics.error && <ErrorBox error={topics.error} onRetry={topics.reload} />}
      {topics.data?.topics.length === 0 && <Empty title="Nessun argomento trovato" />}

      <div className="grid cols-3">
        {topics.data?.topics.map((topic) => (
          <Link key={topic.id} to={`/knowledge/${topic.id}`} className="card topic-card">
            <h3>{topic.title}</h3>
            <div className="row" style={{ marginBottom: 8 }}>
              <TrackBadge track={topic.track} />
              <DifficultyBadge level={topic.level} />
              <span className="badge">{formatMinutes(topic.estimated_minutes)}</span>
            </div>
            <p className="small muted" style={{ marginBottom: 8 }}>
              {topic.summary.slice(0, 150)}
              {topic.summary.length > 150 && '…'}
            </p>
            <div className="faint">
              {categoryLabel(topic.category)}
              {topic.question_count > 0 && ` · ${topic.question_count} domande`}
              {topic.problem_count > 0 && ` · ${topic.problem_count} esercizi`}
            </div>
          </Link>
        ))}
      </div>
    </main>
  )
}
