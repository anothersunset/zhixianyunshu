// v2-step-26: TTS 前端服务 — 调 RAG /tts/speak (edge-tts 代理), 返 audio blob
import axios from 'axios'

const RAG_BASE = (import.meta.env.VITE_RAG_BASE_URL as string) || 'http://localhost:8001'

export interface SpeakOptions {
  text: string
  voice?: string   // 默 zh-CN-XiaoxiaoNeural
  rate?: string    // 默 +0%
  volume?: string  // 默 +0%
}

let currentAudio: HTMLAudioElement | null = null

export async function speak(opts: SpeakOptions): Promise<void> {
  stop()
  const params = new URLSearchParams({
    text: opts.text,
    voice: opts.voice || 'zh-CN-XiaoxiaoNeural',
    rate: opts.rate || '+0%',
    volume: opts.volume || '+0%',
  })
  const res = await axios.get(`${RAG_BASE}/tts/speak?${params.toString()}`, {
    responseType: 'blob',
    validateStatus: () => true,
  })
  if (res.status >= 400) {
    // 未装 edge-tts 优雅降级 — 走浏览器原生 SpeechSynthesis
    fallbackBrowserTts(opts)
    return
  }
  const url = URL.createObjectURL(res.data as Blob)
  currentAudio = new Audio(url)
  currentAudio.onended = () => URL.revokeObjectURL(url)
  await currentAudio.play()
}

export function stop() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
}

export function ttsStatus(): Promise<{ available: boolean; engine?: string }> {
  return axios.get(`${RAG_BASE}/tts/status`, { validateStatus: () => true })
    .then(r => r.status < 400 ? r.data : { available: false })
    .catch(() => ({ available: false }))
}

function fallbackBrowserTts(opts: SpeakOptions) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  const u = new SpeechSynthesisUtterance(opts.text)
  u.lang = opts.voice && opts.voice.startsWith('en') ? 'en-US' : 'zh-CN'
  window.speechSynthesis.speak(u)
}
