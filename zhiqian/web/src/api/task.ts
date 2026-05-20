import http from './http'

export interface MigrationTask {
  id: number
  projectId: number
  name: string
  status: string
  avgConfidence: number | null
  totalUnits: number | null
  reviewRequired: number | null
  createdAt: string
  finishedAt: string | null
}

export interface Suggestion {
  id: number
  taskId: number
  category: string
  target: string
  riskLevel: string
  confidence: number | null
  reviewStatus: string
  unifiedDiff: string
  rationale: string
  createdAt: string
}

export function listTasks(): Promise<MigrationTask[]> {
  return http.get('/tasks')
}

export function getTask(id: number): Promise<MigrationTask> {
  return http.get(`/tasks/${id}`)
}

export function getSuggestions(taskId: number): Promise<Suggestion[]> {
  return http.get(`/tasks/${taskId}/suggestions`)
}

export function buildSseUrl(taskId: number): string {
  const base = import.meta.env.VITE_API_BASE || '/api'
  const token = localStorage.getItem('zq_token') || ''
  return `${base}/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`
}
