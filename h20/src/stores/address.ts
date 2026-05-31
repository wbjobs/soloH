import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Address, AddressListItem, GraphData, SuspiciousScore, PaginationParams } from '../types'
import { addressApi } from '../api'

export interface AddressFilters {
  minBalance?: number
  maxBalance?: number
  minTxCount?: number
  maxTxCount?: number
  minSuspiciousScore?: number
  addressType?: string
}

export const useAddressStore = defineStore('address', () => {
  const addresses = ref<AddressListItem[]>([])
  const currentAddress = ref<Address | null>(null)
  const addressSubgraph = ref<GraphData | null>(null)
  const suspiciousScore = ref<SuspiciousScore | null>(null)
  const filters = ref<AddressFilters>({})
  const pagination = ref<PaginationParams & { total: number; totalPages: number }>({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const searchQuery = ref('')

  const hasFilters = computed(() => Object.keys(filters.value).length > 0)

  async function fetchAddresses(params?: Partial<PaginationParams & AddressFilters>) {
    loading.value = true
    error.value = null
    try {
      const response = await addressApi.getAddresses({
        page: pagination.value.page,
        pageSize: pagination.value.pageSize,
        ...filters.value,
        ...params,
        search: searchQuery.value || undefined
      })
      addresses.value = response.data.items
      pagination.value = {
        page: response.data.page,
        pageSize: response.data.pageSize,
        total: response.data.total,
        totalPages: response.data.totalPages
      }
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取地址列表失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchAddressDetail(address: string) {
    loading.value = true
    error.value = null
    try {
      const response = await addressApi.getAddress(address)
      currentAddress.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取地址详情失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchAddressSubgraph(address: string, params?: {
    maxDepth?: number
    minValue?: number
    maxEdges?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await addressApi.getAddressSubgraph(address, params)
      addressSubgraph.value = response.data.graph
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取地址子图失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchSuspiciousScore(address: string) {
    loading.value = true
    error.value = null
    try {
      const response = await addressApi.getSuspiciousScore(address)
      suspiciousScore.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取风险评分失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function searchAddress(query: string) {
    searchQuery.value = query
    pagination.value.page = 1
    return fetchAddresses()
  }

  function setFilters(newFilters: AddressFilters) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.page = 1
  }

  function clearFilters() {
    filters.value = {}
    searchQuery.value = ''
    pagination.value.page = 1
  }

  function setPagination(params: Partial<PaginationParams>) {
    pagination.value = { ...pagination.value, ...params }
  }

  function clearCurrentAddress() {
    currentAddress.value = null
    suspiciousScore.value = null
    addressSubgraph.value = null
  }

  return {
    addresses,
    currentAddress,
    addressSubgraph,
    suspiciousScore,
    filters,
    pagination,
    loading,
    error,
    searchQuery,
    hasFilters,
    fetchAddresses,
    fetchAddressDetail,
    fetchAddressSubgraph,
    fetchSuspiciousScore,
    searchAddress,
    setFilters,
    clearFilters,
    setPagination,
    clearCurrentAddress
  }
})
