import http from './http'

export interface LoginResult {
  token: string
  role: string
  username: string
  displayName: string
}

export function login(username: string, password: string): Promise<LoginResult> {
  return http.post('/auth/login', { username, password })
}

export function getMe(): Promise<{
  id: number; username: string; displayName: string; role: string
}> {
  return http.get('/users/me')
}
