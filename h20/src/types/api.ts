import type { PaginationParams } from './blockchain'

export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
  timestamp: number
}

export interface ApiError {
  success: boolean
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
  timestamp: number
}

export interface ApiListResponse<T> {
  success: boolean
  data: {
    items: T[]
    total: number
    page: number
    pageSize: number
    totalPages: number
  }
  message?: string
  timestamp: number
}

export interface SortParams {
  field: string
  order: 'asc' | 'desc'
}

export interface QueryParams extends PaginationParams {
  sort?: SortParams
  filter?: Record<string, unknown>
  search?: string
}
