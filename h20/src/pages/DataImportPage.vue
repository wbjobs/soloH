<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Upload,
  FileText,
  Cloud,
  CloudDownload,
  X,
  CheckCircle,
  AlertCircle,
  Loader,
  ChevronRight,
  Play,
  Settings,
  Key,
  Database,
  FileUp,
  Table,
  ArrowRight,
  Trash2,
  Info,
  History
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useTaskStore } from '@/stores/task'
import { TASK_STATUS, TASK_TYPES } from '@/utils/constants'
import { formatNumber, formatDate, formatBytes } from '@/utils/format'

const router = useRouter()
const appStore = useAppStore()
const taskStore = useTaskStore()

const activeTab = ref<'csv' | 'api'>('csv')
const loading = ref(false)
const dragOver = ref(false)

const selectedFile = ref<File | null>(null)
const fileList = ref<{ file: File; progress: number; status: 'pending' | 'uploading' | 'completed' | 'error' }[]>([])
const fieldMapping = ref<Record<string, string>>({
  txid: 'txId',
  block_height: 'blockHeight',
  block_time: 'blockTime',
  input_value: 'inputValue',
  output_value: 'outputValue',
  fee: 'fee'
})
const csvPreview = ref<Record<string, unknown>[]>([])
const delimiter = ref(',')
const hasHeader = ref(true)

const apiSource = ref('blockchain.info')
const startBlock = ref<number | null>(null)
const endBlock = ref<number | null>(null)
const apiKey = ref('')
const apiUrl = ref('')

const importHistory = ref<{
  id: string
  type: 'csv' | 'api'
  source: string
  records: number
  status: string
  createdAt: Date
  completedAt?: Date
  error?: string
}[]>([])

const apiSources = [
  { value: 'blockchain.info', label: 'Blockchain.com', url: 'https://blockchain.info' },
  { value: 'blockchair', label: 'Blockchair', url: 'https://api.blockchair.com' },
  { value: 'blockstream', label: 'Blockstream', url: 'https://blockstream.info' },
  { value: 'mempool', label: 'Mempool.space', url: 'https://mempool.space' },
  { value: 'custom', label: '自定义API', url: '' }
]

const availableFields = [
  { value: 'txId', label: '交易ID' },
  { value: 'blockHeight', label: '区块高度' },
  { value: 'blockTime', label: '区块时间' },
  { value: 'inputCount', label: '输入数量' },
  { value: 'outputCount', label: '输出数量' },
  { value: 'inputValue', label: '输入金额' },
  { value: 'outputValue', label: '输出金额' },
  { value: 'fee', label: '矿工费' },
  { value: 'address', label: '地址' },
  { value: 'value', label: '金额' },
  { value: 'type', label: '类型' }
]

const uploadProgress = computed(() => {
  if (fileList.value.length === 0) return 0
  const total = fileList.value.length * 100
  const current = fileList.value.reduce((sum, f) => sum + f.progress, 0)
  return Math.round((current / total) * 100)
})

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}

function handleDragLeave() {
  dragOver.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFiles(files)
  }
}

function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    handleFiles(input.files)
  }
}

function handleFiles(files: FileList) {
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    if (file.name.endsWith('.csv')) {
      fileList.value.push({
        file,
        progress: 0,
        status: 'pending'
      })
      selectedFile.value = file
      generatePreview(file)
    } else {
      appStore.addNotification({
        type: 'error',
        message: `文件 ${file.name} 不是有效的CSV文件`
      })
    }
  }
}

async function generatePreview(file: File) {
  const text = await file.text()
  const lines = text.split('\n').filter(l => l.trim())
  const headerLine = hasHeader.value ? lines[0] : lines[0]
  const headers = headerLine.split(delimiter.value).map(h => h.trim().replace(/^"|"$/g, ''))
  
  const dataLines = hasHeader.value ? lines.slice(1, 6) : lines.slice(0, 5)
  csvPreview.value = dataLines.map(line => {
    const values = line.split(delimiter.value).map(v => v.trim().replace(/^"|"$/g, ''))
    const obj: Record<string, unknown> = {}
    headers.forEach((header, index) => {
      obj[header] = values[index] || ''
    })
    return obj
  })

  headers.forEach(header => {
    if (!fieldMapping.value[header]) {
      const match = availableFields.find(f => 
        f.label.toLowerCase().includes(header.toLowerCase()) ||
        f.value.toLowerCase().includes(header.toLowerCase())
      )
      fieldMapping.value[header] = match?.value || ''
    }
  })
}

function removeFile(index: number) {
  fileList.value.splice(index, 1)
  if (fileList.value.length === 0) {
    selectedFile.value = null
    csvPreview.value = []
  }
}

async function startCSVImport() {
  if (fileList.value.length === 0) {
    appStore.addNotification({
      type: 'warning',
      message: '请先选择要导入的文件'
    })
    return
  }

  loading.value = true

  for (const item of fileList.value) {
    item.status = 'uploading'
    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 200))
      item.progress = i
    }
    item.status = 'completed'
  }

  await new Promise(resolve => setTimeout(resolve, 500))
  
  const taskId = Date.now().toString()
  importHistory.value.unshift({
    id: taskId,
    type: 'csv',
    source: fileList.value.map(f => f.file.name).join(', '),
    records: Math.floor(Math.random() * 5000) + 1000,
    status: 'completed',
    createdAt: new Date(),
    completedAt: new Date()
  })

  appStore.addNotification({
    type: 'success',
    message: `成功导入 ${fileList.value.length} 个文件`
  })

  fileList.value = []
  selectedFile.value = null
  csvPreview.value = []
  loading.value = false
}

async function startAPIImport() {
  if (!startBlock.value || !endBlock.value) {
    appStore.addNotification({
      type: 'warning',
      message: '请填写完整的区块范围'
    })
    return
  }

  if (apiSource.value === 'custom' && !apiUrl.value) {
    appStore.addNotification({
      type: 'warning',
      message: '请填写API地址'
    })
    return
  }

  loading.value = true
  await new Promise(resolve => setTimeout(resolve, 2000))

  const taskId = Date.now().toString()
  const source = apiSources.find(s => s.value === apiSource.value)?.label || '自定义API'
  
  importHistory.value.unshift({
    id: taskId,
    type: 'api',
    source: `${source} (区块 ${startBlock.value} - ${endBlock.value})`,
    records: Math.floor(Math.random() * 10000) + 5000,
    status: 'completed',
    createdAt: new Date(),
    completedAt: new Date()
  })

  appStore.addNotification({
    type: 'success',
    message: 'API数据导入任务已创建'
  })

  loading.value = false
}

function updateFieldMapping(header: string, field: string) {
  fieldMapping.value[header] = field
}

function navigateToTask(taskId: string) {
  router.push(`/tasks/${taskId}`)
}

async function loadMockData() {
  await taskStore.fetchTasks()
  
  importHistory.value = [
    {
      id: '1',
      type: 'csv',
      source: 'transactions_202405.csv',
      records: 15420,
      status: 'completed',
      createdAt: new Date('2024-05-20T10:30:00'),
      completedAt: new Date('2024-05-20T10:35:00')
    },
    {
      id: '2',
      type: 'api',
      source: 'Blockchain.com (区块 839000 - 839500)',
      records: 28650,
      status: 'completed',
      createdAt: new Date('2024-05-19T14:00:00'),
      completedAt: new Date('2024-05-19T14:12:00')
    },
    {
      id: '3',
      type: 'csv',
      source: 'addresses_export.csv',
      records: 8920,
      status: 'failed',
      createdAt: new Date('2024-05-18T09:15:00'),
      error: '文件格式错误：缺少必要字段 txId'
    },
    {
      id: '4',
      type: 'api',
      source: 'Blockchair (区块 838000 - 839000)',
      records: 52340,
      status: 'completed',
      createdAt: new Date('2024-05-17T16:45:00'),
      completedAt: new Date('2024-05-17T17:05:00')
    }
  ]
}

onMounted(() => {
  loadMockData()
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">数据导入</h1>
        <p class="text-gray-500 dark:text-gray-400 mt-1">从CSV文件或区块链API导入交易数据</p>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div class="border-b border-gray-200 dark:border-gray-700">
        <nav class="flex">
          <button
            @click="activeTab = 'csv'"
            class="flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'csv'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
          >
            <FileText class="w-4 h-4" />
            CSV 导入
          </button>
          <button
            @click="activeTab = 'api'"
            class="flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'api'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
          >
            <Cloud class="w-4 h-4" />
            API 拉取
          </button>
        </nav>
      </div>

      <div v-if="activeTab === 'csv'" class="p-6 space-y-6">
        <div
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
          class="border-2 border-dashed rounded-xl p-12 text-center transition-colors"
          :class="dragOver
            ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
            : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'"
        >
          <input
            type="file"
            accept=".csv"
            multiple
            class="hidden"
            id="file-upload"
            @change="handleFileInput"
          />
          <label for="file-upload" class="cursor-pointer">
            <div class="w-16 h-16 mx-auto mb-4 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
              <Upload class="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <p class="text-lg font-medium text-gray-900 dark:text-white mb-2">
              拖拽文件到此处，或点击选择
            </p>
            <p class="text-sm text-gray-500 dark:text-gray-400">
              支持 .csv 格式文件，单个文件最大 100MB
            </p>
          </label>
        </div>

        <div v-if="fileList.length > 0" class="space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-medium text-gray-900 dark:text-white">已选择的文件</h3>
            <span class="text-sm text-gray-500 dark:text-gray-400">
              {{ fileList.length }} 个文件
            </span>
          </div>
          
          <div class="space-y-3">
            <div
              v-for="(item, index) in fileList"
              :key="index"
              class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4"
            >
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 bg-white dark:bg-gray-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileUp class="w-5 h-5 text-blue-500" />
                </div>
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-gray-900 dark:text-white truncate">{{ item.file.name }}</p>
                  <p class="text-sm text-gray-500 dark:text-gray-400">{{ formatBytes(item.file.size) }}</p>
                  <div v-if="item.status === 'uploading'" class="mt-2">
                    <div class="h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                      <div
                        class="h-full bg-blue-500 rounded-full transition-all"
                        :style="{ width: `${item.progress}%` }"
                      />
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <component
                    :is="item.status === 'completed' ? CheckCircle : item.status === 'error' ? AlertCircle : Loader"
                    class="w-5 h-5 flex-shrink-0"
                    :class="{
                      'text-green-500': item.status === 'completed',
                      'text-red-500': item.status === 'error',
                      'text-blue-500 animate-spin': item.status === 'uploading',
                      'text-gray-400': item.status === 'pending'
                    }"
                  />
                  <button
                    v-if="item.status !== 'uploading'"
                    @click="removeFile(index)"
                    class="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                  >
                    <Trash2 class="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="uploadProgress > 0 && uploadProgress < 100" class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-medium text-blue-700 dark:text-blue-300">正在上传...</span>
              <span class="text-sm text-blue-600 dark:text-blue-400">{{ uploadProgress }}%</span>
            </div>
            <div class="h-2 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
              <div
                class="h-full bg-blue-500 rounded-full transition-all"
                :style="{ width: `${uploadProgress}%` }"
              />
            </div>
          </div>
        </div>

        <div v-if="csvPreview.length > 0" class="space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-medium text-gray-900 dark:text-white flex items-center gap-2">
              <Table class="w-4 h-4" />
              导入预览
            </h3>
            <div class="flex items-center gap-4">
              <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <input
                  type="checkbox"
                  v-model="hasHeader"
                  class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                />
                包含表头
              </label>
              <div class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <span>分隔符:</span>
                <select
                  v-model="delimiter"
                  class="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                >
                  <option value=",">逗号 (,)</option>
                  <option value=";">分号 (;)</option>
                  <option value="\t">制表符 (Tab)</option>
                </select>
              </div>
            </div>
          </div>

          <div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th
                      v-for="(header, idx) in Object.keys(csvPreview[0])"
                      :key="idx"
                      class="px-4 py-3 text-left font-medium text-gray-700 dark:text-gray-300 border-b border-gray-200 dark:border-gray-600"
                    >
                      <div class="space-y-2">
                        <div class="flex items-center gap-2">
                          <Database class="w-3 h-3 text-gray-400" />
                          <span>{{ header }}</span>
                        </div>
                        <select
                          :value="fieldMapping[header]"
                          @change="updateFieldMapping(header, ($event.target as HTMLSelectElement).value)"
                          class="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                        >
                          <option value="">-- 忽略 --</option>
                          <option v-for="field in availableFields" :key="field.value" :value="field.value">
                            {{ field.label }}
                          </option>
                        </select>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                  <tr v-for="(row, idx) in csvPreview" :key="idx" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td
                      v-for="(value, key) in row"
                      :key="key"
                      class="px-4 py-3 text-gray-700 dark:text-gray-300 font-mono text-xs"
                    >
                      {{ String(value).slice(0, 50) }}{{ String(value).length > 50 ? '...' : '' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="px-4 py-3 bg-gray-50 dark:bg-gray-700 border-t border-gray-200 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2">
              <Info class="w-3 h-3" />
              显示前 {{ csvPreview.length }} 条数据预览
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button
            @click="fileList = []; selectedFile = null; csvPreview = []"
            class="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            :disabled="loading"
          >
            清空
          </button>
          <button
            @click="startCSVImport"
            class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
            :disabled="loading || fileList.length === 0"
          >
            <Play class="w-4 h-4" />
            {{ loading ? '导入中...' : '开始导入' }}
          </button>
        </div>
      </div>

      <div v-else class="p-6 space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              API 源
            </label>
            <select
              v-model="apiSource"
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="source in apiSources" :key="source.value" :value="source.value">
                {{ source.label }}
              </option>
            </select>
          </div>

          <div v-if="apiSource === 'custom'">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <span class="flex items-center gap-2">
                <Cloud class="w-4 h-4" />
                API 地址
              </span>
            </label>
            <input
              v-model="apiUrl"
              type="url"
              placeholder="https://api.example.com"
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              起始区块高度
            </label>
            <input
              v-model.number="startBlock"
              type="number"
              min="0"
              placeholder="例如: 830000"
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              结束区块高度
            </label>
            <input
              v-model.number="endBlock"
              type="number"
              min="0"
              placeholder="例如: 840000"
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            <span class="flex items-center gap-2">
              <Key class="w-4 h-4" />
              API 密钥 (可选)
            </span>
          </label>
          <input
            v-model="apiKey"
            type="password"
            placeholder="输入您的API密钥"
            class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            某些API需要密钥才能访问，没有密钥可能会有速率限制
          </p>
        </div>

        <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
          <div class="flex items-start gap-3">
            <Settings class="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 class="font-medium text-gray-900 dark:text-white">高级配置</h4>
              <div class="mt-3 space-y-4">
                <label class="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked
                    class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                  />
                  自动解析地址关联
                </label>
                <label class="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked
                    class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                  />
                  计算交易风险评分
                </label>
                <label class="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    class="w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
                  />
                  跳过已存在的交易
                </label>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button
            @click="apiSource = 'blockchain.info'; startBlock = null; endBlock = null; apiKey = ''; apiUrl = ''"
            class="px-6 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            :disabled="loading"
          >
            重置
          </button>
          <button
            @click="startAPIImport"
            class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
            :disabled="loading"
          >
            <CloudDownload class="w-4 h-4" />
            {{ loading ? '拉取中...' : '开始拉取' }}
          </button>
        </div>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <h3 class="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <History class="w-5 h-5" />
          历史导入记录
        </h3>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">类型</th>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">来源</th>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">记录数</th>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">状态</th>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">创建时间</th>
              <th class="px-6 py-3 text-left font-medium text-gray-700 dark:text-gray-300">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            <tr
              v-for="record in importHistory"
              :key="record.id"
              class="hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              <td class="px-6 py-4">
                <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium" :class="record.type === 'csv' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'">
                  <component :is="record.type === 'csv' ? FileText : Cloud" class="w-3 h-3" />
                  {{ record.type === 'csv' ? 'CSV' : 'API' }}
                </span>
              </td>
              <td class="px-6 py-4 text-gray-900 dark:text-white max-w-xs truncate">{{ record.source }}</td>
              <td class="px-6 py-4 text-gray-900 dark:text-white font-medium">{{ formatNumber(record.records) }}</td>
              <td class="px-6 py-4">
                <span
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
                  :class="TASK_STATUS[record.status as keyof typeof TASK_STATUS]?.bgColor || 'bg-gray-100',
                          TASK_STATUS[record.status as keyof typeof TASK_STATUS]?.textColor || 'text-gray-800'"
                >
                  <component
                    :is="TASK_STATUS[record.status as keyof typeof TASK_STATUS]?.status === 'completed' ? CheckCircle :
                         TASK_STATUS[record.status as keyof typeof TASK_STATUS]?.status === 'failed' ? AlertCircle : Loader"
                    class="w-3 h-3"
                  />
                  {{ TASK_STATUS[record.status as keyof typeof TASK_STATUS]?.label || record.status }}
                </span>
                <p v-if="record.error" class="text-xs text-red-500 mt-1">{{ record.error }}</p>
              </td>
              <td class="px-6 py-4 text-gray-500 dark:text-gray-400">{{ formatDate(record.createdAt, 'full') }}</td>
              <td class="px-6 py-4">
                <button
                  @click="navigateToTask(record.id)"
                  class="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 text-sm"
                >
                  详情
                  <ChevronRight class="w-4 h-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="importHistory.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
        <History class="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>暂无导入记录</p>
      </div>
    </div>
  </div>
</template>
