import http from './http'

export interface ReportStatus {
  typst_available?: boolean
}

export interface ReportStats {
  total_sql?: number
  success?: number
  manual?: number
  high_risk?: number
  tables?: number
  indexes_changed?: number
}

export interface ReportRisk {
  kind: string
  description: string
  level: string
  suggestion: string
}

export interface ReportExample {
  title: string
  source: string
  target: string
  explanation: string
}

export interface ReportPayload {
  project_name: string
  source_dialect?: string
  target_dialect?: string
  generated_at?: string
  owner?: string
  summary?: string
  stats?: ReportStats
  risks?: ReportRisk[]
  examples?: ReportExample[]
}

export function getReportStatus(): Promise<ReportStatus> {
  return http.get('/reports/status')
}

export function generatePdf(payload: ReportPayload): Promise<Blob> {
  return http.post('/reports/generate', payload, { responseType: 'blob' })
}
