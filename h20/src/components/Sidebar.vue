<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  GitBranch,
  MapPin,
  Database,
  ListTodo,
  Layers,
  ChevronLeft,
  ChevronRight,
  Brain,
  Shield,
  FileText
} from 'lucide-vue-next'

interface MenuItem {
  path: string
  label: string
  icon: typeof LayoutDashboard
}

const props = defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-collapse'): void
}>()

const route = useRoute()
const router = useRouter()

const menuItems: MenuItem[] = [
  { path: '/dashboard', label: '仪表盘', icon: LayoutDashboard },
  { path: '/transactions', label: '交易图', icon: GitBranch },
  { path: '/addresses', label: '地址分析', icon: MapPin },
  { path: '/import', label: '数据导入', icon: Database },
  { path: '/tasks', label: '任务管理', icon: ListTodo },
  { path: '/clustering', label: '聚类分析', icon: Layers },
  { path: '/gnn-analysis', label: 'GNN异常评分', icon: Brain },
  { path: '/privacy-analysis', label: '隐私币分析', icon: Shield },
  { path: '/compliance-report', label: '合规报告', icon: FileText }
]

const isActive = (path: string) => {
  return route.path.startsWith(path)
}

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <aside
    class="h-full bg-slate-900 dark:bg-slate-950 border-r border-slate-700/50 flex flex-col transition-all duration-300 ease-in-out"
    :class="[
      collapsed ? 'w-16' : 'w-64'
    ]"
  >
    <div class="flex-1 py-4 overflow-y-auto">
      <nav class="space-y-1 px-2">
        <div
          v-for="item in menuItems"
          :key="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200 group"
          :class="[
            isActive(item.path)
              ? 'bg-gradient-to-r from-cyan-500/20 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border border-transparent'
          ]"
          @click="navigateTo(item.path)"
        >
          <component
            :is="item.icon"
            class="w-5 h-5 flex-shrink-0 transition-transform duration-200"
            :class="[isActive(item.path) ? 'text-cyan-400' : 'group-hover:scale-110']"
          />
          <span
            class="text-sm font-medium whitespace-nowrap transition-all duration-200"
            :class="[collapsed ? 'opacity-0 w-0 overflow-hidden' : 'opacity-100']"
          >
            {{ item.label }}
          </span>
        </div>
      </nav>
    </div>

    <div class="p-3 border-t border-slate-700/50">
      <button
        class="w-full flex items-center justify-center p-2 rounded-lg text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 transition-all duration-200"
        @click="emit('toggle-collapse')"
      >
        <ChevronLeft v-if="!collapsed" class="w-5 h-5" />
        <ChevronRight v-else class="w-5 h-5" />
        <span
          v-if="!collapsed" class="ml-2 text-sm">收起</span>
      </button>
    </div>
  </aside>
</template>
