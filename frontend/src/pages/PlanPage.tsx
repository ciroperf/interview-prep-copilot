import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAsync } from '../components/useAsync'
import {
  Bullets,
  Empty,
  ErrorBox,
  KindBadge,
  Progress,
  Prose,
  Spinner,
  Stat,
  TrackBadge,
  formatMinutes,
} from '../components/ui'
import { ApiError, api } from '../lib/api'
import type { PlanItem, Track } from '../lib/types'

function ItemRow({
  item,
  onToggle,
  busy,
}: {
  item: PlanItem
  onToggle: (item: PlanItem) => void
  busy: boolean
}) {
  const done = item.status === 'done'
  const target = item.kind === 'coding' && item.problem_id ? `/coding/${item.problem_id}` : null
  const topicTarget = item.topic_id ? `/knowledge/${item.topic_id}` : null

  return (
    <div className={`plan-item${done ? ' done' : ''}`}>
      <div className="plan-item-check">
        <input
          type="checkbox"
          checked={done}
          disabled={busy}
          onChange={() => onToggle(item)}
          aria-label={`Segna come completato: ${item.title}`}
        />
      </div>
      <div className="plan-item-body">
        <div className="plan-item-title">{item.title}</div>
        {item.rationale && <div className="plan-item-why">{item.rationale}</div>}
        <div className="plan-item-meta">
          <TrackBadge track={item.track} />
          <KindBadge kind={item.kind} />
          <span className="badge">{formatMinutes(item.estimated_minutes)}</span>
          <span className="badge accent">priorità {item.priority}</span>
          {target && (
            <Link className="btn sm" to={target}>
              Apri l'esercizio
            </Link>
          )}
          {!target && topicTarget && (
            <Link className="btn sm" to={topicTarget}>
              Apri l'argomento
            </Link>
          )}
          {item.kind === 'quiz' && item.topic_id && (
            <Link className="btn sm" to={`/quiz?topic=${item.topic_id}`}>
              Fai il quiz
            </Link>
          )}
        </div>
        {item.resources.length > 0 && (
          <div className="faint" style={{ marginTop: 6 }}>
            {item.resources.map((r, i) => (
              <span key={i}>
                {i > 0 && ' · '}
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noreferrer noopener">
                    {r.title}
                  </a>
                ) : (
                  r.title
                )}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** I suggerimenti che l'AI ha messo nel piano, resi azionabili.
 *
 * Prima erano solo righe di testo: si leggeva "non coperto dal catalogo" e
 * finiva li'. Ora ognuno genera una scheda vera, con il contesto dell'annuncio
 * da cui il suggerimento e' nato.
 */
function SuggeritiDallAi({ planId, voci }: { planId: string; voci: string[] }) {
  const [inCorso, setInCorso] = useState<string | null>(null)
  const [fatti, setFatti] = useState<Record<string, string>>({})
  const [errore, setErrore] = useState('')

  async function genera(suggerimento: string) {
    setInCorso(suggerimento)
    setErrore('')
    try {
      const esito = await api.createTopicFromSuggestion({
        plan_id: planId,
        suggestion: suggerimento,
      })
      setFatti((prec) => ({ ...prec, [suggerimento]: esito.topic.id }))
    } catch (err) {
      setErrore(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setInCorso(null)
    }
  }

  return (
    <div className="card">
      <div className="card-title">
        <h2>Non coperto dal catalogo</h2>
        <span className="faint">{voci.length} suggerimenti</span>
      </div>
      <p className="small muted" style={{ marginTop: -4 }}>
        L&apos;AI ha individuato queste competenze nell&apos;annuncio senza trovare una scheda
        corrispondente. Generane una e finisce nel catalogo, nei piani e nei quiz.
      </p>

      {errore && <ErrorBox error={errore} />}

      <ul className="suggerimenti">
        {voci.map((voce) => {
          const creato = fatti[voce]
          return (
            <li key={voce}>
              <p>{voce}</p>
              {creato ? (
                <Link to={`/knowledge/${creato}`} className="badge accent">
                  Scheda creata — aprila
                </Link>
              ) : (
                <button className="sm" onClick={() => genera(voce)} disabled={inCorso !== null}>
                  {inCorso === voce && <span className="spinner" />}
                  {inCorso === voce ? 'Sto scrivendo la scheda…' : 'Genera la scheda'}
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function PlanPage() {
  const { planId = '' } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload, setData } = useAsync(() => api.getPlan(planId), [planId])
  const [busyItem, setBusyItem] = useState('')
  const [actionError, setActionError] = useState('')
  const [filter, setFilter] = useState<Track | 'all'>('all')

  if (loading) return <Spinner />
  if (error) return <div className="container"><ErrorBox error={error} onRetry={reload} /></div>
  if (!data) return null

  const { plan, progress, by_track, by_day } = data

  async function toggle(item: PlanItem) {
    setBusyItem(item.id)
    setActionError('')
    const next = item.status === 'done' ? 'todo' : 'done'
    try {
      await api.updateItem(plan.id, item.id, next)
      // Ricarico il piano intero: le percentuali per binario si ricalcolano sul server.
      setData(await api.getPlan(plan.id))
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusyItem('')
    }
  }

  async function remove() {
    if (!confirm('Eliminare questo piano? I progressi andranno persi.')) return
    await api.deletePlan(plan.id)
    navigate('/')
  }

  const days = by_day
    .map((day) => ({
      ...day,
      items: filter === 'all' ? day.items : day.items.filter((i) => i.track === filter),
    }))
    .filter((day) => day.items.length > 0)

  return (
    <main className="container">
      <div className="page-header row between">
        <div>
          <h1>{plan.title || 'Piano di studi'}</h1>
          <p>
            {plan.days} giorni · {plan.daily_minutes} min al giorno ·{' '}
            {formatMinutes(progress.minutes_total)} totali
            {plan.ai_generated ? ' · argomenti scelti dall’AI' : ' · selezione euristica'}
          </p>
        </div>
        <div className="row">
          <Link className="btn" to={`/jobs/${plan.job_id}`}>
            Annuncio
          </Link>
          <button className="danger sm" onClick={remove}>
            Elimina
          </button>
        </div>
      </div>

      {actionError && <ErrorBox error={actionError} />}

      <div className="grid cols-3" style={{ marginBottom: 20 }}>
        <Stat value={`${progress.percent}%`} label="Completato" />
        <Stat
          value={`${by_track.knowledge.done}/${by_track.knowledge.total}`}
          label="Parte conoscitiva"
        />
        <Stat
          value={`${by_track.technical.done}/${by_track.technical.total}`}
          label="Parte tecnica"
        />
      </div>

      <div className="card">
        <div className="stack">
          <div>
            <div className="row between small">
              <span>Avanzamento complessivo</span>
              <span className="muted">
                {formatMinutes(progress.minutes_done)} / {formatMinutes(progress.minutes_total)}
              </span>
            </div>
            <Progress percent={progress.percent} />
          </div>
          <div>
            <div className="row between small">
              <span>Conoscitiva — teoria, azienda, comportamentale</span>
              <span className="muted">{by_track.knowledge.percent}%</span>
            </div>
            <Progress percent={by_track.knowledge.percent} track="knowledge" />
          </div>
          <div>
            <div className="row between small">
              <span>Tecnica — quiz, coding, system design</span>
              <span className="muted">{by_track.technical.percent}%</span>
            </div>
            <Progress percent={by_track.technical.percent} track="technical" />
          </div>
        </div>
      </div>

      {plan.summary && (
        <div className="card">
          <h2>Strategia</h2>
          <Prose text={plan.summary} />
          {plan.focus_areas.length > 0 && (
            <div className="tags" style={{ marginTop: 10 }}>
              {plan.focus_areas.map((area, i) => (
                <span key={i} className="badge accent">
                  {area}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {plan.gap_analysis.length > 0 && (
        <div className="card">
          <Bullets items={plan.gap_analysis} title="Su cosa concentrarti" />
        </div>
      )}

      {plan.suggested_topics?.length > 0 && (
        <SuggeritiDallAi planId={plan.id} voci={plan.suggested_topics} />
      )}

      <div className="row between" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Calendario</h2>
        <div className="row">
          {(['all', 'knowledge', 'technical'] as const).map((value) => (
            <button
              key={value}
              className={filter === value ? 'primary sm' : 'sm'}
              onClick={() => setFilter(value)}
            >
              {value === 'all' ? 'Tutto' : value === 'knowledge' ? 'Conoscitiva' : 'Tecnica'}
            </button>
          ))}
        </div>
      </div>

      {days.length === 0 ? (
        <Empty title="Nessuna attività con questo filtro" />
      ) : (
        days.map((day) => (
          <div key={day.day} className="plan-day">
            <div className="plan-day-head">
              <strong>
                Giorno {day.day}
                {day.date && <span className="muted"> · {day.date}</span>}
              </strong>
              <span className="badge">{formatMinutes(day.minutes)}</span>
            </div>
            {day.items.map((item) => (
              <ItemRow
                key={item.id}
                item={item}
                onToggle={toggle}
                busy={busyItem === item.id}
              />
            ))}
          </div>
        ))
      )}
    </main>
  )
}
