import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  executeTask,
  getSuggestions,
  getTask,
  getTaskSteps,
  listTasks,
  observeTask,
  type MigrationTask,
  type Suggestion,
} from '@/api/task'

export interface AgentStep {
  taskId: number
  runId: string
  stage: string
  agentName: string
  status: string
  elapsedMs?: number
  confidence?: number
  payload?: Record<string, unknown>
}

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<MigrationTask[]>([])
  const current = ref<MigrationTask | null>(null)
  const suggestions = ref<Suggestion[]>([])
  const steps = ref<AgentStep[]>([])
  const progress = ref(0)
  const starting = ref(false)
  const streaming = ref(false)
  const terminalStatus = ref<string | null>(null)
  const streamError = ref<string | null>(null)
  const streamStoppedByUser = ref(false)
  const activeRunId = ref<string | null>(null)
  let abortController: AbortController | null = null

  async function refreshAll() {
    tasks.value = await listTasks()
  }

  async function loadOne(id: number) {
    const snapshot = await fetchSnapshot(id)
    applySnapshot(snapshot)
  }

  async function fetchSnapshot(id: number) {
    const [task, taskSuggestions, persistedSteps] = await Promise.all([
      getTask(id),
      getSuggestions(id),
      getTaskSteps(id),
    ])
    return { task, taskSuggestions, persistedSteps }
  }

  function applySnapshot({
    task,
    taskSuggestions,
    persistedSteps,
  }: Awaited<ReturnType<typeof fetchSnapshot>>) {
    current.value = task
    suggestions.value = taskSuggestions
    steps.value = persistedSteps.map((step) => ({
      taskId: step.taskId,
      runId: task.runId ?? '',
      stage: step.stage,
      agentName: step.agentName,
      status: step.status,
      elapsedMs: step.elapsedMs ?? undefined,
      confidence: step.confidence ?? undefined,
      payload: parsePayload(step.payload),
    }))
    activeRunId.value = task.runId
    progress.value = isTerminal(task.status)
      ? 100
      : Math.min(95, Math.round((steps.value.length / 6) * 100))
    terminalStatus.value = ['DONE', 'FAILED', 'REVIEW_REQUIRED'].includes(current.value.status)
      ? current.value.status
      : null
    streamError.value = task.status === 'FAILED' ? task.errorMessage : null
  }

  async function runTask(id: number) {
    stopStream(false)
    steps.value = []
    progress.value = 0
    terminalStatus.value = null
    streamError.value = null
    streamStoppedByUser.value = false
    starting.value = true
    try {
      const started = await executeTask(id)
      activeRunId.value = started.runId
      if (current.value) {
        current.value.status = started.status
        current.value.runId = started.runId
      }
      await watchRun(id, started.runId)
    } catch (error) {
      setUnexpectedError(error)
    } finally {
      starting.value = false
    }
  }

  async function resumeStream(id: number) {
    const runId = current.value?.runId ?? activeRunId.value
    if (!runId) {
      streamError.value = '当前任务没有可连接的运行记录'
      return
    }
    streamError.value = null
    streamStoppedByUser.value = false
    await watchRun(id, runId)
  }

  async function watchRun(id: number, runId: string) {
    stopStream(false)
    const controller = new AbortController()
    abortController = controller
    streaming.value = true
    try {
      await observeTask(id, runId, controller.signal, handleEvent)
    } catch (error) {
      setUnexpectedError(error)
    } finally {
      // A stopped stream may settle after a reconnect has already installed a
      // new controller. Only the stream that still owns the controller may
      // apply a fetched snapshot or mutate the shared connection state.
      if (abortController !== controller) return
      streaming.value = false
      try {
        const snapshot = await fetchSnapshot(id)
        if (abortController !== controller) return
        applySnapshot(snapshot)
        if (current.value?.status === 'RUNNING' && !streamStoppedByUser.value && !streamError.value) {
          streamStoppedByUser.value = true
        }
      } catch (error) {
        if (abortController === controller) setUnexpectedError(error)
      } finally {
        if (abortController === controller) abortController = null
      }
    }
  }

  function handleEvent(event: { name: string; data: string }) {
    try {
      if (event.name === 'step') {
        steps.value.push(JSON.parse(event.data) as AgentStep)
      } else if (event.name === 'progress') {
        progress.value = Math.max(0, Math.min(100, Number(event.data) || 0))
      } else if (event.name === 'completed' || event.name === 'failed') {
        const terminal = JSON.parse(event.data) as { status?: string; error?: string }
        terminalStatus.value = terminal.status ?? (event.name === 'failed' ? 'FAILED' : 'DONE')
        streamError.value = terminal.error ?? null
        progress.value = 100
      }
    } catch {
      streamError.value = `无法解析任务流事件：${event.name}`
    }
  }

  function stopStream(byUser = true) {
    if (byUser && streaming.value) streamStoppedByUser.value = true
    abortController?.abort()
    streaming.value = false
  }

  function setUnexpectedError(error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    streamError.value = error instanceof Error ? error.message : String(error)
  }

  function parsePayload(payload: string | null): Record<string, unknown> {
    if (!payload) return {}
    try {
      return JSON.parse(payload) as Record<string, unknown>
    } catch {
      return { raw: payload }
    }
  }

  function isTerminal(status: string) {
    return ['DONE', 'FAILED', 'REVIEW_REQUIRED'].includes(status)
  }

  return {
    tasks,
    current,
    suggestions,
    steps,
    progress,
    starting,
    streaming,
    terminalStatus,
    streamError,
    streamStoppedByUser,
    activeRunId,
    refreshAll,
    loadOne,
    runTask,
    resumeStream,
    stopStream,
  }
})
