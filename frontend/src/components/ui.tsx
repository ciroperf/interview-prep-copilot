/** Componenti di presentazione riusati in tutte le pagine. */

import type { ReactNode } from 'react'

import type { Difficulty, ItemKind, Track } from '../lib/types'

export function Spinner({ label = 'Caricamento…' }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="alert error" role="alert">
      <div className="row between">
        <span>{error}</span>
        {onRetry && (
          <button className="sm" onClick={onRetry}>
            Riprova
          </button>
        )}
      </div>
    </div>
  )
}

export function Empty({
  title,
  children,
  action,
}: {
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Progress({
  percent,
  track,
}: {
  percent: number
  track?: Track
}) {
  return (
    <div
      className={`progress${track ? ` ${track}` : ''}`}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  )
}

export function Stat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

const TRACK_LABEL: Record<Track, string> = {
  knowledge: 'Conoscitiva',
  technical: 'Tecnica',
}

export function TrackBadge({ track }: { track: Track }) {
  return <span className={`badge ${track}`}>{TRACK_LABEL[track]}</span>
}

const KIND_LABEL: Record<ItemKind, string> = {
  study: 'Studio',
  quiz: 'Quiz',
  coding: 'Coding',
  behavioral: 'Comportamentale',
  company: 'Azienda',
  system_design: 'System design',
  review: 'Ripasso',
}

export function KindBadge({ kind }: { kind: ItemKind }) {
  return <span className="badge">{KIND_LABEL[kind] ?? kind}</span>
}

const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  easy: 'Facile',
  medium: 'Media',
  hard: 'Difficile',
}

export function DifficultyBadge({ level }: { level: Difficulty }) {
  return <span className={`badge ${level}`}>{DIFFICULTY_LABEL[level] ?? level}</span>
}

/** Rende un testo multi-paragrafo preservando le righe vuote. */
export function Prose({ text }: { text: string }) {
  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim())
  return (
    <div className="prose">
      {paragraphs.map((p, i) => (
        <p key={i}>{p.trim()}</p>
      ))}
    </div>
  )
}

export function Bullets({ items, title }: { items: string[]; title?: string }) {
  if (!items.length) return null
  return (
    <>
      {title && <h3>{title}</h3>}
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </>
  )
}

export const CATEGORY_LABEL: Record<string, string> = {
  'core-concepts': 'Fondamenti API & HTTP',
  databases: 'Database e dati',
  caching: 'Caching e performance',
  distributed: 'Sistemi distribuiti',
  reliability: 'Affidabilità',
  dsa: 'Algoritmi e strutture dati',
  'system-design': 'System design',
  behavioral: 'Comportamentale',
  company: 'Azienda e carriera',
  engineering: 'Pratiche di ingegneria',
  languages: 'Linguaggi',
  patterns: 'Architettura del codice',
  frontend: 'Frontend e interfacce',
}

export function categoryLabel(id: string): string {
  return CATEGORY_LABEL[id] ?? id
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h}h ${m}min` : `${h}h`
}

export function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}
