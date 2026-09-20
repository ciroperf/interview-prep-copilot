import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAsync } from '../components/useAsync'
import {
  Bullets,
  DifficultyBadge,
  ErrorBox,
  Prose,
  Spinner,
  TrackBadge,
  categoryLabel,
  formatMinutes,
} from '../components/ui'
import { api } from '../lib/api'
import type { Example, FollowUp, TradeOff } from '../lib/types'

/** Un esempio: si legge, si prova, si capisce se si era capito. */
function ExampleBlock({ example }: { example: Example }) {
  return (
    <figure className="example">
      <figcaption>
        {example.title}
        {example.language !== 'text' && <span className="badge">{example.language}</span>}
      </figcaption>
      <pre>
        <code>{example.code.replace(/\n+$/, '')}</code>
      </pre>
      {example.note && <p className="faint">{example.note}</p>}
    </figure>
  )
}

/** La domanda vera non è "cos'è X" ma "perché X e non Y": qui c'è il prezzo. */
function TradeOffTable({ rows }: { rows: TradeOff[] }) {
  return (
    <div className="table-scroll">
      <table className="grid">
        <thead>
          <tr>
            <th>Opzione</th>
            <th>A favore</th>
            <th>Contro</th>
            <th>Quando</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <th scope="row">{row.option}</th>
              <td>{row.pros}</td>
              <td>{row.cons}</td>
              <td className="muted">{row.when}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Chiusa di default: prima prova a rispondere, poi apri. */
function FollowUpList({ items }: { items: FollowUp[] }) {
  return (
    <div className="followups">
      {items.map((item, i) => (
        <details key={i}>
          <summary>{item.question}</summary>
          {item.answer && <Prose text={item.answer} />}
        </details>
      ))}
    </div>
  )
}

export default function TopicDetail() {
  const { topicId = '' } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useAsync(() => api.getTopic(topicId), [topicId])

  if (loading) return <Spinner />
  if (error) return <div className="container"><ErrorBox error={error} onRetry={reload} /></div>
  if (!data) return null

  const { topic, question_count, problems } = data

  async function remove() {
    if (!confirm('Eliminare questo argomento dal catalogo?')) return
    await api.deleteTopic(topicId)
    navigate('/knowledge')
  }

  return (
    <main className="container" style={{ maxWidth: 820 }}>
      <div className="page-header">
        <div className="row between">
          <h1>{topic.title}</h1>
          {topic.custom && (
            <button className="danger sm" onClick={remove}>
              Elimina
            </button>
          )}
        </div>
        <div className="row">
          <TrackBadge track={topic.track} />
          <DifficultyBadge level={topic.level} />
          <span className="badge">{categoryLabel(topic.category)}</span>
          <span className="badge">{formatMinutes(topic.estimated_minutes)}</span>
          {topic.custom && <span className="badge accent">aggiunto da un annuncio</span>}
        </div>
      </div>

      <div className="card">
        <Prose text={topic.summary} />
        {topic.tags.length > 0 && (
          <div className="tags">
            {topic.tags.map((tag) => (
              <span key={tag} className="badge">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {topic.deep_dive && (
        <div className="card">
          <h2>Come funziona</h2>
          <Prose text={topic.deep_dive} />
        </div>
      )}

      {topic.key_points.length > 0 && (
        <div className="card">
          <Bullets items={topic.key_points} title="Punti chiave" />
        </div>
      )}

      {topic.examples.length > 0 && (
        <div className="card">
          <h2>Esempi</h2>
          {topic.examples.map((example, i) => (
            <ExampleBlock key={i} example={example} />
          ))}
        </div>
      )}

      {topic.trade_offs.length > 0 && (
        <div className="card">
          <h2>Trade-off</h2>
          <TradeOffTable rows={topic.trade_offs} />
        </div>
      )}

      {topic.numbers.length > 0 && (
        <div className="card">
          <Bullets items={topic.numbers} title="Numeri da ricordare" />
          <p className="faint">
            Un ordine di grandezza detto con sicurezza vale più di tre frasi di contorno.
          </p>
        </div>
      )}

      {topic.interview_answer && (
        <div className="card">
          <h2>Come rispondere al colloquio</h2>
          <div className="answer-box">
            <Prose text={topic.interview_answer} />
          </div>
          <p className="faint">
            Non impararla a memoria: leggila, chiudi la pagina e riformulala a voce con parole
            tue. È così che si verifica di averla capita.
          </p>
        </div>
      )}

      {topic.senior_signals.length > 0 && (
        <div className="card">
          <Bullets items={topic.senior_signals} title="Cosa distingue una risposta senior" />
        </div>
      )}

      {topic.pitfalls.length > 0 && (
        <div className="card">
          <Bullets items={topic.pitfalls} title="Errori da evitare" />
        </div>
      )}

      {(topic.follow_ups.length > 0 || topic.follow_up_questions.length > 0) && (
        <div className="card">
          <h2>Possibili domande di approfondimento</h2>
          {topic.follow_ups.length > 0 ? (
            <FollowUpList items={topic.follow_ups} />
          ) : (
            <ul>
              {topic.follow_up_questions.map((question, i) => (
                <li key={i}>{question}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {topic.related.length > 0 && (
        <div className="card">
          <h2>Argomenti collegati</h2>
          <div className="row">
            {topic.related.map((id) => (
              <Link key={id} className="btn sm" to={`/knowledge/${id}`}>
                {id.replace(/^[a-z]+-\d+-/, '').replace(/-/g, ' ')}
              </Link>
            ))}
          </div>
        </div>
      )}

      {topic.resources.length > 0 && (
        <div className="card">
          <h2>Approfondimenti</h2>
          <ul>
            {topic.resources.map((resource, i) => (
              <li key={i}>
                {resource.url ? (
                  <a href={resource.url} target="_blank" rel="noreferrer noopener">
                    {resource.title}
                  </a>
                ) : (
                  resource.title
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card row between">
        <span className="muted">
          {question_count} domande · {problems.length} esercizi collegati
        </span>
        <div className="row">
          {problems.map((problem) => (
            <Link key={problem.id} className="btn sm" to={`/coding/${problem.id}`}>
              {problem.title}
            </Link>
          ))}
          {question_count > 0 && (
            <Link className="btn btn-primary sm" to={`/quiz?topic=${topic.id}`}>
              Mettiti alla prova
            </Link>
          )}
        </div>
      </div>
    </main>
  )
}
