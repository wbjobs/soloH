<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Play,
  Download,
  Layers,
  Users,
  Wallet,
  TrendingUp,
  Loader,
  X,
  ChevronDown,
  ChevronUp,
  FileJson,
  FileText,
  Hash,
  ExternalLink,
  Filter
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useAnalysisStore } from '@/stores/analysis'
import { RISK_LEVELS } from '@/utils/constants'
import { formatBTC, formatNumber, formatHash, formatDate } from '@/utils/format'
import type { AddressCluster } from '@/types'
import ClusterCard from '@/components/ClusterCard.vue'

const router = useRouter()
const appStore = useAppStore()
const analysisStore = useAnalysisStore()

const loading = ref(true)
const showSidebar = ref(false)
const selectedCluster = ref<AddressCluster | null>(null)
const heuristicMethod = ref('common_input')
const showExportDropdown = ref(false)
const filterMinSize = ref(1)
const filterMaxRisk = ref(100)

const heuristicMethods = [
  { value: 'common_input', label: '公共输入启发式', description: '基于多输入地址归并' },
  { value: 'change_address', label: '找零地址启发式', description: '基于找零地址识别' },
  { value: 'shadow_wallet', label: '影子钱包聚类', description: '基于钱包行为特征' },
  { value: 'combined', label: '综合方法', description: '多种启发式算法组合' }
]

const filteredClusters = computed(() => {
  return analysisStore.clusters.filter(cluster => {
    const sizeMatch = cluster.size >= filterMinSize.value
    const riskMatch = (cluster.avgSuspiciousScore || 0) <= filterMaxRisk.value
    return sizeMatch && riskMatch
  })
})

const clusterStats = computed(() => {
  const clusters = analysisStore.clusters
  if (clusters.length === 0) {
    return {
      totalClusters: 0,
      totalAddresses: 0,
      avgClusterSize: 0,
      totalBalance: 0
    }
  }
  
  return {
    totalClusters: clusters.length,
    totalAddresses: clusters.reduce((sum, c) => sum + c.size, 0),
    avgClusterSize: clusters.reduce((sum, c) => sum + c.size, 0) / clusters.length,
    totalBalance: clusters.reduce((sum, c) => sum + c.balance, 0)
  }
})

function getRiskColor(score: number) {
  if (score >= 75) return RISK_LEVELS.critical.color
  if (score >= 50) return RISK_LEVELS.high.color
  if (score >= 25) return RISK_LEVELS.medium.color
  return RISK_LEVELS.low.color
}

function viewClusterDetail(cluster: AddressCluster) {
  selectedCluster.value = cluster
  analysisStore.selectCluster(cluster)
  showSidebar.value = true
}

function closeSidebar() {
  showSidebar.value = false
  selectedCluster.value = null
  analysisStore.clearSelectedCluster()
}

function navigateToGraph() {
  if (selectedCluster.value) {
    router.push({
      path: '/graph',
      query: { cluster: selectedCluster.value.clusterId }
    })
  }
}

function exportData(format: 'csv' | 'json') {
  showExportDropdown.value = false
  appStore.addNotification({
    type: 'success',
    message: `聚类数据已导出为 ${format.toUpperCase()} 格式`
  })
}

async function runClustering() {
  try {
    await analysisStore.runClustering({ algorithm: heuristicMethod.value })
    appStore.addNotification({
      type: 'success',
      message: '聚类分析完成'
    })
  } catch (e) {
    appStore.addNotification({
      type: 'error',
      message: '聚类分析失败，请重试'
    })
  }
}

async function loadMockData() {
  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 1000))
  
  const tags = ['交易所', '混币服务', '暗网市场', '矿池', '普通地址', '大额持有', '快速转账']
  
  const mockClusters: AddressCluster[] = Array.from({ length: 12 }, (_, i) => ({
    clusterId: `cluster_${i + 1}`,
    name: `聚类 #${i + 1}`,
    size: Math.floor(Math.random() * 500) + 2,
    addresses: Array.from({ length: Math.min(Math.floor(Math.random() * 10) + 2, 10) }, () => 
      `bc1q${Math.random().toString(36).slice(2, 40)}`
    ),
    totalReceived: Math.random() * 1000 * 1e8,
    totalSent: Math.random() * 800 * 1e8,
    balance: Math.random() * 200 * 1e8,
    txCount: Math.floor(Math.random() * 5000) + 100,
    avgSuspiciousScore: Math.floor(Math.random() * 80) + 10,
    tags: Array.from({ length: Math.floor(Math.random() * 3) + 1 }, () => 
      tags[Math.floor(Math.random() * tags.length)]
    ),
    firstSeen: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000),
    lastSeen: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000)
  })).sort((a, b) => (b.avgSuspiciousScore || 0) - (a.avgSuspiciousScore || 0))
  
  analysisStore.clusters = mockClusters
  analysisStore.clusteringResult = {
    id: 1,
    algorithm: heuristicMethod.value,
    parameters: { algorithm: heuristicMethod.value },
    clusterCount: mockClusters.length,
    addressCount: mockClusters.reduce((sum, c) => sum + c.size, 0),
    clusters: mockClusters,
    createdAt: new Date()
  }
  
  loading.value = false
}

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">聚类分析</h1>
        <p class="text-gray-500 dark:text-gray-400 mt-1">基于启发式方法的地址聚类分析</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="runClustering"
          :disabled="analysisStore.isClustering"
          class="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white rounded-lg transition-colors"
        >
          <component :is="analysisStore.isClustering ? Loader : Play" class="w-4 h-4" :class="{ 'animate-spin': analysisStore.isClustering }" />
          {{ analysisStore.isClustering ? '聚类中...' : '运行聚类分析' }}
        </button>
        <div class="relative">
          <button
            @click="showExportDropdown = !showExportDropdown"
            class="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <Download class="w-4 h-4" />
            导出
            <component :is="showExportDropdown ? ChevronUp : ChevronDown" class="w-4 h-4" />
          </button>
          <div
            v-if="showExportDropdown"
            class="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-10"
          >
            <button
              @click="exportData('csv')"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <FileText class="w-4 h-4" />
              导出为 CSV
            </button>
            <button
              @click="exportData('json')"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <FileJson class="w-4 h-4" />
              导出为 JSON
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="flex flex-col md:flex-row md:items-center gap-4">
        <div class="flex items-center gap-2">
          <Filter class="w-5 h-5 text-gray-500 dark:text-gray-400" />
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">启发式方法</span>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="method in heuristicMethods"
            :key="method.value"
            @click="heuristicMethod = method.value"
            class="px-3 py-1.5 text-sm rounded-lg transition-colors"
            :class="[
              heuristicMethod === method.value
                ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-600'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border border-transparent hover:bg-gray-200 dark:hover:bg-gray-600'
            ]"
          >
            {{ method.label }}
          </button>
        </div>
      </div>
      
      <div class="flex flex-wrap items-center gap-6 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <label class="text-sm text-gray-600 dark:text-gray-400">最小聚类大小</label>
          <input
            v-model.number="filterMinSize"
            type="range"
            min="1"
            max="100"
            class="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
          <span class="text-sm font-medium text-gray-900 dark:text-white w-8">{{ filterMinSize }}</span>
        </div>
        <div class="flex items-center gap-3">
          <label class="text-sm text-gray-600 dark:text-gray-400">最大风险分数</label>
          <input
            v-model.number="filterMaxRisk"
            type="range"
            min="0"
            max="100"
            class="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
          <span class="text-sm font-medium text-gray-900 dark:text-white w-8">{{ filterMaxRisk }}</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center">
            <Layers class="w-5 h-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <p class="text-xs text-gray-500 dark:text-gray-400">聚类数量</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(clusterStats.totalClusters) }}</span>
            </p>
          </div>
        </div>
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
            <Users class="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <p class="text-xs text-gray-500 dark:text-gray-400">地址总数</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(clusterStats.totalAddresses) }}</span>
            </p>
          </div>
        </div>
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
            <TrendingUp class="w-5 h-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p class="text-xs text-gray-500 dark:text-gray-400">平均大小</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white">
              <span v-if="loading">---</span>
              <span v-else>{{ formatNumber(clusterStats.avgClusterSize, 1) }}</span>
            </p>
          </div>
        </div>
      </div>
      
      <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg flex items-center justify-center">
            <Wallet class="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div>
            <p class="text-xs text-gray-500 dark:text-gray-400">总余额</p>
            <p class="text-xl font-bold text-gray-900 dark:text-white">
              <span v-if="loading">---</span>
              <span v-else>{{ formatBTC(clusterStats.totalBalance) }}</span>
            </p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="analysisStore.isClustering" class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="flex items-center gap-4 mb-4">
        <Loader class="w-6 h-6 text-purple-500 animate-spin" />
        <div class="flex-1">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-900 dark:text-white">正在执行聚类分析</span>
            <span class="text-sm text-gray-500 dark:text-gray-400">{{ analysisStore.clusteringProgress }}%</span>
          </div>
          <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-purple-500 rounded-full transition-all duration-300"
              :style="{ width: `${analysisStore.clusteringProgress}%` }"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 animate-pulse">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-xl" />
            <div>
              <div class="w-24 h-4 bg-gray-200 dark:bg-gray-700 rounded mb-1" />
              <div class="w-16 h-3 bg-gray-200 dark:bg-gray-700 rounded" />
            </div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-2 mb-4">
          <div class="h-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
          <div class="h-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
          <div class="h-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
        </div>
        <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
    </div>

    <div v-else-if="filteredClusters.length === 0" class="bg-white dark:bg-gray-800 rounded-xl p-12 shadow-sm border border-gray-200 dark:border-gray-700 text-center">
      <Layers class="w-12 h-12 text-gray-400 mx-auto mb-4" />
      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">暂无聚类结果</h3>
      <p class="text-gray-500 dark:text-gray-400 mb-4">点击"运行聚类分析"按钮开始分析</p>
      <button
        @click="runClustering"
        class="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
      >
        <Play class="w-4 h-4" />
        运行聚类分析
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ClusterCard
        v-for="cluster in filteredClusters"
        :key="cluster.clusterId"
        :cluster="cluster"
        @view-detail="viewClusterDetail"
      />
    </div>

    <div
      v-if="showSidebar && selectedCluster"
      class="fixed inset-0 z-50 flex"
    >
      <div class="absolute inset-0 bg-black/50" @click="closeSidebar" />
      <div class="relative ml-auto w-full max-w-xl bg-white dark:bg-gray-900 h-full overflow-y-auto shadow-xl">
        <div class="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 p-4 flex items-center justify-between z-10">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg flex items-center justify-center">
              <Layers class="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <Hash class="w-4 h-4 text-gray-500" />
                {{ selectedCluster.name || selectedCluster.clusterId }}
              </h3>
              <p class="text-xs text-gray-500 dark:text-gray-400">聚类详情</p>
            </div>
          </div>
          <button
            @click="closeSidebar"
            class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X class="w-5 h-5 text-gray-500" />
          </button>
        </div>
        
        <div class="p-6 space-y-6">
          <div class="grid grid-cols-2 gap-4">
            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">地址数量</p>
              <p class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(selectedCluster.size) }}</p>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">交易次数</p>
              <p class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(selectedCluster.txCount) }}</p>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">余额</p>
              <p class="text-xl font-bold text-gray-900 dark:text-white">{{ formatBTC(selectedCluster.balance) }}</p>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">平均风险</p>
              <p class="text-2xl font-bold" :style="{ color: getRiskColor(selectedCluster.avgSuspiciousScore || 0) }">
                {{ selectedCluster.avgSuspiciousScore?.toFixed(1) || '-' }}
              </p>
            </div>
          </div>

          <div>
            <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-3">标签</h4>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="tag in selectedCluster.tags"
                :key="tag"
                class="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-medium text-gray-900 dark:text-white">成员地址</h4>
              <button
                @click="navigateToGraph"
                class="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
              >
                查看关联图
                <ExternalLink class="w-3 h-3" />
              </button>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg overflow-hidden">
              <div class="max-h-80 overflow-y-auto">
                <div
                  v-for="(address, idx) in selectedCluster.addresses.slice(0, 20)"
                  :key="idx"
                  class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 last:border-b-0 hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                  @click="router.push(`/address/${address}`)"
                >
                  <div class="flex items-center gap-3">
                    <div class="w-2 h-2 rounded-full bg-purple-500" />
                    <span class="font-mono text-sm text-gray-700 dark:text-gray-300">{{ formatHash(address, 25) }}</span>
                  </div>
                  <ExternalLink class="w-4 h-4 text-gray-400" />
                </div>
              </div>
              <div v-if="selectedCluster.addresses.length > 20" class="px-4 py-2 text-center text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800/50">
                还有 {{ selectedCluster.addresses.length - 20 }} 个地址...
              </div>
            </div>
          </div>

          <div>
            <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-3">时间范围</h4>
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">首次活动</p>
                <p class="text-sm font-medium text-gray-900 dark:text-white">{{ formatDate(selectedCluster.firstSeen) }}</p>
              </div>
              <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">最近活动</p>
                <p class="text-sm font-medium text-gray-900 dark:text-white">{{ formatDate(selectedCluster.lastSeen) }}</p>
              </div>
            </div>
          </div>

          <div class="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-800">
            <button
              @click="navigateToGraph"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              <ExternalLink class="w-4 h-4" />
              查看关联图
            </button>
            <button
              @click="exportData('csv')"
              class="flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              <Download class="w-4 h-4" />
              导出
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
