<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { AlertTriangle, AlertCircle, Info, X, Bell } from 'lucide-vue-next'

interface Props {
  type?: 'info' | 'warning' | 'error' | 'critical'
  title: string
  message?: string
  autoClose?: boolean
  autoCloseDelay?: number
  showClose?: boolean
  showIcon?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  autoClose: false,
  autoCloseDelay: 5000,
  showClose: true,
  showIcon: true
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'action'): void
}>()

const isVisible = ref(true)
const isLeaving = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const getConfig = (type: string) => {
  switch (type) {
    case 'critical':
      return {
        bgColor: 'bg-gradient-to-r from-red-600/90 to-red-700/90',
        borderColor: 'border-red-500',
        textColor: 'text-white',
        icon: AlertTriangle,
        pulse: true
      }
    case 'error':
      return {
        bgColor: 'bg-red-500/20',
        borderColor: 'border-red-500/50',
        textColor: 'text-red-400',
        icon: AlertCircle,
        pulse: false
      }
    case 'warning':
      return {
        bgColor: 'bg-yellow-500/20',
        borderColor: 'border-yellow-500/50',
        textColor: 'text-yellow-400',
        icon: AlertTriangle,
        pulse: false
      }
    case 'info':
    default:
      return {
        bgColor: 'bg-cyan-500/20',
        borderColor: 'border-cyan-500/50',
        textColor: 'text-cyan-400',
        icon: Info,
        pulse: false
      }
  }
}

const config = getConfig(props.type)

const close = () => {
  isLeaving.value = true
  setTimeout(() => {
    isVisible.value = false
    emit('close')
  }, 300)
}

const startAutoClose = () => {
  if (props.autoClose) {
    timer = setTimeout(() => {
      close()
    }, props.autoCloseDelay)
  }
}

const stopAutoClose = () => {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

watch(() => props.autoClose, (newVal) => {
  if (newVal) {
    startAutoClose()
  } else {
    stopAutoClose()
  }
})

onMounted(() => {
  startAutoClose()
})

onUnmounted(() => {
  stopAutoClose()
})
</script>

<template>
  <Transition name="alert">
    <div
      v-if="isVisible"
      class="relative overflow-hidden rounded-xl border backdrop-blur-sm transition-all duration-300"
      :class="[
        config.bgColor,
        config.borderColor,
        isLeaving ? 'opacity-0 scale-95' : 'opacity-100 scale-100'
      ]"
      @mouseenter="stopAutoClose"
      @mouseleave="startAutoClose"
    >
      <div
        v-if="config.pulse"
        class="absolute inset-0 animate-pulse"
        style="background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent); animation: shimmer 2s infinite;"
      ></div>

      <div class="relative z-10 p-4">
        <div class="flex items-start gap-3">
          <div
            v-if="showIcon"
            class="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
            :class="[props.type === 'critical' ? 'bg-white/20' : 'bg-current/10']"
            :style="{ color: props.type === 'critical' ? 'white' : undefined }"
          >
            <component
              :is="config.icon"
              class="w-5 h-5"
              :class="[config.pulse ? 'animate-bounce text-white' : config.textColor]"
            />
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <Bell
                v-if="props.type === 'critical'"
                class="w-4 h-4 text-white/80 animate-ping"
              />
              <h4
                class="font-semibold"
                :class="[props.type === 'critical' ? 'text-white' : config.textColor]"
              >
                {{ title }}
              </h4>
            </div>
            <p
              v-if="message"
              class="text-sm mt-1"
              :class="[props.type === 'critical' ? 'text-white/80' : 'text-slate-400']"
            >
              {{ message }}
            </p>

            <div class="flex items-center gap-3 mt-3">
              <button
                class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
                :class="[
                  props.type === 'critical'
                    ? 'bg-white/20 text-white hover:bg-white/30'
                    : 'bg-current/10 hover:bg-current/20',
                  config.textColor
                ]"
                :style="{ color: props.type === 'critical' ? 'white' : undefined }"
                @click="emit('action')"
              >
                立即处理
              </button>
              <button
                v-if="props.type !== 'critical'"
                class="text-sm text-slate-500 hover:text-slate-300 transition-colors"
                @click="close"
              >
                稍后提醒
              </button>
            </div>
          </div>

          <button
            v-if="showClose && props.type !== 'critical'"
            class="flex-shrink-0 p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            :class="[config.textColor]"
            @click="close"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        v-if="autoClose"
        class="absolute bottom-0 left-0 h-1 bg-current/30 animate-shrink"
        :class="[config.textColor]"
        :style="{ animationDuration: `${autoCloseDelay}ms` }"
      ></div>
    </div>
  </Transition>
</template>

<style scoped>
.alert-enter-active,
.alert-leave-active {
  transition: all 0.3s ease;
}

.alert-enter-from {
  opacity: 0;
  transform: translateY(-20px) scale(0.95);
}

.alert-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes shrink {
  from { width: 100%; }
  to { width: 0%; }
}

.animate-shrink {
  animation: shrink linear forwards;
}
</style>
