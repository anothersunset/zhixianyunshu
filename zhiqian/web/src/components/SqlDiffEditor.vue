<template>
  <div ref="el" class="sql-diff" :style="{ height }"></div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  original: string
  modified: string
  language?: string
  height?: string
  theme?: 'vs' | 'vs-dark' | 'hc-black'
  readOnly?: boolean
}>(), {
  language: 'sql',
  height: '420px',
  theme: 'vs-dark',
  readOnly: true,
})

const el = ref<HTMLDivElement | null>(null)
let editor: any = null
let monacoMod: any = null

onMounted(async () => {
  // v2-step-10: 关闭 worker 要求, 走主线程语法服务。SQL diff 只需高亮+diff, 足够。
  ;(self as any).MonacoEnvironment = {
    getWorkerUrl: () => 'data:text/javascript;charset=utf-8,',
  }
  monacoMod = await import('monaco-editor/esm/vs/editor/editor.api')
  if (!el.value) return
  editor = monacoMod.editor.createDiffEditor(el.value, {
    theme: props.theme,
    readOnly: props.readOnly,
    renderSideBySide: true,
    automaticLayout: true,
    fontSize: 13,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    originalEditable: false,
  })
  setModel()
})

function setModel() {
  if (!editor || !monacoMod) return
  // 释放旧 model
  const old = editor.getModel()
  if (old) {
    old.original?.dispose()
    old.modified?.dispose()
  }
  const original = monacoMod.editor.createModel(props.original || '', props.language)
  const modified = monacoMod.editor.createModel(props.modified || '', props.language)
  editor.setModel({ original, modified })
}

watch(() => [props.original, props.modified, props.language], () => setModel())

onBeforeUnmount(() => {
  if (editor) {
    const m = editor.getModel()
    editor.dispose()
    m?.original?.dispose()
    m?.modified?.dispose()
  }
})
</script>

<style scoped>
.sql-diff {
  width: 100%;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #2c3e50;
}
</style>
