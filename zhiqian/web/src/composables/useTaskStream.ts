import { onUnmounted, ref } from "vue"

export interface AgentStepEvent {
  taskId: number
  stage: string
  agentName?: string
  status?: string
  elapsedMs?: number
  confidence?: number
  payload?: unknown
}

export function useTaskStream(taskId: number) {
  const steps = ref<AgentStepEvent[]>([])
  const connected = ref(false)
  const progress = ref(0)

  const token = localStorage.getItem("zhiqian_jwt") ?? ""
  const url = `/api/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`
  const es = new EventSource(url, { withCredentials: false })

  es.onopen = () => (connected.value = true)
  es.addEventListener("step", (ev) => {
    const data = JSON.parse((ev as MessageEvent).data) as AgentStepEvent
    steps.value.push(data)
  })
  es.addEventListener("progress", (ev) => {
    progress.value = Number((ev as MessageEvent).data)
  })
  es.onerror = () => (connected.value = false)

  onUnmounted(() => es.close())

  return { steps, connected, progress }
}
