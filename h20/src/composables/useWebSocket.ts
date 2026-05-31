import { ref, onUnmounted, type Ref } from 'vue'

export interface WebSocketMessage {
  type: string
  data?: unknown
  message?: string
  progress?: number
  timestamp: number
}

export interface WebSocketProgress {
  taskId: string
  progress: number
  message?: string
  status: string
}

export interface UseWebSocketOptions {
  url?: string
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
const DEFAULT_RECONNECT_INTERVAL = 3000
const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5
const DEFAULT_HEARTBEAT_INTERVAL = 30000

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    url: customUrl,
    reconnectInterval = DEFAULT_RECONNECT_INTERVAL,
    maxReconnectAttempts = DEFAULT_MAX_RECONNECT_ATTEMPTS,
    heartbeatInterval = DEFAULT_HEARTBEAT_INTERVAL
  } = options

  const ws: Ref<WebSocket | null> = ref(null)
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const reconnectAttempts = ref(0)
  const lastMessage = ref<WebSocketMessage | null>(null)
  const error = ref<string | null>(null)

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let messageCallbacks: Array<(message: WebSocketMessage) => void> = []
  let progressCallbacks: Array<(progress: WebSocketProgress) => void> = []
  let currentTaskId: string | null = null

  function buildUrl(taskId?: string): string {
    if (customUrl) {
      return taskId ? `${customUrl}/${taskId}` : customUrl
    }
    const baseUrl = WS_BASE_URL.replace(/^http/, 'ws')
    return taskId ? `${baseUrl}/ws/tasks/${taskId}` : `${baseUrl}/ws`
  }

  function clearTimers() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function startHeartbeat() {
    heartbeatTimer = setInterval(() => {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        ws.value.send(JSON.stringify({ type: 'ping' }))
      }
    }, heartbeatInterval)
  }

  function attemptReconnect(url: string) {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      error.value = `重连失败，已尝试 ${maxReconnectAttempts} 次`
      isConnecting.value = false
      return
    }

    reconnectAttempts.value++
    reconnectTimer = setTimeout(() => {
      connect(currentTaskId || undefined)
    }, reconnectInterval * reconnectAttempts.value)
  }

  function connect(taskId?: string) {
    disconnect()
    
    currentTaskId = taskId || null
    const url = buildUrl(taskId)
    
    isConnecting.value = true
    error.value = null

    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        isConnected.value = true
        isConnecting.value = false
        reconnectAttempts.value = 0
        startHeartbeat()
      }

      ws.value.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          lastMessage.value = message
          message.timestamp = Date.now()

          messageCallbacks.forEach(callback => callback(message))

          if (message.type === 'progress' && message.data) {
            const progress = message.data as WebSocketProgress
            progressCallbacks.forEach(callback => callback(progress))
          }

          if (message.type === 'error') {
            error.value = message.message || 'WebSocket 错误'
          }

          if (message.type === 'pong') {
          }
        } catch (e) {
          console.error('解析 WebSocket 消息失败:', e)
        }
      }

      ws.value.onerror = (event) => {
        console.error('WebSocket 错误:', event)
        error.value = 'WebSocket 连接错误'
        isConnected.value = false
        isConnecting.value = false
      }

      ws.value.onclose = (event) => {
        isConnected.value = false
        isConnecting.value = false
        clearTimers()

        if (event.code !== 1000) {
          attemptReconnect(url)
        }
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建 WebSocket 连接失败'
      isConnecting.value = false
    }
  }

  function disconnect() {
    clearTimers()
    
    if (ws.value) {
      if (ws.value.readyState === WebSocket.OPEN) {
        ws.value.close(1000, '正常关闭')
      }
      ws.value = null
    }
    
    isConnected.value = false
    isConnecting.value = false
    reconnectAttempts.value = 0
    currentTaskId = null
  }

  function send(data: unknown) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
      return true
    }
    return false
  }

  function onMessage(callback: (message: WebSocketMessage) => void) {
    messageCallbacks.push(callback)
    return () => {
      messageCallbacks = messageCallbacks.filter(cb => cb !== callback)
    }
  }

  function onProgress(callback: (progress: WebSocketProgress) => void) {
    progressCallbacks.push(callback)
    return () => {
      progressCallbacks = progressCallbacks.filter(cb => cb !== callback)
    }
  }

  function clearCallbacks() {
    messageCallbacks = []
    progressCallbacks = []
  }

  onUnmounted(() => {
    disconnect()
    clearCallbacks()
  })

  return {
    ws,
    isConnected,
    isConnecting,
    reconnectAttempts,
    lastMessage,
    error,
    connect,
    disconnect,
    send,
    onMessage,
    onProgress,
    clearCallbacks
  }
}
