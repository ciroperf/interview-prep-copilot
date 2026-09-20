import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useMeta } from '../App'
import { ErrorBox } from '../components/ui'
import { ApiError, api } from '../lib/api'

export default function NewJob() {
  const meta = useMeta()
  const navigate = useNavigate()
  const [rawText, setRawText] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [notes, setNotes] = useState('')
  const [researchCompany, setResearchCompany] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const tooShort = rawText.trim().length < 30

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { job } = await api.createJob({
        raw_text: rawText,
        company_name: companyName.trim(),
        source_url: sourceUrl.trim(),
        notes: notes.trim(),
        research_company: researchCompany && Boolean(meta?.ai_enabled),
      })
      navigate(`/jobs/${job.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
      setBusy(false)
    }
  }

  return (
    <main className="container" style={{ maxWidth: 780 }}>
      <div className="page-header">
        <h1>Nuovo annuncio</h1>
        <p>
          Incolla il testo integrale dell'annuncio. L'app ne estrae ruolo, seniority, stack e
          requisiti, e su quelli costruisce il piano.
        </p>
      </div>

      {error && <ErrorBox error={error} />}

      <form onSubmit={submit}>
        <div className="card">
          <div className="field">
            <label htmlFor="raw-text">Testo dell'annuncio *</label>
            <textarea
              id="raw-text"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={16}
              placeholder={
                'Es.\n\nSenior Backend Engineer - Acme\n\nResponsabilità:\n- Sviluppare microservizi in Python…\n\nRequisiti:\n- 5 anni di esperienza…'
              }
              required
            />
            <div className="field-hint">
              {rawText.trim().length} caratteri · più contesto significa un piano più preciso.
            </div>
          </div>

          <div className="grid cols-2">
            <div className="field">
              <label htmlFor="company">Azienda</label>
              <input
                id="company"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Se non è chiara dal testo"
              />
            </div>
            <div className="field">
              <label htmlFor="url">Link all'annuncio</label>
              <input
                id="url"
                type="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://…"
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="notes">Note per l'analisi</label>
            <input
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Es. il recruiter ha detto che ci sarà un live coding in Python"
            />
          </div>

          <div className="checkbox">
            <input
              id="research"
              type="checkbox"
              checked={researchCompany && Boolean(meta?.ai_enabled)}
              disabled={!meta?.ai_enabled}
              onChange={(e) => setResearchCompany(e.target.checked)}
            />
            <label htmlFor="research">
              Prepara anche la scheda azienda
              {!meta?.ai_enabled && ' (richiede un modello AI configurato)'}
            </label>
          </div>
        </div>

        <div className="row end">
          <button className="primary" type="submit" disabled={tooShort || busy}>
            {busy && <span className="spinner" />}
            {busy ? 'Analisi in corso…' : "Analizza l'annuncio"}
          </button>
        </div>
      </form>
    </main>
  )
}
