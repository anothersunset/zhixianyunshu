/** Shared shape for the task timeline. Streaming is owned by the task store. */
export interface AgentStepEvent {
  taskId: number
  runId?: string
  stage: string
  agentName?: string
  status?: string
  elapsedMs?: number
  confidence?: number
  payload?: unknown
}
