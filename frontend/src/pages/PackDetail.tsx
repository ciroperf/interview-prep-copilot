import { Link, useParams } from 'react-router-dom'

import { useAsync } from '../components/useAsync'
import {
  Bullets,
  DifficultyBadge,
  ErrorBox,
  Prose,
  Spinner,
  TrackBadge,
  formatMinutes,
} from '../components/ui'
import { api } from '../lib/api'
import type { PackSource } from '../lib/types'

const KIND_LABEL: Record<string, string> = {
  book: 'libro',
  doc: 'documentazione',
  repo: 'repository',
  article: 'articolo',
  practice: 'esercizi',
  video: 'video',
  course: 'corso',
}

/** Una fonte si consiglia solo se si dice perché: il `note` è la parte utile. */
function SourceCard({ source }: { source: PackSource }) {
  return (
    <li className="source">
      <div className="row" style={{ marginBottom: 4 }}>
        {source.url ? (
          <a href={source.url} target="_blank" rel="noreferrer noopener">
            {source.title}
          </a>
        ) : (
          <strong>{source.title}</strong>
        )}
        <span className="badge">{KIND_LABEL[source.kind] ?? source.kind}</span>
      </div>
      {source.note && <p className="small muted">{source.note}</p>}
    </li>
  )
}

export default function PackDetail() {
  const { packId = '' } = useParams()
  const { data, loading, error, reload } = useAsync(() => api.getPack(packId), [packId])

  if (loading) return <Spinner />
  if (error)
    return (
      <div className="container">
        <ErrorBox error={error} onRetry={reload} />
      </div>
    )
  if (!data) return null

  const { pack, estimated_minutes, topics } = data

  return (
    <main className="container" style={{ maxWidth: 820 }}>
      <div className="page-header">
        <Link to="/percorsi" className="faint">
          ← Tutti i percorsi
        </Link>
        <h1>{pack.title}</h1>
        <p className="muted">{pack.subtitle}</p>
        <div className="row">
          <DifficultyBadge level={pack.level} />
          <span className="badge">{topics.length} argomenti</span>
          <span className="badge">{formatMinutes(estimated_minutes)}</span>
          <span className="badge">{pack.sources.length} fonti</span>
        </div>
      </div>

      <div className="card">
        <Prose text={pack.summary} />
        {pack.tags.length > 0 && (
          <div className="tags">
            {pack.tags.map((tag) => (
              <span key={tag} className="badge">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {pack.for_whom && (
        <div className="card">
          <h2>A chi serve</h2>
          <Prose text={pack.for_whom} />
        </div>
      )}

      {pack.prerequisites.length > 0 && (
        <div className="card">
          <Bullets items={pack.prerequisites} title="Prima di iniziare" />
        </div>
      )}

      <div className="card">
        <h2>Argomenti, in ordine di studio</h2>
        <ol className="pack-steps">
          {topics.map((topic) => (
            <li key={topic.id}>
              <Link to={`/knowledge/${topic.id}`}>{topic.title}</Link>
              <div className="row" style={{ marginTop: 4 }}>
                <TrackBadge track={topic.track} />
                <DifficultyBadge level={topic.level} />
                <span className="badge">{formatMinutes(topic.estimated_minutes)}</span>
              </div>
              <p className="small muted" style={{ marginTop: 4 }}>
                {topic.summary}
              </p>
            </li>
          ))}
        </ol>
      </div>

      {pack.sources.length > 0 && (
        <div className="card">
          <h2>Da dove approfondire</h2>
          <ul className="sources">
            {pack.sources.map((source, i) => (
              <SourceCard key={i} source={source} />
            ))}
          </ul>
        </div>
      )}
    </main>
  )
}
