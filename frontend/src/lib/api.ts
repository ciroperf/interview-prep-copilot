/** Client HTTP verso l'API. Un solo punto per base URL, codice di accesso ed errori. */

import { entraEnabled, getAccessToken } from './auth'
import type {
  CodeReview,
  CodingProblem,
  CustomExport,
  CvReview,
  JobPosting,
  JobSummary,
  Meta,
  PlanResponse,
  PlanSummary,
  ProblemSummary,
  Quiz,
  QuizResult,
  Topic,
  TopicDraft,
  TopicGap,
  TopicSummary,
  Track,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const ACCESS_CODE_KEY = 'ipc.access_code'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** L'API chiede un codice di accesso che non abbiamo o che è errato. */
  get isAuth() {
    return this.status === 401
  }
}

export function getAccessCode(): string {
  try {
    return localStorage.getItem(ACCESS_CODE_KEY) ?? ''
  } catch {
    // Modalità privata o storage bloccato: si continua senza ricordare il codice.
    return ''
  }
}

export function setAccessCode(code: string): void {
  try {
    if (code) localStorage.setItem(ACCESS_CODE_KEY, code)
    else localStorage.removeItem(ACCESS_CODE_KEY)
  } catch {
    /* ignorato di proposito */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)

  if (entraEnabled) {
    // Con il login Microsoft il token va nel Bearer: lo valida
    // l'autenticazione integrata di Container Apps prima del backend.
    const token = await getAccessToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  } else {
    const code = getAccessCode()
    if (code) headers.set('X-Access-Code', code)
  }

  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${BASE}/api${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, "Impossibile contattare l'API. È in esecuzione?")
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  const data = text ? safeParse(text) : null

  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(data) ?? `Errore ${response.status}`)
  }
  return data as T
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text.slice(0, 300) }
  }
}

function extractDetail(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  // FastAPI restituisce una lista di errori di validazione: la rendiamo leggibile.
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const loc = Array.isArray(e?.loc) ? e.loc.slice(1).join('.') : ''
        return loc ? `${loc}: ${e?.msg ?? ''}` : String(e?.msg ?? '')
      })
      .filter(Boolean)
      .join('; ')
  }
  return null
}

const json = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  meta: () => request<Meta>('/meta'),

  listTopics: (params: { category?: string; track?: Track; q?: string } = {}) => {
    const search = new URLSearchParams()
    if (params.category) search.set('category', params.category)
    if (params.track) search.set('track', params.track)
    if (params.q) search.set('q', params.q)
    const qs = search.toString()
    return request<{ total: number; topics: TopicSummary[] }>(
      `/knowledge/topics${qs ? `?${qs}` : ''}`,
    )
  },
  getTopic: (id: string) =>
    request<{ topic: Topic; question_count: number; problems: ProblemSummary[] }>(
      `/knowledge/topics/${id}`,
    ),
  categories: () =>
    request<{ categories: { id: string; count: number }[] }>('/knowledge/categories'),

  findGaps: (jobId: string) =>
    request<{ job_id: string; gaps: TopicGap[]; missing: number }>(
      `/knowledge/gaps?job_id=${encodeURIComponent(jobId)}`,
    ),
  createTopic: (body: {
    term: string
    job_id?: string
    category?: string
    num_questions?: number
    draft?: TopicDraft
  }) => request<{ topic: Topic; question_count: number }>('/knowledge/topics', json(body)),
  deleteTopic: (id: string) => request<void>(`/knowledge/topics/${id}`, { method: 'DELETE' }),
  exportCustom: () => request<CustomExport>('/knowledge/export'),

  listJobs: () => request<{ total: number; jobs: JobSummary[] }>('/jobs'),
  getJob: (id: string) => request<{ job: JobPosting }>(`/jobs/${id}`),
  createJob: (body: {
    raw_text: string
    source_url?: string
    company_name?: string
    notes?: string
    research_company?: boolean
  }) => request<{ job: JobPosting }>('/jobs', json(body)),
  deleteJob: (id: string) => request<void>(`/jobs/${id}`, { method: 'DELETE' }),

  listPlans: (jobId?: string) =>
    request<{ total: number; plans: PlanSummary[] }>(`/plans${jobId ? `?job_id=${jobId}` : ''}`),
  getPlan: (id: string) => request<PlanResponse>(`/plans/${id}`),
  createPlan: (body: {
    job_id: string
    days: number
    daily_minutes: number
    interview_date?: string | null
    known_strengths?: string[]
    weak_areas?: string[]
    use_ai?: boolean
  }) => request<PlanResponse>('/plans', json(body)),
  updateItem: (planId: string, itemId: string, status: string) =>
    request<{ item: unknown; progress: unknown }>(`/plans/${planId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  deletePlan: (id: string) => request<void>(`/plans/${id}`, { method: 'DELETE' }),

  createQuiz: (body: {
    job_id?: string
    plan_id?: string
    topic_ids?: string[]
    num_questions: number
    difficulty?: string
    use_ai?: boolean
  }) => request<Quiz>('/quizzes', json(body)),
  getQuiz: (id: string) => request<Quiz>(`/quizzes/${id}`),
  submitQuiz: (id: string, answers: { question_id: string; selected_index: number }[]) =>
    request<QuizResult>(`/quizzes/${id}/submit`, json({ answers })),

  listProblems: (params: { job_id?: string; difficulty?: string } = {}) => {
    const search = new URLSearchParams()
    if (params.job_id) search.set('job_id', params.job_id)
    if (params.difficulty) search.set('difficulty', params.difficulty)
    const qs = search.toString()
    return request<{ total: number; problems: ProblemSummary[] }>(
      `/problems${qs ? `?${qs}` : ''}`,
    )
  },
  getProblem: (id: string) => request<{ problem: CodingProblem }>(`/problems/${id}`),
  submitCode: (id: string, code: string) =>
    request<{ review: CodeReview }>(`/problems/${id}/submit`, json({ problem_id: id, code })),
  getSolution: (id: string) =>
    request<{ solution: string; target_complexity: string }>(`/problems/${id}/solution`),

  reviewCv: (file: File, jobId?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (jobId) form.append('job_id', jobId)
    return request<{ review: CvReview }>('/cv/review', { method: 'POST', body: form })
  },
  listCvReviews: () =>
    request<{ total: number; reviews: Partial<CvReview>[] }>('/cv'),
  getCvReview: (id: string) => request<{ review: CvReview }>(`/cv/${id}`),
}
