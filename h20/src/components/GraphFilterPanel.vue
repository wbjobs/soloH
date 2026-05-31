<script setup lang="ts">
import { ref, watch } from 'vue'
import { SlidersHorizontal, RotateCcw, Calendar, DollarSign, Layers, Network } from 'lucide-vue-next'

export type LayoutType = 'force' | 'circular' | 'hierarchical'
export type NodeTypeFilter = 'all' | 'normal' | 'suspicious' | 'cluster'

interface Filters {
  minAmount: number
  timeRange: { start: string; end: string }
  nodeType: NodeTypeFilter
  layout: LayoutType
}

const emit = defineEmits<{
  (e: 'filter-change', filters: Filters): void
  (e: 'reset'): void
}>()

const props = defineProps<{
  expanded?: boolean
}>()

const isExpanded = ref(props.expanded ?? true)

const filters = ref<Filters>({
  minAmount: 0,
  timeRange: {
    start: '',
    end: ''
  },
  nodeType: 'all',
  layout: 'force'
})

const amountSlider = ref(0)

const layoutOptions: { value: LayoutType; label: string; icon: typeof Network }[] = [
  { value: 'force', label: '力导向', icon: Network },
  { value: 'circular', label: '环形', icon: Layers },
  { value: 'hierarchical', label: '层次', icon: Layers }
]

const nodeTypeOptions: { value: NodeTypeFilter; label: string; color: string }[] = [
  { value: 'all', label: '全部', color: 'bg-slate-500' },
  { value: 'normal', label: '正常', color: 'bg-green-500' },
  { value: 'suspicious', label: '可疑', color: 'bg-red-500' },
  { value: 'cluster', label: '聚类', color: 'bg-purple-500' }
]

watch(amountSlider, (newVal) => {
  filters.value.minAmount = newVal
  emitFilters()
}, { deep: true })

watch(filters, (newVal) => {
  emit('filter-change', newVal)
}, { deep: true })

const emitFilters = () => {
  emit('filter-change', { ...filters.value })
}

const resetFilters = () => {
  filters.value = {
    minAmount: 0,
    timeRange: { start: '', end: '' },
    nodeType: 'all',
    layout: 'force'
  }
  amountSlider.value = 0
  emit('reset')
}

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const formatAmount = (value: number) => {
  if (value >= 100000000) {
    return `${(value / 100000000).toFixed(1)} BTC`
  }
  return `${value.toLocaleString()} sats`
}
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
    <div
      class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors"
      @click="toggleExpand"
    >
      <div class="flex items-center gap-2">
        <SlidersHorizontal class="w-5 h-5 text-cyan-400" />
        <span class="font-medium text-white">图过滤</span>
      </div>
      <button class="p-1 text-slate-400 hover:text-slate-200 transition-colors">
        <RotateCcw
          class="w-4 h-4 transition-transform duration-300"
          :class="{ 'rotate-180': isExpanded }"
        />
      </button>
    </div>

    <Transition name="slide">
      <div v-if="isExpanded" class="px-4 pb-4 space-y-4">
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-sm text-slate-400 flex items-center gap-1">
              <DollarSign class="w-4 h-4" />
              金额阈值
            </label>
            <span class="text-sm font-mono text-cyan-400">{{ formatAmount(amountSlider) }}</span>
          </div>
          <input
            v-model="amountSlider"
            type="range"
            min="0"
            max="1000000000"
            step="10000"
            class="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <div class="flex justify-between text-xs text-slate-500">
            <span>0</span>
            <span>10 BTC</span>
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm text-slate-400 flex items-center gap-1">
            <Calendar class="w-4 h-4" />
            时间范围
          </label>
          <div class="grid grid-cols-2 gap-2">
            <input
              v-model="filters.timeRange.start"
              type="date"
              class="px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
            />
            <input
              v-model="filters.timeRange.end"
              type="date"
              class="px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm text-slate-400">节点类型</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="option in nodeTypeOptions"
              :key="option.value"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200"
              :class="[
                filters.nodeType === option.value
                  ? 'bg-cyan-500 text-white'
                  : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
              ]"
              @click="filters.nodeType = option.value"
            >
              <span :class="[option.color, 'w-2 h-2 rounded-full inline-block mr-1.5']"></span>
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm text-slate-400">布局方式</label>
          <div class="grid grid-cols-3 gap-2">
            <button
              v-for="option in layoutOptions"
              :key="option.value"
              class="flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-all duration-200"
              :class="[
                filters.layout === option.value
                  ? 'bg-cyan-500/20 border border-cyan-500/50 text-cyan-400'
                  : 'bg-slate-700/50 border border-transparent text-slate-300 hover:bg-slate-700'
              ]"
              @click="filters.layout = option.value"
            >
              <component :is="option.icon" class="w-4 h-4" />
              <span class="text-xs">{{ option.label }}</span>
            </button>
          </div>
        </div>

        <button
          class="w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
          @click.stop="resetFilters"
        >
          <RotateCcw class="w-4 h-4" />
          重置过滤器
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}

input[type="range"]::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #22d3ee;
  cursor: pointer;
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
}

input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #22d3ee;
  cursor: pointer;
  border: none;
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
}
</style>
