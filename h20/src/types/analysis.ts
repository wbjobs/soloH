export interface RiskFactor {
  name: string
  score: number
  weight: number
  description: string
  evidence?: Record<string, unknown>
}

export interface SuspiciousScore {
  address: string
  overallScore: number
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  factors: {
    layeringScore: number
    mixingScore: number
    structuringScore: number
    cycleScore: number
    suddenChangeScore: number
  }
  relatedPatterns: SuspiciousPattern[]
}

export interface SuspiciousPattern {
  id: number
  type: 'layering' | 'cycle' | 'structuring' | 'mixing'
  patternType?: string
  name?: string
  confidence: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  description: string
  evidence: string[]
  detectedAt: Date
  address?: string
  txid?: string
  addresses?: string[]
  transactions?: string[]
  firstSeen?: Date
  lastSeen?: Date
}

export interface AddressCluster {
  clusterId: string
  name?: string
  size: number
  addresses: string[]
  totalValue?: number
  totalReceived?: number
  totalSent?: number
  balance?: number
  txCount?: number
  avgSuspiciousScore?: number
  heuristic?: 'common-input' | 'change-address' | 'combined'
  confidence?: number
  tags?: string[]
  createdAt?: Date
  firstSeen?: Date
  lastSeen?: Date
}

export interface ClusteringResult {
  id?: number
  algorithm: string
  parameters: Record<string, unknown>
  clusterCount: number
  addressCount: number
  clusters: AddressCluster[]
  createdAt?: Date
}

export interface GNNAnomalyScoreRequest {
  address: string
  depth?: number
}

export interface GNNAnomalyScoreResponse {
  address: string
  anomalyScore: number
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  features: Record<string, number>
  featureImportance: Record<string, number>
  subgraphSize: {
    nodes: number
    edges: number
  }
  analysisDepth: number
  explanations: Array<{
    type: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    description: string
    contribution: number
  }>
}

export interface PrivacyCoinAnalysisRequest {
  address: string
  depth?: number
}

export interface PrivacyCoinAnalysisResponse {
  address: string
  overallRiskScore: number
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  detectedPrivacyCoins: Record<string, Array<{
    address: string
    coinName: string
    description: string
    riskLevel: string
  }>>
  privacyCoinCount: number
  associatedAddressCount: number
  suspiciousTransactions: Array<{
    txid: string
    fromAddress: string
    toAddress: string
    value: number
    timestamp: number
    privacyType?: string
    direction: 'incoming' | 'outgoing'
    gatewayInfo?: {
      gatewayId: string
      name: string
      type: string
      riskLevel: string
    }
  }>
  totalPrivacyRelatedValue: number
  mixingPatterns: Array<{
    type: string
    description: string
    confidence: number
    evidence: Record<string, unknown>
  }>
  crossChainLinks: Array<{
    type: 'privacy_coin' | 'privacy_gateway'
    privacyType?: string
    coinName?: string
    address?: string
    description?: string
    riskLevel?: string
    transactionCount?: number
    totalValue?: number
    gatewayName?: string
    gatewayType?: string
    transaction?: {
      txid: string
      from: string
      to: string
      value: number
    }
  }>
  analysisDepth: number
  analysisTimestamp: string
  threatIntelligence?: {
    threatLevel: string
    threatIndicators: Array<{
      type: string
      description: string
      severity: string
    }>
    recommendedActions: string[]
    summary: string
  }
}

export interface ComplianceReportRequest {
  address: string
  format?: 'pdf' | 'json'
  includeVisualizations?: boolean
}

export interface ComplianceReportResponse {
  address: string
  reportType: string
  format: string
  generatedAt: string
  fileSize?: number
  filename?: string
  downloadUrl?: string
  summary?: {
    overallRiskScore: number
    riskLevel: string
    gnnAnomalyScore: number
    privacyRiskScore: number
    suspiciousPatternCount: number
    privacyCoinAssociations: number
    reportDate: string
    analysisPeriod: string
  }
}

export interface BatchReportRequest {
  addresses: string[]
  format?: 'pdf' | 'json'
}
