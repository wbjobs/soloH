export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'

export type TaskType =
  | 'import'
  | 'clustering'
  | 'pattern-detection'
  | 'graph-build'
  | 'import_csv'
  | 'import_api'
  | 'sync_blockchain'
  | 'analyze_address'
  | 'analyze_transaction'
  | 'cluster_addresses'
  | 'build_graph'
  | 'export_data'

export interface Task {
  id: string
  type: TaskType
  name?: string
  description?: string
  status: TaskStatus
  progress: number
  message?: string
  parameters?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  createdAt: Date
  startedAt?: Date
  completedAt?: Date
}

export interface TaskCreate {
  type: TaskType
  name?: string
  description?: string
  parameters?: Record<string, unknown>
}

export interface TaskListItem {
  id: string
  type: TaskType
  name?: string
  status: TaskStatus
  progress: number
  message?: string
  parameters?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  createdAt: Date
  startedAt?: Date
  completedAt?: Date
}

export interface TaskLog {
  id: number
  taskId: string
  level: string
  message: string
  createdAt: Date
}

export interface ImportCSVRequest {
  filePath?: string
  type?: string
  delimiter?: string
  hasHeader?: boolean
  encoding?: string
  mapping?: Record<string, string>
}

export interface ImportAPIRequest {
  source?: string
  type?: string
  apiUrl?: string
  apiKey?: string
  parameters?: Record<string, unknown>
  startBlock?: number
  endBlock?: number
  addresses?: string[]
}
