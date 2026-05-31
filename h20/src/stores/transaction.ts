import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Transaction, TransactionListItem, GraphData, PaginationParams } from '../types'
import { transactionApi } from '../api'

export interface TransactionFilters {
  minValue?: number
  maxValue?: number
  startDate?: string
  endDate?: string
  minSuspiciousScore?: number
  address?: string
}

export const useTransactionStore = defineStore('transaction', () => {
  const transactions = ref<TransactionListItem[]>([])
  const currentTransaction = ref<Transaction | null>(null)
  const graphData = ref<GraphData | null>(null)
  const filters = ref<TransactionFilters>({})
  const pagination = ref<PaginationParams & { total: number; totalPages: number }>({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  const hasFilters = computed(() => Object.keys(filters.value).length > 0)

  async function fetchTransactions(params?: Partial<PaginationParams & TransactionFilters>) {
    loading.value = true
    error.value = null
    try {
      const response = await transactionApi.getTransactions({
        page: pagination.value.page,
        pageSize: pagination.value.pageSize,
        ...filters.value,
        ...params
      })
      transactions.value = response.data.items
      pagination.value = {
        page: response.data.page,
        pageSize: response.data.pageSize,
        total: response.data.total,
        totalPages: response.data.totalPages
      }
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取交易列表失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchTransactionDetail(txid: string) {
    loading.value = true
    error.value = null
    try {
      const response = await transactionApi.getTransaction(txid)
      currentTransaction.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取交易详情失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchGraphData(params?: {
    startTxId?: string
    maxDepth?: number
    minValue?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await transactionApi.getGraphData(params)
      graphData.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取图数据失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function setFilters(newFilters: TransactionFilters) {
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

  function clearCurrentTransaction() {
    currentTransaction.value = null
  }

  function clearGraphData() {
    graphData.value = null
  }

  return {
    transactions,
    currentTransaction,
    graphData,
    filters,
    pagination,
    loading,
    error,
    hasFilters,
    fetchTransactions,
    fetchTransactionDetail,
    fetchGraphData,
    setFilters,
    clearFilters,
    setPagination,
    clearCurrentTransaction,
    clearGraphData
  }
})
