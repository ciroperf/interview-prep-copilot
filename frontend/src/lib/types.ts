/** Tipi condivisi con l'API. Rispecchiano i modelli Pydantic del backend. */

export type Track = 'knowledge' | 'technical'
export type ItemStatus = 'todo' | 'in_progress' | 'done' | 'skipped'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type ItemKind =
  | 'study'
  | 'quiz'
  | 'coding'
  | 'behavioral'
  | 'company'
  | 'system_design'
  | 'review'

export interface Meta {
  app_name: string
  environment: string
  ai_enabled: boolean
  ai_deployment: string
  ai_auth: string
  code_execution_enabled: boolean
  access_code_required: boolean
  storage_backend: string
  content: {
    topics: number
    questions: number
    problems: number
    categories: string[]
  }
}

export interface Resource {
  title: string
  url: string
  kind: string
}

export interface TopicSummary {
  id: string
  title: string
  category: string
  track: Track
  level: Difficulty
  tags: string[]
  summary: string
  estimated_minutes: number
  question_count: number
  problem_count: number
  custom?: boolean
}

export interface Example {
  title: string
  code: string
  language: string
  note: string
}

export interface TradeOff {
  option: string
  pros: string
  cons: string
  when: string
}

export interface FollowUp {
  question: string
  answer: string
}

export interface Topic extends Omit<TopicSummary, 'question_count' | 'problem_count'> {
  custom: boolean
  source_term: string
  /** La spiegazione lunga: è la parte da studiare, non da ripassare. */
  deep_dive: string
  key_points: string[]
  examples: Example[]
  trade_offs: TradeOff[]
  numbers: string[]
  interview_answer: string
  senior_signals: string[]
  pitfalls: string[]
  follow_ups: FollowUp[]
  /** Forma storica, senza risposta: la usano gli argomenti generati dall'AI. */
  follow_up_questions: string[]
  related: string[]
  resources: Resource[]
}

export interface TopicGap {
  term: string
  importance: number
  covered: boolean
  coverage_score: number
  best_topic_id: string
  best_topic_title: string
}

export interface TopicDraft {
  title: string
  summary: string
  category?: string
  track?: Track
  level?: Difficulty
  tags?: string[]
  key_points?: string[]
  interview_answer?: string
  pitfalls?: string[]
  follow_up_questions?: string[]
  estimated_minutes?: number
}

export interface CustomExport {
  count: number
  question_count: number
  topics_yaml: string
  questions_yaml: string
}

export interface JobRequirement {
  name: string
  category: string
  importance: number
  evidence: string
}

export interface CompanyProfile {
  name: string
  industry: string
  size: string
  products: string[]
  tech_culture: string
  interview_process: string[]
  talking_points: string[]
  questions_to_ask: string[]
  research_notes: string
  ai_generated: boolean
}

export interface JobPosting {
  id: string
  created_at: string
  raw_text: string
  source_url: string
  company_name: string
  role_title: string
  seniority: string
  location: string
  work_mode: string
  tech_stack: string[]
  requirements: JobRequirement[]
  nice_to_have: string[]
  responsibilities: string[]
  interview_focus: string[]
  red_flags: string[]
  company: CompanyProfile
  analyzed_with_ai: boolean
}

export interface JobSummary {
  id: string
  created_at: string
  role_title: string
  company_name: string
  seniority: string
  location: string
  work_mode: string
  tech_stack: string[]
  analyzed_with_ai: boolean
}

export interface PlanItem {
  id: string
  day: number
  track: Track
  kind: ItemKind
  title: string
  topic_id: string
  problem_id: string
  rationale: string
  estimated_minutes: number
  priority: number
  status: ItemStatus
  completed_at: string | null
  resources: Resource[]
}

export interface StudyPlan {
  id: string
  job_id: string
  created_at: string
  title: string
  summary: string
  interview_date: string | null
  days: number
  daily_minutes: number
  items: PlanItem[]
  focus_areas: string[]
  gap_analysis: string[]
  ai_generated: boolean
}

export interface Progress {
  total: number
  done: number
  skipped: number
  percent: number
  minutes_total: number
  minutes_done: number
}

export interface TrackStats {
  total: number
  done: number
  minutes: number
  minutes_done: number
  percent: number
}

export interface PlanDay {
  day: number
  date: string | null
  minutes: number
  items: PlanItem[]
}

export interface PlanResponse {
  plan: StudyPlan
  progress: Progress
  by_track: Record<Track, TrackStats>
  by_day: PlanDay[]
}

export interface PlanSummary {
  id: string
  job_id: string
  title: string
  created_at: string
  interview_date: string | null
  days: number
  daily_minutes: number
  ai_generated: boolean
  progress: Progress
}

export interface QuizQuestion {
  id: string
  topic_id: string
  topic_title: string
  prompt: string
  options: string[]
  difficulty: Difficulty
  tags: string[]
}

export interface Quiz {
  id: string
  job_id: string
  plan_id: string
  created_at: string
  submitted: boolean
  questions: QuizQuestion[]
  result?: QuizResult
}

export interface GradedAnswer {
  question_id: string
  prompt: string
  selected_index: number
  answer_index: number
  correct: boolean
  explanation: string
  topic_id: string
  topic_title: string
  options: string[]
}

export interface QuizResult {
  id: string
  score: number
  correct: number
  total: number
  submitted_at: string | null
  answers: GradedAnswer[]
  weak_topics: { id: string; title: string }[]
}

export interface ProblemSummary {
  id: string
  title: string
  difficulty: Difficulty
  tags: string[]
  estimated_minutes: number
  target_complexity: string
  topic_ids: string[]
}

export interface CodingProblem extends ProblemSummary {
  statement: string
  function_name: string
  starter_code: string
  examples: string[]
  hints: string[]
  tests: { kwargs: Record<string, unknown>; expected: unknown; hidden: boolean }[]
}

export interface TestOutcome {
  name: string
  passed: boolean
  expected: string
  actual: string
  error: string
}

export interface CodeReview {
  id: string
  problem_id: string
  executed: boolean
  tests_passed: number
  tests_total: number
  outcomes: TestOutcome[]
  verdict: string
  correctness: string
  complexity: string
  strengths: string[]
  improvements: string[]
  interview_notes: string
  ai_generated: boolean
}

export interface CvReview {
  id: string
  created_at: string
  job_id: string
  filename: string
  char_count: number
  overall_score: number
  summary: string
  matched_keywords: string[]
  missing_keywords: string[]
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  bullet_rewrites: { original: string; improved: string; why: string }[]
  tailored_summary: string
  likely_questions: string[]
  ai_generated: boolean
}
