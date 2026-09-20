import { Link } from 'react-router-dom'

import { useMeta } from '../App'
import { useAsync } from '../components/useAsync'
import { Empty, ErrorBox, Progress, Spinner, Stat, formatDate } from '../components/ui'
import { api } from '../lib/api'

export default function Dashboard() {
  const meta = useMeta()
  const jobs = useAsync(() => api.listJobs(), [])
  const plans = useAsync(() => api.listPlans(), [])

  if (jobs.loading || plans.loading) return <Spinner />

  const jobList = jobs.data?.jobs ?? []
  const planList = plans.data?.plans ?? []
  const attive = planList.filter((p) => p.progress.percent < 100)

  return (
    <main className="container">
      <div className="page-header row between">
        <div>
          <h1>Le tue preparazioni</h1>
          <p>Un annuncio, un piano di studi. Parti da qui.</p>
        </div>
        <Link to="/jobs/new" className="btn btn-primary">
          + Nuovo annuncio
        </Link>
      </div>

      {(jobs.error || plans.error) && <ErrorBox error={jobs.error || plans.error} />}

      <div className="grid cols-4" style={{ marginBottom: 24 }}>
        <Stat value={jobList.length} label="Annunci analizzati" />
        <Stat value={planList.length} label="Piani creati" />
        <Stat value={attive.length} label="Piani in corso" />
        <Stat value={meta?.content.topics ?? 0} label="Argomenti disponibili" />
      </div>

      {!jobList.length ? (
        <div className="card">
          <Empty
            title="Nessun annuncio ancora"
            action={
              <Link to="/jobs/new" className="btn btn-primary">
                Incolla il tuo primo annuncio
              </Link>
            }
          >
            Incolla il testo di un annuncio di lavoro: l'app ne estrae ruolo, stack e requisiti,
            poi costruisce un piano di studi tarato su quello.
          </Empty>
        </div>
      ) : (
        <>
          {planList.length > 0 && (
            <section style={{ marginBottom: 28 }}>
              <h2>Piani di studio</h2>
              <div className="card flush">
                {planList.map((plan) => (
                  <Link key={plan.id} to={`/plans/${plan.id}`} className="link-row">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <strong>{plan.title || 'Piano senza titolo'}</strong>
                      <div className="faint">
                        {plan.days} giorni · {plan.daily_minutes} min/giorno
                        {plan.interview_date && ` · colloquio il ${formatDate(plan.interview_date)}`}
                        {plan.ai_generated && ' · generato con AI'}
                      </div>
                      <div style={{ marginTop: 8, maxWidth: 380 }}>
                        <Progress percent={plan.progress.percent} />
                      </div>
                    </div>
                    <div className="center nowrap">
                      <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>
                        {plan.progress.percent}%
                      </div>
                      <div className="faint">
                        {plan.progress.done}/{plan.progress.total}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          <section>
            <h2>Annunci</h2>
            <div className="card flush">
              {jobList.map((job) => (
                <Link key={job.id} to={`/jobs/${job.id}`} className="link-row">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <strong>{job.role_title || 'Ruolo non rilevato'}</strong>
                    <div className="faint">
                      {[job.company_name, job.location, job.work_mode]
                        .filter(Boolean)
                        .join(' · ') || 'Dettagli non rilevati'}
                    </div>
                    {job.tech_stack.length > 0 && (
                      <div className="tags" style={{ marginTop: 7 }}>
                        {job.tech_stack.slice(0, 7).map((tech) => (
                          <span key={tech} className="badge">
                            {tech}
                          </span>
                        ))}
                        {job.tech_stack.length > 7 && (
                          <span className="badge">+{job.tech_stack.length - 7}</span>
                        )}
                      </div>
                    )}
                  </div>
                  <span className="badge accent nowrap">{job.seniority}</span>
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
