import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAsync } from '../components/useAsync'
import { DifficultyBadge, Empty, ErrorBox, Spinner, formatMinutes } from '../components/ui'
import { api } from '../lib/api'

export default function CodingPage() {
  const [jobId, setJobId] = useState('')
  const [difficulty, setDifficulty] = useState('')
  const jobs = useAsync(() => api.listJobs(), [])
  const problems = useAsync(
    () => api.listProblems({ job_id: jobId || undefined, difficulty: difficulty || undefined }),
    [jobId, difficulty],
  )

  return (
    <main className="container">
      <div className="page-header">
        <h1>Esercizi di coding</h1>
        <p>
          Problemi in stile colloquio, con test eseguibili e una revisione della soluzione.
          Filtra per annuncio per vedere prima quelli più pertinenti.
        </p>
      </div>

      <div className="card row">
        <div style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="job">Pertinenti all'annuncio</label>
          <select id="job" value={jobId} onChange={(e) => setJobId(e.target.value)}>
            <option value="">Tutti i problemi</option>
            {jobs.data?.jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.role_title || 'Annuncio'} {job.company_name && `— ${job.company_name}`}
              </option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label htmlFor="difficulty">Difficoltà</label>
          <select
            id="difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          >
            <option value="">Tutte</option>
            <option value="easy">Facile</option>
            <option value="medium">Media</option>
            <option value="hard">Difficile</option>
          </select>
        </div>
      </div>

      {problems.loading && <Spinner />}
      {problems.error && <ErrorBox error={problems.error} onRetry={problems.reload} />}

      {problems.data && problems.data.problems.length === 0 && (
        <Empty title="Nessun problema con questi filtri" />
      )}

      <div className="grid cols-2">
        {problems.data?.problems.map((problem) => (
          <Link key={problem.id} to={`/coding/${problem.id}`} className="card topic-card">
            <div className="row between" style={{ marginBottom: 6 }}>
              <h3 style={{ margin: 0 }}>{problem.title}</h3>
              <DifficultyBadge level={problem.difficulty} />
            </div>
            <div className="faint">
              {formatMinutes(problem.estimated_minutes)}
              {problem.target_complexity && ` · obiettivo ${problem.target_complexity}`}
            </div>
            <div className="tags" style={{ marginTop: 10 }}>
              {problem.tags.slice(0, 4).map((tag) => (
                <span key={tag} className="badge">
                  {tag}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </main>
  )
}
