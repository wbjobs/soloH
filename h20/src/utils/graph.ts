import type { GraphData, GraphNode, GraphEdge } from '../types'
import { NODE_CATEGORIES, RISK_LEVELS, type NodeCategory } from './constants'
import { formatBTC } from './format'

export interface BackendGraphNode {
  id: string
  type: 'address' | 'transaction'
  label?: string
  value?: number
  category?: string
  suspiciousScore?: number
  metadata?: Record<string, unknown>
}

export interface BackendGraphEdge {
  id: string
  source: string
  target: string
  value?: number
  type?: string
  timestamp?: number
  metadata?: Record<string, unknown>
}

export interface BackendGraphData {
  nodes: BackendGraphNode[]
  edges: BackendGraphEdge[]
  directed?: boolean
  metadata?: Record<string, unknown>
}

export interface GraphFilters {
  minNodeValue?: number
  maxNodeValue?: number
  minEdgeValue?: number
  maxEdgeValue?: number
  nodeCategories?: string[]
  minSuspiciousScore?: number
  maxSuspiciousScore?: number
  startTimestamp?: number
  endTimestamp?: number
}

export function transformGraphData(backendData: BackendGraphData): GraphData {
  const nodes: GraphNode[] = backendData.nodes.map(node => ({
    id: node.id,
    address: node.id,
    value: node.value || 0,
    category: (node.category === 'suspicious' || node.category === 'cluster' ? node.category : 'normal') as 'normal' | 'suspicious' | 'cluster',
    label: node.label || node.id,
    type: node.type,
    data: node.metadata,
    size: node.value ? calculateNodeSize(node.value) : undefined,
    color: node.category || node.suspiciousScore !== undefined
      ? getNodeColor(node.category as NodeCategory, node.suspiciousScore)
      : undefined,
    suspiciousScore: node.suspiciousScore
  }))

  const edges: GraphEdge[] = backendData.edges.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    value: edge.value || 0,
    txid: edge.id,
    type: edge.type,
    timestamp: edge.timestamp || Date.now(),
    data: edge.metadata,
    width: edge.value ? calculateEdgeWidth(edge.value) : undefined
  }))

  return {
    nodes,
    edges,
    directed: backendData.directed ?? true,
    metadata: backendData.metadata
  }
}

export function applyGraphFilters(
  graphData: GraphData,
  filters: GraphFilters
): GraphData {
  const filteredNodeIds = new Set<string>()

  const filteredNodes = graphData.nodes.filter(node => {
    if (filters.minNodeValue !== undefined && node.size !== undefined) {
      if (node.size < filters.minNodeValue) return false
    }
    if (filters.maxNodeValue !== undefined && node.size !== undefined) {
      if (node.size > filters.maxNodeValue) return false
    }
    if (filters.nodeCategories !== undefined && filters.nodeCategories.length > 0) {
      const category = node.data?.category as string | undefined
      if (!category || !filters.nodeCategories.includes(category)) return false
    }
    if (filters.minSuspiciousScore !== undefined && node.suspiciousScore !== undefined) {
      if (node.suspiciousScore < filters.minSuspiciousScore) return false
    }
    if (filters.maxSuspiciousScore !== undefined && node.suspiciousScore !== undefined) {
      if (node.suspiciousScore > filters.maxSuspiciousScore) return false
    }
    filteredNodeIds.add(node.id)
    return true
  })

  const filteredEdges = graphData.edges.filter(edge => {
    if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) {
      return false
    }
    if (filters.minEdgeValue !== undefined && edge.value !== undefined) {
      if (edge.value < filters.minEdgeValue) return false
    }
    if (filters.maxEdgeValue !== undefined && edge.value !== undefined) {
      if (edge.value > filters.maxEdgeValue) return false
    }
    if (filters.startTimestamp !== undefined && edge.timestamp !== undefined) {
      const ts = edge.timestamp instanceof Date ? edge.timestamp.getTime() : edge.timestamp
      if (ts < filters.startTimestamp) return false
    }
    if (filters.endTimestamp !== undefined && edge.timestamp !== undefined) {
      const ts = edge.timestamp instanceof Date ? edge.timestamp.getTime() : edge.timestamp
      if (ts > filters.endTimestamp) return false
    }
    return true
  })

  return {
    nodes: filteredNodes,
    edges: filteredEdges,
    directed: graphData.directed,
    metadata: graphData.metadata
  }
}

export function calculateNodeSize(
  value: number,
  min: number = 10,
  max: number = 50
): number {
  if (value <= 0) return min
  
  const logValue = Math.log10(value + 1)
  const size = min + (logValue / 10) * (max - min)
  
  return Math.min(Math.max(size, min), max)
}

export function calculateEdgeWidth(
  value: number,
  min: number = 1,
  max: number = 10
): number {
  if (value <= 0) return min
  
  const logValue = Math.log10(value + 1)
  const width = min + (logValue / 10) * (max - min)
  
  return Math.min(Math.max(width, min), max)
}

export function getNodeColor(
  category?: NodeCategory | string,
  suspiciousScore?: number
): string {
  if (suspiciousScore !== undefined && suspiciousScore >= 0) {
    return getColorBySuspiciousScore(suspiciousScore)
  }

  if (category && category in NODE_CATEGORIES) {
    return NODE_CATEGORIES[category as NodeCategory].color
  }

  return NODE_CATEGORIES.normal.color
}

export function getColorBySuspiciousScore(score: number): string {
  if (score >= RISK_LEVELS.critical.minScore) {
    return RISK_LEVELS.critical.color
  } else if (score >= RISK_LEVELS.high.minScore) {
    return RISK_LEVELS.high.color
  } else if (score >= RISK_LEVELS.medium.minScore) {
    return RISK_LEVELS.medium.color
  } else {
    return RISK_LEVELS.low.color
  }
}

export function getRiskLevel(score: number): keyof typeof RISK_LEVELS {
  if (score >= RISK_LEVELS.critical.minScore) {
    return 'critical'
  } else if (score >= RISK_LEVELS.high.minScore) {
    return 'high'
  } else if (score >= RISK_LEVELS.medium.minScore) {
    return 'medium'
  } else {
    return 'low'
  }
}

export function calculateGraphStats(graphData: GraphData): {
  nodeCount: number
  edgeCount: number
  addressCount: number
  transactionCount: number
  avgSuspiciousScore: number
  maxSuspiciousScore: number
  totalValue: number
} {
  const nodes = graphData.nodes
  const edges = graphData.edges

  const addressNodes = nodes.filter(n => n.type === 'address')
  const transactionNodes = nodes.filter(n => n.type === 'transaction')

  const scores = nodes
    .map(n => n.suspiciousScore)
    .filter((s): s is number => s !== undefined && s !== null)

  const values = edges
    .map(e => e.value)
    .filter((v): v is number => v !== undefined && v !== null)

  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    addressCount: addressNodes.length,
    transactionCount: transactionNodes.length,
    avgSuspiciousScore: scores.length > 0 
      ? scores.reduce((a, b) => a + b, 0) / scores.length 
      : 0,
    maxSuspiciousScore: scores.length > 0 
      ? Math.max(...scores) 
      : 0,
    totalValue: values.length > 0 
      ? values.reduce((a, b) => a + b, 0) 
      : 0
  }
}

export function convertToEChartsOption(graphData: GraphData): Record<string, unknown> {
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: { dataType: string; data: GraphNode | GraphEdge }) => {
        if (params.dataType === 'node') {
          const node = params.data as GraphNode
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">${node.label}</div>
              <div>类型: ${node.type === 'address' ? '地址' : '交易'}</div>
              ${node.suspiciousScore !== undefined ? `<div>风险评分: ${node.suspiciousScore.toFixed(2)}</div>` : ''}
              ${node.data ? `<div>数据: ${JSON.stringify(node.data)}</div>` : ''}
            </div>
          `
        } else {
          const edge = params.data as GraphEdge
          const ts = edge.timestamp instanceof Date ? edge.timestamp.getTime() : (typeof edge.timestamp === 'number' && edge.timestamp < 1e12 ? edge.timestamp * 1000 : (edge.timestamp || 0))
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">交易</div>
              ${edge.value !== undefined && edge.value !== null ? `<div>金额: ${formatBTC(edge.value, 'auto')}</div>` : ''}
              ${edge.timestamp !== undefined ? `<div>时间: ${new Date(ts).toLocaleString()}</div>` : ''}
            </div>
          `
        }
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: graphData.nodes.map(node => ({
        id: node.id,
        name: node.label,
        value: node.size,
        symbolSize: node.size || 20,
        itemStyle: {
          color: node.color || '#3b82f6'
        },
        category: node.type,
        ...node
      })),
      links: graphData.edges.map(edge => ({
        source: edge.source,
        target: edge.target,
        value: edge.value,
        lineStyle: {
          width: edge.width || 1,
          opacity: 0.6
        },
        ...edge
      })),
      categories: [
        { name: 'address', itemStyle: { color: '#3b82f6' } },
        { name: 'transaction', itemStyle: { color: '#6b7280' } }
      ],
      roam: true,
      draggable: true,
      force: {
        repulsion: 500,
        gravity: 0.1,
        edgeLength: [100, 200]
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 3
        }
      }
    }]
  }
}
