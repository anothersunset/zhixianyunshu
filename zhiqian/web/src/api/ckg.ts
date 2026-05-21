// v2-step-16: CKG graph backend client
import axios from 'axios'

export interface CkgNode {
  id: string
  label: string
  type: string
  properties?: Record<string, any>
}

export interface CkgEdge {
  id: string
  source: string
  target: string
  type: string
  label?: string
}

export interface CkgGraphResp {
  nodes: CkgNode[]
  edges: CkgEdge[]
  projectId: number
  demo: boolean
  stats?: Record<string, number>
}

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('zq_token')
  if (t) cfg.headers.Authorization = 'Bearer ' + t
  return cfg
})

export async function fetchCkgGraph(projectId: number): Promise<CkgGraphResp> {
  const { data } = await api.get('/ckg/graph', { params: { projectId } })
  return (data && data.data) ? data.data : data
}
