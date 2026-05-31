import type {
  Transaction, TransactionListItem, Address, AddressListItem,
  GraphData, SuspiciousScore, SuspiciousPattern, AddressCluster,
  Task, TaskListItem, PaginatedResponse, Block, ClusteringResult,
  GraphNode, GraphEdge
} from '@/types'

const delay = (ms: number = 1000) => new Promise(resolve => setTimeout(resolve, ms))

function generateBTCAddress(): string {
  const types = ['1', '3', 'bc1q']
  const type = types[Math.floor(Math.random() * types.length)]
  const chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
  let address = type
  for (let i = 0; i < (type.startsWith('bc1') ? 35 : 30); i++) {
    address += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return address
}

function generateTxid(): string {
  const chars = '0123456789abcdef'
  let txid = ''
  for (let i = 0; i < 64; i++) {
    txid += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return txid
}

function randomInRange(min: number, max: number): number {
  return Math.random() * (max - min) + min
}

function formatDate(d: Date): Date {
  return d
}

export const mockApi = {
  auth: {
    async login(username: string, password: string) {
      await delay(800)
      if (username === 'admin' && password === 'admin123') {
        return {
          token: 'mock-jwt-token-' + Date.now(),
          user: { id: 1, username: 'admin', role: 'admin' }
        }
      }
      throw new Error('Invalid credentials')
    }
  },

  transactions: {
    async getTransactions(params: any): Promise<PaginatedResponse<TransactionListItem>> {
      await delay(600)
      const page = params.page || 1
      const pageSize = params.pageSize || 10
      const items: TransactionListItem[] = []

      for (let i = 0; i < pageSize; i++) {
        const txTime = new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000)
        const totalInput = randomInRange(0.01, 10)
        const fee = randomInRange(0.0001, 0.01)
        items.push({
          txid: generateTxid(),
          blockHeight: Math.floor(840000 + Math.random() * 1000),
          blockTime: formatDate(txTime),
          inputCount: Math.floor(randomInRange(1, 5)),
          outputCount: Math.floor(randomInRange(1, 5)),
          totalInput,
          totalOutput: totalInput - fee,
          fee,
          isCoinbase: false
        })
      }

      return {
        items,
        total: 1000,
        page,
        pageSize,
        totalPages: Math.ceil(1000 / pageSize)
      }
    },

    async getTransaction(txid: string): Promise<Transaction> {
      await delay(500)
      const txTime = new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000)
      const totalInput = randomInRange(0.01, 10)
      const fee = randomInRange(0.0001, 0.01)

      const inputCount = Math.floor(randomInRange(1, 4))
      const outputCount = Math.floor(randomInRange(1, 4))

      const inputs = []
      const outputs = []
      const inputAddr = generateBTCAddress()
      const outputAddr1 = generateBTCAddress()
      const outputAddr2 = generateBTCAddress()

      for (let i = 0; i < inputCount; i++) {
        inputs.push({
          txid: generateTxid(),
          vout: i,
          address: i === 0 ? inputAddr : generateBTCAddress(),
          value: totalInput / inputCount
        })
      }

      outputs.push({
        address: outputAddr1,
        value: (totalInput - fee) * 0.7,
        scriptType: 'p2pkh'
      })
      if (outputCount > 1) {
        outputs.push({
          address: outputAddr2,
          value: (totalInput - fee) * 0.3,
          scriptType: 'p2pkh'
        })
      }

      return {
        txid,
        blockHeight: Math.floor(840000 + Math.random() * 1000),
        blockTime: formatDate(txTime),
        inputs,
        outputs,
        totalInput,
        totalOutput: totalInput - fee,
        fee,
        inputCount,
        outputCount,
        isCoinbase: false
      }
    },

    async getGraphData(params: any): Promise<GraphData> {
      await delay(800)
      const nodeCount = params.limit || 50
      const minValue = params.minValue || 0.001

      const addresses: string[] = []
      for (let i = 0; i < nodeCount; i++) {
        addresses.push(generateBTCAddress())
      }

      const nodes: GraphNode[] = addresses.map((addr, idx) => {
        const suspScore = Math.random() * 100
        let category: 'normal' | 'suspicious' | 'cluster' = 'normal'
        if (suspScore > 70) category = 'suspicious'
        else if (idx % 7 === 0) category = 'cluster'

        return {
          id: addr,
          address: addr,
          value: randomInRange(0.1, 100),
          category,
          suspiciousScore: Math.round(suspScore * 100) / 100,
          label: addr.substring(0, 8) + '...'
        }
      })

      const edges: GraphEdge[] = []
      for (let i = 0; i < nodeCount * 1.5; i++) {
        const fromIdx = Math.floor(Math.random() * nodeCount)
        let toIdx = Math.floor(Math.random() * nodeCount)
        while (toIdx === fromIdx) {
          toIdx = Math.floor(Math.random() * nodeCount)
        }
        const value = randomInRange(minValue, 5)

        edges.push({
          source: addresses[fromIdx],
          target: addresses[toIdx],
          value: Math.round(value * 1e8) / 1e8,
          txid: generateTxid(),
          timestamp: formatDate(new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000))
        })
      }

      return { nodes, edges }
    },

    async importCSV(file: File) {
      await delay(2000)
      return {
        taskId: 'task-' + Date.now(),
        message: 'Import task started'
      }
    },

    async importFromAPI(params: any) {
      await delay(1000)
      return {
        taskId: 'task-' + Date.now(),
        message: 'API import task started'
      }
    }
  },

  addresses: {
    async getAddresses(params: any): Promise<PaginatedResponse<AddressListItem>> {
      await delay(600)
      const page = params.page || 1
      const pageSize = params.pageSize || 10
      const items: AddressListItem[] = []

      for (let i = 0; i < pageSize; i++) {
        const balance = randomInRange(0.001, 100)
        const suspScore = Math.random() * 100
        const riskLevel = suspScore < 30 ? 'low' : suspScore < 60 ? 'medium' : suspScore < 80 ? 'high' : 'critical'

        items.push({
          address: generateBTCAddress(),
          balance,
          txCount: Math.floor(randomInRange(1, 1000)),
          totalReceived: balance + randomInRange(0, 100),
          firstSeen: formatDate(new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000)),
          lastSeen: formatDate(new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000)),
          suspiciousScore: Math.round(suspScore * 100) / 100,
          riskLevel
        })
      }

      return {
        items,
        total: 50000,
        page,
        pageSize,
        totalPages: Math.ceil(50000 / pageSize)
      }
    },

    async getAddress(address: string): Promise<Address> {
      await delay(500)
      const balance = randomInRange(0.001, 100)
      const txCount = Math.floor(randomInRange(1, 1000))
      const totalReceived = balance + randomInRange(0, 100)
      const totalSent = totalReceived - balance
      const suspScore = Math.random() * 100
      const riskLevel = suspScore < 30 ? 'low' : suspScore < 60 ? 'medium' : suspScore < 80 ? 'high' : 'critical'

      return {
        address,
        firstSeen: formatDate(new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000)),
        lastSeen: formatDate(new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000)),
        totalReceived,
        totalSent,
        balance,
        txCount,
        suspiciousScore: Math.round(suspScore * 100) / 100,
        riskLevel,
        clusterId: Math.random() > 0.7 ? 'cluster-' + Math.floor(Math.random() * 1000) : undefined
      }
    },

    async getAddressSubgraph(address: string, params: any): Promise<GraphData> {
      await delay(600)
      const depth = params.depth || 2
      const minValue = params.minValue || 0.0001

      const relatedAddresses: string[] = [address]
      for (let i = 0; i < depth * 5; i++) {
        relatedAddresses.push(generateBTCAddress())
      }

      const nodes: GraphNode[] = relatedAddresses.map((addr, idx) => {
        const suspScore = Math.random() * 100
        let category: 'normal' | 'suspicious' | 'cluster' = 'normal'
        if (suspScore > 70) category = 'suspicious'
        if (addr === address) category = 'suspicious'

        return {
          id: addr,
          address: addr,
          value: addr === address ? randomInRange(10, 100) : randomInRange(0.1, 10),
          category,
          suspiciousScore: addr === address ? 85.5 : Math.round(suspScore * 100) / 100,
          label: addr.substring(0, 8) + '...'
        }
      })

      const edges: GraphEdge[] = []
      for (let i = 1; i < relatedAddresses.length; i++) {
        const connectTo = Math.random() > 0.5 ? 0 : Math.floor(Math.random() * i)
        const value = randomInRange(minValue, 5)

        edges.push({
          source: relatedAddresses[connectTo],
          target: relatedAddresses[i],
          value: Math.round(value * 1e8) / 1e8,
          txid: generateTxid(),
          timestamp: formatDate(new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000))
        })
      }

      return { nodes, edges }
    },

    async getSuspiciousScore(address: string): Promise<SuspiciousScore> {
      await delay(500)
      const layering = Math.random() * 100
      const mixing = Math.random() * 100
      const structuring = Math.random() * 100
      const cycle = Math.random() * 100
      const suddenChange = Math.random() * 100

      const overall = Math.round((layering * 0.25 + mixing * 0.3 + structuring * 0.2 + cycle * 0.25 + suddenChange * 0.2))
      const riskLevel = overall < 30 ? 'low' : overall < 60 ? 'medium' : overall < 80 ? 'high' : 'critical'

      const relatedPatterns: SuspiciousPattern[] = []

      if (layering > 60) {
        relatedPatterns.push({
          id: Date.now(),
          type: 'layering',
          confidence: Math.round(layering) / 100,
          severity: layering > 80 ? 'high' : 'medium',
          description: '检测到多层级转账模式，资金经过3层以上跳转',
          evidence: ['Layer 1: 5笔交易', 'Layer 2: 12笔交易', 'Layer 3: 8笔交易'],
          detectedAt: formatDate(new Date()),
          address
        })
      }

      if (mixing > 70) {
        relatedPatterns.push({
          id: Date.now() + 1,
          type: 'mixing',
          confidence: Math.round(mixing) / 100,
          severity: mixing > 85 ? 'high' : 'medium',
          description: '疑似混币服务关联，多进多出模式',
          evidence: ['15个不同来源地址', '22个不同接收地址', '价值匹配率92%'],
          detectedAt: formatDate(new Date()),
          address
        })
      }

      if (structuring > 65) {
        relatedPatterns.push({
          id: Date.now() + 2,
          type: 'structuring',
          confidence: Math.round(structuring) / 100,
          severity: structuring > 80 ? 'high' : 'medium',
          description: '检测到结构化拆分模式，大额拆分为小额规避监控',
          evidence: ['24小时内18笔小额交易', '平均金额0.5 BTC', '时间间隔规律'],
          detectedAt: formatDate(new Date()),
          address
        })
      }

      return {
        address,
        overallScore: overall,
        factors: {
          layeringScore: Math.round(layering),
          mixingScore: Math.round(mixing),
          structuringScore: Math.round(structuring),
          cycleScore: Math.round(cycle),
          suddenChangeScore: Math.round(suddenChange)
        },
        riskLevel,
        relatedPatterns
      }
    },

    async getAddressTransactions(address: string, params: any) {
      await delay(500)
      const page = params.page || 1
      const pageSize = params.pageSize || 20
      const items: any[] = []

      for (let i = 0; i < pageSize; i++) {
        const isOutgoing = Math.random() > 0.5
        const value = randomInRange(0.001, 5)
        const txTime = new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000)

        items.push({
          txid: generateTxid(),
          type: isOutgoing ? 'outgoing' : 'incoming',
          value,
          counterparty: generateBTCAddress(),
          blockTime: formatDate(txTime),
          blockHeight: Math.floor(840000 + Math.random() * 1000)
        })
      }

      return {
        items,
        total: 500,
        page,
        pageSize,
        totalPages: Math.ceil(500 / pageSize)
      }
    },

    async getTopAddresses(limit: number = 10) {
      await delay(400)
      const items: AddressListItem[] = []

      for (let i = 0; i < limit; i++) {
        const suspScore = 70 + Math.random() * 30
        items.push({
          address: generateBTCAddress(),
          balance: randomInRange(100, 10000),
          txCount: Math.floor(randomInRange(100, 10000)),
          totalReceived: randomInRange(1000, 100000),
          firstSeen: formatDate(new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000)),
          lastSeen: formatDate(new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000)),
          suspiciousScore: Math.round(suspScore * 100) / 100,
          riskLevel: suspScore > 85 ? 'critical' : 'high'
        })
      }

      return items.sort((a, b) => b.suspiciousScore - a.suspiciousScore)
    }
  },

  analysis: {
    async getClusteringResults(params: any): Promise<PaginatedResponse<AddressCluster>> {
      await delay(600)
      const page = params.page || 1
      const pageSize = params.pageSize || 10
      const items: AddressCluster[] = []

      const heuristics: Array<'common-input' | 'change-address' | 'combined'> = ['common-input', 'change-address', 'combined']

      for (let i = 0; i < pageSize; i++) {
        const size = Math.floor(randomInRange(2, 50))
        const addresses: string[] = []
        for (let j = 0; j < Math.min(size, 5); j++) {
          addresses.push(generateBTCAddress())
        }

        items.push({
          clusterId: 'cluster-' + (1000 + i),
          addresses,
          size,
          totalValue: randomInRange(10, 1000),
          heuristic: heuristics[Math.floor(Math.random() * heuristics.length)],
          confidence: Math.round((0.6 + Math.random() * 0.35) * 10000) / 10000,
          createdAt: formatDate(new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000))
        })
      }

      return {
        items,
        total: 500,
        page,
        pageSize,
        totalPages: Math.ceil(500 / pageSize)
      }
    },

    async runClustering(params: any): Promise<Task> {
      await delay(800)
      return {
        id: 'task-' + Date.now(),
        type: 'clustering',
        status: 'pending',
        progress: 0,
        createdAt: formatDate(new Date()),
        parameters: params,
        result: null,
        error: null
      }
    },

    async getSuspiciousPatterns(params: any): Promise<PaginatedResponse<SuspiciousPattern>> {
      await delay(500)
      const page = params.page || 1
      const pageSize = params.pageSize || 10
      const items: SuspiciousPattern[] = []

      const types: Array<'layering' | 'cycle' | 'structuring' | 'mixing'> = ['layering', 'cycle', 'structuring', 'mixing']
      const severities: Array<'low' | 'medium' | 'high' | 'critical'> = ['low', 'medium', 'high', 'critical']

      for (let i = 0; i < pageSize; i++) {
        const type = types[Math.floor(Math.random() * types.length)]
        const severity = severities[Math.floor(Math.random() * severities.length)]

        items.push({
          id: Date.now() + i,
          type,
          confidence: Math.round((0.5 + Math.random() * 0.5) * 10000) / 10000,
          severity,
          description: `检测到${type}模式，${severity}风险等级`,
          evidence: ['证据1', '证据2', '证据3'],
          detectedAt: formatDate(new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000)),
          address: generateBTCAddress()
        })
      }

      return {
        items,
        total: 200,
        page,
        pageSize,
        totalPages: Math.ceil(200 / pageSize)
      }
    },

    async analyzeAddress(address: string): Promise<Task> {
      await delay(500)
      return {
        id: 'task-' + Date.now(),
        type: 'pattern-detection',
        status: 'pending',
        progress: 0,
        createdAt: formatDate(new Date()),
        parameters: { address },
        result: null,
        error: null
      }
    },

    async getPatternDetail(patternId: string): Promise<SuspiciousPattern> {
      await delay(400)
      return {
        id: parseInt(patternId) || Date.now(),
        type: 'layering',
        confidence: 0.85,
        severity: 'high',
        description: '检测到多层级转账模式',
        evidence: ['Layer 1: 5 addresses', 'Layer 2: 12 addresses', 'Layer 3: 8 addresses'],
        detectedAt: formatDate(new Date()),
        address: generateBTCAddress()
      }
    },

    async getDashboardStats() {
      await delay(500)
      return {
        totalTransactions: 12584732,
        totalAddresses: 584723,
        highRiskAddresses: 1247,
        todayVolume: 45238.67,
        transactions24h: 12847,
        patterns24h: 86,
        suspiciousTrend: [
          { date: '2024-01-01', count: 12, volume: 1250 },
          { date: '2024-01-02', count: 19, volume: 2100 },
          { date: '2024-01-03', count: 15, volume: 1800 },
          { date: '2024-01-04', count: 25, volume: 3200 },
          { date: '2024-01-05', count: 22, volume: 2800 },
          { date: '2024-01-06', count: 31, volume: 4100 },
          { date: '2024-01-07', count: 28, volume: 3600 },
        ]
      }
    },

    async getRecentAlerts() {
      await delay(400)
      return [
        {
          id: 1,
          type: 'critical',
          title: '检测到大额循环交易',
          message: '涉及12个地址，总金额125.8 BTC',
          time: '5分钟前',
          address: generateBTCAddress()
        },
        {
          id: 2,
          type: 'high',
          title: '可疑混币模式',
          message: '24小时内45笔小额交易合并转出',
          time: '12分钟前',
          address: generateBTCAddress()
        },
        {
          id: 3,
          type: 'high',
          title: '结构化拆分模式',
          message: '大额资金拆分为23笔小额交易分散转出',
          time: '28分钟前',
          address: generateBTCAddress()
        },
        {
          id: 4,
          type: 'medium',
          title: '新发现地址聚类',
          message: '基于共同输入法识别到8个地址属于同一实体',
          time: '1小时前',
          address: generateBTCAddress()
        }
      ]
    },

    async calculateGNNAnomalyScore(params: { address: string; depth?: number }) {
      await delay(1200)
      const anomalyScore = Math.round((30 + Math.random() * 60) * 100) / 100
      const riskLevel = anomalyScore >= 75 ? 'critical' : anomalyScore >= 50 ? 'high' : anomalyScore >= 25 ? 'medium' : 'low'

      const features: Record<string, number> = {
        in_degree: Math.floor(randomInRange(1, 50)),
        out_degree: Math.floor(randomInRange(1, 50)),
        total_in_value: randomInRange(0.1, 100),
        total_out_value: randomInRange(0.1, 100),
        mean_in_value: randomInRange(0.01, 5),
        mean_out_value: randomInRange(0.01, 5),
        std_in_value: randomInRange(0.01, 2),
        std_out_value: randomInRange(0.01, 2),
        value_entropy: randomInRange(0, 1),
        flow_ratio: randomInRange(0.3, 1.5),
        clustering_coefficient: randomInRange(0, 1),
        pagerank: randomInRange(0, 1),
        min_time_interval: randomInRange(0, 3600),
        max_time_interval: randomInRange(3600, 86400 * 7),
        mean_time_interval: randomInRange(60, 86400),
        std_time_interval: randomInRange(0, 86400),
        unique_days: Math.floor(randomInRange(1, 30)),
        total_tx_count: Math.floor(randomInRange(5, 500)),
        anomaly_pattern_score: randomInRange(0, 100),
        transaction_count: Math.floor(randomInRange(5, 500))
      }

      const featureImportance: Record<string, number> = {
        value_entropy: 0.15,
        anomaly_pattern_score: 0.25,
        flow_ratio: 0.1,
        std_in_value: 0.1,
        std_out_value: 0.1,
        min_time_interval: 0.1,
        clustering_coefficient: 0.08,
        pagerank: 0.07,
        in_degree: 0.05,
        out_degree: 0.05
      }

      const explanations = [
        {
          type: 'value_entropy',
          severity: anomalyScore > 60 ? 'high' : anomalyScore > 40 ? 'medium' : 'low',
          description: `金额分布熵为${features.value_entropy.toFixed(3)}，${features.value_entropy > 0.7 ? '显示出高度不规则的金额模式' : features.value_entropy > 0.4 ? '存在一定程度的金额异常' : '金额模式相对正常'}`,
          contribution: features.value_entropy * 15
        },
        {
          type: 'anomaly_pattern_score',
          severity: features.anomaly_pattern_score > 70 ? 'high' : features.anomaly_pattern_score > 40 ? 'medium' : 'low',
          description: `异常模式综合得分为${features.anomaly_pattern_score.toFixed(1)}/100`,
          contribution: features.anomaly_pattern_score * 0.25
        },
        {
          type: 'flow_ratio',
          severity: Math.abs(features.flow_ratio - 1) > 0.5 ? 'high' : Math.abs(features.flow_ratio - 1) > 0.2 ? 'medium' : 'low',
          description: `资金流入流出比率为${features.flow_ratio.toFixed(2)}，${Math.abs(features.flow_ratio - 1) > 0.5 ? '严重失衡' : Math.abs(features.flow_ratio - 1) > 0.2 ? '轻度失衡' : '基本平衡'}`,
          contribution: Math.abs(features.flow_ratio - 1) * 10
        },
        {
          type: 'clustering_coefficient',
          severity: features.clustering_coefficient > 0.6 ? 'high' : features.clustering_coefficient > 0.3 ? 'medium' : 'low',
          description: `聚类系数为${features.clustering_coefficient.toFixed(3)}，${features.clustering_coefficient > 0.6 ? '显示出高度关联的地址网络' : features.clustering_coefficient > 0.3 ? '存在一定的地址聚集' : '地址关联度较低'}`,
          contribution: features.clustering_coefficient * 8
        }
      ]

      return {
        success: true,
        data: {
          address: params.address,
          anomalyScore,
          riskLevel,
          features,
          featureImportance,
          subgraphSize: {
            nodes: Math.floor(randomInRange(50, 500)),
            edges: Math.floor(randomInRange(100, 1000))
          },
          analysisDepth: params.depth || 3,
          explanations
        },
        timestamp: Date.now()
      }
    },

    async analyzePrivacyCoinAssociations(params: { address: string; depth?: number }) {
      await delay(1500)
      const overallRiskScore = Math.round((20 + Math.random() * 70) * 100) / 100
      const riskLevel = overallRiskScore >= 75 ? 'critical' : overallRiskScore >= 50 ? 'high' : overallRiskScore >= 25 ? 'medium' : 'low'

      const hasPrivacyCoin = Math.random() > 0.4
      const hasMixingPattern = Math.random() > 0.5
      const hasCrossChain = Math.random() > 0.6

      const detectedPrivacyCoins: Record<string, Array<{
        address: string
        coinName: string
        description: string
        riskLevel: string
      }>> = {}

      if (hasPrivacyCoin) {
        const coins = ['monero', 'zcash', 'dash']
        const coinNames = { monero: 'Monero (XMR)', zcash: 'Zcash (ZEC)', dash: 'Dash (DASH)' }
        const selectedCoin = coins[Math.floor(Math.random() * coins.length)]

        const xmrAddress = '4' + Array.from({ length: 94 }, () =>
          '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'.charAt(Math.floor(Math.random() * 58))
        ).join('')

        detectedPrivacyCoins[selectedCoin] = [{
          address: xmrAddress,
          coinName: coinNames[selectedCoin as keyof typeof coinNames],
          description: `检测到与${coinNames[selectedCoin as keyof typeof coinNames]}的关联交易`,
          riskLevel: 'high'
        }]
      }

      const suspiciousTransactions: Array<{
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
      }> = []

      for (let i = 0; i < Math.floor(randomInRange(1, 5)); i++) {
        const isIncoming = Math.random() > 0.5
        const timestamp = Date.now() - Math.floor(randomInRange(1, 30)) * 86400000

        suspiciousTransactions.push({
          txid: generateTxid(),
          fromAddress: isIncoming ? generateBTCAddress() : params.address,
          toAddress: isIncoming ? params.address : generateBTCAddress(),
          value: randomInRange(0.01, 10),
          timestamp,
          privacyType: hasPrivacyCoin ? 'coinjoin' : undefined,
          direction: isIncoming ? 'incoming' : 'outgoing',
          gatewayInfo: hasCrossChain && Math.random() > 0.5 ? {
            gatewayId: 'gateway-' + Math.floor(Math.random() * 1000),
            name: ['ChangeNow', 'FixedFloat', 'SimpleSwap'][Math.floor(Math.random() * 3)],
            type: 'instant_exchange',
            riskLevel: 'medium'
          } : undefined
        })
      }

      const mixingPatterns: Array<{
        type: string
        description: string
        confidence: number
        evidence: Record<string, unknown>
      }> = []

      if (hasMixingPattern) {
        const patternTypes = [
          { type: 'value_matching', desc: '金额匹配模式：总流入与总流出高度一致，可能为混币服务' },
          { type: 'automated_mixing', desc: '自动化混币模式：短时间内多笔金额相似的交易' },
          { type: 'structuring_split', desc: '结构化拆分：大额资金拆分为多笔小额交易' }
        ]
        const pattern = patternTypes[Math.floor(Math.random() * patternTypes.length)]

        mixingPatterns.push({
          type: pattern.type,
          description: pattern.desc,
          confidence: Math.round((0.6 + Math.random() * 0.35) * 10000) / 10000,
          evidence: {
            matchingTransactionCount: Math.floor(randomInRange(5, 50)),
            totalValue: randomInRange(0.5, 50),
            timeWindowMinutes: Math.floor(randomInRange(10, 1440))
          }
        })
      }

      const crossChainLinks: Array<{
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
      }> = []

      if (hasCrossChain) {
        if (hasPrivacyCoin && detectedPrivacyCoins.monero) {
          crossChainLinks.push({
            type: 'privacy_coin',
            privacyType: 'monero',
            coinName: 'Monero (XMR)',
            address: detectedPrivacyCoins.monero[0].address,
            description: '检测到Monero跨链交易关联',
            riskLevel: 'high',
            transactionCount: Math.floor(randomInRange(1, 10)),
            totalValue: randomInRange(0.1, 20)
          })
        }

        crossChainLinks.push({
          type: 'privacy_gateway',
          gatewayName: 'ChangeNow',
          gatewayType: 'instant_exchange',
          description: '检测到通过即时兑换网关的跨链交易',
          riskLevel: 'medium',
          transaction: {
            txid: generateTxid(),
            from: params.address,
            to: generateBTCAddress(),
            value: randomInRange(0.1, 5)
          }
        })
      }

      const threatIntelligence = {
        threatLevel: riskLevel,
        threatIndicators: [
          {
            type: 'privacy_coin_association',
            description: hasPrivacyCoin ? '检测到与隐私币的直接关联' : '未检测到隐私币关联',
            severity: hasPrivacyCoin ? 'high' : 'low'
          },
          {
            type: 'mixing_pattern',
            description: hasMixingPattern ? '检测到可疑混币模式' : '未检测到混币模式',
            severity: hasMixingPattern ? 'high' : 'low'
          },
          {
            type: 'cross_chain_activity',
            description: hasCrossChain ? '存在跨链交易活动' : '未检测到跨链活动',
            severity: hasCrossChain ? 'medium' : 'low'
          }
        ],
        recommendedActions: [
          '持续监控该地址的交易活动',
          '分析相关联地址的行为模式',
          hasPrivacyCoin ? '上报监管机构并启动合规调查' : '进行常规风险评估',
          hasMixingPattern ? '追溯资金来源并评估是否涉及非法活动' : '执行标准KYC/AML流程'
        ],
        summary: hasPrivacyCoin || hasMixingPattern || hasCrossChain
          ? '该地址存在高风险隐私币关联活动，建议加强监控并启动合规调查'
          : '该地址未检测到明显的隐私币关联风险，风险等级为低'
      }

      return {
        success: true,
        data: {
          address: params.address,
          overallRiskScore,
          riskLevel,
          detectedPrivacyCoins,
          privacyCoinCount: Object.keys(detectedPrivacyCoins).length,
          associatedAddressCount: Math.floor(randomInRange(5, 100)),
          suspiciousTransactions,
          totalPrivacyRelatedValue: suspiciousTransactions.reduce((sum, tx) => sum + tx.value, 0),
          mixingPatterns,
          crossChainLinks,
          analysisDepth: params.depth || 3,
          analysisTimestamp: new Date().toISOString(),
          threatIntelligence
        },
        timestamp: Date.now()
      }
    },

    async generateComplianceReport(params: { address: string; format?: string; includeVisualizations?: boolean }) {
      await delay(2000)

      const now = new Date()
      const reportDate = now.toISOString().split('T')[0]
      const analysisPeriod = `${new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]} 至 ${reportDate}`

      const mockBlob = new Blob(['PDF Report Content Placeholder'], { type: 'application/pdf' })

      return {
        success: true,
        data: {
          address: params.address,
          reportType: 'address_compliance',
          format: params.format || 'pdf',
          generatedAt: now.toISOString(),
          fileSize: Math.floor(randomInRange(100000, 500000)),
          filename: `compliance-report-${params.address}-${reportDate}.${params.format || 'pdf'}`,
          downloadUrl: `/api/v1/analysis/report/download/${params.address}`,
          summary: {
            overallRiskScore: Math.round((30 + Math.random() * 60) * 100) / 100,
            riskLevel: Math.random() > 0.5 ? 'high' : 'medium',
            gnnAnomalyScore: Math.round((25 + Math.random() * 65) * 100) / 100,
            privacyRiskScore: Math.round((20 + Math.random() * 70) * 100) / 100,
            suspiciousPatternCount: Math.floor(randomInRange(0, 10)),
            privacyCoinAssociations: Math.random() > 0.6 ? 1 : 0,
            reportDate,
            analysisPeriod
          }
        },
        blob: mockBlob,
        timestamp: Date.now()
      }
    }
  },

  tasks: {
    async getTasks(params: any): Promise<PaginatedResponse<TaskListItem>> {
      await delay(500)
      const page = params.page || 1
      const pageSize = params.pageSize || 10
      const items: TaskListItem[] = []

      const types: Array<'import' | 'clustering' | 'pattern-detection' | 'graph-build'> = ['import', 'clustering', 'pattern-detection', 'graph-build']
      const statuses: Array<'pending' | 'processing' | 'completed' | 'failed'> = ['pending', 'processing', 'completed', 'failed']

      for (let i = 0; i < pageSize; i++) {
        const type = types[Math.floor(Math.random() * types.length)]
        const status = statuses[Math.floor(Math.random() * statuses.length)]
        const progress = status === 'completed' ? 100 : status === 'failed' ? Math.floor(Math.random() * 80) : Math.floor(Math.random() * 100)

        items.push({
          id: 'task-' + (Date.now() + i),
          type,
          status,
          progress,
          createdAt: formatDate(new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000)),
          startedAt: status !== 'pending' ? formatDate(new Date(Date.now() - Math.random() * 12 * 60 * 60 * 1000)) : undefined,
          completedAt: status === 'completed' || status === 'failed' ? formatDate(new Date(Date.now() - Math.random() * 60 * 60 * 1000)) : undefined,
          parameters: {},
          result: status === 'completed' ? { recordsProcessed: Math.floor(Math.random() * 10000) } : null,
          error: status === 'failed' ? 'Connection timeout after 30 seconds' : null
        })
      }

      return {
        items,
        total: 150,
        page,
        pageSize,
        totalPages: Math.ceil(150 / pageSize)
      }
    },

    async getTask(taskId: string): Promise<Task> {
      await delay(400)
      const statuses: Array<'pending' | 'processing' | 'completed' | 'failed'> = ['pending', 'processing', 'completed', 'failed']
      const status = statuses[Math.floor(Math.random() * statuses.length)]

      return {
        id: taskId,
        type: 'import',
        status,
        progress: status === 'completed' ? 100 : Math.floor(Math.random() * 80),
        createdAt: formatDate(new Date(Date.now() - 3600000)),
        startedAt: status !== 'pending' ? formatDate(new Date(Date.now() - 3000000)) : undefined,
        completedAt: status === 'completed' ? formatDate(new Date()) : undefined,
        parameters: { source: 'csv', filename: 'transactions.csv' },
        result: status === 'completed' ? { recordsImported: 15420, errors: 3 } : null,
        error: status === 'failed' ? 'Database connection error' : null
      }
    },

    async getTaskLogs(taskId: string) {
      await delay(400)
      return [
        { id: 1, level: 'info', message: 'Task started', createdAt: formatDate(new Date(Date.now() - 3600000)) },
        { id: 2, level: 'info', message: 'Reading file transactions.csv', createdAt: formatDate(new Date(Date.now() - 3550000)) },
        { id: 3, level: 'info', message: 'Validating 15423 records', createdAt: formatDate(new Date(Date.now() - 3500000)) },
        { id: 4, level: 'warning', message: 'Skipping 3 invalid records', createdAt: formatDate(new Date(Date.now() - 3400000)) },
        { id: 5, level: 'info', message: 'Importing into database...', createdAt: formatDate(new Date(Date.now() - 3300000)) },
        { id: 6, level: 'info', message: 'Processing batch 1/16', createdAt: formatDate(new Date(Date.now() - 3200000)) },
      ]
    },

    async retryTask(taskId: string): Promise<Task> {
      await delay(500)
      return {
        id: taskId,
        type: 'import',
        status: 'pending',
        progress: 0,
        createdAt: formatDate(new Date()),
        parameters: {},
        result: null,
        error: null
      }
    },

    async cancelTask(taskId: string): Promise<{ success: boolean }> {
      await delay(300)
      return { success: true }
    }
  }
}

export default mockApi
