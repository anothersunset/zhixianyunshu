/**
 * v2-step-10: rag /transpile API 包装。
 *
 * 直接打 rag service (默认 http://localhost:8001), 不走 backend 代理, 避免额外路由。
 * 靠 rag main.py 的 CORS allow_origins=['*'] 走通。
 * 生产环境可用 nginx /transpile -> http://rag:8001/transpile 。
 */
import axios from 'axios'

const ragHttp = axios.create({
  baseURL: import.meta.env.VITE_RAG_BASE || 'http://localhost:8001',
  timeout: 15000,
})

export interface TranspileReq {
  sql: string
  source?: string
  target?: string
  explain?: boolean
  pretty?: boolean
}

export interface TranspileResp {
  ok: boolean
  source: string
  target?: string
  source_dialect?: string
  target_dialect?: string
  notes?: Array<{ keyword: string; note: string }>
  sqlglot_version?: string
  error?: string
}

export async function transpile(req: TranspileReq): Promise<TranspileResp> {
  const r = await ragHttp.post('/transpile', req)
  return r.data
}

export interface TranspileBatchResp {
  items: Array<Record<string, any>>
  summary: { total: number; ok: number; fail: number }
}

export async function transpileBatch(
  sqls: string[],
  source = 'mysql',
  target = 'postgres',
): Promise<TranspileBatchResp> {
  const r = await ragHttp.post('/transpile/batch', { sqls, source, target })
  return r.data
}

export async function getRagHealth(): Promise<any> {
  const r = await ragHttp.get('/health')
  return r.data
}
