import { get, post } from './client'
import type { Transaction, TransactionListItem, GraphData, PaginatedResponse, ApiResponse } from '../types'

export interface GetTransactionsParams {
  page?: number
  pageSize?: number
  minValue?: number
  maxValue?: number
  startDate?: string
  endDate?: string
  minSuspiciousScore?: number
  address?: string
  sort?: string
  order?: 'asc' | 'desc'
  search?: string
}

export interface GetGraphDataParams {
  startTxId?: string
  startAddress?: string
  maxDepth?: number
  minValue?: number
  maxEdges?: number
  startBlock?: number
  endBlock?: number
}

export interface ImportFromAPIParams {
  source: string
  apiUrl: string
  apiKey?: string
  startBlock?: number
  endBlock?: number
  addresses?: string[]
}

export function getTransactions(params?: GetTransactionsParams): Promise<ApiResponse<PaginatedResponse<TransactionListItem>>> {
  return get<ApiResponse<PaginatedResponse<TransactionListItem>>>('/transactions', {
    params
  })
}

export function getTransaction(txid: string): Promise<ApiResponse<Transaction>> {
  return get<ApiResponse<Transaction>>(`/transactions/${txid}`)
}

export function getGraphData(params?: GetGraphDataParams): Promise<ApiResponse<GraphData>> {
  return get<ApiResponse<GraphData>>('/transactions/graph', {
    params
  })
}

export function importCSV(file: File): Promise<ApiResponse<{ taskId: string }>> {
  const formData = new FormData()
  formData.append('file', file)
  
  return post<ApiResponse<{ taskId: string }>>('/transactions/import/csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function importFromAPI(params: ImportFromAPIParams): Promise<ApiResponse<{ taskId: string }>> {
  return post<ApiResponse<{ taskId: string }>>('/transactions/import/api', params)
}
