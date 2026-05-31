<script setup lang="ts">import { ref } from 'vue';
import { Play, XCircle, RotateCw, FileText, AlertCircle, CheckCircle, Loader, Clock } from 'lucide-vue-next';
import type { Task } from '../types';
import { formatTimestamp } from '../utils/format';
interface Props {
 task: Task;
}
const props = defineProps<Props>();
const emit = defineEmits<{
 (e: 'cancel', task: Task): void;
 (e: 'retry', task: Task): void;
 (e: 'view-log', task: Task): void;
}>();
const showError = ref(false);
const getStatusConfig = (status: string) => {
 switch (status) {
 case 'completed':
 return { label: '已完成', bgColor: 'bg-green-500/20', textColor: 'text-green-400', icon: CheckCircle };
 case 'processing':
 return { label: '运行中', bgColor: 'bg-cyan-500/20', textColor: 'text-cyan-400', icon: Loader };
 case 'pending':
 return { label: '等待中', bgColor: 'bg-yellow-500/20', textColor: 'text-yellow-400', icon: Clock };
 case 'failed':
 return { label: '失败', bgColor: 'bg-red-500/20', textColor: 'text-red-400', icon: XCircle };
 case 'cancelled':
 return { label: '已取消', bgColor: 'bg-slate-500/20', textColor: 'text-slate-400', icon: XCircle };
 default:
 return { label: '未知', bgColor: 'bg-slate-500/20', textColor: 'text-slate-400', icon: AlertCircle };
 }
};
const getTypeLabel = (type: string) => {
 const typeMap: Record<string, string> = {
 'import_csv': 'CSV导入',
 'import_api': 'API导入',
 'sync_blockchain': '区块链同步',
 'analyze_address': '地址分析',
 'analyze_transaction': '交易分析',
 'cluster_addresses': '地址聚类',
 'build_graph': '图构建',
 'export_data': '数据导出'
 };
 return typeMap[type] || type;
};
const statusConfig = getStatusConfig(props.task.status);
const StatusIcon = statusConfig.icon;
</script>

<template>
  <div
    class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 transition-all duration-300 hover:shadow-xl overflow-hidden"
  >
    <div class="p-4">
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-center gap-3">
          <div
            class="w-12 h-12 rounded-xl flex items-center justify-center"
            :class="[statusConfig.bgColor]"
          >
            <component
              :is="StatusIcon"
              class="w-6 h-6"
              :class="[statusConfig.textColor, task.status === 'processing' ? 'animate-spin' : '']"
            />
          </div>
          <div>
            <h4 class="font-semibold text-white">{{ task.name || getTypeLabel(task.type) }}</h4>
            <div class="flex items-center gap-2 mt-0.5">
              <span
                class="px-2 py-0.5 rounded text-xs font-medium"
                :class="[statusConfig.bgColor, statusConfig.textColor]"
              >
                {{ statusConfig.label }}
              </span>
              <span class="text-xs text-slate-500">{{ getTypeLabel(task.type) }}</span>
            </div>
          </div>
        </div>
      </div>

      <p v-if="task.description" class="text-sm text-slate-400 mb-3 line-clamp-2">
        {{ task.description }}
      </p>

      <div v-if="task.status === 'processing' || task.progress > 0" class="mb-3">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs text-slate-500">进度</span>
          <span class="text-xs font-medium text-cyan-400">{{ task.progress.toFixed(0) }}%</span>
        </div>
        <div class="h-2 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500 relative"
            :class="[
              task.status === 'failed' ? 'bg-red-500' :
              task.status === 'completed' ? 'bg-green-500' :
              'bg-gradient-to-r from-cyan-500 to-blue-500'
            ]"
            :style="{ width: `${task.progress}%` }"
          >
            <div
              v-if="task.status === 'processing'"
              class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-pulse"
            ></div>
          </div>
        </div>
        <p v-if="task.message" class="text-xs text-slate-400 mt-2 truncate">
          {{ task.message }}
        </p>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-3 text-xs">
        <div>
          <p class="text-slate-500 mb-0.5">开始时间</p>
          <p class="text-slate-300 font-mono">{{ task.startedAt ? formatTimestamp(task.startedAt, 'date') : '-' }}</p>
        </div>
        <div>
          <p class="text-slate-500 mb-0.5">结束时间</p>
          <p class="text-slate-300 font-mono">{{ task.completedAt ? formatTimestamp(task.completedAt, 'date') : '-' }}</p>
        </div>
      </div>

      <Transition name="slide-down">
        <div v-if="task.error && showError" class="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <div class="flex items-start gap-2">
            <AlertCircle class="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p class="text-xs text-red-400">{{ task.error }}</p>
          </div>
        </div>
      </Transition>

      <div class="flex items-center justify-between pt-3 border-t border-slate-700/50">
        <div class="text-xs text-slate-500">
          创建: {{ formatTimestamp(task.createdAt, 'relative') }}
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="task.error"
            class="flex items-center gap-1 px-2 py-1.5 rounded text-xs text-red-400 hover:bg-red-500/10 transition-colors"
            @click="showError = !showError"
          >
            <AlertCircle class="w-3 h-3" />
            {{ showError ? '隐藏错误' : '查看错误' }}
          </button>
          <button
            class="flex items-center gap-1 px-2 py-1.5 rounded text-xs text-slate-400 hover:bg-slate-700 transition-colors"
            @click="emit('view-log', task)"
          >
            <FileText class="w-3 h-3" />
            日志
          </button>
          <button
            v-if="task.status === 'failed'"
            class="flex items-center gap-1 px-2 py-1.5 rounded text-xs text-cyan-400 hover:bg-cyan-500/10 transition-colors"
            @click="emit('retry', task)"
          >
            <RotateCw class="w-3 h-3" />
            重试
          </button>
          <button
            v-if="task.status === 'processing' || task.status === 'pending'"
            class="flex items-center gap-1 px-2 py-1.5 rounded text-xs text-red-400 hover:bg-red-500/10 transition-colors"
            @click="emit('cancel', task)"
          >
            <XCircle class="w-3 h-3" />
            取消
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
