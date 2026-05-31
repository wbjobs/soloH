<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  Calendar,
  Layout,
  SlidersHorizontal,
  Filter,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  Download,
  X,
  Loader,
  MapPin,
  ArrowRightLeft,
  AlertTriangle,
  Users
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useAddressStore } from '@/stores/address'
import { RISK_LEVELS, NODE_CATEGORIES, CHART_COLORS } from '@/utils/constants'
import { formatBTC, formatNumber, formatDate, formatHash } from '@/utils/format'
import type { GraphNode, GraphEdge } from '@/types'

const router = useRouter()
const appStore = useAppStore()
const addressStore = useAddressStore()

const loading = ref(true)
const searchQuery = ref('')
const timeRange = ref('7d')
const layoutType = ref('force')
const minValue = ref(0.1)
const nodeTypes = ref<string[]>(['address', 'transaction'])
const riskLevels = ref<string[]>(['high', 'critical'])
const selectedNode = ref<GraphNode | null>(null)
const selectedEdge = ref<GraphEdge | null>(null)
const showFilters = ref(true)
const showInfoPanel = ref(true)
const zoom = ref(1)

const graphData = ref<{ nodes: GraphNode[]; edges: GraphEdge[] }>({
  nodes: [],
  edges: []
})

const svgRef = ref<SVGSVGElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

const nodePositions = ref<Map<string, { x: number; y: number }>>(new Map())

const nodeColors: Record<string, string> = {
  normal: '#3b82f6',
  suspicious: '#ef4444',
  cluster: '#8b5cf6'
}

const layoutOptions = [
  { value: 'force', label: '力导向布局' },
  { value: 'circular', label: '环形布局' },
  { value: 'tree', label: '树形布局' },
  { value: 'grid', label: '网格布局' }
]

const timeRangeOptions = [
  { value: '1d', label: '最近1天' },
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
  { value: '90d', label: '最近90天' },
  { value: 'all', label: '全部' }
]

const riskLevelOptions = [
  { value: 'low', label: '低风险', color: RISK_LEVELS.low.color },
  { value: 'medium', label: '中风险', color: RISK_LEVELS.medium.color },
  { value: 'high', label: '高风险', color: RISK_LEVELS.high.color },
  { value: 'critical', label: '极高风险', color: RISK_LEVELS.critical.color }
]

const nodeTypeOptions = [
  { value: 'address', label: '地址节点' },
  { value: 'transaction', label: '交易节点' }
]

function getNodeColor(node: GraphNode): string {
  if (node.suspiciousScore !== undefined) {
    if (node.suspiciousScore >= 75) return RISK_LEVELS.critical.color
    if (node.suspiciousScore >= 50) return RISK_LEVELS.high.color
    if (node.suspiciousScore >= 25) return RISK_LEVELS.medium.color
    return RISK_LEVELS.low.color
  }
  return nodeColors[node.category] || '#6b7280'
}

function getNodeSize(node: GraphNode): number {
  const baseSize = node.category === 'cluster' ? 16 : node.category === 'suspicious' ? 14 : 12
  const score = node.suspiciousScore || 0
  return baseSize + (score / 100) * 10
}

function getEdgeWidth(edge: GraphEdge): number {
  const value = edge.value || 0
  return Math.max(1, Math.min(5, Math.log10(value + 1) * 0.8))
}

function getEdgeColor(edge: GraphEdge): string {
  const value = edge.value || 0
  if (value >= 10) return RISK_LEVELS.critical.color
  if (value >= 1) return RISK_LEVELS.high.color
  if (value >= 0.1) return RISK_LEVELS.medium.color
  return '#9ca3af'
}

function calculatePositions() {
  const width = 800
  const height = 500
  const centerX = width / 2
  const centerY = height / 2

  if (layoutType.value === 'circular') {
    const radius = Math.min(width, height) * 0.35
    const angleStep = (2 * Math.PI) / graphData.value.nodes.length

    graphData.value.nodes.forEach((node, index) => {
      const angle = index * angleStep - Math.PI / 2
      nodePositions.value.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      })
    })
  } else if (layoutType.value === 'grid') {
    const cols = Math.ceil(Math.sqrt(graphData.value.nodes.length))
    const rows = Math.ceil(graphData.value.nodes.length / cols)
    const cellWidth = width / (cols + 1)
    const cellHeight = height / (rows + 1)

    graphData.value.nodes.forEach((node, index) => {
      const col = index % cols
      const row = Math.floor(index / cols)
      nodePositions.value.set(node.id, {
        x: cellWidth * (col + 1),
        y: cellHeight * (row + 1)
      })
    })
  } else if (layoutType.value === 'tree') {
    const levels: Record<number, GraphNode[]> = {}
    const visited = new Set<string>()
    const queue: { node: GraphNode; level: number }[] = []

    if (graphData.value.nodes.length > 0) {
      queue.push({ node: graphData.value.nodes[0], level: 0 })
      visited.add(graphData.value.nodes[0].id)
    }

    while (queue.length > 0) {
      const { node, level } = queue.shift()!
      if (!levels[level]) levels[level] = []
      levels[level].push(node)

      graphData.value.edges.forEach(edge => {
        let neighborId: string | null = null
        if (edge.source === node.id && !visited.has(edge.target)) {
          neighborId = edge.target
        } else if (edge.target === node.id && !visited.has(edge.source)) {
          neighborId = edge.source
        }

        if (neighborId) {
          const neighbor = graphData.value.nodes.find(n => n.id === neighborId)
          if (neighbor) {
            visited.add(neighborId)
            queue.push({ node: neighbor, level: level + 1 })
          }
        }
      })
    }

    graphData.value.nodes.forEach(node => {
      if (!visited.has(node.id)) {
        if (!levels[0]) levels[0] = []
        levels[0].push(node)
      }
    })

    const levelCount = Object.keys(levels).length
    const levelHeight = height / (levelCount + 1)

    Object.entries(levels).forEach(([levelStr, nodes]) => {
      const level = parseInt(levelStr)
      const y = levelHeight * (level + 1)
      const levelWidth = width / (nodes.length + 1)

      nodes.forEach((node, index) => {
        nodePositions.value.set(node.id, {
          x: levelWidth * (index + 1),
          y
        })
      })
    })
  } else {
    graphData.value.nodes.forEach((node, index) => {
      nodePositions.value.set(node.id, {
        x: centerX + (Math.random() - 0.5) * width * 0.6,
        y: centerY + (Math.random() - 0.5) * height * 0.6
      })
    })

    for (let i = 0; i < 50; i++) {
      graphData.value.nodes.forEach(node => {
        const pos = nodePositions.value.get(node.id)!
        let fx = 0
        let fy = 0

        graphData.value.nodes.forEach(otherNode => {
          if (otherNode.id !== node.id) {
            const otherPos = nodePositions.value.get(otherNode.id)!
            const dx = pos.x - otherPos.x
            const dy = pos.y - otherPos.y
            const dist = Math.sqrt(dx * dx + dy * dy) || 1
            const force = 2000 / (dist * dist)
            fx += (dx / dist) * force
            fy += (dy / dist) * force
          }
        })

        graphData.value.edges.forEach(edge => {
          let otherId: string | null = null
          if (edge.source === node.id) otherId = edge.target
          else if (edge.target === node.id) otherId = edge.source

          if (otherId) {
            const otherPos = nodePositions.value.get(otherId)
            if (otherPos) {
              const dx = otherPos.x - pos.x
              const dy = otherPos.y - pos.y
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const targetDist = 120
              const force = (dist - targetDist) * 0.02
              fx += (dx / dist) * force
              fy += (dy / dist) * force
            }
          }
        })

        fx += (centerX - pos.x) * 0.005
        fy += (centerY - pos.y) * 0.005

        pos.x = Math.max(50, Math.min(width - 50, pos.x + fx * 0.1))
        pos.y = Math.max(50, Math.min(height - 50, pos.y + fy * 0.1))
      })
    }
  }
}

function selectNode(node: GraphNode) {
  selectedNode.value = node
  selectedEdge.value = null
}

function selectEdge(edge: GraphEdge) {
  selectedEdge.value = edge
  selectedNode.value = null
}

function clearSelection() {
  selectedNode.value = null
  selectedEdge.value = null
}

function zoomIn() {
  zoom.value = Math.min(3, zoom.value + 0.2)
}

function zoomOut() {
  zoom.value = Math.max(0.5, zoom.value - 0.2)
}

function resetZoom() {
  zoom.value = 1
}

function toggleRiskLevel(level: string) {
  const index = riskLevels.value.indexOf(level)
  if (index > -1) {
    riskLevels.value.splice(index, 1)
  } else {
    riskLevels.value.push(level)
  }
}

function toggleNodeType(type: string) {
  const index = nodeTypes.value.indexOf(type)
  if (index > -1) {
    nodeTypes.value.splice(index, 1)
  } else {
    nodeTypes.value.push(type)
  }
}

function navigateToAddress(address: string) {
  router.push(`/address/${address}`)
}

async function loadMockData() {
  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 1000))

  const nodes: GraphNode[] = [
    { id: 'addr-1', address: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq', value: 125.5, category: 'suspicious', suspiciousScore: 85, label: 'bc1q...a1b2', size: 14 },
    { id: 'addr-2', address: '1A2b3C4d5E6f7G8h9I0jK1lM2n3O4p5Q6r', value: 2.3, category: 'normal', suspiciousScore: 15, label: '1A2b...3C4d', size: 12 },
    { id: 'addr-3', address: '3XyZ7890AbCdEfGhIjKlMnOpQrStUvWxYz', value: 45.8, category: 'suspicious', suspiciousScore: 62, label: '3XyZ...7890', size: 14 },
    { id: 'addr-4', address: 'bc1p0xyzabcdefghijklmnopqrstuvwxyz1234567890', value: 500.2, category: 'suspicious', suspiciousScore: 92, label: 'bc1p...mnop', size: 16 },
    { id: 'addr-5', address: '1QrStUvWxYz1234567890AbCdEfGhIjKlM', value: 12.1, category: 'normal', suspiciousScore: 35, label: '1QrS...tUvW', size: 12 },
    { id: 'addr-6', address: '3DeF4567GhIjKlMnOpQrStUvWxYz123456', value: 89.3, category: 'suspicious', suspiciousScore: 78, label: '3DeF...4567', size: 14 },
    { id: 'tx-1', address: 'abc123def456ghi789jkl012mno345pqr678stu90', value: 15.5, category: 'normal', label: 'abc123...', size: 10 },
    { id: 'tx-2', address: 'def456ghi789jkl012mno345pqr678stu90vwx12', value: 2.8, category: 'normal', label: 'def456...', size: 10 },
    { id: 'tx-3', address: 'ghi789jkl012mno345pqr678stu90vwx12yz34', value: 120.0, category: 'suspicious', label: 'ghi789...', size: 12 },
    { id: 'tx-4', address: 'jkl012mno345pqr678stu90vwx12yz34abc56', value: 0.5, category: 'normal', label: 'jkl012...', size: 10 }
  ]

  const edges: GraphEdge[] = [
    { source: 'addr-1', target: 'tx-1', value: 15.5, txid: 'tx1-abc123', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), type: 'input' },
    { source: 'tx-1', target: 'addr-2', value: 2.3, txid: 'tx1-abc123', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), type: 'output' },
    { source: 'tx-1', target: 'addr-3', value: 13.2, txid: 'tx1-abc123', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), type: 'output' },
    { source: 'addr-3', target: 'tx-2', value: 2.8, txid: 'tx2-def456', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 23), type: 'input' },
    { source: 'tx-2', target: 'addr-4', value: 2.8, txid: 'tx2-def456', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 23), type: 'output' },
    { source: 'addr-4', target: 'tx-3', value: 120.0, txid: 'tx3-ghi789', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 22), type: 'input' },
    { source: 'tx-3', target: 'addr-5', value: 12.1, txid: 'tx3-ghi789', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 22), type: 'output' },
    { source: 'tx-3', target: 'addr-6', value: 107.9, txid: 'tx3-ghi789', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 22), type: 'output' },
    { source: 'addr-6', target: 'tx-4', value: 0.5, txid: 'tx4-jkl012', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 21), type: 'input' },
    { source: 'tx-4', target: 'addr-1', value: 0.5, txid: 'tx4-jkl012', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 21), type: 'output' }
  ]

  graphData.value = { nodes, edges }
  calculatePositions()
  loading.value = false
}

watch(layoutType, () => {
  calculatePositions()
})

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex-1 min-w-64">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索地址或交易哈希..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        <div class="flex items-center gap-2">
          <Calendar class="w-4 h-4 text-gray-400" />
          <select
            v-model="timeRange"
            class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option v-for="opt in timeRangeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <Layout class="w-4 h-4 text-gray-400" />
          <select
            v-model="layoutType"
            class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option v-for="opt in layoutOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <button
          @click="showFilters = !showFilters"
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          :class="{ 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-600': showFilters }"
        >
          <SlidersHorizontal class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>

        <button
          @click="loadMockData"
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          :disabled="loading"
        >
          <RefreshCw class="w-5 h-5 text-gray-600 dark:text-gray-300" :class="{ 'animate-spin': loading }" />
        </button>

        <button
          @click="zoomIn"
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <ZoomIn class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>

        <button
          @click="zoomOut"
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <ZoomOut class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>

        <button
          @click="resetZoom"
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <Maximize2 class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>

        <button
          class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <Download class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>
      </div>
    </div>

    <div class="flex-1 flex overflow-hidden">
      <div
        v-show="showFilters"
        class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto"
      >
        <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Filter class="w-4 h-4" />
            过滤器
          </h3>
          <button @click="showFilters = false" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="p-4 space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              金额阈值 (BTC)
            </label>
            <input
              v-model.number="minValue"
              type="number"
              step="0.1"
              min="0"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              v-model.number="minValue"
              class="w-full mt-2"
            />
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">最小值: {{ minValue }} BTC</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              节点类型
            </label>
            <div class="space-y-2">
              <label v-for="opt in nodeTypeOptions" :key="opt.value" class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="nodeTypes.includes(opt.value)"
                  @change="toggleNodeType(opt.value)"
                  class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
                <span class="text-sm text-gray-700 dark:text-gray-300">{{ opt.label }}</span>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              风险等级
            </label>
            <div class="space-y-2">
              <label v-for="opt in riskLevelOptions" :key="opt.value" class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="riskLevels.includes(opt.value)"
                  @change="toggleRiskLevel(opt.value)"
                  class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                  :style="{ accentColor: opt.color }"
                />
                <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: opt.color }" />
                <span class="text-sm text-gray-700 dark:text-gray-300">{{ opt.label }}</span>
              </label>
            </div>
          </div>
        </div>

        <div class="p-4 border-t border-gray-200 dark:border-gray-700">
          <div class="space-y-2 text-sm">
            <div class="flex justify-between text-gray-600 dark:text-gray-400">
              <span>节点数量</span>
              <span class="font-medium text-gray-900 dark:text-white">{{ graphData.nodes.length }}</span>
            </div>
            <div class="flex justify-between text-gray-600 dark:text-gray-400">
              <span>边数量</span>
              <span class="font-medium text-gray-900 dark:text-white">{{ graphData.edges.length }}</span>
            </div>
            <div class="flex justify-between text-gray-600 dark:text-gray-400">
              <span>缩放比例</span>
              <span class="font-medium text-gray-900 dark:text-white">{{ (zoom * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div ref="containerRef" class="flex-1 relative overflow-hidden bg-gray-100 dark:bg-gray-900">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="text-center">
            <Loader class="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
            <p class="text-gray-600 dark:text-gray-400">加载图数据中...</p>
          </div>
        </div>

        <div v-else class="absolute inset-0 flex items-center justify-center" :style="{ transform: `scale(${zoom})`, transition: 'transform 0.2s' }">
          <svg ref="svgRef" width="900" height="600" class="cursor-move">
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
              </marker>
            </defs>

            <g>
              <line
                v-for="edge in graphData.edges"
                :key="`${edge.source}-${edge.target}`"
                :x1="nodePositions.get(edge.source)?.x || 0"
                :y1="nodePositions.get(edge.source)?.y || 0"
                :x2="nodePositions.get(edge.target)?.x || 0"
                :y2="nodePositions.get(edge.target)?.y || 0"
                :stroke="getEdgeColor(edge)"
                :stroke-width="getEdgeWidth(edge)"
                :opacity="selectedEdge?.source === edge.source && selectedEdge?.target === edge.target ? 1 : 0.6"
                class="cursor-pointer hover:opacity-100 transition-opacity"
                marker-end="url(#arrowhead)"
                @click="selectEdge(edge)"
              />
            </g>

            <g>
              <g
                v-for="node in graphData.nodes"
                :key="node.id"
                :transform="`translate(${nodePositions.get(node.id)?.x || 0}, ${nodePositions.get(node.id)?.y || 0})`"
                class="cursor-pointer"
                @click="selectNode(node)"
              >
                <circle
                  :r="getNodeSize(node)"
                  :fill="getNodeColor(node)"
                  :stroke="selectedNode?.id === node.id ? '#ffffff' : 'transparent'"
                  :stroke-width="selectedNode?.id === node.id ? 3 : 0"
                  class="hover:opacity-80 transition-opacity"
                  :style="{ filter: selectedNode?.id === node.id ? 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.8))' : '' }"
                />
                <text
                  v-if="zoom >= 0.8"
                  y="25"
                  text-anchor="middle"
                  class="text-xs fill-gray-600 dark:fill-gray-400 pointer-events-none"
                >
                  {{ node.label }}
                </text>
                <text
                  v-if="node.suspiciousScore !== undefined && zoom >= 1"
                  y="-15"
                  text-anchor="middle"
                  class="text-xs font-bold fill-gray-900 dark:fill-white pointer-events-none"
                >
                  {{ node.suspiciousScore }}
                </text>
              </g>
            </g>
          </svg>
        </div>

        <button
          v-if="!showFilters"
          @click="showFilters = true"
          class="absolute left-4 top-4 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors z-10"
        >
          <SlidersHorizontal class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>

        <button
          v-if="!showInfoPanel"
          @click="showInfoPanel = true"
          class="absolute right-4 top-4 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors z-10"
        >
          <AlertTriangle class="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>
      </div>

      <div
        v-show="showInfoPanel"
        class="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 overflow-y-auto"
      >
        <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <MapPin class="w-4 h-4" />
            详情面板
          </h3>
          <button @click="showInfoPanel = false" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div v-if="!selectedNode && !selectedEdge" class="p-8 text-center text-gray-500 dark:text-gray-400">
          <AlertTriangle class="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>选择一个节点或边查看详情</p>
        </div>

        <div v-else-if="selectedNode" class="p-4 space-y-4">
          <div class="flex items-center gap-3">
            <div
              class="w-12 h-12 rounded-full flex items-center justify-center"
              :style="{ backgroundColor: getNodeColor(selectedNode) + '30' }"
            >
              <component
                :is="selectedNode.category === 'cluster' ? Users : selectedNode.category === 'suspicious' ? AlertTriangle : MapPin"
                class="w-6 h-6"
                :style="{ color: getNodeColor(selectedNode) }"
              />
            </div>
            <div class="flex-1 min-w-0">
              <p class="font-medium text-gray-900 dark:text-white truncate">{{ selectedNode.label }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">
                {{ selectedNode.category === 'cluster' ? '聚类节点' : selectedNode.category === 'suspicious' ? '可疑节点' : '普通节点' }}
              </p>
            </div>
          </div>

          <div v-if="selectedNode.suspiciousScore !== undefined" class="p-3 rounded-lg" :style="{ backgroundColor: getNodeColor(selectedNode) + '15' }">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm text-gray-600 dark:text-gray-400">风险评分</span>
              <span class="text-lg font-bold" :style="{ color: getNodeColor(selectedNode) }">
                {{ selectedNode.suspiciousScore }}
              </span>
            </div>
            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :style="{ width: `${selectedNode.suspiciousScore}%`, backgroundColor: getNodeColor(selectedNode) }"
              />
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">ID</span>
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ selectedNode.id }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">地址</span>
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedNode.address, 12) }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">金额</span>
              <span class="text-gray-900 dark:text-white font-medium">{{ formatBTC(selectedNode.value) }}</span>
            </div>
            <div v-if="selectedNode.size !== undefined" class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">节点大小</span>
              <span class="text-gray-900 dark:text-white font-medium">{{ selectedNode.size.toFixed(1) }}</span>
            </div>
            <div v-if="selectedNode.category !== undefined" class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">类别</span>
              <span class="text-gray-900 dark:text-white font-medium">
                {{ selectedNode.category === 'cluster' ? '聚类' : selectedNode.category === 'suspicious' ? '可疑' : '普通' }}
              </span>
            </div>
          </div>

          <button
            @click="navigateToAddress(selectedNode.address)"
            class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            查看地址详情
            <ArrowRightLeft class="w-4 h-4" />
          </button>
        </div>

        <div v-else-if="selectedEdge" class="p-4 space-y-4">
          <div class="flex items-center gap-3">
            <div
              class="w-12 h-12 rounded-full flex items-center justify-center"
              :style="{ backgroundColor: getEdgeColor(selectedEdge) + '30' }"
            >
              <ArrowRightLeft class="w-6 h-6" :style="{ color: getEdgeColor(selectedEdge) }" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="font-medium text-gray-900 dark:text-white truncate">交易边</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">{{ selectedEdge.type }}</p>
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">交易哈希</span>
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedEdge.txid, 12) }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">源节点</span>
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedEdge.source, 12) }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">目标节点</span>
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedEdge.target, 12) }}</span>
            </div>
            <div v-if="selectedEdge.value !== undefined" class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">金额</span>
              <span class="text-gray-900 dark:text-white font-medium">{{ formatBTC(selectedEdge.value) }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">时间</span>
              <span class="text-gray-900 dark:text-white">{{ formatDate(selectedEdge.timestamp, 'full') }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">类型</span>
              <span class="text-gray-900 dark:text-white">{{ selectedEdge.type || 'N/A' }}</span>
            </div>
          </div>

          <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">流向</p>
            <div class="flex items-center gap-2 text-sm">
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedEdge.source, 6) }}</span>
              <ArrowRightLeft class="w-4 h-4 text-blue-500" />
              <span class="text-gray-900 dark:text-white font-mono text-xs">{{ formatHash(selectedEdge.target, 6) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-6 py-3">
      <div class="flex items-center gap-6 flex-wrap">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">图例:</span>
        </div>

        <div class="flex items-center gap-2">
          <span class="w-4 h-4 rounded-full" :style="{ backgroundColor: nodeColors.address }" />
          <span class="text-sm text-gray-600 dark:text-gray-400">地址</span>
        </div>

        <div class="flex items-center gap-2">
          <span class="w-4 h-4 rounded-full" :style="{ backgroundColor: nodeColors.transaction }" />
          <span class="text-sm text-gray-600 dark:text-gray-400">交易</span>
        </div>

        <div class="h-4 w-px bg-gray-300 dark:bg-gray-600" />

        <div v-for="opt in riskLevelOptions" :key="opt.value" class="flex items-center gap-2">
          <span class="w-4 h-4 rounded-full" :style="{ backgroundColor: opt.color }" />
          <span class="text-sm text-gray-600 dark:text-gray-400">{{ opt.label }}</span>
        </div>

        <div class="h-4 w-px bg-gray-300 dark:bg-gray-600" />

        <div class="flex items-center gap-2">
          <span class="w-8 h-0.5" :style="{ backgroundColor: '#9ca3af' }" />
          <span class="text-sm text-gray-600 dark:text-gray-400">小额交易</span>
        </div>

        <div class="flex items-center gap-2">
          <span class="w-8 h-1" :style="{ backgroundColor: RISK_LEVELS.high.color }" />
          <span class="text-sm text-gray-600 dark:text-gray-400">大额交易</span>
        </div>
      </div>
    </div>
  </div>
</template>
