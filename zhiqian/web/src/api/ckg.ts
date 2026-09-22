// v2-step-16: CKG graph backend client
import http from './http'

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

// 复用共享 http 实例: 统一注入 Bearer token, 且 401/403 时清 token 跳登录。
// 响应拦截器已解包 {code,message,data} 信封, 直接返回 CkgGraphResp。
export async function fetchCkgGraph(projectId: number): Promise<CkgGraphResp> {
  return http.get('/ckg/graph', { params: { projectId } })
}
