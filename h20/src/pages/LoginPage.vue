<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Eye, EyeOff, Loader, Shield, AlertCircle } from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const appStore = useAppStore()

const username = ref('')
const password = ref('')
const rememberMe = ref(false)
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')

function togglePassword() {
  showPassword.value = !showPassword.value
}

async function handleLogin() {
  if (!username.value.trim()) {
    error.value = '请输入用户名'
    return
  }
  if (!password.value.trim()) {
    error.value = '请输入密码'
    return
  }

  error.value = ''
  loading.value = true

  await new Promise(resolve => setTimeout(resolve, 1500))

  if (username.value === 'admin' && password.value === 'admin123') {
    localStorage.setItem('auth_token', 'mock_token_' + Date.now())
    if (rememberMe.value) {
      localStorage.setItem('remember_username', username.value)
    } else {
      localStorage.removeItem('remember_username')
    }
    
    appStore.addNotification({
      type: 'success',
      message: '登录成功！'
    })
    
    router.push('/dashboard')
  } else {
    error.value = '用户名或密码错误'
  }

  loading.value = false
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    handleLogin()
  }
}

onMounted(() => {
  const savedUsername = localStorage.getItem('remember_username')
  if (savedUsername) {
    username.value = savedUsername
    rememberMe.value = true
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
    <div class="absolute inset-0">
      <div class="absolute inset-0 bg-gradient-to-br from-slate-950 via-blue-950/20 to-slate-950" />
      <div 
        class="absolute inset-0 opacity-30"
        style="
          background-image: 
            linear-gradient(rgba(59, 130, 246, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59, 130, 246, 0.1) 1px, transparent 1px);
          background-size: 50px 50px;
        "
      />
      <div class="absolute top-1/4 -left-20 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
      <div class="absolute bottom-1/4 -right-20 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-3xl" />
    </div>

    <div class="relative w-full max-w-md">
      <div class="bg-slate-900/80 backdrop-blur-xl rounded-2xl border border-slate-800 shadow-2xl p-8">
        <div class="text-center mb-8">
          <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/25">
            <Shield class="w-8 h-8 text-white" />
          </div>
          <h1 class="text-2xl font-bold text-white mb-2">区块链交易分析系统</h1>
          <p class="text-slate-400 text-sm">请登录以访问系统</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">用户名</label>
            <input
              v-model="username"
              type="text"
              placeholder="请输入用户名"
              class="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              @keydown="handleKeydown"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">密码</label>
            <div class="relative">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                class="w-full px-4 py-3 pr-12 bg-slate-800/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                @keydown="handleKeydown"
              />
              <button
                type="button"
                @click="togglePassword"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300 transition-colors"
              >
                <component :is="showPassword ? EyeOff : Eye" class="w-5 h-5" />
              </button>
            </div>
          </div>

          <div v-if="error" class="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
            <AlertCircle class="w-4 h-4 flex-shrink-0" />
            <span>{{ error }}</span>
          </div>

          <div class="flex items-center justify-between">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="rememberMe"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
              />
              <span class="text-sm text-slate-400">记住我</span>
            </label>
            <button type="button" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">
              忘记密码？
            </button>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-blue-800 disabled:to-purple-800 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-all duration-300 shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 flex items-center justify-center gap-2"
          >
            <Loader v-if="loading" class="w-5 h-5 animate-spin" />
            <span>{{ loading ? '登录中...' : '登 录' }}</span>
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-slate-800">
          <div class="text-center text-sm text-slate-500">
            <p>测试账号: <span class="text-slate-400 font-mono">admin / admin123</span></p>
          </div>
        </div>
      </div>

      <p class="text-center text-slate-600 text-xs mt-6">
        © 2024 区块链交易分析系统. 安全、专业、高效
      </p>
    </div>
  </div>
</template>
