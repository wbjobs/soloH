export type TaskStatus = 
  | 'pending' 
  | 'preprocessing' 
  | 'detecting' 
  | 'recognizing' 
  | 'postprocessing' 
  | 'punctuating' 
  | 'completed' 
  | 'failed';

export type FileType = 'image' | 'pdf';

export interface Point {
  x: number;
  y: number;
}

export interface TextBox {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  x3: number;
  y3: number;
  x4: number;
  y4: number;
  confidence: number;
}

export interface TextLine {
  id: string;
  textBox: TextBox;
  content: string;
  confidence: number;
  candidates: string[];
  columnIndex: number;
  lineIndex: number;
}

export interface PageResult {
  pageNumber: number;
  width: number;
  height: number;
  imageUrl: string;
  textLines: TextLine[];
  columns: TextLine[][];
}

export interface TaskResult {
  taskId: string;
  pages: PageResult[];
  fullText: string;
  readonly totalPages: number;
}

export interface ProgressMessage {
  taskId: string;
  status: TaskStatus;
  progress: number;
  message: string;
  currentPage?: number;
  totalPages?: number;
}

export interface Task {
  id: string;
  fileName: string;
  fileType: FileType;
  status: TaskStatus;
  progress: number;
  createdAt: string;
  completedAt?: string;
  pageCount: number;
  currentPage: number;
  errorMessage?: string;
  result?: TaskResult;
}

export interface UploadResponse {
  taskId: string;
  fileName: string;
  fileType: FileType;
  pageCount: number;
}

export interface MarkdownExportOptions {
  format: 'markdown';
  includeConfidence?: boolean;
  includeBBox?: boolean;
  headingLevel?: number;
  preserveLineBreaks?: boolean;
}

export interface TeiExportOptions {
  format: 'tei';
  includeConfidence?: boolean;
  includeBBox?: boolean;
  teiVersion?: string;
  includeMetadata?: boolean;
}

export interface TextExportOptions {
  format: 'txt';
  includeConfidence?: boolean;
  includeBBox?: boolean;
  lineSeparator?: string;
  pageSeparator?: string;
}

export interface JsonExportOptions {
  format: 'json';
  includeConfidence?: boolean;
  includeBBox?: boolean;
  prettyPrint?: boolean;
}

export type ExportOptions =
  | MarkdownExportOptions
  | TeiExportOptions
  | TextExportOptions
  | JsonExportOptions;

export interface UpdateBoxRequest {
  pageNumber: number;
  lineId: string;
  content: string;
}

export interface UpdateBoxResponse {
  success: boolean;
  updated: boolean;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  pageSize: number;
}

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '等待中',
  preprocessing: '预处理中',
  detecting: '文本检测中',
  recognizing: '文字识别中',
  postprocessing: '后处理中',
  punctuating: '标点处理中',
  completed: '已完成',
  failed: '失败',
};

export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  pending: '#909399',
  preprocessing: '#409EFF',
  detecting: '#E6A23C',
  recognizing: '#67C23A',
  postprocessing: '#909399',
  punctuating: '#8E44AD',
  completed: '#67C23A',
  failed: '#C41E3A',
};
