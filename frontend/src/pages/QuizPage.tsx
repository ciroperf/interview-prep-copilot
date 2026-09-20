import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useMeta } from '../App'
import { useAsync } from '../components/useAsync'
import { DifficultyBadge, ErrorBox } from '../components/ui'
import { ApiError, api } from '../lib/api'
import type { Quiz, QuizResult } from '../lib/types'

function Runner({ quiz, onDone }: { quiz: Quiz; onDone: () => void }) {
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<QuizResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const answered = Object.keys(answers).length

  async function submit() {
    setBusy(true)
    setError('')
    try {
      setResult(
        await api.submitQuiz(
          quiz.id,
          quiz.questions.map((q) => ({
            question_id: q.id,
            // Una domanda saltata vale come errore: -1 non corrisponde a nessuna opzione.
            selected_index: answers[q.id] ?? -1,
          })),
        ),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    const tone = result.score >= 75 ? 'good' : result.score >= 50 ? 'mid' : 'bad'
    return (
      <>
        <div className="card center">
          <div className={`score-ring ${tone}`}>{result.score}</div>
          <h2 style={{ marginTop: 14 }}>
            {result.correct} risposte corrette su {result.total}
          </h2>
          {result.weak_topics.length > 0 && (
            <p className="muted">
              Da rivedere:{' '}
              {result.weak_topics.map((topic, i) => (
                <span key={topic.id}>
                  {i > 0 && ', '}
                  <Link to={`/knowledge/${topic.id}`}>{topic.title}</Link>
                </span>
              ))}
            </p>
          )}
          <button className="primary" onClick={onDone}>
            Nuovo quiz
          </button>
        </div>

        {result.answers.map((answer, index) => (
          <div key={answer.question_id} className="card">
            <div className="row between" style={{ marginBottom: 10 }}>
              <strong>
                {index + 1}. {answer.prompt}
              </strong>
              <span className={`badge ${answer.correct ? 'ok' : 'ko'}`}>
                {answer.correct ? 'corretta' : 'sbagliata'}
              </span>
            </div>
            {answer.options.map((option, i) => {
              const isAnswer = i === answer.answer_index
              const isPicked = i === answer.selected_index
              const cls = isAnswer ? 'correct' : isPicked ? 'wrong' : ''
              return (
                <div key={i} className={`quiz-option disabled ${cls}`}>
                  <span style={{ minWidth: 18 }}>{String.fromCharCode(65 + i)}.</span>
                  <span>{option}</span>
                </div>
              )
            })}
            {answer.explanation && (
              <p className="small muted" style={{ marginTop: 10, marginBottom: 0 }}>
                {answer.explanation}
              </p>
            )}
            {answer.topic_title && (
              <div className="faint" style={{ marginTop: 6 }}>
                <Link to={`/knowledge/${answer.topic_id}`}>{answer.topic_title}</Link>
              </div>
            )}
          </div>
        ))}
      </>
    )
  }

  return (
    <>
      {error && <ErrorBox error={error} />}
      {quiz.questions.map((question, index) => (
        <div key={question.id} className="card">
          <div className="row between" style={{ marginBottom: 10 }}>
            <strong>
              {index + 1}. {question.prompt}
            </strong>
            <DifficultyBadge level={question.difficulty} />
          </div>
          {question.options.map((option, i) => (
            <label
              key={i}
              className={`quiz-option${answers[question.id] === i ? ' selected' : ''}`}
            >
              <input
                type="radio"
                name={question.id}
                checked={answers[question.id] === i}
                onChange={() => setAnswers((prev) => ({ ...prev, [question.id]: i }))}
              />
              <span>
                <strong>{String.fromCharCode(65 + i)}.</strong> {option}
              </span>
            </label>
          ))}
          {question.topic_title && <div className="faint">{question.topic_title}</div>}
        </div>
      ))}

      <div className="card row between">
        <span className="muted">
          {answered} di {quiz.questions.length} risposte date
        </span>
        <button className="primary" onClick={submit} disabled={busy || answered === 0}>
          {busy && <span className="spinner" />} Consegna
        </button>
      </div>
    </>
  )
}

export default function QuizPage() {
  const meta = useMeta()
  const [params] = useSearchParams()
  const topicParam = params.get('topic') ?? ''
  const jobs = useAsync(() => api.listJobs(), [])

  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [jobId, setJobId] = useState('')
  const [count, setCount] = useState(10)
  const [difficulty, setDifficulty] = useState('')
  const [useAi, setUseAi] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function start() {
    setBusy(true)
    setError('')
    try {
      setQuiz(
        await api.createQuiz({
          job_id: jobId || undefined,
          topic_ids: topicParam ? [topicParam] : undefined,
          num_questions: count,
          difficulty: difficulty || undefined,
          use_ai: useAi && Boolean(meta?.ai_enabled),
        }),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore imprevisto')
    } finally {
      setBusy(false)
    }
  }

  if (quiz) {
    return (
      <main className="container" style={{ maxWidth: 820 }}>
        <div className="page-header row between">
          <h1>Quiz</h1>
          <button className="ghost sm" onClick={() => setQuiz(null)}>
            Annulla
          </button>
        </div>
        <Runner quiz={quiz} onDone={() => setQuiz(null)} />
      </main>
    )
  }

  return (
    <main className="container" style={{ maxWidth: 680 }}>
      <div className="page-header">
        <h1>Quiz</h1>
        <p>
          Domande a risposta multipla dal catalogo
          {meta ? ` (${meta.content.questions} disponibili)` : ''}. Le opzioni vengono
          mescolate a ogni esecuzione.
        </p>
      </div>

      {error && <ErrorBox error={error} />}
      {topicParam && (
        <div className="alert info">Quiz mirato sull'argomento selezionato dal piano.</div>
      )}

      <div className="card">
        {!topicParam && (
          <div className="field">
            <label htmlFor="job">Tara le domande su un annuncio</label>
            <select id="job" value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">Tutti gli argomenti</option>
              {jobs.data?.jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.role_title || 'Annuncio'} {job.company_name && `— ${job.company_name}`}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="grid cols-2">
          <div className="field">
            <label htmlFor="count">Numero di domande</label>
            <input
              id="count"
              type="number"
              min={1}
              max={40}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label htmlFor="difficulty">Difficoltà</label>
            <select
              id="difficulty"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
            >
              <option value="">Mista</option>
              <option value="easy">Facile</option>
              <option value="medium">Media</option>
              <option value="hard">Difficile</option>
            </select>
          </div>
        </div>

        <div className="checkbox">
          <input
            id="quiz-ai"
            type="checkbox"
            checked={useAi && Boolean(meta?.ai_enabled)}
            disabled={!meta?.ai_enabled}
            onChange={(e) => setUseAi(e.target.checked)}
          />
          <label htmlFor="quiz-ai">
            Genera domande nuove con l'AI se il catalogo non ne ha abbastanza
            {!meta?.ai_enabled && ' (non configurata)'}
          </label>
        </div>

        <div className="row end" style={{ marginTop: 14 }}>
          <button className="primary" onClick={start} disabled={busy}>
            {busy && <span className="spinner" />} Inizia
          </button>
        </div>
      </div>
    </main>
  )
}
