import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
})

http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('zq_token')
  if (token) {
    cfg.headers = cfg.headers || {}
    cfg.headers['Authorization'] = `Bearer ${token}`
  }
  return cfg
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(body)
      }
      return body.data
    }
    return body
  },
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem('zq_token')
      ElMessage.warning('登录已过期，请重新登录')
      window.location.hash = '#/login'
    } else {
      ElMessage.error(err?.message || '网络异常')
    }
    return Promise.reject(err)
  },
)

export default http
