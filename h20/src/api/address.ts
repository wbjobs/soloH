import { get } from './client'
import type { Address, AddressListItem, SuspiciousScore, TransactionListItem, PaginatedResponse, ApiResponse, SubgraphResponse } from '../types'

export interface GetAddressesParams {
  page?: number
  pageSize?: number
  minBalance?: number
  maxBalance?: number
  minTxCount?: number
  maxTxCount?: number
  minSuspiciousScore?: number
  addressType?: string
  sort?: string
  order?: 'asc' | 'desc'
  search?: string
}

export interface GetAddressSubgraphParams {
  maxDepth?: number
  minValue?: number
  maxEdges?: number
  includeAddresses?: string[]
  excludeAddresses?: string[]
  startBlock?: number
  endBlock?: number
}

export interface GetAddressTransactionsParams {
  page?: number
  pageSize?: number
  minValue?: number
  maxValue?: number
  startDate?: string
  endDate?: string
}

export function getAddresses(params?: GetAddressesParams): Promise<ApiResponse<PaginatedResponse<AddressListItem>>> {
  return get<ApiResponse<PaginatedResponse<AddressListItem>>>('/addresses', {
    params
  })
}

export function getAddress(address: string): Promise<ApiResponse<Address>> {
  return get<ApiResponse<Address>>(`/addresses/${address}`)
}

export function getAddressSubgraph(
  address: string,
  params?: GetAddressSubgraphParams
): Promise<ApiResponse<SubgraphResponse>> {
  return get<ApiResponse<SubgraphResponse>>(`/addresses/${address}/subgraph`, {
    params
  })
}

export function getSuspiciousScore(address: string): Promise<ApiResponse<SuspiciousScore>> {
  return get<ApiResponse<SuspiciousScore>>(`/addresses/${address}/suspicious-score`)
}

export function getAddressTransactions(
  address: string,
  params?: GetAddressTransactionsParams
): Promise<ApiResponse<PaginatedResponse<TransactionListItem>>> {
  return get<ApiResponse<PaginatedResponse<TransactionListItem>>>(`/addresses/${address}/transactions`, {
    params
  })
}

export function getTopAddresses(limit: number = 10): Promise<ApiResponse<AddressListItem[]>> {
  return get<ApiResponse<AddressListItem[]>>('/addresses/top', {
    params: { limit }
  })
}
