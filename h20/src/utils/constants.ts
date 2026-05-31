export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export const USE_MOCK_API = (import.meta.env.VITE_USE_MOCK_API || 'true') === 'true'

export const BTC_DECIMALS = 8

export const SATOSHI_PER_BTC = 100000000

export const RISK_LEVELS = {
  low: {
    level: 'low',
    label: '低风险',
    color: '#10b981',
    bgColor: 'bg-green-100',
    textColor: 'text-green-800',
    minScore: 0,
    maxScore: 25
  },
  medium: {
    level: 'medium',
    label: '中风险',
    color: '#f59e0b',
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-800',
    minScore: 25,
    maxScore: 50
  },
  high: {
    level: 'high',
    label: '高风险',
    color: '#ef4444',
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    minScore: 50,
    maxScore: 75
  },
  critical: {
    level: 'critical',
    label: '极高风险',
    color: '#7c3aed',
    bgColor: 'bg-purple-100',
    textColor: 'text-purple-800',
    minScore: 75,
    maxScore: 100
  }
} as const

export type RiskLevel = keyof typeof RISK_LEVELS

export const PATTERN_TYPES = {
  coinjoin: {
    type: 'coinjoin',
    label: 'CoinJoin 混合',
    description: '使用 CoinJoin 等混币服务',
    severity: 'high'
  },
  layering: {
    type: 'layering',
    label: '分层洗钱',
    description: '通过多层转账掩盖资金来源',
    severity: 'high'
  },
  dusting: {
    type: 'dusting',
    label: '粉尘攻击',
    description: '发送小额 UTXO 进行地址追踪',
    severity: 'medium'
  },
  rapid_transfer: {
    type: 'rapid_transfer',
    label: '快速转账',
    description: '短时间内大量快速转账',
    severity: 'medium'
  },
  large_holding: {
    type: 'large_holding',
    label: '大额持有',
    description: '持有大量 BTC 的地址',
    severity: 'low'
  },
  mixing_service: {
    type: 'mixing_service',
    label: '混币服务',
    description: '与已知混币服务交互',
    severity: 'critical'
  },
  darknet_market: {
    type: 'darknet_market',
    label: '暗网市场',
    description: '与暗网市场地址交互',
    severity: 'critical'
  },
  ransomware: {
    type: 'ransomware',
    label: '勒索软件',
    description: '与已知勒索软件地址交互',
    severity: 'critical'
  }
} as const

export type PatternType = keyof typeof PATTERN_TYPES

export const TASK_STATUS = {
  pending: {
    status: 'pending',
    label: '等待中',
    color: '#6b7280',
    bgColor: 'bg-gray-100',
    textColor: 'text-gray-800',
    icon: 'clock'
  },
  processing: {
    status: 'processing',
    label: '运行中',
    color: '#3b82f6',
    bgColor: 'bg-blue-100',
    textColor: 'text-blue-800',
    icon: 'loader'
  },
  completed: {
    status: 'completed',
    label: '已完成',
    color: '#10b981',
    bgColor: 'bg-green-100',
    textColor: 'text-green-800',
    icon: 'check-circle'
  },
  failed: {
    status: 'failed',
    label: '失败',
    color: '#ef4444',
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    icon: 'x-circle'
  },
  cancelled: {
    status: 'cancelled',
    label: '已取消',
    color: '#f59e0b',
    bgColor: 'bg-yellow-100',
    textColor: 'text-yellow-800',
    icon: 'x-octagon'
  }
} as const

export type TaskStatusType = keyof typeof TASK_STATUS

export const TASK_TYPES = {
  import_csv: {
    type: 'import_csv',
    label: '导入 CSV',
    description: '从 CSV 文件导入交易数据',
    icon: 'file-text'
  },
  import_api: {
    type: 'import_api',
    label: 'API 导入',
    description: '从区块链 API 导入数据',
    icon: 'cloud-download'
  },
  sync_blockchain: {
    type: 'sync_blockchain',
    label: '同步区块链',
    description: '同步区块链数据',
    icon: 'refresh-cw'
  },
  analyze_address: {
    type: 'analyze_address',
    label: '分析地址',
    description: '分析地址风险和关联',
    icon: 'search'
  },
  analyze_transaction: {
    type: 'analyze_transaction',
    label: '分析交易',
    description: '分析交易详情和流向',
    icon: 'git-branch'
  },
  cluster_addresses: {
    type: 'cluster_addresses',
    label: '地址聚类',
    description: '对地址进行聚类分析',
    icon: 'layers'
  },
  build_graph: {
    type: 'build_graph',
    label: '构建图谱',
    description: '构建交易关系图谱',
    icon: 'network'
  },
  export_data: {
    type: 'export_data',
    label: '导出数据',
    description: '导出分析结果数据',
    icon: 'download'
  }
} as const

export type TaskTypeKey = keyof typeof TASK_TYPES

export const COLOR_PALETTE = {
  primary: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a'
  },
  success: {
    50: '#ecfdf5',
    100: '#d1fae5',
    200: '#a7f3d0',
    300: '#6ee7b7',
    400: '#34d399',
    500: '#10b981',
    600: '#059669',
    700: '#047857',
    800: '#065f46',
    900: '#064e3b'
  },
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f'
  },
  danger: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    300: '#fca5a5',
    400: '#f87171',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    800: '#991b1b',
    900: '#7f1d1d'
  },
  info: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#0ea5e9',
    600: '#0284c7',
    700: '#0369a1',
    800: '#075985',
    900: '#0c4a6e'
  },
  purple: {
    50: '#faf5ff',
    100: '#f3e8ff',
    200: '#e9d5ff',
    300: '#d8b4fe',
    400: '#c084fc',
    500: '#a855f7',
    600: '#9333ea',
    700: '#7c3aed',
    800: '#6d28d9',
    900: '#5b21b6'
  }
}

export const CHART_COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
  '#f97316',
  '#6366f1'
]

export const NODE_CATEGORIES = {
  normal: {
    category: 'normal',
    label: '普通地址',
    color: '#3b82f6'
  },
  exchange: {
    category: 'exchange',
    label: '交易所',
    color: '#10b981'
  },
  mining: {
    category: 'mining',
    label: '矿池',
    color: '#f59e0b'
  },
  mixing: {
    category: 'mixing',
    label: '混币服务',
    color: '#ef4444'
  },
  darknet: {
    category: 'darknet',
    label: '暗网市场',
    color: '#7c3aed'
  },
  ransomware: {
    category: 'ransomware',
    label: '勒索软件',
    color: '#dc2626'
  },
  scam: {
    category: 'scam',
    label: '诈骗地址',
    color: '#f97316'
  },
  transaction: {
    category: 'transaction',
    label: '交易节点',
    color: '#6b7280'
  }
} as const

export type NodeCategory = keyof typeof NODE_CATEGORIES

export const ADDRESS_TYPES = {
  legacy: {
    type: 'legacy',
    label: 'Legacy (P2PKH)',
    prefix: '1',
    regex: /^1[a-km-zA-HJ-NP-Z1-9]{25,34}$/
  },
  segwit: {
    type: 'segwit',
    label: 'SegWit (P2SH)',
    prefix: '3',
    regex: /^3[a-km-zA-HJ-NP-Z1-9]{25,34}$/
  },
  bech32: {
    type: 'bech32',
    label: 'Bech32 (P2WPKH)',
    prefix: 'bc1',
    regex: /^bc1[a-z0-9]{39,59}$/
  },
  taproot: {
    type: 'taproot',
    label: 'Taproot (P2TR)',
    prefix: 'bc1p',
    regex: /^bc1p[a-z0-9]{38,87}$/
  }
} as const

export type AddressType = keyof typeof ADDRESS_TYPES
