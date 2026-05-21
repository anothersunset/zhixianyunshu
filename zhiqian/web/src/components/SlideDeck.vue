<!-- v2-step-26: 幻灯片容器。接受 slides 数组, 提供 ←/→ / Home/End / Esc 控制。-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { speak, stop as stopTts } from '@/services/tts'

export interface Slide {
  title: string
  body?: string
  bullets?: string[]
  notes?: string
  color?: string
}

const props = defineProps<{ slides: Slide[] }>()
const router = useRouter()
const idx = ref(0)
const playing = ref(false)

const current = computed<Slide>(() => props.slides[idx.value] || { title: '' })
const total = computed(() => props.slides.length)

function next() { if (idx.value < total.value - 1) { idx.value++; stopTts() } }
function prev() { if (idx.value > 0) { idx.value--; stopTts() } }
function first() { idx.value = 0; stopTts() }
function last() { idx.value = total.value - 1; stopTts() }
function exit() { stopTts(); router.push('/') }

async function readAloud() {
  if (playing.value) { stopTts(); playing.value = false; return }
  playing.value = true
  const s = current.value
  const text = [s.title, s.body, ...(s.bullets || [])].filter(Boolean).join('. ')
  try { await speak({ text }) } finally { playing.value = false }
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); next() }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev() }
  else if (e.key === 'Home') { e.preventDefault(); first() }
  else if (e.key === 'End') { e.preventDefault(); last() }
  else if (e.key === 'Escape') { e.preventDefault(); exit() }
  else if (e.key.toLowerCase() === 'r') { e.preventDefault(); readAloud() }
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); stopTts() })
watch(idx, () => { /* slide changed */ })
</script>

<template>
  <div class="slide-deck" :data-color="current.color || 'blue'">
    <div class="slide">
      <h1 v-text="current.title" />
      <p v-if="current.body" class="body" v-text="current.body" />
      <ul v-if="current.bullets && current.bullets.length" class="bullets">
        <li v-for="(b, i) in current.bullets" :key="i" v-text="b" />
      </ul>
    </div>
    <div class="hud">
      <span class="page">
        <span v-text="idx + 1" /> / <span v-text="total" />
      </span>
      <button @click="prev" :disabled="idx === 0">←</button>
      <button @click="next" :disabled="idx === total - 1">→</button>
      <button @click="readAloud" :class="{ active: playing }">🔊 读稿</button>
      <button @click="exit">✖</button>
    </div>
    <div v-if="current.notes" class="notes" v-text="current.notes" />
  </div>
</template>

<style scoped>
.slide-deck {
  position: fixed; inset: 0; background: var(--zq-bg-primary, #111);
  color: var(--zq-text-primary, #f8f8f8);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  font-family: 'PingFang SC', 'Noto Sans CJK SC', sans-serif;
}
.slide { max-width: 80vw; text-align: left; padding: 4vh 6vw; }
.slide h1 { font-size: 4.2rem; margin-bottom: 2rem; color: #0c66e4; font-weight: 700; }
.slide .body { font-size: 1.6rem; line-height: 1.7; opacity: 0.92; }
.slide .bullets { list-style: '▶  '; padding-left: 1em; }
.slide .bullets li { font-size: 1.4rem; line-height: 2; margin-bottom: 0.4rem; }
.hud { position: absolute; bottom: 2vh; right: 3vw; display: flex; gap: 8px; align-items: center; opacity: 0.65; }
.hud .page { font-variant-numeric: tabular-nums; font-size: 0.95rem; }
.hud button { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18);
  color: inherit; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 1rem; }
.hud button:hover:not(:disabled) { background: rgba(255,255,255,0.18); }
.hud button:disabled { opacity: 0.3; cursor: not-allowed; }
.hud button.active { background: #0c66e4; border-color: #0c66e4; }
.notes { position: absolute; bottom: 2vh; left: 3vw; max-width: 50vw;
  font-size: 0.85rem; opacity: 0.45; font-style: italic; }
</style>
