<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Play,
  Pause,
  CheckCircle,
  XCircle,
  Clock,
  Loader,
  Filter,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Trash2,
  RefreshCw,
  XOctagon,
  Calendar,
  FileText,
  Cloud,
  Layers,
  GitBranch,
  Search,
  Download,
  Settings,
  AlertCircle,
  MoreHorizontal,
  Info
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useTaskStore } from '@/stores/task'
import { TASK_STATUS, TASK_TYPES } from '@/utils/constants'
import { formatNumber, formatDate, formatBytes } from '@/utils/format'
import type { Task, TaskLog } from '@/types'

const router = useRouter()
const appStore = useAppStore()
const taskStore = useTaskStore()

const loading = ref(true)
const selectedTaskIds = ref<string[]>([])
const expandedTaskId = ref<string | null>(null)
const sortField = ref('createdAt')
const sortOrder = ref<'asc' | 'desc'>('desc')

const taskTypeFilter = ref<string>('all')
const statusFilter = ref<string>('all')
const startDate = ref<string>('')
const endDate = ref<string>('')
const searchQuery = ref('')

const taskLogs = ref<Record<string, TaskLog[]>>({})
const loadingLogs = ref<Record<string, boolean>>({})

const stats = computed(() => ({
  running: taskStore.tasks.filter(t => t.status === 'processing').length,
  pending: taskStore.tasks.filter(t => t.status === 'pending').length,
  completed: taskStore.tasks.filter(t => t.status === 'completed').length,
  failed: taskStore.tasks.filter(t => t.status === 'failed').length
}))

const filteredTasks = computed(() => {
  let tasks = [...taskStore.tasks]

  if (taskTypeFilter.value !== 'all') {
    tasks = tasks.filter(t => t.type === taskTypeFilter.value)
  }

  if (statusFilter.value !== 'all') {
    tasks = tasks.filter(t => t.status === statusFilter.value)
  }

  if (startDate.value) {
    const start = new Date(startDate.value)
    tasks = tasks.filter(t => new Date(t.createdAt) >= start)
  }

  if (endDate.value) {
    const end = new Date(endDate.value)
    end.setHours(23, 59, 59)
    tasks = tasks.filter(t => new Date(t.createdAt) <= end)
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    tasks = tasks.filter(t =>
      t.name?.toLowerCase().includes(query) ||
      t.type.toLowerCase().includes(query) ||
      t.id.toLowerCase().includes(query)
    )
  }

  tasks.sort((a, b) => {
    let aVal: unknown = a[sortField.value as keyof typeof a]
    let bVal: unknown = b[sortField.value as keyof typeof b]

    if (sortField.value === 'createdAt' || sortField.value === 'startedAt' || sortField.value === 'completedAt') {
      aVal = new Date(aVal as Date).getTime()
      bVal = new Date(bVal as Date).getTime()
    }

    if (aVal === null || aVal === undefined) return 1
    if (bVal === null || bVal === undefined) return -1

    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortOrder.value === 'asc' ? aVal - bVal : bVal - aVal
    }

    return 0
  })

  return tasks
})

const allSelected = computed(() => {
  return filteredTasks.value.length > 0 && filteredTasks.value.every(t => selectedTaskIds.value.includes(t.id))
})

const hasSelection = computed(() => selectedTaskIds.value.length > 0)

function getTaskIcon(type: string) {
  const taskType = TASK_TYPES[type as keyof typeof TASK_TYPES]
  switch (taskType?.icon) {
    case 'file-text': return FileText
    case 'cloud-download': return Cloud
    case 'refresh-cw': return RefreshCw
    case 'search': return Search
    case 'git-branch': return GitBranch
    case 'layers': return Layers
    case 'network': return GitBranch
    case 'download': return Download
    default: return Settings
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'processing': return Loader
    case 'completed': return CheckCircle
    case 'failed': return XCircle
    case 'cancelled': return XOctagon
    default: return Clock
  }
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedTaskIds.value = []
  } else {
    selectedTaskIds.value = filteredTasks.value.map(t => t.id)
  }
}

function toggleSelect(taskId: string) {
  const index = selectedTaskIds.value.indexOf(taskId)
  if (index > -1) {
    selectedTaskIds.value.splice(index, 1)
  } else {
    selectedTaskIds.value.push(taskId)
  }
}

function toggleExpand(taskId: string) {
  if (expandedTaskId.value === taskId) {
    expandedTaskId.value = null
  } else {
    expandedTaskId.value = taskId
    loadTaskLogs(taskId)
  }
}

async function loadTaskLogs(taskId: string) {
  if (taskLogs.value[taskId]) return
  
  loadingLogs.value[taskId] = true
  await new Promise(resolve => setTimeout(resolve, 500))
  
  taskLogs.value[taskId] = [
    { id: 1, taskId, level: 'info', message: '任务开始执行', createdAt: new Date(Date.now() - 1000 * 60 * 30) },
    { id: 2, taskId, level: 'info', message: '正在连接数据库...', createdAt: new Date(Date.now() - 1000 * 60 * 29) },
    { id: 3, taskId, level: 'info', message: '数据库连接成功', createdAt: new Date(Date.now() - 1000 * 60 * 28) },
    { id: 4, taskId, level: 'info', message: '开始处理数据，共 15420 条记录', createdAt: new Date(Date.now() - 1000 * 60 * 25) },
    { id: 5, taskId, level: 'warning', message: '第 1234 条记录格式异常，已跳过', createdAt: new Date(Date.now() - 1000 * 60 * 15) },
    { id: 6, taskId, level: 'info', message: '已处理 5000 条记录', createdAt: new Date(Date.now() - 1000 * 60 * 10) },
    { id: 7, taskId, level: 'info', message: '已处理 10000 条记录', createdAt: new Date(Date.now() - 1000 * 60 * 5) },
    { id: 8, taskId, level: 'info', message: '数据处理完成，共 15419 条有效记录', createdAt: new Date(Date.now() - 1000 * 60 * 1) },
    { id: 9, taskId, level: 'success', message: '任务执行成功', createdAt: new Date() }
  ]
  
  loadingLogs.value[taskId] = false
}

function sortBy(field: string) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
}

async function cancelSelected() {
  for (const taskId of selectedTaskIds.value) {
    await taskStore.cancelTask(taskId)
  }
  selectedTaskIds.value = []
  appStore.addNotification({
    type: 'success',
    message: `已取消 ${selectedTaskIds.value.length} 个任务`
  })
}

async function retrySelected() {
  for (const taskId of selectedTaskIds.value) {
    await taskStore.retryTask(taskId)
  }
  selectedTaskIds.value = []
  appStore.addNotification({
    type: 'success',
    message: `已重试 ${selectedTaskIds.value.length} 个任务`
  })
}

function clearFilters() {
  taskTypeFilter.value = 'all'
  statusFilter.value = 'all'
  startDate.value = ''
  endDate.value = ''
  searchQuery.value = ''
}

async function loadMockData() {
  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 800))

  const mockTasks: Task[] = [
    {
      id: 'task-001',
      type: 'import_csv',
      name: '导入交易数据 transactions_202405.csv',
      description: '从CSV文件导入2024年5月的交易数据',
      status: 'completed',
      progress: 100,
      message: '成功导入15420条记录',
      parameters: { filePath: 'transactions_202405.csv', type: 'transactions' },
      result: { imported: 15420, skipped: 1, errors: 0 },
      createdAt: new Date('2024-05-23T10:30:00'),
      startedAt: new Date('2024-05-23T10:30:05'),
      completedAt: new Date('2024-05-23T10:35:00')
    },
    {
      id: 'task-002',
      type: 'cluster_addresses',
      name: '地址聚类分析',
      description: '使用共输入启发式算法进行地址聚类',
      status: 'processing',
      progress: 67,
      message: '正在计算地址相似度...',
      parameters: { algorithm: 'common_input', minClusterSize: 2 },
      createdAt: new Date('2024-05-23T09:15:00'),
      startedAt: new Date('2024-05-23T09:15:10')
    },
    {
      id: 'task-003',
      type: 'import_api',
      name: '从Blockchain.com拉取数据',
      description: '拉取区块839000-839500的交易数据',
      status: 'pending',
      progress: 0,
      parameters: { source: 'blockchain.info', startBlock: 839000, endBlock: 839500 },
      createdAt: new Date('2024-05-23T08:00:00')
    },
    {
      id: 'task-004',
      type: 'analyze_address',
      name: '分析高风险地址 bc1q...a1b2',
      description: '分析地址的风险评分和关联模式',
      status: 'failed',
      progress: 45,
      message: '网络超时，连接区块链API失败',
      error: 'Connection timeout after 30s',
      parameters: { address: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq' },
      createdAt: new Date('2024-05-22T16:30:00'),
      startedAt: new Date('2024-05-22T16:30:05'),
      completedAt: new Date('2024-05-22T16:35:00')
    },
    {
      id: 'task-005',
      type: 'build_graph',
      name: '构建交易关系图谱',
      description: '基于最近30天的交易数据构建图谱',
      status: 'completed',
      progress: 100,
      message: '图谱构建完成，包含45231个节点和128456条边',
      parameters: { days: 30, minValue: 0.01 },
      result: { nodes: 45231, edges: 128456, avgDegree: 5.68 },
      createdAt: new Date('2024-05-22T14:00:00'),
      startedAt: new Date('2024-05-22T14:00:10'),
      completedAt: new Date('2024-05-22T14:25:00')
    },
    {
      id: 'task-006',
      type: 'export_data',
      name: '导出高风险地址数据',
      description: '导出风险评分大于50的地址列表',
      status: 'completed',
      progress: 100,
      message: '成功导出1247条记录',
      parameters: { minScore: 50, format: 'csv' },
      result: { exported: 1247, fileSize: 245760 },
      createdAt: new Date('2024-05-21T11:20:00'),
      startedAt: new Date('2024-05-21T11:20:05'),
      completedAt: new Date('2024-05-21T11:22:00')
    },
    {
      id: 'task-007',
      type: 'sync_blockchain',
      name: '同步区块链数据',
      description: '同步最新区块数据到本地数据库',
      status: 'processing',
      progress: 34,
      message: '正在同步区块 #840123...',
      parameters: { mode: 'latest' },
      createdAt: new Date('2024-05-23T00:00:00'),
      startedAt: new Date('2024-05-23T00:00:10')
    },
    {
      id: 'task-008',
      type: 'analyze_transaction',
      name: '分析大额交易 abc123def...',
      description: '分析可疑交易的资金流向',
      status: 'cancelled',
      progress: 12,
      message: '用户取消了任务',
      parameters: { txId: 'abc123def4567890' },
      createdAt: new Date('2024-05-20T09:00:00'),
      startedAt: new Date('2024-05-20T09:00:05'),
      completedAt: new Date('2024-05-20T09:01:00')
    }
  ]

  taskStore.tasks = mockTasks
  loading.value = false
}

function navigateToTask(taskId: string) {
  router.push(`/tasks/${taskId}`)
}

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">任务管理</h1>
        <p class="text-gray-500 dark:text-gray-400 mt-1">查看和管理系统任务</p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">运行中</p>
            <p class="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{{ stats.running }}</p>
          </div>
          <div class="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
            <Loader class="w-6 h-6 text-blue-600 dark:text-blue-400 animate-spin" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">等待中</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white mt-1">{{ stats.pending }}</p>
          </div>
          <div class="w-12 h-12 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center">
            <Clock class="w-6 h-6 text-gray-600 dark:text-gray-400" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">已完成</p>
            <p class="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">{{ stats.completed }}</p>
          </div>
          <div class="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
            <CheckCircle class="w-6 h-6 text-green-600 dark:text-green-400" />
          </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">失败</p>
            <p class="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">{{ stats.failed }}</p>
          </div>
          <div class="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
            <XCircle class="w-6 h-6 text-red-600 dark:text-red-400" />
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div class="p-4 border-b border-gray-200 dark:border-gray-700">
        <div class="flex flex-wrap items-center gap-4">
          <div class="flex items-center gap-2 flex-1 min-w-64">
            <Search class="w-5 h-5 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索任务名称或ID..."
              class="flex-1 bg-transparent border-none outline-none text-gray-900 dark:text-white placeholder-gray-400"
            />
          </div>

          <div class="flex items-center gap-2">
            <Filter class="w-4 h-4 text-gray-400" />
            <select
              v-model="taskTypeFilter"
              class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">全部类型</option>
              <option v-for="(type, key) in TASK_TYPES" :key="key" :value="key">
                {{ type.label }}
              </option>
            </select>
          </div>

          <div class="flex items-center gap-2">
            <select
              v-model="statusFilter"
              class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">全部状态</option>
              <option v-for="(status, key) in TASK_STATUS" :key="key" :value="key">
                {{ status.label }}
              </option>
            </select>
          </div>

          <div class="flex items-center gap-2">
            <Calendar class="w-4 h-4 text-gray-400" />
            <input
              v-model="startDate"
              type="date"
              class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span class="text-gray-400">至</span>
            <input
              v-model="endDate"
              type="date"
              class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <button
            @click="clearFilters"
            class="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            清除筛选
          </button>
        </div>

        <div v-if="hasSelection" class="flex items-center gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            已选择 {{ selectedTaskIds.length }} 个任务
          </span>
          <button
            @click="cancelSelected"
            class="px-3 py-1.5 text-sm border border-yellow-300 dark:border-yellow-600 text-yellow-700 dark:text-yellow-300 rounded-lg hover:bg-yellow-50 dark:hover:bg-yellow-900/20 transition-colors flex items-center gap-1"
          >
            <XOctagon class="w-4 h-4" />
            取消
          </button>
          <button
            @click="retrySelected"
            class="px-3 py-1.5 text-sm border border-blue-300 dark:border-blue-600 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors flex items-center gap-1"
          >
            <RefreshCw class="w-4 h-4" />
            重试
          </button>
        </div>
      </div>

      <div v-if="loading" class="flex items-center justify-center py-20">
        <Loader class="w-12 h-12 text-blue-500 animate-spin" />
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-4 py-3 text-left w-12">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                  class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
              </th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300">
                <button @click="sortBy('type')" class="flex items-center gap-1 hover:text-gray-900 dark:hover:text-white">
                  类型
                  <component :is="sortField === 'type' ? (sortOrder === 'asc' ? ChevronUp : ChevronDown) : ChevronDown" class="w-4 h-4 opacity-50" />
                </button>
              </th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300">名称</th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300">
                <button @click="sortBy('status')" class="flex items-center gap-1 hover:text-gray-900 dark:hover:text-white">
                  状态
                  <component :is="sortField === 'status' ? (sortOrder === 'asc' ? ChevronUp : ChevronDown) : ChevronDown" class="w-4 h-4 opacity-50" />
                </button>
              </th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300">
                <button @click="sortBy('progress')" class="flex items-center gap-1 hover:text-gray-900 dark:hover:text-white">
                  进度
                  <component :is="sortField === 'progress' ? (sortOrder === 'asc' ? ChevronUp : ChevronDown) : ChevronDown" class="w-4 h-4 opacity-50" />
                </button>
              </th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300">
                <button @click="sortBy('createdAt')" class="flex items-center gap-1 hover:text-gray-900 dark:hover:text-white">
                  创建时间
                  <component :is="sortField === 'createdAt' ? (sortOrder === 'asc' ? ChevronUp : ChevronDown) : ChevronDown" class="w-4 h-4 opacity-50" />
                </button>
              </th>
              <th class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300 w-12"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            <template v-for="task in filteredTasks" :key="task.id">
              <tr
                class="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                :class="{ 'bg-blue-50 dark:bg-blue-900/20': selectedTaskIds.includes(task.id) }"
              >
                <td class="px-4 py-4" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedTaskIds.includes(task.id)"
                    @change="toggleSelect(task.id)"
                    class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                  />
                </td>
                <td class="px-4 py-4">
                  <div class="flex items-center gap-2">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center"
                      :class="TASK_STATUS[task.status]?.bgColor || 'bg-gray-100'"
                    >
                      <component
                        :is="getTaskIcon(task.type)"
                        class="w-4 h-4"
                        :class="TASK_STATUS[task.status]?.textColor || 'text-gray-800'"
                      />
                    </div>
                    <span class="text-gray-900 dark:text-white font-medium">
                      {{ TASK_TYPES[task.type as keyof typeof TASK_TYPES]?.label || task.type }}
                    </span>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="max-w-xs">
                    <p class="font-medium text-gray-900 dark:text-white truncate">{{ task.name || task.type }}</p>
                    <p v-if="task.message" class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ task.message }}</p>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <span
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
                    :class="TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.bgColor || 'bg-gray-100',
                            TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.textColor || 'text-gray-800'"
                  >
                    <component
                      :is="getStatusIcon(task.status)"
                      class="w-3 h-3"
                      :class="{ 'animate-spin': task.status === 'processing' }"
                    />
                    {{ TASK_STATUS[task.status as keyof typeof TASK_STATUS]?.label || task.status }}
                  </span>
                  <p v-if="task.error" class="text-xs text-red-500 mt-1 truncate max-w-xs">{{ task.error }}</p>
                </td>
                <td class="px-4 py-4">
                  <div class="w-32">
                    <div class="flex items-center justify-between mb-1">
                      <span class="text-xs text-gray-500 dark:text-gray-400">{{ task.progress }}%</span>
                    </div>
                    <div class="h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all duration-300"
                        :class="{
                          'bg-blue-500': task.status === 'processing',
                          'bg-green-500': task.status === 'completed',
                          'bg-red-500': task.status === 'failed',
                          'bg-yellow-500': task.status === 'cancelled',
                          'bg-gray-400': task.status === 'pending'
                        }"
                        :style="{ width: `${task.progress}%` }"
                      />
                    </div>
                  </div>
                </td>
                <td class="px-4 py-4 text-gray-500 dark:text-gray-400">
                  {{ formatDate(task.createdAt, 'full') }}
                </td>
                <td class="px-4 py-4" @click.stop>
                  <button
                    @click="toggleExpand(task.id)"
                    class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                  >
                    <component
                      :is="expandedTaskId === task.id ? ChevronUp : ChevronDown"
                      class="w-5 h-5 text-gray-400"
                    />
                  </button>
                </td>
              </tr>
              <tr v-if="expandedTaskId === task.id" class="bg-gray-50 dark:bg-gray-700/30">
                <td colspan="7" class="px-4 py-4">
                  <div class="pl-12 space-y-4">
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div v-if="task.startedAt">
                        <p class="text-xs text-gray-500 dark:text-gray-400">开始时间</p>
                        <p class="text-sm font-medium text-gray-900 dark:text-white">{{ formatDate(task.startedAt, 'full') }}</p>
                      </div>
                      <div v-if="task.completedAt">
                        <p class="text-xs text-gray-500 dark:text-gray-400">完成时间</p>
                        <p class="text-sm font-medium text-gray-900 dark:text-white">{{ formatDate(task.completedAt, 'full') }}</p>
                      </div>
                      <div v-if="task.parameters">
                        <p class="text-xs text-gray-500 dark:text-gray-400">参数</p>
                        <p class="text-sm font-medium text-gray-900 dark:text-white font-mono truncate">{{ JSON.stringify(task.parameters) }}</p>
                      </div>
                      <div v-if="task.result">
                        <p class="text-xs text-gray-500 dark:text-gray-400">结果</p>
                        <p class="text-sm font-medium text-gray-900 dark:text-white font-mono truncate">{{ JSON.stringify(task.result) }}</p>
                      </div>
                    </div>

                    <div class="border-t border-gray-200 dark:border-gray-600 pt-4">
                      <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <FileText class="w-4 h-4" />
                        任务日志
                      </h4>
                      
                      <div v-if="loadingLogs[task.id]" class="flex items-center justify-center py-8">
                        <Loader class="w-6 h-6 text-blue-500 animate-spin" />
                      </div>
                      
                      <div v-else class="space-y-2 max-h-64 overflow-y-auto">
                        <div
                          v-for="log in taskLogs[task.id]"
                          :key="log.id"
                          class="flex items-start gap-3 p-2 rounded bg-white dark:bg-gray-800"
                        >
                          <component
                            :is="log.level === 'error' ? AlertCircle : log.level === 'success' ? CheckCircle : Info"
                            class="w-4 h-4 mt-0.5 flex-shrink-0"
                            :class="{
                              'text-red-500': log.level === 'error',
                              'text-green-500': log.level === 'success',
                              'text-yellow-500': log.level === 'warning',
                              'text-blue-500': log.level === 'info'
                            }"
                          />
                          <div class="flex-1 min-w-0">
                            <p class="text-sm text-gray-900 dark:text-white">{{ log.message }}</p>
                            <p class="text-xs text-gray-500 dark:text-gray-400">{{ formatDate(log.createdAt, 'full') }}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="flex items-center gap-3 pt-4 border-t border-gray-200 dark:border-gray-600">
                      <button
                        v-if="task.status === 'failed'"
                        @click="taskStore.retryTask(task.id)"
                        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors flex items-center gap-2"
                      >
                        <RefreshCw class="w-4 h-4" />
                        重试任务
                      </button>
                      <button
                        v-if="task.status === 'processing' || task.status === 'pending'"
                        @click="taskStore.cancelTask(task.id)"
                        class="px-4 py-2 border border-yellow-300 dark:border-yellow-600 text-yellow-700 dark:text-yellow-300 text-sm rounded-lg hover:bg-yellow-50 dark:hover:bg-yellow-900/20 transition-colors flex items-center gap-2"
                      >
                        <XOctagon class="w-4 h-4" />
                        取消任务
                      </button>
                      <button
                        @click="navigateToTask(task.id)"
                        class="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center gap-2"
                      >
                        <MoreHorizontal class="w-4 h-4" />
                        查看详情
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <div v-if="filteredTasks.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
          <FileText class="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>没有找到符合条件的任务</p>
        </div>
      </div>

      <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <p class="text-sm text-gray-500 dark:text-gray-400">
          共 {{ filteredTasks.length }} 个任务
        </p>
        <div class="flex items-center gap-2">
          <button class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
            上一页
          </button>
          <span class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg">1</span>
          <button class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
            2
          </button>
          <button class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
            3
          </button>
          <button class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
