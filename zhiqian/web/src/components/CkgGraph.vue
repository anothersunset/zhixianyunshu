<template>
  <div class="ckg-graph">
    <div ref="container" class="cy"></div>
    <div class="legend">
      <span class="item"><span class="dot c-file"></span>File</span>
      <span class="item"><span class="dot c-class"></span>Class</span>
      <span class="item"><span class="dot c-method"></span>Method</span>
      <span class="item"><span class="dot c-table"></span>Table</span>
      <span class="item"><span class="dot c-column"></span>Column</span>
    </div>
  </div>
</template>

<script setup lang="ts">
// v2-step-16: Cytoscape.js wrapper. lazy import keeps main bundle slim.
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import type { CkgNode, CkgEdge } from '@/api/ckg'

const props = defineProps<{
  nodes: CkgNode[]
  edges: CkgEdge[]
  typeFilter?: string[]
  search?: string
}>()

const emit = defineEmits<{ (e: 'node-click', node: CkgNode): void }>()

const container = ref<HTMLDivElement | null>(null)
let cy: any = null

const COLOR_MAP: Record<string, string> = {
  File: '#3b82f6',
  Class: '#10b981',
  Method: '#f59e0b',
  Table: '#8b5cf6',
  Column: '#6b7280',
}

async function initCy() {
  if (!container.value) return
  const cytoscape = (await import('cytoscape')).default
  const fcose = (await import('cytoscape-fcose')).default
  try { cytoscape.use(fcose) } catch (e) { /* already registered */ }

  cy = cytoscape({
    container: container.value,
    elements: buildElements(),
    style: [
      {
        selector: 'node',
        style: {
          'background-color': (ele: any) => COLOR_MAP[ele.data('type')] || '#94a3b8',
          'label': 'data(label)',
          'color': '#1f2937',
          'font-size': 11,
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'width': 28,
          'height': 28,
          'border-width': 1,
          'border-color': '#fff',
        },
      },
      {
        selector: 'node:selected',
        style: { 'border-width': 3, 'border-color': '#0ea5e9' },
      },
      {
        selector: 'node.dim',
        style: { 'opacity': 0.15 },
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#cbd5e1',
          'target-arrow-color': '#cbd5e1',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': 9,
          'color': '#94a3b8',
        },
      },
      {
        selector: 'edge[type = "calls"]',
        style: { 'line-style': 'dashed', 'line-color': '#f59e0b' },
      },
      {
        selector: 'edge[type = "reads"]',
        style: { 'line-style': 'dotted', 'line-color': '#8b5cf6' },
      },
      {
        selector: 'edge.dim',
        style: { 'opacity': 0.1 },
      },
    ],
    layout: { name: 'fcose', animate: true, randomize: true, nodeRepulsion: 5000, idealEdgeLength: 80 } as any,
    wheelSensitivity: 0.2,
  })

  cy.on('tap', 'node', (evt: any) => {
    const n = evt.target.data()
    emit('node-click', n)
  })
  applyFilter()
}

function buildElements() {
  const els: any[] = []
  for (const n of props.nodes) {
    els.push({ data: { id: n.id, label: n.label, type: n.type, ...n.properties } })
  }
  for (const e of props.edges) {
    els.push({ data: { id: e.id, source: e.source, target: e.target, type: e.type, label: e.label || e.type } })
  }
  return els
}

function applyFilter() {
  if (!cy) return
  const types = props.typeFilter && props.typeFilter.length > 0 ? new Set(props.typeFilter) : null
  const search = (props.search || '').trim().toLowerCase()
  cy.batch(() => {
    cy.nodes().forEach((n: any) => {
      const d = n.data()
      const typeOk = !types || types.has(d.type)
      const searchOk = !search || (d.label || '').toLowerCase().includes(search)
      if (typeOk && searchOk) n.removeClass('dim')
      else n.addClass('dim')
    })
    cy.edges().forEach((e: any) => {
      const sOk = !e.source().hasClass('dim')
      const tOk = !e.target().hasClass('dim')
      if (sOk && tOk) e.removeClass('dim')
      else e.addClass('dim')
    })
  })
}

async function refresh() {
  if (!cy) { await initCy(); return }
  cy.elements().remove()
  cy.add(buildElements())
  cy.layout({ name: 'fcose', animate: true, randomize: true, nodeRepulsion: 5000, idealEdgeLength: 80 } as any).run()
  applyFilter()
}

onMounted(initCy)
onBeforeUnmount(() => { if (cy) { cy.destroy(); cy = null } })
watch(() => [props.nodes, props.edges], refresh, { deep: true })
watch(() => [props.typeFilter, props.search], applyFilter, { deep: true })

defineExpose({ fit: () => cy && cy.fit(undefined, 40) })
</script>

<style scoped>
.ckg-graph { position: relative; width: 100%; height: 600px; background: #f8fafc; border-radius: 6px; overflow: hidden; }
.cy { width: 100%; height: 100%; }
.legend { position: absolute; bottom: 8px; left: 8px; display: flex; gap: 12px; background: rgba(255,255,255,0.9); padding: 6px 10px; border-radius: 4px; font-size: 12px; }
.item { display: flex; align-items: center; gap: 4px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.c-file { background: #3b82f6; }
.c-class { background: #10b981; }
.c-method { background: #f59e0b; }
.c-table { background: #8b5cf6; }
.c-column { background: #6b7280; }
</style>
