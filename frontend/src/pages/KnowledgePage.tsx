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
function ManualTopicForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [term, setTerm] = useState('')
  const [draft, setDraft] = useState<TopicDraft>({ title: '', summary: '' })
  const [keyPoints, setKeyPoints] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

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
      setOpen(false)
      setTerm('')
      setDraft({ title: '', summary: '' })
      setKeyPoints('')
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="sm" onClick={() => setOpen(true)}>
        + Scrivi un argomento
      </button>
    )
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-title">
        <h3>Nuovo argomento</h3>
        <button type="button" className="ghost sm" onClick={() => setOpen(false)}>
          Chiudi
        </button>
      </div>
      {error && <ErrorBox error={error} />}
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
          <div className="field-hint">Serve a collegarlo agli annunci che lo richiedono.</div>
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
        </div>
      </div>
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
        <label htmlFor="points">Punti chiave (uno per riga)</label>
        <textarea
          id="points"
          rows={4}
          value={keyPoints}
          onChange={(e) => setKeyPoints(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="answer">Risposta da dare al colloquio</label>
        <textarea
          id="answer"
          rows={3}
          value={draft.interview_answer ?? ''}
          onChange={(e) => setDraft({ ...draft, interview_answer: e.target.value })}
        />
      </div>
      <div className="row end">
        <button className="primary" type="submit" disabled={busy}>
          {busy && <span className="spinner" />} Aggiungi al catalogo
        </button>
      </div>
    </form>
  )
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
          <ManualTopicForm onCreated={topics.reload} />
          <button className="sm" onClick={esporta} disabled={exportBusy}>
            {exportBusy && <span className="spinner" />} Esporta aggiunti
          </button>
        </div>
      </div>

      {exportMsg && <div className="alert info small">{exportMsg}</div>}

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
