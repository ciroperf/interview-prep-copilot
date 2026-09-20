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

      {topic.key_points.length > 0 && (
        <div className="card">
          <Bullets items={topic.key_points} title="Punti chiave" />
        </div>
      )}

      {topic.pitfalls.length > 0 && (
        <div className="card">
          <Bullets items={topic.pitfalls} title="Errori da evitare" />
        </div>
      )}

      {topic.follow_up_questions.length > 0 && (
        <div className="card">
          <Bullets items={topic.follow_up_questions} title="Possibili domande di approfondimento" />
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
