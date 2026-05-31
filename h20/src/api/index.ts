export { apiClient, tryRealThenMock, mockApi } from './client'
export * as transactionApi from './transaction'
export * as addressApi from './address'
export * as analysisApi from './analysis'
export * as taskApi from './task'

export {
  calculateGNNAnomalyScore,
  batchCalculateGNNScores,
  analyzePrivacyCoinAssociations,
  batchAnalyzePrivacyAssociations,
  generateComplianceReport,
  generateReportInfo,
  batchGenerateReports
} from './analysis'

export type {
  GNNAnomalyScoreRequest,
  GNNAnomalyScoreResponse,
  PrivacyCoinAnalysisRequest,
  PrivacyCoinAnalysisResponse,
  ComplianceReportRequest,
  ComplianceReportResponse
} from '@/types'
