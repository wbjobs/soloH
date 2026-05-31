# GWAS全基因组关联分析系统 - 技术架构文档

## 1. 架构设计

```mermaid
graph TD
    subgraph "前端层"
        A1["Vue 3 + TypeScript"]
        A2["ECharts 可视化"]
        A3["Axios HTTP客户端"]
        A4["Vue Router 路由"]
        A5["Pinia 状态管理"]
    end

    subgraph "网关层"
        B1["Nginx 反向代理"]
        B2["静态资源服务"]
    end

    subgraph "后端服务层"
        C1["Flask API服务"]
        C2["用户认证模块"]
        C3["文件上传模块"]
        C4["数据校验模块"]
        C5["任务调度API"]
    end

    subgraph "任务队列层"
        D1["Celery 分布式队列"]
        D2["Redis 消息中间件"]
        D3["GWAS分析Worker"]
        D4["PCA计算Worker"]
        D5["LD分析Worker"]
    end

    subgraph "分析引擎层"
        E1["Python statsmodels"]
        E2["scikit-allel (VCF处理)"]
        E3["numpy/pandas 数据处理"]
        E4["matplotlib/seaborn 绘图"]
    end

    subgraph "数据层"
        F1["PostgreSQL 关系数据库"]
        F2["MongoDB 任务元数据"]
        F3["MinIO 文件存储"]
        F4["参考基因组数据库"]
    end

    A1 --> B1
    B1 --> C1
    C1 --> D1
    D1 --> D2
    D3 --> E1
    D3 --> E2
    D4 --> E3
    D5 --> E4
    C1 --> F1
    C1 --> F2
    C3 --> F3
    D3 --> F4
```

## 2. 技术选型说明

### 2.1 前端技术栈
- **框架**: Vue 3.4 + TypeScript 5.4
- **构建工具**: Vite 5.2
- **UI组件库**: Element Plus 2.7
- **可视化**: ECharts 5.5
- **状态管理**: Pinia 2.1
- **路由**: Vue Router 4.3
- **HTTP客户端**: Axios 1.7
- **样式**: TailwindCSS 3.4
- **图标**: Iconify Vue

### 2.2 后端技术栈
- **Web框架**: Flask 3.0
- **异步任务**: Celery 5.4 + Redis 7.2
- **科学计算**: 
  - numpy 1.26, pandas 2.2
  - statsmodels 0.14 (GLM/MLM)
  - scikit-allel 1.3 (VCF处理, LD计算)
  - matplotlib 3.8, seaborn 0.13
- **数据库**: 
  - PostgreSQL 16 (用户、任务元数据)
  - SQLite (轻量级部署备选)
- **文件存储**: MinIO (本地对象存储)

### 2.3 初始化工具
- 前端: `npm create vite@latest`
- 后端: 手动搭建Flask项目结构

## 3. 路由定义

| 前端路由 | 页面 | 后端API前缀 |
|---------|------|-------------|
| /login | 登录页 | /api/auth |
| /upload | 数据上传页 | /api/upload |
| /analysis/config | 分析配置页 | /api/analysis |
| /tasks | 任务队列页 | /api/tasks |
| /results/:taskId | 结果可视化页 | /api/results |
| /reference | 参考基因组页 | /api/reference |
| /settings | 用户设置页 | /api/user |

## 4. API定义

```typescript
// ============ 文件上传相关 ============
interface FileUploadResponse {
  fileId: string;
  fileName: string;
  fileType: 'vcf' | 'phenotype' | 'covariate';
  sampleCount: number;
  variantCount?: number;
  uploadTime: string;
}

// POST /api/upload/vcf
// POST /api/upload/phenotype
// POST /api/upload/covariate

// ============ 样本匹配 ============
interface SampleMatchRequest {
  vcfFileId: string;
  phenotypeFileId: string;
}

interface SampleMatchResponse {
  matchedSamples: string[];
  vcfOnlySamples: string[];
  phenotypeOnlySamples: string[];
}

// POST /api/analysis/match-samples

// ============ PCA计算 ============
interface PCARequest {
  vcfFileId: string;
  nComponents: number;
}

interface PCAResponse {
  taskId: string;
  explainedVarianceRatio: number[];
  pcData: { sampleId: string; PC1: number; PC2: number; PC3: number }[];
}

// POST /api/analysis/pca

// ============ GWAS任务提交 ============
interface GWASRequest {
  vcfFileId: string;
  phenotypeFileId: string;
  phenotypeName: string;
  model: 'GLM' | 'MLM';
  covariates: {
    pcaComponents: number[];
    customCovariateFileId?: string;
    customCovariateNames: string[];
  };
  significanceThreshold: number;
  referenceGenome: string;
}

interface GWASResponse {
  taskId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  createdAt: string;
}

// POST /api/analysis/gwas

// ============ 任务查询 ============
interface TaskStatusResponse {
  taskId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  stage: string;
  errorMessage?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
}

// GET /api/tasks/:taskId
// GET /api/tasks?page=1&pageSize=20

// ============ GWAS结果 ============
interface GWASResultResponse {
  taskId: string;
  model: string;
  phenotype: string;
  inflationFactor: number;
  significantSNPCount: number;
  manhattanData: {
    chr: string;
    pos: number;
    snp: string;
    pValue: number;
    log10P: number;
  }[];
  qqData: {
    expected: number;
    observed: number;
  }[];
  significantSNPs: {
    snp: string;
    chr: string;
    pos: number;
    ref: string;
    alt: string;
    pValue: number;
    log10P: number;
    effectSize: number;
    maf: number;
    gene?: string;
    annotation?: string;
  }[];
}

// GET /api/results/:taskId

// ============ LD热图 ============
interface LDHeatmapRequest {
  vcfFileId: string;
  chr: string;
  start: number;
  end: number;
}

interface LDHeatmapResponse {
  snpNames: string[];
  positions: number[];
  ldMatrix: number[][];
  hapBlocks?: { start: number; end: number; snps: string[] }[];
}

// POST /api/analysis/ld-heatmap

// ============ 结果下载 ============
// GET /api/results/:taskId/download/manhattan.png
// GET /api/results/:taskId/download/qq.png
// GET /api/results/:taskId/download/ld-heatmap.png
// GET /api/results/:taskId/download/snps.csv
// GET /api/results/:taskId/download/report.pdf
```

## 5. 后端服务架构

```mermaid
graph TD
    subgraph "API层"
        A["API Routes (Flask)"]
        A1["auth_routes.py"]
        A2["upload_routes.py"]
        A3["analysis_routes.py"]
        A4["task_routes.py"]
        A5["result_routes.py"]
        A --> A1
        A --> A2
        A --> A3
        A --> A4
        A --> A5
    end

    subgraph "服务层"
        B["Services"]
        B1["AuthService"]
        B2["FileService"]
        B3["VCFParser"]
        B4["SampleMatcher"]
        B5["PCAService"]
        B6["GWASService"]
        B7["LDService"]
        B8["VisualizationService"]
        B --> B1
        B --> B2
        B --> B3
        B --> B4
        B --> B5
        B --> B6
        B --> B7
        B --> B8
    end

    subgraph "数据层"
        C["Data Access"]
        C1["UserRepository"]
        C2["FileRepository"]
        C3["TaskRepository"]
        C4["ResultRepository"]
        C5["ReferenceGenomeDB"]
        C --> C1
        C --> C2
        C --> C3
        C --> C4
        C --> C5
    end

    subgraph "任务队列"
        D["Celery Tasks"]
        D1["pca_calculation_task"]
        D2["gwas_glm_task"]
        D3["gwas_mlm_task"]
        D4["ld_analysis_task"]
        D5["visualization_task"]
    end

    A1 --> B1 --> C1
    A2 --> B2 --> C2
    A3 --> B3
    A3 --> B4
    A3 --> B5 --> D1
    A3 --> B6 --> D2
    A3 --> B6 --> D3
    A3 --> B7 --> D4
    A5 --> B8 --> D5
    D1 --> C2
    D2 --> C3
    D3 --> C3
    D4 --> C4
    D5 --> C4
    B6 --> C5
```

## 6. 数据模型

### 6.1 ER图

```mermaid
erDiagram
    USER ||--o{ UPLOAD_FILE : has
    USER ||--o{ ANALYSIS_TASK : creates
    ANALYSIS_TASK }o--|| UPLOAD_FILE : uses
    ANALYSIS_TASK ||--o{ GWAS_RESULT : produces
    GWAS_RESULT ||--o{ SIGNIFICANT_SNP : contains
    GWAS_RESULT ||--o{ VISUALIZATION_FILE : has
    REFERENCE_GENOME ||--o{ GENE_ANNOTATION : contains
    SIGNIFICANT_SNP }o--|| GENE_ANNOTATION : "annotated by"

    USER {
        uuid id PK
        string email
        string password_hash
        string name
        datetime created_at
        datetime last_login
    }

    UPLOAD_FILE {
        uuid id PK
        uuid user_id FK
        string file_name
        string file_type
        string storage_path
        int64 file_size
        json metadata
        datetime uploaded_at
    }

    ANALYSIS_TASK {
        uuid id PK
        uuid user_id FK
        string task_type
        string status
        json parameters
        float progress
        string current_stage
        text error_message
        datetime created_at
        datetime started_at
        datetime completed_at
    }

    GWAS_RESULT {
        uuid id PK
        uuid task_id FK
        string model_type
        string phenotype
        float inflation_factor
        int significant_snp_count
        json manhattan_data
        json qq_data
        datetime created_at
    }

    SIGNIFICANT_SNP {
        uuid id PK
        uuid result_id FK
        string snp_id
        string chromosome
        int position
        string ref_allele
        string alt_allele
        float p_value
        float log10_p
        float effect_size
        float maf
        string gene
        string annotation
    }

    VISUALIZATION_FILE {
        uuid id PK
        uuid result_id FK
        string file_type
        string file_path
        int width
        int height
        datetime created_at
    }

    REFERENCE_GENOME {
        string id PK
        string name
        string species
        string version
        string fasta_path
        string gff_path
        datetime created_at
    }

    GENE_ANNOTATION {
        uuid id PK
        string genome_id FK
        string gene_id
        string gene_name
        string chromosome
        int start_pos
        int end_pos
        string strand
        text description
    }
```

### 6.2 DDL语句

```sql
-- PostgreSQL DDL

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE upload_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL CHECK (file_type IN ('vcf', 'phenotype', 'covariate')),
    storage_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    metadata JSONB,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analysis_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    parameters JSONB NOT NULL,
    progress FLOAT DEFAULT 0,
    current_stage VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE gwas_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES analysis_tasks(id) ON DELETE CASCADE NOT NULL,
    model_type VARCHAR(10) NOT NULL,
    phenotype VARCHAR(100) NOT NULL,
    inflation_factor FLOAT,
    significant_snp_count INTEGER DEFAULT 0,
    manhattan_data JSONB,
    qq_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE significant_snps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    result_id UUID REFERENCES gwas_results(id) ON DELETE CASCADE NOT NULL,
    snp_id VARCHAR(100) NOT NULL,
    chromosome VARCHAR(20) NOT NULL,
    position INTEGER NOT NULL,
    ref_allele VARCHAR(50) NOT NULL,
    alt_allele VARCHAR(50) NOT NULL,
    p_value DOUBLE PRECISION NOT NULL,
    log10_p DOUBLE PRECISION NOT NULL,
    effect_size DOUBLE PRECISION,
    maf FLOAT,
    gene VARCHAR(100),
    annotation TEXT
);

CREATE TABLE visualization_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    result_id UUID REFERENCES gwas_results(id) ON DELETE CASCADE NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reference_genomes (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    species VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    fasta_path VARCHAR(500) NOT NULL,
    gff_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE gene_annotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    genome_id VARCHAR(50) REFERENCES reference_genomes(id) NOT NULL,
    gene_id VARCHAR(50) NOT NULL,
    gene_name VARCHAR(100),
    chromosome VARCHAR(20) NOT NULL,
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    strand CHAR(1),
    description TEXT
);

-- 索引
CREATE INDEX idx_snps_result_id ON significant_snps(result_id);
CREATE INDEX idx_snps_chr_pos ON significant_snps(chromosome, position);
CREATE INDEX idx_tasks_user_id ON analysis_tasks(user_id);
CREATE INDEX idx_tasks_status ON analysis_tasks(status);
CREATE INDEX idx_files_user_id ON upload_files(user_id);
CREATE INDEX idx_gene_ann_chr ON gene_annotations(chromosome, start_pos, end_pos);
```

## 7. 玉米参考基因组预存储配置

系统预配置以下常见玉米自交系参考基因组：

| 基因组ID | 名称 | 版本 | 说明 |
|---------|------|------|------|
| B73_v5 | B73 | v5 | 玉米标准参考基因组 |
| Mo17_v1 | Mo17 | v1 | 重要自交系 |
| W22_v2 | W22 | v2 | 常用实验品系 |
| PH207_v1 | PH207 | v1 | 玉米父本系 |
| B97_v1 | B97 | v1 | 耐旱自交系 |

参考基因组数据存储在 `/data/reference/maize/` 目录，包含FASTA序列和GFF注释文件。
