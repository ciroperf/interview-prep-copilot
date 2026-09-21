import { Link } from 'react-router-dom'

import { useAsync } from '../components/useAsync'
import { DifficultyBadge, Empty, ErrorBox, Spinner, formatMinutes } from '../components/ui'
import { api } from '../lib/api'

export default function PacksPage() {
  const packs = useAsync(() => api.listPacks(), [])

  return (
    <main className="container">
      <div className="page-header">
        <h1>Percorsi</h1>
        <p>
          Un linguaggio o l&apos;affidabilità non stanno in una scheda sola. Ogni percorso mette
          gli argomenti in ordine di studio e indica da dove approfondire.
        </p>
      </div>

      {packs.loading && <Spinner />}
      {packs.error && <ErrorBox error={packs.error} onRetry={packs.reload} />}
      {packs.data?.packs.length === 0 && <Empty title="Nessun percorso disponibile" />}

      <div className="grid cols-3">
        {packs.data?.packs.map((pack) => (
          <Link key={pack.id} to={`/percorsi/${pack.id}`} className="card topic-card">
            <h3>{pack.title}</h3>
            <p className="small muted" style={{ marginBottom: 8 }}>
              {pack.subtitle}
            </p>
            <div className="row" style={{ marginBottom: 8 }}>
              <DifficultyBadge level={pack.level} />
              <span className="badge">{pack.topic_count} argomenti</span>
              <span className="badge">{formatMinutes(pack.estimated_minutes)}</span>
            </div>
            <p className="small muted" style={{ marginBottom: 8 }}>
              {pack.summary.slice(0, 180)}
              {pack.summary.length > 180 && '…'}
            </p>
            <div className="faint">{pack.source_count} fonti consigliate</div>
          </Link>
        ))}
      </div>
    </main>
  )
}
