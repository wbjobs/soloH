export interface GraphNode {
  id: string
  address: string
  value: number
  category: 'normal' | 'suspicious' | 'cluster'
  suspiciousScore?: number
  label?: string
  x?: number
  y?: number
  size?: number
  color?: string
  type?: string
  data?: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  value: number
  txid: string
  timestamp: Date | number
  label?: string
  type?: string
  color?: string
  width?: number
  id?: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  directed?: boolean
  metadata?: Record<string, unknown>
}

export interface SubgraphRequest {
  startAddress?: string
  startTxId?: string
  depth?: number
  minValue?: number
  maxEdges?: number
  includeAddresses?: string[]
  excludeAddresses?: string[]
  startTime?: Date
  endTime?: Date
}

export interface SubgraphResponse {
  graph: GraphData
  stats: Record<string, unknown>
  warnings?: string[]
}
