<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent
} from 'echarts/components'
import {
  ArrowLeft,
  Copy,
  ExternalLink,
  Loader,
  Wallet,
  Clock,
  Hash,
  TrendingUp,
  AlertTriangle,
  ChevronRight,
  MapPin,
  Activity,
  ShieldAlert,
  Target
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useAddressStore } from '@/stores/address'
import { useAnalysisStore } from '@/stores/analysis'
import { RISK_LEVELS, CHART_COLORS, PATTERN_TYPES } from '@/utils/constants'
import { formatBTC, formatNumber, formatDate, formatHash } from '@/utils/format'
import type { EChartsOption } from 'echarts'
import type { RiskFactor, SuspiciousPattern, TransactionListItem } from '@/types'

use([
  CanvasRenderer,
  GaugeChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent
])

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const addressStore = useAddressStore()
const analysisStore = useAnalysisStore()

const addressHash = computed(() => route.params.address as string)
const loading = ref(true)
const activeTab = ref<'transactions' | 'patterns'>('transactions')

const addressInfo = ref({
  address: '',
  balance: 0,
  txCount: 0,
  firstSeen: new Date(),
  lastSeen: new Date(),
  type: 'bech32',
  received: 0,
  sent: 0
})

const suspiciousScore = ref(0)
const riskLevel = computed(() => {
  if (suspiciousScore.value >= 75) return 'critical'
  if (suspiciousScore.value >= 50) return 'high'
  if (suspiciousScore.value >= 25) return 'medium'
  return 'low'
})

const riskFactors = ref<RiskFactor[]>([
  { name: '混币服务交互', score: 85, weight: 0.25, description: '与已知混币服务地址有交易往来' },
  { name: '交易频率异常', score: 72, weight: 0.2, description: '短时间内大量交易' },
  { name: '大额持有', score: 45, weight: 0.15, description: '持有大量BTC' },
  { name: '地址聚类', score: 68, weight: 0.2, description: '与高风险地址属于同一聚类' },
  { name: '暗网关联', score: 90, weight: 0.2, description: '与暗网市场地址有交易' }
])

const transactions = ref<TransactionListItem[]>([])
const patterns = ref<SuspiciousPattern[]>([])

const subgraphPreview = ref<{ nodes: { id: string; label: string; x: number; y: number; type: string; score?: number }[]; edges: { source: string; target: string; value: number }[] }>({
  nodes: [],
  edges: []
})

const gaugeOption = computed<EChartsOption>(() => {
  const level = RISK_LEVELS[riskLevel.value as keyof typeof RISK_LEVELS]
  return {
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        splitNumber: 10,
        itemStyle: {
          color: level?.color || '#10b981'
        },
        progress: {
          show: true,
          width: 20
        },
        pointer: {
          show: false
        },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.25, RISK_LEVELS.low.color],
              [0.5, RISK_LEVELS.medium.color],
              [0.75, RISK_LEVELS.high.color],
              [1, RISK_LEVELS.critical.color]
            ]
          }
        },
        axisTick: {
          show: false
        },
        splitLine: {
          show: false
        },
        axisLabel: {
          show: false
        },
        anchor: {
          show: false
        },
        title: {
          show: false
        },
        detail: {
          valueAnimation: true,
          width: '60%',
          lineHeight: 40,
          borderRadius: 8,
          offsetCenter: [0, '0%'],
          fontSize: 36,
          fontWeight: 'bold',
          formatter: '{value}',
          color: level?.color || '#10b981'
        },
        data: [
          {
            value: suspiciousScore.value
          }
        ]
      }
    ]
  }
})

const radarOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: appStore.isDark ? '#1f2937' : '#ffffff',
    borderColor: appStore.isDark ? '#374151' : '#e5e7eb',
    textStyle: {
      color: appStore.isDark ? '#e5e7eb' : '#374151'
    }
  },
  radar: {
    indicator: riskFactors.value.map(f => ({
      name: f.name,
      max: 100
    })),
    shape: 'polygon',
    splitNumber: 5,
    axisName: {
      color: appStore.isDark ? '#9ca3af' : '#6b7280',
      fontSize: 11
    },
    splitLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#e5e7eb'
      }
    },
    splitArea: {
      show: true,
      areaStyle: {
        color: appStore.isDark
          ? ['#1f2937', '#1f2937', '#1f2937', '#1f2937', '#1f2937']
          : ['#f9fafb', '#f9fafb', '#f9fafb', '#f9fafb', '#f9fafb']
      }
    },
    axisLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#e5e7eb'
      }
    }
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: riskFactors.value.map(f => f.score),
          name: '风险因子',
          areaStyle: {
            color: `${RISK_LEVELS[riskLevel.value as keyof typeof RISK_LEVELS]?.color}40`
          },
          lineStyle: {
            color: RISK_LEVELS[riskLevel.value as keyof typeof RISK_LEVELS]?.color,
            width: 2
          },
          itemStyle: {
            color: RISK_LEVELS[riskLevel.value as keyof typeof RISK_LEVELS]?.color
          }
        }
      ]
    }
  ]
}))

function getNodeColor(type: string, score?: number): string {
  if (score !== undefined) {
    if (score >= 75) return RISK_LEVELS.critical.color
    if (score >= 50) return RISK_LEVELS.high.color
    if (score >= 25) return RISK_LEVELS.medium.color
    return RISK_LEVELS.low.color
  }
  return type === 'address' ? CHART_COLORS[0] : CHART_COLORS[7]
}

function copyAddress() {
  navigator.clipboard.writeText(addressInfo.value.address)
  appStore.addNotification({
    type: 'success',
    message: '地址已复制到剪贴板'
  })
}

function goBack() {
  router.back()
}

function navigateToGraph() {
  router.push({
    path: '/graph',
    query: { address: addressHash.value }
  })
}

function navigateToPattern(patternId: number) {
  router.push(`/analysis/patterns/${patternId}`)
}

function loadMockSubgraph() {
  const centerX = 150
  const centerY = 100

  subgraphPreview.value = {
    nodes: [
      { id: addressHash.value, label: formatHash(addressHash.value, 4), x: centerX, y: centerY, type: 'address', score: suspiciousScore.value },
      { id: 'addr-1', label: '1A2b...3C4d', x: centerX - 80, y: centerY - 60, type: 'address', score: 15 },
      { id: 'addr-2', label: '3XyZ...7890', x: centerX + 80, y: centerY - 60, type: 'address', score: 62 },
      { id: 'addr-3', label: 'bc1p...mnop', x: centerX - 100, y: centerY + 50, type: 'address', score: 92 },
      { id: 'addr-4', label: '1QrS...tUvW', x: centerX + 100, y: centerY + 50, type: 'address', score: 35 },
      { id: 'tx-1', label: 'abc1...', x: centerX - 40, y: centerY - 30, type: 'transaction' },
      { id: 'tx-2', label: 'def2...', x: centerX + 40, y: centerY - 30, type: 'transaction' },
      { id: 'tx-3', label: 'ghi3...', x: centerX, y: centerY + 40, type: 'transaction' }
    ],
    edges: [
      { source: 'addr-1', target: 'tx-1', value: 2.5 },
      { source: 'tx-1', target: addressHash.value, value: 2.5 },
      { source: addressHash.value, target: 'tx-2', value: 5.0 },
      { source: 'tx-2', target: 'addr-2', value: 5.0 },
      { source: 'addr-3', target: 'tx-3', value: 10.0 },
      { source: 'tx-3', target: addressHash.value, value: 10.0 },
      { source: addressHash.value, target: 'tx-3', value: 8.0 },
      { source: 'tx-3', target: 'addr-4', value: 8.0 }
    ]
  }
}

async function loadMockData() {
  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 1000))

  const addr = addressHash.value || 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq'
  addressInfo.value = {
    address: addr,
    balance: 125.6789,
    txCount: 342,
    firstSeen: new Date('2023-01-15'),
    lastSeen: new Date('2024-05-20'),
    type: 'bech32',
    received: 5678.2345,
    sent: 5552.5556
  }

  suspiciousScore.value = 78

  transactions.value = [
    { txid: 'abc123def456abc123def456abc123def456abc123', blockHeight: 840000, blockTime: new Date('2024-05-20'), inputCount: 2, outputCount: 3, totalInput: 1500000000, totalOutput: 1490000000, inputValue: 1500000000, outputValue: 1490000000, fee: 10000000, suspiciousScore: 65 },
    { txid: 'def456ghi789def456ghi789def456ghi789def456', blockHeight: 839950, blockTime: new Date('2024-05-19'), inputCount: 1, outputCount: 2, totalInput: 500000000, totalOutput: 490000000, inputValue: 500000000, outputValue: 490000000, fee: 10000000, suspiciousScore: 45 },
    { txid: 'ghi789jkl012ghi789jkl012ghi789jkl012ghi789jkl012', blockHeight: 839900, blockTime: new Date('2024-05-18'), inputCount: 5, outputCount: 1, totalInput: 2500000000, totalOutput: 2480000000, inputValue: 2500000000, outputValue: 2480000000, fee: 20000000, suspiciousScore: 82 },
    { txid: 'jkl012mno345jkl012mno345jkl012mno345jkl012mno345', blockHeight: 839850, blockTime: new Date('2024-05-17'), inputCount: 3, outputCount: 4, totalInput: 1800000000, totalOutput: 1780000000, inputValue: 1800000000, outputValue: 1780000000, fee: 20000000, suspiciousScore: 35 },
    { txid: 'mno345pqr678mno345pqr678mno345pqr678mno345pqr678', blockHeight: 839800, blockTime: new Date('2024-05-16'), inputCount: 1, outputCount: 1, totalInput: 1000000000, totalOutput: 990000000, inputValue: 1000000000, outputValue: 990000000, fee: 10000000, suspiciousScore: 55 }
  ]

  patterns.value = [
    { id: 1, type: 'mixing', patternType: 'darknet_market', name: '暗网市场交易', description: '与已知暗网市场地址存在多笔交易', severity: 'critical', confidence: 0.95, evidence: ['交易1', '交易2'], detectedAt: new Date('2024-05-20'), addresses: [addr, '1A2b...3C4d'], transactions: ['abc123...', 'def456...'], firstSeen: new Date('2024-01-10'), lastSeen: new Date('2024-05-20') },
    { id: 2, type: 'layering', patternType: 'layering', name: '分层洗钱模式', description: '通过多层转账混淆资金来源', severity: 'high', confidence: 0.88, evidence: ['交易1', '交易2'], detectedAt: new Date('2024-05-18'), addresses: [addr, '3XyZ...7890', 'bc1p...mnop'], transactions: ['ghi789...', 'jkl012...'], firstSeen: new Date('2024-02-15'), lastSeen: new Date('2024-05-18') },
    { id: 3, type: 'mixing', patternType: 'mixing_service', name: '混币服务交互', description: '与CoinJoin等混币服务有交易往来', severity: 'critical', confidence: 0.92, evidence: ['交易1'], detectedAt: new Date('2024-05-15'), addresses: [addr, '1QrS...tUvW'], transactions: ['mno345...'], firstSeen: new Date('2024-03-01'), lastSeen: new Date('2024-05-15') }
  ]

  loadMockSubgraph()
  loading.value = false
}

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center gap-4">
      <button
        @click="goBack"
        class="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <ArrowLeft class="w-5 h-5 text-gray-600 dark:text-gray-300" />
      </button>
      <div class="flex-1">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">地址详情</h1>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <Loader class="w-12 h-12 text-blue-500 animate-spin" />
    </div>

    <template v-else>
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="flex items-start gap-4 flex-1">
            <div class="w-14 h-14 bg-blue-100 dark:bg-blue-900/30 rounded-xl flex items-center justify-center flex-shrink-0">
              <Wallet class="w-7 h-7 text-blue-600 dark:text-blue-400" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <code class="text-lg font-mono text-gray-900 dark:text-white break-all">{{ addressInfo.address }}</code>
                <button
                  @click="copyAddress"
                  class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
                  title="复制地址"
                >
                  <Copy class="w-4 h-4 text-gray-400" />
                </button>
                <a
                  :href="`https://blockchain.com/btc/address/${addressInfo.address}`"
                  target="_blank"
                  class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
                  title="在区块浏览器中查看"
                >
                  <ExternalLink class="w-4 h-4 text-gray-400" />
                </a>
              </div>
              <div class="flex items-center gap-4 mt-3 flex-wrap">
                <span
                  class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium"
                  :class="RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.bgColor || 'bg-gray-100',
                          RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.textColor || 'text-gray-800'"
                >
                  <ShieldAlert class="w-3 h-3" />
                  {{ RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.label || '未知' }}
                </span>
                <span class="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <Hash class="w-3 h-3" />
                  {{ addressInfo.type.toUpperCase() }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-6 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">余额</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white mt-1">{{ formatBTC(addressInfo.balance * 1e8) }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">交易次数</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white mt-1">{{ formatNumber(addressInfo.txCount) }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">首次交易</p>
            <p class="text-lg font-medium text-gray-900 dark:text-white mt-1">{{ formatDate(addressInfo.firstSeen, 'date') }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">末次交易</p>
            <p class="text-lg font-medium text-gray-900 dark:text-white mt-1">{{ formatDate(addressInfo.lastSeen, 'date') }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-6 mt-4 pt-6 border-t border-gray-200 dark:border-gray-700">
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">总收入</p>
            <p class="text-lg font-bold text-green-600 dark:text-green-400 mt-1">+{{ formatBTC(addressInfo.received * 1e8) }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-500 dark:text-gray-400">总支出</p>
            <p class="text-lg font-bold text-red-600 dark:text-red-400 mt-1">-{{ formatBTC(addressInfo.sent * 1e8) }}</p>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Target class="w-5 h-5" />
            风险评分
          </h3>
          <div class="h-56">
            <v-chart :option="gaugeOption" autoresize />
          </div>
          <div class="text-center mt-2">
            <span
              class="inline-block px-3 py-1 rounded-full text-sm font-medium"
              :class="RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.bgColor || 'bg-gray-100',
                      RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.textColor || 'text-gray-800'"
            >
              {{ RISK_LEVELS[riskLevel as keyof typeof RISK_LEVELS]?.label || '未知' }}风险
            </span>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Activity class="w-5 h-5" />
            风险因子分析
          </h3>
          <div class="h-56">
            <v-chart :option="radarOption" autoresize />
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <MapPin class="w-5 h-5" />
              关联子图
            </h3>
            <button
              @click="navigateToGraph"
              class="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            >
              查看大图
              <ChevronRight class="w-4 h-4" />
            </button>
          </div>
          <div class="h-56 bg-gray-50 dark:bg-gray-700/50 rounded-lg overflow-hidden cursor-pointer" @click="navigateToGraph">
            <svg width="100%" height="100%" viewBox="0 0 300 200">
              <defs>
                <marker
                  id="arrowhead-preview"
                  markerWidth="6"
                  markerHeight="4"
                  refX="5"
                  refY="2"
                  orient="auto"
                >
                  <polygon points="0 0, 6 2, 0 4" fill="#9ca3af" />
                </marker>
              </defs>
              <line
                v-for="edge in subgraphPreview.edges"
                :key="edge.source + edge.target"
                :x1="subgraphPreview.nodes.find(n => n.id === edge.source)?.x || 0"
                :y1="subgraphPreview.nodes.find(n => n.id === edge.source)?.y || 0"
                :x2="subgraphPreview.nodes.find(n => n.id === edge.target)?.x || 0"
                :y2="subgraphPreview.nodes.find(n => n.id === edge.target)?.y || 0"
                stroke="#9ca3af"
                stroke-width="1.5"
                opacity="0.6"
                marker-end="url(#arrowhead-preview)"
              />
              <g v-for="node in subgraphPreview.nodes" :key="node.id">
                <circle
                  :cx="node.x"
                  :cy="node.y"
                  :r="node.type === 'address' ? 10 : 6"
                  :fill="getNodeColor(node.type, node.score)"
                  :stroke="node.id === addressHash ? '#fff' : 'transparent'"
                  stroke-width="2"
                />
                <text
                  v-if="node.type === 'address'"
                  :x="node.x"
                  :y="node.y + 22"
                  text-anchor="middle"
                  class="text-[10px] fill-gray-500 dark:fill-gray-400"
                >
                  {{ node.label }}
                </text>
              </g>
            </svg>
          </div>
          <div class="mt-3 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>{{ subgraphPreview.nodes.length }} 个节点</span>
            <span>{{ subgraphPreview.edges.length }} 条边</span>
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="border-b border-gray-200 dark:border-gray-700">
          <nav class="flex">
            <button
              @click="activeTab = 'transactions'"
              class="px-6 py-4 text-sm font-medium border-b-2 transition-colors"
              :class="activeTab === 'transactions'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
            >
              交易历史
            </button>
            <button
              @click="activeTab = 'patterns'"
              class="px-6 py-4 text-sm font-medium border-b-2 transition-colors"
              :class="activeTab === 'patterns'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
            >
              可疑模式
              <span v-if="patterns.length" class="ml-2 px-1.5 py-0.5 rounded-full text-xs bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                {{ patterns.length }}
              </span>
            </button>
          </nav>
        </div>

        <div v-if="activeTab === 'transactions'" class="p-4">
          <div class="space-y-4">
            <div
              v-for="tx in transactions"
              :key="tx.txid"
              class="relative pl-8 pb-4 border-l-2 border-gray-200 dark:border-gray-700 last:border-l-0 last:pb-0"
            >
              <div class="absolute left-[-9px] top-0 w-4 h-4 rounded-full bg-blue-500 border-4 border-white dark:border-gray-800" />
              <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 ml-2">
                <div class="flex items-start justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <code class="text-sm font-mono text-gray-900 dark:text-white">{{ tx.txid }}</code>
                      <span
                        v-if="tx.suspiciousScore !== undefined && tx.suspiciousScore >= 50"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                      >
                        <AlertTriangle class="w-3 h-3" />
                        可疑
                      </span>
                    </div>
                    <div class="flex items-center gap-4 mt-2 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
                      <span class="flex items-center gap-1">
                        <Clock class="w-4 h-4" />
                        {{ formatDate(tx.blockTime, 'full') }}
                      </span>
                      <span class="flex items-center gap-1">
                        <Hash class="w-4 h-4" />
                        区块 #{{ formatNumber(tx.blockHeight) }}
                      </span>
                    </div>
                  </div>
                  <div class="text-right flex-shrink-0">
                    <p class="text-lg font-bold text-gray-900 dark:text-white">
                      {{ formatBTC(tx.outputValue || tx.totalOutput) }}
                    </p>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      矿工费: {{ formatBTC(tx.fee || 0) }}
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-6 mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                  <div class="text-sm">
                    <span class="text-gray-500 dark:text-gray-400">输入: </span>
                    <span class="font-medium text-gray-900 dark:text-white">{{ tx.inputCount }} 个</span>
                  </div>
                  <div class="text-sm">
                    <span class="text-gray-500 dark:text-gray-400">输出: </span>
                    <span class="font-medium text-gray-900 dark:text-white">{{ tx.outputCount }} 个</span>
                  </div>
                  <div v-if="tx.suspiciousScore !== undefined" class="text-sm">
                    <span class="text-gray-500 dark:text-gray-400">风险分: </span>
                    <span
                      class="font-medium"
                      :style="{ color: tx.suspiciousScore >= 50 ? RISK_LEVELS.high.color : RISK_LEVELS.low.color }"
                    >
                      {{ tx.suspiciousScore }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="p-4">
          <div class="space-y-4">
            <div
              v-for="pattern in patterns"
              :key="pattern.id"
              class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              @click="navigateToPattern(pattern.id)"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="flex items-start gap-3">
                  <div
                    class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    :class="pattern.severity === 'critical' ? 'bg-purple-100 dark:bg-purple-900/30' :
                            pattern.severity === 'high' ? 'bg-red-100 dark:bg-red-900/30' :
                            pattern.severity === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/30' :
                            'bg-green-100 dark:bg-green-900/30'"
                  >
                    <AlertTriangle
                      class="w-5 h-5"
                      :class="pattern.severity === 'critical' ? 'text-purple-600 dark:text-purple-400' :
                              pattern.severity === 'high' ? 'text-red-600 dark:text-red-400' :
                              pattern.severity === 'medium' ? 'text-yellow-600 dark:text-yellow-400' :
                              'text-green-600 dark:text-green-400'"
                    />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <h4 class="font-medium text-gray-900 dark:text-white">{{ pattern.name }}</h4>
                      <span
                        class="px-2 py-0.5 rounded-full text-xs font-medium"
                        :class="pattern.severity === 'critical' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' :
                                pattern.severity === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' :
                                pattern.severity === 'medium' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' :
                                'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'"
                      >
                        {{ pattern.severity === 'critical' ? '严重' :
                           pattern.severity === 'high' ? '高危' :
                           pattern.severity === 'medium' ? '中危' : '低危' }}
                      </span>
                    </div>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ pattern.description }}</p>
                    <div class="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400 flex-wrap">
                      <span>置信度: {{ (pattern.confidence * 100).toFixed(0) }}%</span>
                      <span>首次发现: {{ formatDate(pattern.firstSeen, 'date') }}</span>
                      <span>关联交易: {{ pattern.transactions.length }} 笔</span>
                    </div>
                  </div>
                </div>
                <ChevronRight class="w-5 h-5 text-gray-400 flex-shrink-0" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
