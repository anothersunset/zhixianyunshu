import http from './http'

export interface Project {
  id: number
  name: string
  sourceDb: string
  targetDb: string
  framework: string
  description: string
  status: string
  createdAt: string
}

export function listProjects(): Promise<Project[]> {
  return http.get('/projects')
}

export function getProject(id: number): Promise<Project> {
  return http.get(`/projects/${id}`)
}
