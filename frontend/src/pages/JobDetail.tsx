import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useMeta } from '../App'
import GapPanel from '../components/GapPanel'
import { useAsync } from '../components/useAsync'
import { Bullets, ErrorBox, Prose, Spinner, formatDate } from '../components/ui'
import { ApiError, api } from '../lib/api'

/** Form di generazione del piano: è l'azione principale di questa pagina. */
function PlanForm({ jobId }: { jobId: string }) {
  const meta = useMeta()
  const navigate = useNavigate()
  const [days, setDays] = useState(7)
  const [dailyMinutes, setDailyMinutes] = useState(90)
  const [interviewDate, setInterviewDate] = useState('')
  const [strengths, setStrengths] = useState('')
  const [weak, setWeak] = useState('')
  const [useAi, setUseAi] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const split = (value: string) =>
    value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await api.createPlan({
        job_id: jobId,
        days,
        daily_minutes: dailyMinutes,
        interview_date: interviewDate || null,
        known_strengths: split(strengths),
        weak_areas: split(weak),
        use_ai: useAi && Boolean(meta?.ai_enabled),
      })
      navigate(`/plans/${response.plan.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="card">
      <div className="card-title">
        <h2>Genera il piano di studi</h2>
      </div>
      {error && <ErrorBox error={error} />}

      <div className="grid cols-3">
        <div className="field">
          <label htmlFor="days">Giorni a disposizione</label>
          <input
            id="days"
            type="number"
            min={1}
            max={60}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="minutes">Minuti al giorno</label>
          <input
            id="minutes"
            type="number"
            min={20}
            max={600}
            step={15}
            value={dailyMinutes}
            onChange={(e) => setDailyMinutes(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="date">Data del colloquio</label>
          <input
            id="date"
            type="date"
            value={interviewDate}
            onChange={(e) => setInterviewDate(e.target.value)}
          />
        </div>
      </div>

      <div className="grid cols-2">
        <div className="field">
          <label htmlFor="strengths">Su cosa sei già solido</label>
          <input
            id="strengths"
            value={strengths}
            onChange={(e) => setStrengths(e.target.value)}
            placeholder="Python, REST, SQL"
          />
          <div className="field-hint">Separa con virgole: abbassa la priorità di questi temi.</div>
        </div>
        <div className="field">
          <label htmlFor="weak">Dove ti senti debole</label>
          <input
            id="weak"
            value={weak}
            onChange={(e) => setWeak(e.target.value)}
            placeholder="system design, grafi, Kafka"
          />
          <div className="field-hint">Questi entrano nel piano con priorità alta.</div>
        </div>
      </div>

      <div className="row between">
        <div className="checkbox">
          <input
            id="use-ai"
            type="checkbox"
            checked={useAi && Boolean(meta?.ai_enabled)}
            disabled={!meta?.ai_enabled}
            onChange={(e) => setUseAi(e.target.checked)}
          />
          <label htmlFor="use-ai">
            Fai scegliere e motivare gli argomenti all'AI
            {!meta?.ai_enabled && ' (non configurata)'}
          </label>
        </div>
        <button className="primary" type="submit" disabled={busy}>
          {busy && <span className="spinner" />}
          {busy ? 'Generazione…' : 'Crea il piano'}
        </button>
      </div>
      <div className="field-hint" style={{ marginTop: 10 }}>
        Budget totale: {days * dailyMinutes} minuti. Il piano si ferma qui: gli argomenti che non
        ci stanno vengono esclusi, a partire da quelli meno prioritari.
      </div>
    </form>
  )
}

export default function JobDetail() {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useAsync(() => api.getJob(jobId), [jobId])
  const plans = useAsync(() => api.listPlans(jobId), [jobId])

  if (loading) return <Spinner />
  if (error) return <div className="container"><ErrorBox error={error} onRetry={reload} /></div>
  if (!data) return null

  const job = data.job
  const company = job.company

  async function remove() {
    if (!confirm("Eliminare questo annuncio? I piani collegati restano ma perdono il riferimento.")) return
    await api.deleteJob(jobId)
    navigate('/')
  }

  return (
    <main className="container">
      <div className="page-header row between">
        <div>
          <h1>{job.role_title || 'Ruolo non rilevato'}</h1>
          <p>
            {[job.company_name, job.location, job.work_mode].filter(Boolean).join(' · ')}
            {' · analizzato il '}
            {formatDate(job.created_at)}
            {!job.analyzed_with_ai && ' · analisi euristica'}
          </p>
        </div>
        <button className="danger sm" onClick={remove}>
          Elimina
        </button>
      </div>

      {(plans.data?.plans.length ?? 0) > 0 && (
        <div className="alert info">
          Hai già {plans.data!.plans.length} piano/i per questo annuncio:{' '}
          {plans.data!.plans.map((p, i) => (
            <span key={p.id}>
              {i > 0 && ', '}
              <Link to={`/plans/${p.id}`}>
                {p.days} giorni ({p.progress.percent}%)
              </Link>
            </span>
          ))}
        </div>
      )}

      <PlanForm jobId={jobId} />

      <GapPanel jobId={jobId} />

      <div className="grid cols-2">
        <div className="card">
          <h2>Cosa chiede l'annuncio</h2>
          <div className="row" style={{ marginBottom: 14 }}>
            <span className="badge accent">{job.seniority}</span>
            {job.tech_stack.map((tech) => (
              <span key={tech} className="badge">
                {tech}
              </span>
            ))}
          </div>
          {job.requirements.length > 0 && (
            <>
              <h3>Requisiti per importanza</h3>
              <ul className="list-reset">
                {[...job.requirements]
                  .sort((a, b) => b.importance - a.importance)
                  .map((req, i) => (
                    <li key={i} className="row" style={{ marginBottom: 6 }}>
                      <span className="badge accent nowrap">{req.importance}/5</span>
                      <span>{req.name}</span>
                      {req.evidence && <span className="faint">— {req.evidence}</span>}
                    </li>
                  ))}
              </ul>
            </>
          )}
          <Bullets items={job.responsibilities} title="Responsabilità" />
          <Bullets items={job.nice_to_have} title="Gradito ma non richiesto" />
          <Bullets items={job.interview_focus} title="Probabile focus del colloquio" />
          {job.red_flags.length > 0 && (
            <>
              <h3>Punti a cui fare attenzione</h3>
              <ul>
                {job.red_flags.map((flag, i) => (
                  <li key={i} className="muted">
                    {flag}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="card">
          <div className="card-title">
            <h2>Scheda azienda</h2>
            {company.ai_generated && <span className="badge accent">AI</span>}
          </div>
          {!company.ai_generated && !company.talking_points.length && (
            <p className="muted small">
              Scheda non generata. Serve un modello AI configurato, oppure compilala tu partendo
              dal sito e dall'engineering blog.
            </p>
          )}
          {company.industry && (
            <p>
              <strong>Settore:</strong> {company.industry}
              {company.size && ` · ${company.size}`}
            </p>
          )}
          {company.tech_culture && <Prose text={company.tech_culture} />}
          <Bullets items={company.products} title="Prodotti" />
          <Bullets items={company.interview_process} title="Processo di selezione tipico" />
          <Bullets items={company.talking_points} title="Punti da citare" />
          <Bullets items={company.questions_to_ask} title="Domande da fare" />
          {company.research_notes && (
            <div className="alert warn small">{company.research_notes}</div>
          )}
        </div>
      </div>

      <details className="card">
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Testo originale</summary>
        <pre style={{ marginTop: 14, whiteSpace: 'pre-wrap' }}>{job.raw_text}</pre>
      </details>
    </main>
  )
}
