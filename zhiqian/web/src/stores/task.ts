import { defineStore } from 'pinia'
import { ref } from 'vue'
import { buildSseUrl, getSuggestions, getTask, listTasks, type MigrationTask, type Suggestion } from '@/api/task'

export interface AgentStep {
  taskId: number
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
  let es: EventSource | null = null

  async function refreshAll() {
    tasks.value = await listTasks()
  }

  async function loadOne(id: number) {
    current.value = await getTask(id)
    suggestions.value = await getSuggestions(id)
    steps.value = []
    progress.value = 0
  }

  function streamTask(id: number) {
    stopStream()
    steps.value = []
    progress.value = 0
    es = new EventSource(buildSseUrl(id))
    es.addEventListener('step', (e: MessageEvent) => {
      try {
        const step = JSON.parse(e.data) as AgentStep
        steps.value.push(step)
      } catch (err) { console.warn('parse step failed', err) }
    })
    es.addEventListener('progress', (e: MessageEvent) => {
      progress.value = Number(e.data) || 0
    })
    es.onerror = () => { stopStream() }
  }

  function stopStream() {
    if (es) { es.close(); es = null }
  }

  return { tasks, current, suggestions, steps, progress, refreshAll, loadOne, streamTask, stopStream }
})
