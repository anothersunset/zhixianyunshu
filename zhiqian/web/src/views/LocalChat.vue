<!-- v2-step-28 (polish): 端侧 LLM Demo。加载 Phi-3.5-mini ONNX, 走 WebGPU / WASM, 后端完全不走。
     注: 不能直接在 Vue template 用二重大括号绑定 — 上游 URL 压缩会吞掉, 故全程用 v-text / v-bind。-->
<script setup lang="ts">
import { ref } from 'vue'
import { useLocalLlm, isWebGpuAvailable } from '@/composables/useLocalLlm'

const { state, progress, errorMsg, init, generate } = useLocalLlm()
const input = ref('帮我把 SELECT IFNULL(a, b) FROM t LIMIT 5,10 转为 openGauss SQL')
const output = ref('')
const loading = ref(false)
const webgpu = isWebGpuAvailable()

async function onLoad() {
  await init()
}

async function onSend() {
  if (state.value !== 'ready' && state.value !== 'thinking') return
  loading.value = true
  output.value = ''
  const prompt = `<|system|>\n你是 SQL 转译助手, 需要把 MySQL SQL 转为 openGauss SQL.\n<|user|>\n${input.value}\n<|assistant|>\n`
  output.value = await generate(prompt, 256)
  loading.value = false
}
</script>

<template>
  <div class="local-chat">
    <h2>💻 端侧推理 Demo</h2>
    <p class="note">本页完全走浏览器 (transformers.js + Phi-3.5-mini ONNX), 不走后端。</p>
    <div class="badges">
      <el-tag :type="webgpu ? 'success' : 'warning'" v-text="webgpu ? 'WebGPU ✓' : 'WASM (fallback)'" />
      <el-tag>
        状态: <span v-text="state" />
      </el-tag>
      <el-tag v-if="state === 'loading'">
        <span v-text="progress" />%
      </el-tag>
    </div>

    <el-button v-if="state === 'idle' || state === 'error'" type="primary" @click="onLoad">
      加载模型 (首次 ~ 600MB, 之后缓存)
    </el-button>
    <el-alert v-if="errorMsg" type="error" :title="errorMsg" />

    <div v-if="state === 'ready' || state === 'thinking'" class="chat-area">
      <el-input v-model="input" type="textarea" :rows="3" placeholder="说点什么…" />
      <el-button type="primary" :loading="loading" @click="onSend" style="margin-top: 10px">发送</el-button>
      <div v-if="output" class="output">
        <h4>回复:</h4>
        <pre v-text="output" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.local-chat { padding: 24px; max-width: 900px; margin: 0 auto; }
.note { color: var(--zq-text-secondary); margin: 8px 0 16px; }
.badges { display: flex; gap: 8px; margin-bottom: 16px; }
.chat-area { margin-top: 20px; }
.output { margin-top: 20px; padding: 16px; background: var(--zq-bg-tertiary); border-radius: 6px; }
.output pre { white-space: pre-wrap; font-family: Menlo, Consolas, monospace; font-size: 13px; }
</style>
