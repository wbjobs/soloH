<script setup lang="ts">
import { AlertTriangle, Eye, Zap, GitBranch, RefreshCcw } from 'lucide-vue-next'
import type { SuspiciousPattern } from '../types'
import { formatTimestamp, formatHash } from '../utils/format'

interface Props {
  pattern: SuspiciousPattern
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view-detail', pattern: SuspiciousPattern): void
}>()

const getSeverityConfig = (severity: string) => {
  switch (severity) {
    case 'critical':
      return { label: '严重', bgColor: 'bg-red-500/20', textColor: 'text-red-400', borderColor: 'border-red-500/50' }
    case 'high':
      return { label: '高', bgColor: 'bg-orange-500/20', textColor: 'text-orange-400', borderColor: 'border-orange-500/50' }
    case 'medium':
      return { label: '中', bgColor: 'bg-yellow-500/20', textColor: 'text-yellow-400', borderColor: 'border-yellow-500/50' }
    default:
      return { label: '低', bgColor: 'bg-green-500/20', textColor: 'text-green-400', borderColor: 'border-green-500/50' }
  }
}

const getPatternIcon = (patternType: string) => {
  if (patternType.includes('mixer') || patternType.includes('混币')) return Zap
  if (patternType.includes('chain') || patternType.includes('链')) return GitBranch
  if (patternType.includes('wash') || patternType.includes('清洗')) return RefreshCcw
  return AlertTriangle
}

const severityConfig = getSeverityConfig(props.pattern.severity)
const PatternIcon = getPatternIcon(props.pattern.patternType)
</script>

<template>
  <div
    class="bg-slate-800/50 backdrop-blur-sm rounded-xl border transition-all duration-300 hover:shadow-xl hover:scale-[1.01] overflow-hidden"
    :class="[severityConfig.borderColor]"
  >
    <div class="p-4">
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-center gap-3">
          <div
            class="w-12 h-12 rounded-xl flex items-center justify-center"
            :class="[severityConfig.bgColor]"
          >
            <component :is="PatternIcon" class="w-6 h-6" :class="[severityConfig.textColor]" />
          </div>
          <div>
            <h4 class="font-semibold text-white">{{ pattern.name }}</h4>
            <p class="text-xs text-slate-400 mt-0.5">{{ pattern.patternType }}</p>
          </div>
        </div>
        <span
          class="px-2.5 py-1 rounded-full text-xs font-medium"
          :class="[severityConfig.bgColor, severityConfig.textColor]"
        >
          {{ severityConfig.label }}
        </span>
      </div>

      <p class="text-sm text-slate-400 mb-4 line-clamp-2">
        {{ pattern.description }}
      </p>

      <div class="mb-4">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs text-slate-500">置信度</span>
          <span class="text-xs font-medium" :class="[severityConfig.textColor]">{{ (pattern.confidence * 100).toFixed(1) }}%</span>
        </div>
        <div class="h-2 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="[severityConfig.textColor.replace('text', 'bg')]"
            :style="{ width: `${pattern.confidence * 100}%` }"
          ></div>
        </div>
      </div>

      <div class="space-y-2 mb-4">
        <div class="text-xs text-slate-500">检测证据</div>
        <div class="space-y-1">
          <div
            v-for="(addr, idx) in pattern.addresses.slice(0, 3)"
            :key="idx"
            class="flex items-center gap-2 text-xs"
          >
            <div class="w-1.5 h-1.5 rounded-full bg-cyan-500"></div>
            <span class="text-slate-400 font-mono truncate">{{ formatHash(addr, 16) }}</span>
          </div>
          <div v-if="pattern.addresses.length > 3" class="text-xs text-slate-500 pl-3.5">
            还有 {{ pattern.addresses.length - 3 }} 个地址...
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-3 border-t border-slate-700/50">
        <div class="flex items-center gap-4 text-xs text-slate-500">
          <span>{{ pattern.addresses.length }} 个地址</span>
          <span>{{ pattern.transactions.length }} 笔交易</span>
        </div>
        <button
          class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 text-xs font-medium hover:bg-cyan-500/20 transition-colors"
          @click="emit('view-detail', pattern)"
        >
          <Eye class="w-3 h-3" />
          查看详情
        </button>
      </div>
    </div>
  </div>
</template>
