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
  sourceSql: string | null
  resultSql: string | null
  errorMessage: string | null
  runId: string | null
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

export interface StartTaskResponse {
  taskId: number
  runId: string
  status: string
}

export interface TaskStreamEvent {
  name: string
  data: string
}

export interface PersistedAgentStep {
  id: number
  taskId: number
  stage: string
  agentName: string
  status: string
  elapsedMs: number | null
  confidence: number | null
  payload: string | null
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

export function getTaskSteps(taskId: number): Promise<PersistedAgentStep[]> {
  return http.get(`/tasks/${taskId}/steps`)
}

export function executeTask(taskId: number): Promise<StartTaskResponse> {
  return http.post(`/tasks/${taskId}/execute`)
}

export async function observeTask(
  taskId: number,
  runId: string,
  signal: AbortSignal,
  onEvent: (event: TaskStreamEvent) => void,
): Promise<void> {
  const base = import.meta.env.VITE_API_BASE || '/api'
  const token = localStorage.getItem('zq_token') || ''
  const response = await fetch(
    `${base}/tasks/${taskId}/stream?runId=${encodeURIComponent(runId)}`,
    {
      headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
      signal,
    },
  )
  if (!response.ok) {
    const detail = (await response.text()).trim()
    throw new Error(`任务流连接失败（${response.status}）${detail ? `：${detail}` : ''}`)
  }
  const reader = response.body?.getReader()
  if (!reader) throw new Error('SSE response has no body')

  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      let name = 'message'
      const data: string[] = []
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith('event:')) name = line.slice(6).trim()
        if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
      }
      if (data.length) onEvent({ name, data: data.join('\n') })
    }
  }
}
