<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components'
import {
  TrendingUp,
  Users,
  AlertTriangle,
  DollarSign,
  Clock,
  CheckCircle,
  XCircle,
  Loader,
  ChevronRight,
  Activity
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useTransactionStore } from '@/stores/transaction'
import { useAddressStore } from '@/stores/address'
import { useTaskStore } from '@/stores/task'
import { RISK_LEVELS, CHART_COLORS, TASK_STATUS } from '@/utils/constants'
import { formatBTC, formatNumber, formatDate } from '@/utils/format'
import type { EChartsOption } from 'echarts'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
])

const router = useRouter()
const appStore = useAppStore()
const transactionStore = useTransactionStore()
const addressStore = useAddressStore()
const taskStore = useTaskStore()

const loading = ref(true)
const stats = ref({
  totalTransactions: 0,
  totalAddresses: 0,
  highRiskAddresses: 0,
  todayVolume: 0
})

const trendData = ref<{ date: string; count: number; value: number }[]>([])
const topRiskAddresses = ref<{ address: string; score: number; txCount: number }[]>([])
const alerts = ref<{ id: number; type: string; message: string; time: Date; severity: string }[]>([])

const lineChartOption = computed<EChartsOption>(() => ({
  title: {
    text: '可疑交易趋势',
    left: 'center',
    textStyle: {
      fontSize: 14,
      color: appStore.isDark ? '#e5e7eb' : '#374151'
    }
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: appStore.isDark ? '#1f2937' : '#ffffff',
    borderColor: appStore.isDark ? '#374151' : '#e5e7eb',
    textStyle: {
      color: appStore.isDark ? '#e5e7eb' : '#374151'
    }
  },
  legend: {
    data: ['交易数量', '交易额'],
    bottom: 0,
    textStyle: {
      color: appStore.isDark ? '#9ca3af' : '#6b7280'
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '15%',
    top: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trendData.value.map(d => d.date),
    axisLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#e5e7eb'
      }
    },
    axisLabel: {
      color: appStore.isDark ? '#9ca3af' : '#6b7280'
    }
  },
  yAxis: [
    {
      type: 'value',
      name: '交易数',
      axisLine: {
        lineStyle: {
          color: appStore.isDark ? '#374151' : '#e5e7eb'
        }
      },
      axisLabel: {
        color: appStore.isDark ? '#9ca3af' : '#6b7280'
      },
      splitLine: {
        lineStyle: {
          color: appStore.isDark ? '#374151' : '#f3f4f6'
        }
      }
    },
    {
      type: 'value',
      name: '交易额(BTC)',
      axisLine: {
        lineStyle: {
          color: appStore.isDark ? '#374151' : '#e5e7eb'
        }
      },
      axisLabel: {
        color: appStore.isDark ? '#9ca3af' : '#6b7280'
      },
      splitLine: {
        show: false
      }
    }
  ],
  series: [
    {
      name: '交易数量',
      type: 'line',
      smooth: true,
      data: trendData.value.map(d => d.count),
      lineStyle: {
        color: CHART_COLORS[0],
        width: 2
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: `${CHART_COLORS[0]}40` },
            { offset: 1, color: `${CHART_COLORS[0]}05` }
          ]
        }
      },
      itemStyle: {
        color: CHART_COLORS[0]
      }
    },
    {
      name: '交易额',
      type: 'line',
      smooth: true,
      yAxisIndex: 1,
      data: trendData.value.map(d => d.value),
      lineStyle: {
        color: CHART_COLORS[1],
        width: 2
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: `${CHART_COLORS[1]}40` },
            { offset: 1, color: `${CHART_COLORS[1]}05` }
          ]
        }
      },
      itemStyle: {
        color: CHART_COLORS[1]
      }
    }
  ]
}))

const barChartOption = computed<EChartsOption>(() => ({
  title: {
    text: '高风险地址 TOP10',
    left: 'center',
    textStyle: {
      fontSize: 14,
      color: appStore.isDark ? '#e5e7eb' : '#374151'
    }
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow'
    },
    backgroundColor: appStore.isDark ? '#1f2937' : '#ffffff',
    borderColor: appStore.isDark ? '#374151' : '#e5e7eb',
    textStyle: {
      color: appStore.isDark ? '#e5e7eb' : '#374151'
    },
    formatter: (params: unknown) => {
      const p = params as { dataIndex: number }[]
      const item = topRiskAddresses.value[p[0].dataIndex]
      return `
        <div class="font-medium">${item.address.slice(0, 8)}...${item.address.slice(-8)}</div>
        <div>风险评分: ${item.score}</div>
        <div>交易次数: ${item.txCount}</div>
      `
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'value',
    max: 100,
    axisLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#e5e7eb'
      }
    },
    axisLabel: {
      color: appStore.isDark ? '#9ca3af' : '#6b7280'
    },
    splitLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#f3f4f6'
      }
    }
  },
  yAxis: {
    type: 'category',
    data: topRiskAddresses.value.map(a => `${a.address.slice(0, 6)}...`),
    axisLine: {
      lineStyle: {
        color: appStore.isDark ? '#374151' : '#e5e7eb'
      }
    },
    axisLabel: {
      color: appStore.isDark ? '#9ca3af' : '#6b7280'
    }
  },
  series: [
    {
      type: 'bar',
      data: topRiskAddresses.value.map(a => ({
        value: a.score,
        itemStyle: {
          color: a.score >= 75 ? RISK_LEVELS.critical.color :
                 a.score >= 50 ? RISK_LEVELS.high.color :
                 a.score >= 25 ? RISK_LEVELS.medium.color : RISK_LEVELS.low.color,
          borderRadius: [0, 4, 4, 0]
        }
      })),
      barWidth: '60%'
    }
  ]
}))

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'critical': return 'bg-purple-500'
    case 'high': return 'bg-red-500'
    case 'medium': return 'bg-yellow-500'
    default: return 'bg-green-500'
  }
}

function getSeverityLabel(severity: string) {
  switch (severity) {
    case 'critical': return '严重'
    case 'high': return '高危'
    case 'medium': return '中危'
    default: return '低危'
  }
}

function getTaskStatusIcon(status: string) {
  switch (status) {
    case 'processing': return Loader
    case 'completed': return CheckCircle
    case 'failed': return XCircle
    default: return Clock
  }
}

function navigateToGraph() {
  router.push('/graph')
}

function navigateToAddress(address: string) {
  router.push(`/address/${address}`)
}

function navigateToTasks() {
  router.push('/tasks')
}

async function loadMockData() {
  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 1000))

  stats.value = {
    totalTransactions: 128456,
    totalAddresses: 45231,
    highRiskAddresses: 1247,
    todayVolume: 1256.78
  }

  const days = ['05-17', '05-18', '05-19', '05-20', '05-21', '05-22', '05-23']
  trendData.value = days.map(date => ({
    date,
    count: Math.floor(Math.random() * 500) + 100,
    value: Math.random() * 500 + 50
  }))

  topRiskAddresses.value = Array.from({ length: 10 }, (_, i) => ({
    address: `bc1q${Math.random().toString(36).slice(2, 40)}`,
    score: Math.floor(Math.random() * 30) + 70,
    txCount: Math.floor(Math.random() * 1000) + 100
  })).sort((a, b) => b.score - a.score)

  alerts.value = [
    { id: 1, type: 'mixing_service', message: '检测到与混币服务的大额交易', time: new Date(Date.now() - 1000 * 60 * 5), severity: 'critical' },
    { id: 2, type: 'layering', message: '发现可疑分层洗钱模式', time: new Date(Date.now() - 1000 * 60 * 30), severity: 'high' },
    { id: 3, type: 'rapid_transfer', message: '地址1A2b...3C4d 快速转账异常', time: new Date(Date.now() - 1000 * 60 * 60 * 2), severity: 'medium' },
    { id: 4, type: 'darknet_market', message: '检测到与暗网市场地址交互', time: new Date(Date.now() - 1000 * 60 * 60 * 5), severity: 'critical' },
    { id: 5, type: 'dusting', message: '多个地址收到小额粉尘攻击', time: new Date(Date.now() - 1000 * 60 * 60 * 8), severity: 'low' }
  ]

  loading.value = false
}

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">仪表盘</h1>
        <p class="text-gray-500 dark:text-gray-400 mt-1">系统概览与实时监控</p>
      </div>
      <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Activity class="w-4 h-4 text-green-500 animate-pulse" />
        <span>实时更新中</span>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">总交易数</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(stats.totalTransactions) }}</span>
            </p>
            <p class="text-xs text-green-500 mt-2 flex items-center gap-1">
              <TrendingUp class="w-3 h-3" />
              +12.5% 较昨日
            </p>
          </div>
          <div class="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
            <TrendingUp class="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">总地址数</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(stats.totalAddresses) }}</span>
            </p>
            <p class="text-xs text-green-500 mt-2 flex items-center gap-1">
              <TrendingUp class="w-3 h-3" />
              +8.3% 较昨日
            </p>
          </div>
          <div class="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
            <Users class="w-6 h-6 text-green-600 dark:text-green-400" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">高风险地址数</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(stats.highRiskAddresses) }}</span>
            </p>
            <p class="text-xs text-red-500 mt-2 flex items-center gap-1">
              <AlertTriangle class="w-3 h-3" />
              +23 新增
            </p>
          </div>
          <div class="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
            <AlertTriangle class="w-6 h-6 text-red-600 dark:text-red-400" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">今日交易额</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              <span v-if="loading">---</span>
              <span v-else>{{ formatBTC(stats.todayVolume) }}</span>
            </p>
            <p class="text-xs text-gray-500 mt-2">BTC</p>
          </div>
          <div class="w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg flex items-center justify-center">
            <DollarSign class="w-6 h-6 text-yellow-600 dark:text-yellow-400" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div v-if="loading" class="h-80 flex items-center justify-center">
          <Loader class="w-8 h-8 text-blue-500 animate-spin" />
        </div>
        <v-chart v-else :option="lineChartOption" class="h-80" autoresize />
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div v-if="loading" class="h-80 flex items-center justify-center">
          <Loader class="w-8 h-8 text-blue-500 animate-spin" />
        </div>
        <v-chart v-else :option="barChartOption" class="h-80" autoresize />
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">最近警报</h3>
          <button 
            class="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            @click="navigateToGraph"
          >
            查看全部
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
        
        <div v-if="loading" class="h-64 flex items-center justify-center">
          <Loader class="w-8 h-8 text-blue-500 animate-spin" />
        </div>
        
        <div v-else class="relative">
          <div class="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />
          
          <div class="space-y-4">
            <div 
              v-for="alert in alerts" 
              :key="alert.id"
              class="relative pl-10 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-lg p-3 -ml-3 transition-colors"
            >
              <div 
                class="absolute left-2 top-4 w-4 h-4 rounded-full border-2 border-white dark:border-gray-800"
                :class="getSeverityColor(alert.severity)"
              />
              
              <div class="flex items-start justify-between">
                <div>
                  <span 
                    class="inline-block px-2 py-0.5 text-xs font-medium rounded-full mb-1"
                    :class="getSeverityColor(alert.severity) === 'bg-purple-500' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' :
                            getSeverityColor(alert.severity) === 'bg-red-500' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' :
                            getSeverityColor(alert.severity) === 'bg-yellow-500' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' :
                            'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'"
                  >
                    {{ getSeverityLabel(alert.severity) }}
                  </span>
                  <p class="text-sm text-gray-900 dark:text-white">{{ alert.message }}</p>
                  <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ formatDate(alert.time, 'relative') }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">最近任务</h3>
          <button 
            class="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            @click="navigateToTasks"
          >
            全部任务
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
        
        <div v-if="loading" class="h-64 flex items-center justify-center">
          <Loader class="w-8 h-8 text-blue-500 animate-spin" />
        </div>
        
        <div v-else class="space-y-3">
          <div 
            v-for="task in taskStore.tasks.slice(0, 5)" 
            :key="task.id"
            class="p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 transition-colors cursor-pointer"
            @click="navigateToTasks"
          >
            <div class="flex items-center gap-3">
              <component 
                :is="getTaskStatusIcon(task.status)" 
                class="w-5 h-5 flex-shrink-0"
                :class="{
                  'text-blue-500 animate-spin': task.status === 'processing',
                  'text-green-500': task.status === 'completed',
                  'text-red-500': task.status === 'failed',
                  'text-gray-500': task.status === 'pending'
                }"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {{ task.name || TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.label || task.type }}
                </p>
                <p class="text-xs text-gray-500 dark:text-gray-400">
                  {{ formatDate(task.createdAt, 'relative') }}
                </p>
              </div>
              <span 
                class="text-xs font-medium px-2 py-0.5 rounded-full"
                :class="TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.bgColor || 'bg-gray-100',
                        TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.textColor || 'text-gray-800'"
              >
                {{ TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.label || task.status }}
              </span>
            </div>
            
            <div v-if="task.status === 'processing'" class="mt-2">
              <div class="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div 
                  class="h-full bg-blue-500 rounded-full transition-all duration-300"
                  :style="{ width: `${task.progress || 0}%` }"
                />
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ task.progress || 0 }}%</p>
            </div>
          </div>
          
          <div v-if="taskStore.tasks.length === 0" class="text-center py-8 text-gray-500 dark:text-gray-400">
            <p class="text-sm">暂无任务记录</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
