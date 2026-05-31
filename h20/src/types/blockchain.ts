export interface TxInput {
  txid: string
  vout: number
  address: string
  value: number
  prevTxid?: string
  prevVout?: number
  prevAddress?: string
}

export interface TxInputCreate {
  txid: string
  vout: number
  address: string
  value: number
}

export interface TxOutput {
  address: string
  value: number
  scriptType?: string
  vout?: number
  isSpent?: boolean
}

export interface TxOutputCreate {
  address: string
  value: number
  scriptType?: string
}

export interface Transaction {
  txid: string
  id?: string
  txId?: string
  blockHeight?: number
  blockTime: Date
  inputs: TxInput[]
  outputs: TxOutput[]
  totalInput: number
  totalOutput: number
  inputValue?: number
  outputValue?: number
  fee?: number
  inputCount: number
  outputCount: number
  isCoinbase?: boolean
  suspiciousScore?: number
  confirmations?: number
}

export interface TransactionCreate {
  txid: string
  blockHeight?: number
  blockTime: Date
  inputs: TxInputCreate[]
  outputs: TxOutputCreate[]
}

export interface TransactionListItem {
  txid: string
  id?: string
  txId?: string
  blockHeight?: number
  blockTime: Date
  inputCount: number
  outputCount: number
  totalInput: number
  totalOutput: number
  inputValue?: number
  outputValue?: number
  fee?: number
  isCoinbase?: boolean
  suspiciousScore?: number
}

export interface Block {
  blockHeight: number
  blockHash: string
  blockTime: Date
  txCount?: number
  totalBtc?: number
  size?: number
  weight?: number
  previousBlockHash?: string
}

export interface BlockCreate {
  blockHeight: number
  blockHash: string
  blockTime: Date
  txCount?: number
  totalBtc?: number
}

export interface Address {
  address: string
  firstSeen?: Date
  lastSeen?: Date
  totalReceived: number
  totalSent: number
  balance: number
  txCount: number
  clusterId?: string
  suspiciousScore?: number
  riskLevel?: 'low' | 'medium' | 'high' | 'critical'
  riskFactors?: Record<string, number>
}

export interface AddressCreate {
  address: string
  firstSeen?: Date
  lastSeen?: Date
}

export interface AddressListItem {
  address: string
  balance: number
  txCount: number
  totalReceived?: number
  firstSeen?: Date
  lastSeen?: Date
  suspiciousScore?: number
  riskLevel?: 'low' | 'medium' | 'high' | 'critical'
}

export interface PaginationParams {
  page: number
  pageSize: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}
