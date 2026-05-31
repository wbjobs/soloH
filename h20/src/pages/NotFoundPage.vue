<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Home, ArrowLeft, Search, AlertTriangle } from 'lucide-vue-next'

const router = useRouter()

function goHome() {
  router.push('/')
}

function goBack() {
  router.go(-1)
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
    <div class="text-center max-w-lg">
      <div class="relative mb-8">
        <div class="text-[120px] sm:text-[150px] font-bold text-gray-200 dark:text-gray-800 leading-none select-none">
          404
        </div>
        <div class="absolute inset-0 flex items-center justify-center">
          <div class="w-20 h-20 bg-gradient-to-br from-orange-400 to-red-500 rounded-2xl flex items-center justify-center shadow-lg shadow-red-500/25">
            <AlertTriangle class="w-10 h-10 text-white" />
          </div>
        </div>
      </div>

      <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-3">
        页面未找到
      </h1>
      <p class="text-gray-500 dark:text-gray-400 mb-8">
        抱歉，您访问的页面不存在或已被移除。请检查URL是否正确，或返回首页继续浏览。
      </p>

      <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
        <button
          @click="goBack"
          class="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          <ArrowLeft class="w-4 h-4" />
          返回上一页
        </button>
        <button
          @click="goHome"
          class="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors shadow-lg shadow-blue-500/25"
        >
          <Home class="w-4 h-4" />
          返回首页
        </button>
      </div>

      <div class="mt-12 p-6 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700">
        <div class="flex items-center gap-2 mb-4">
          <Search class="w-5 h-5 text-blue-500" />
          <h3 class="text-sm font-medium text-gray-900 dark:text-white">您可能在找：</h3>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <button
            @click="router.push('/dashboard')"
            class="p-3 text-left bg-gray-50 dark:bg-gray-700/50 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white">仪表盘</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">系统概览</p>
          </button>
          <button
            @click="router.push('/graph')"
            class="p-3 text-left bg-gray-50 dark:bg-gray-700/50 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white">交易图谱</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">关系可视化</p>
          </button>
          <button
            @click="router.push('/tasks')"
            class="p-3 text-left bg-gray-50 dark:bg-gray-700/50 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white">任务管理</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">查看任务状态</p>
          </button>
          <button
            @click="router.push('/import')"
            class="p-3 text-left bg-gray-50 dark:bg-gray-700/50 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white">数据导入</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">导入区块链数据</p>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
