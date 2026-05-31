import { get, post } from './client'
import type { ClusteringResult, SuspiciousPattern, SuspiciousScore, PaginatedResponse, ApiResponse, GNNAnomalyScoreRequest, GNNAnomalyScoreResponse, PrivacyCoinAnalysisRequest, PrivacyCoinAnalysisResponse, ComplianceReportRequest, ComplianceReportResponse } from '../types'

export interface GetClusteringResultsParams {
  algorithm?: string
  page?: number
  pageSize?: number
  minClusterSize?: number
  maxClusters?: number
}

export interface RunClusteringParams {
  algorithm: string
  minClusterSize?: number
  maxClusters?: number
  similarityThreshold?: number
  includeTransactions?: boolean
  startBlock?: number
  endBlock?: number
}

export interface GetSuspiciousPatternsParams {
  patternType?: string
  minSeverity?: string
  page?: number
  pageSize?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export interface AnalyzeAddressResult {
  address: string
  score: SuspiciousScore
  patterns: SuspiciousPattern[]
  relatedAddresses: string[]
  summary: string
}

export function getClusteringResults(params?: GetClusteringResultsParams): Promise<ApiResponse<ClusteringResult>> {
  return get<ApiResponse<ClusteringResult>>('/analysis/clusters', {
    params
  })
}

export function runClustering(params: RunClusteringParams): Promise<ApiResponse<ClusteringResult>> {
  return post<ApiResponse<ClusteringResult>>('/analysis/cluster', params)
}

export function getSuspiciousPatterns(params?: GetSuspiciousPatternsParams): Promise<ApiResponse<PaginatedResponse<SuspiciousPattern>>> {
  return get<ApiResponse<PaginatedResponse<SuspiciousPattern>>>('/analysis/patterns', {
    params
  })
}

export function analyzeAddress(address: string): Promise<ApiResponse<AnalyzeAddressResult>> {
  return post<ApiResponse<AnalyzeAddressResult>>(`/analysis/analyze/${address}`)
}

export function getPatternDetail(patternId: number | string): Promise<ApiResponse<SuspiciousPattern>> {
  return get<ApiResponse<SuspiciousPattern>>(`/analysis/patterns/${patternId}`)
}

export function calculateGNNAnomalyScore(params: GNNAnomalyScoreRequest): Promise<ApiResponse<GNNAnomalyScoreResponse>> {
  return post<ApiResponse<GNNAnomalyScoreResponse>>('/analysis/gnn/anomaly-score', params)
}

export function batchCalculateGNNScores(addresses: string[], depth?: number): Promise<ApiResponse<GNNAnomalyScoreResponse[]>> {
  return post<ApiResponse<GNNAnomalyScoreResponse[]>>('/analysis/gnn/batch-score', addresses, {
    params: { depth }
  })
}

export function analyzePrivacyCoinAssociations(params: PrivacyCoinAnalysisRequest): Promise<ApiResponse<PrivacyCoinAnalysisResponse>> {
  return post<ApiResponse<PrivacyCoinAnalysisResponse>>('/analysis/privacy/analyze', params)
}

export function batchAnalyzePrivacyAssociations(addresses: string[], depth?: number): Promise<ApiResponse<PrivacyCoinAnalysisResponse[]>> {
  return post<ApiResponse<PrivacyCoinAnalysisResponse[]>>('/analysis/privacy/batch-analyze', addresses, {
    params: { depth }
  })
}

export function generateComplianceReport(params: ComplianceReportRequest): Promise<Blob> {
  return post<Blob>('/analysis/report/generate', params, {
    responseType: 'blob'
  })
}

export function generateReportInfo(params: ComplianceReportRequest): Promise<ApiResponse<ComplianceReportResponse>> {
  return post<ApiResponse<ComplianceReportResponse>>('/analysis/report/generate/info', params)
}

export function batchGenerateReports(addresses: string[], format?: string): Promise<ApiResponse<any>> {
  return post<ApiResponse<any>>('/analysis/report/batch-generate', {
    addresses,
    format
  })
}
