<script setup lang="ts">
import { ref } from 'vue'
import {
  Bell,
  Moon,
  Sun,
  User,
  LogOut,
  Settings,
  ChevronDown
} from 'lucide-vue-next'
import { useTheme } from '../composables/useTheme'

const { theme, toggleTheme, isDark } = useTheme()

const showNotifications = ref(false)
const showUserMenu = ref(false)

interface Notification {
  id: number
  title: string
  message: string
  type: 'info' | 'warning' | 'error'
  time: string
  read: boolean
}

const notifications = ref<Notification[]>([
  { id: 1, title: '新可疑模式', message: '检测到新的洗钱模式', type: 'warning', time: '5分钟前', read: false },
  { id: 2, title: '任务完成', message: '数据导入任务已完成', type: 'info', time: '1小时前', read: false },
  { id: 3, title: '高风险警报', message: '地址 bc1q... 风险评分达到95', type: 'error', time: '2小时前', read: true }
])

const unreadCount = () => notifications.value.filter(n => !n.read).length

const toggleNotifications = () => {
  showNotifications.value = !showNotifications.value
  showUserMenu.value = false
}

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
  showNotifications.value = false
}

const markAsRead = (id: number) => {
  const notification = notifications.value.find(n => n.id === id)
  if (notification) notification.read = true
}

const getNotificationColor = (type: string) => {
  switch (type) {
    case 'warning': return 'bg-amber-500'
    case 'error': return 'bg-red-500'
    default: return 'bg-cyan-500'
  }
}
</script>

<template>
  <header class="h-16 bg-slate-900/80 dark:bg-slate-950/80 backdrop-blur-md border-b border-slate-700/50 px-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
        <span class="text-white font-bold text-lg">B</span>
      </div>
      <div>
        <h1 class="text-lg font-bold text-white">比特币交易分析系统</h1>
        <p class="text-xs text-slate-400">Transaction Intelligence Platform</p>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <button
        class="relative p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-all duration-200"
        @click="toggleTheme"
      >
        <Sun v-if="isDark" class="w-5 h-5" />
        <Moon v-else class="w-5 h-5" />
      </button>

      <div class="relative">
        <button
          class="relative p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-all duration-200"
          @click="toggleNotifications"
        >
          <Bell class="w-5 h-5" />
          <span
            v-if="unreadCount() > 0"
            class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center"
          >
            {{ unreadCount() }}
          </span>
        </button>

        <Transition name="dropdown">
          <div
            v-if="showNotifications"
            class="absolute right-0 top-full mt-2 w-80 bg-slate-800 dark:bg-slate-900 rounded-lg border border-slate-700 shadow-xl z-50 overflow-hidden"
          >
            <div class="px-4 py-3 border-b border-slate-700">
              <h3 class="text-sm font-semibold text-white">通知</h3>
            </div>
            <div class="max-h-80 overflow-y-auto">
              <div
                v-for="notification in notifications"
                :key="notification.id"
                class="px-4 py-3 border-b border-slate-700/50 hover:bg-slate-700/30 cursor-pointer transition-colors"
                @click="markAsRead(notification.id)"
              >
                <div class="flex items-start gap-3">
                  <div :class="[getNotificationColor(notification.type), 'w-2 h-2 rounded-full mt-2 flex-shrink-0']"></div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                      <p class="text-sm font-medium text-white" :class="{ 'opacity-60': notification.read }">{{ notification.title }}</p>
                      <span class="text-xs text-slate-500 flex-shrink-0 ml-2">{{ notification.time }}</span>
                    </div>
                    <p class="text-xs text-slate-400 mt-1 truncate">{{ notification.message }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <div class="relative">
        <button
          class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-800 transition-all duration-200"
          @click="toggleUserMenu"
        >
          <div class="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <User class="w-4 h-4 text-white" />
          </div>
          <span class="text-sm text-slate-300 hidden sm:block">管理员</span>
          <ChevronDown class="w-4 h-4 text-slate-400" />
        </button>

        <Transition name="dropdown">
          <div
            v-if="showUserMenu"
            class="absolute right-0 top-full mt-2 w-48 bg-slate-800 dark:bg-slate-900 rounded-lg border border-slate-700 shadow-xl z-50 overflow-hidden"
          >
            <button class="w-full px-4 py-2.5 text-left text-sm text-slate-300 hover:bg-slate-700/50 flex items-center gap-2 transition-colors">
              <User class="w-4 h-4" />
              个人资料
            </button>
            <button class="w-full px-4 py-2.5 text-left text-sm text-slate-300 hover:bg-slate-700/50 flex items-center gap-2 transition-colors">
              <Settings class="w-4 h-4" />
              系统设置
            </button>
            <div class="border-t border-slate-700"></div>
            <button class="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2 transition-colors">
              <LogOut class="w-4 h-4" />
              退出登录
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
