import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Task, TaskListItem, TaskLog, PaginationParams, TaskCreate } from '../types'
import { taskApi } from '../api'

export interface TaskFilters {
  status?: string
  type?: string
  startDate?: string
  endDate?: string
}

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<TaskListItem[]>([])
  const currentTask = ref<Task | null>(null)
  const taskLogs = ref<TaskLog[]>([])
  const filters = ref<TaskFilters>({})
  const pagination = ref<PaginationParams & { total: number; totalPages: number }>({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  const hasFilters = computed(() => Object.keys(filters.value).length > 0)

  const runningTasks = computed(() => 
    tasks.value.filter(t => t.status === 'processing')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  const failedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'failed')
  )

  async function fetchTasks(params?: Partial<PaginationParams & TaskFilters>) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.getTasks({
        page: pagination.value.page,
        pageSize: pagination.value.pageSize,
        ...filters.value,
        ...params
      })
      tasks.value = response.data.items
      pagination.value = {
        page: response.data.page,
        pageSize: response.data.pageSize,
        total: response.data.total,
        totalPages: response.data.totalPages
      }
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取任务列表失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchTaskDetail(taskId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.getTask(taskId)
      currentTask.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取任务详情失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchTaskLogs(taskId: string, params?: { page?: number; pageSize?: number }) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.getTaskLogs(taskId, params)
      taskLogs.value = response.data.items
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取任务日志失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createTask(taskData: TaskCreate) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.createTask(taskData)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建任务失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function retryTask(taskId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.retryTask(taskId)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '重试任务失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function cancelTask(taskId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await taskApi.cancelTask(taskId)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '取消任务失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function setFilters(newFilters: TaskFilters) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.page = 1
  }

  function clearFilters() {
    filters.value = {}
    pagination.value.page = 1
  }

  function setPagination(params: Partial<PaginationParams>) {
    pagination.value = { ...pagination.value, ...params }
  }

  function clearCurrentTask() {
    currentTask.value = null
    taskLogs.value = []
  }

  function updateTaskProgress(taskId: string, progress: number, message?: string) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = progress
      if (message) {
        task.message = message
      }
    }
    if (currentTask.value && currentTask.value.id === taskId) {
      currentTask.value.progress = progress
      if (message) {
        currentTask.value.message = message
      }
    }
  }

  function addTaskLog(log: TaskLog) {
    taskLogs.value.push(log)
  }

  return {
    tasks,
    currentTask,
    taskLogs,
    filters,
    pagination,
    loading,
    error,
    hasFilters,
    runningTasks,
    completedTasks,
    failedTasks,
    fetchTasks,
    fetchTaskDetail,
    fetchTaskLogs,
    createTask,
    retryTask,
    cancelTask,
    setFilters,
    clearFilters,
    setPagination,
    clearCurrentTask,
    updateTaskProgress,
    addTaskLog
  }
})
