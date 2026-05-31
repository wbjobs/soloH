import { get, post } from './client'
import type { Task, TaskListItem, TaskLog, PaginatedResponse, ApiResponse, TaskCreate } from '../types'

export interface GetTasksParams {
  page?: number
  pageSize?: number
  status?: string
  type?: string
  startDate?: string
  endDate?: string
  sort?: string
  order?: 'asc' | 'desc'
}

export interface GetTaskLogsParams {
  page?: number
  pageSize?: number
  level?: string
}

export function getTasks(params?: GetTasksParams): Promise<ApiResponse<PaginatedResponse<TaskListItem>>> {
  return get<ApiResponse<PaginatedResponse<TaskListItem>>>('/tasks', {
    params
  })
}

export function getTask(taskId: string): Promise<ApiResponse<Task>> {
  return get<ApiResponse<Task>>(`/tasks/${taskId}`)
}

export function getTaskLogs(
  taskId: string,
  params?: GetTaskLogsParams
): Promise<ApiResponse<PaginatedResponse<TaskLog>>> {
  return get<ApiResponse<PaginatedResponse<TaskLog>>>(`/tasks/${taskId}/logs`, {
    params
  })
}

export function createTask(taskData: TaskCreate): Promise<ApiResponse<Task>> {
  return post<ApiResponse<Task>>('/tasks', taskData)
}

export function retryTask(taskId: string): Promise<ApiResponse<Task>> {
  return post<ApiResponse<Task>>(`/tasks/${taskId}/retry`)
}

export function cancelTask(taskId: string): Promise<ApiResponse<Task>> {
  return post<ApiResponse<Task>>(`/tasks/${taskId}/cancel`)
}
