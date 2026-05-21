// v2-step-28: 端侧 LLM。transformers.js v3 + WebGPU 首选, WASM 降级。
// 读者可在火车/飞机上玩转译 Demo, 后端完全不动。
import { ref } from 'vue'

export type LocalLlmState = 'idle' | 'loading' | 'ready' | 'thinking' | 'error'

const state = ref<LocalLlmState>('idle')
const progress = ref(0)
const errorMsg = ref('')
// pipeline lazy 加, 类型 unknown 避免引 transformers.js 类型依赖
let generator: any = null

export function useLocalLlm() {
  async function init(modelId = 'Xenova/Phi-3.5-mini-instruct-onnx-web') {
    if (state.value !== 'idle' && state.value !== 'error') return
    state.value = 'loading'
    progress.value = 0
    errorMsg.value = ''
    try {
      // dynamic import 避免初始 bundle 肥肿
      // @ts-ignore - 包由者自装
      const { pipeline, env } = await import('@xenova/transformers')
      env.allowLocalModels = false  // CDN 拉
      env.backends.onnx.wasm.numThreads = navigator.hardwareConcurrency || 4

      const device = (navigator as any).gpu ? 'webgpu' : 'wasm'
      generator = await pipeline('text-generation', modelId, {
        device,
        dtype: device === 'webgpu' ? 'q4' : 'q4',
        progress_callback: (p: { progress?: number }) => {
          if (typeof p.progress === 'number') progress.value = Math.floor(p.progress)
        },
      } as any)
      state.value = 'ready'
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = String(e?.message || e)
    }
  }

  async function generate(prompt: string, maxNewTokens = 256): Promise<string> {
    if (!generator) throw new Error('generator not initialised')
    state.value = 'thinking'
    try {
      const out: any = await generator(prompt, {
        max_new_tokens: maxNewTokens, temperature: 0.3, do_sample: true,
      })
      state.value = 'ready'
      // transformers.js 返为 [{generated_text}]
      const text = Array.isArray(out) ? out[0]?.generated_text : out?.generated_text
      return String(text || '').slice(prompt.length).trim()
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = String(e?.message || e)
      return ''
    }
  }

  return { state, progress, errorMsg, init, generate }
}

export function isWebGpuAvailable(): boolean {
  return typeof navigator !== 'undefined' && !!(navigator as any).gpu
}
