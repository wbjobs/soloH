# RNA Secondary Structure Prediction API

基于Zuker算法的RNA二级结构预测RESTful API服务，使用Go + Gin框架实现。

## 功能特性

- **Zuker算法**：O(n³)动态规划实现，预测最小自由能二级结构
- **点括号表示法**：返回RNA二级结构的标准点括号表示
- **碱基对概率**：使用配分函数计算各碱基对的配对概率
- **Redis缓存**：自动缓存重复序列的预测结果，提升响应速度
- **PostgreSQL约束**：存储已知RNA家族的结构约束条件
- **容错设计**：Redis/PostgreSQL连接失败时仍可正常运行核心功能

## 项目结构

```
e:\soloH\h6\
├── api/
│   └── handler.go          # API路由和处理器
├── cache/
│   └── redis.go            # Redis缓存层
├── config/
│   └── config.go           # 配置管理
├── db/
│   └── postgres.go         # PostgreSQL数据库层
├── models/
│   └── models.go           # 数据模型定义
├── zuker/
│   └── zuker.go            # Zuker算法核心实现
├── main.go                 # 主程序入口
├── go.mod
├── go.sum
├── .env                    # 环境变量
├── .env.example            # 环境变量示例
├── Dockerfile              # Docker镜像构建
├── docker-compose.yml      # 服务编排
├── init_db.sql             # 数据库初始化脚本
├── test_api.sh             # Linux/Mac测试脚本
└── test_api.ps1            # Windows测试脚本
```

## 快速开始

### 方式一：使用Docker Compose（推荐）

```bash
docker-compose up -d --build
```

### 方式二：本地运行

1. **安装Go 1.21+**
   - Windows: `winget install GoLang.Go`
   - 或从 https://go.dev/dl/ 下载安装

2. **启动依赖服务**
   ```bash
   docker-compose up -d redis postgres
   ```

3. **安装依赖并运行**
   ```bash
   go mod download
   go run main.go
   ```

## API接口

### 1. 预测RNA二级结构

**POST** `/api/v1/predict`

请求体：
```json
{
  "sequence": "AUGCAUCGUAUGCAUCG"
}
```

响应：
```json
{
  "sequence": "AUGCAUCGUAUGCAUCG",
  "structure": "(((...)))(((...)))",
  "min_free_energy": -12.5,
  "base_pair_probabilities": [
    {
      "i": 0,
      "j": 8,
      "base_i": "A",
      "base_j": "U",
      "probability": 0.95
    }
  ],
  "from_cache": false,
  "family_constraint": null
}
```

### 2. 获取RNA家族列表

**GET** `/api/v1/families`

### 3. 清除缓存

**DELETE** `/api/v1/cache`

### 4. 健康检查

**GET** `/health`

## 算法说明

### Zuker算法核心实现

位于 [zuker/zuker.go](file:///e:/soloH/h6/zuker/zuker.go#L1-L334)

- **动态规划表**：V[i][j]（i,j配对时的最小能量），W[i][j]（区间i,j的最小能量）
- **时间复杂度**：O(n³)
- **能量模型**：简化的Turner能量参数，支持GC、AU、GU配对
- **回溯**：从DP表重建点括号结构

### 碱基对概率计算

使用配分函数（Partition Function）和玻尔兹曼分布：
- Q[i][j]：区间i,j的配分函数
- P(i,j) = exp(-E(i,j)/kT) × Q(i+1,j-1) / Q(0,n-1)

### 家族约束系统

位于 [db/postgres.go](file:///e:/soloH/h6/db/postgres.go#L1-L198)

预定义的RNA家族：
- **tRNA-like**：类tRNA结构模式
- **Stem-loop**：茎环结构模式
- **miRNA**：微小RNA模式（21-23nt）

约束类型：
- `must_pair`：必须配对的碱基位置
- `must_unpair`：必须不配对的碱基位置

## 测试

Windows PowerShell:
```powershell
.\test_api.ps1
```

Linux/Mac:
```bash
chmod +x test_api.sh
./test_api.sh
```

## 配置说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| PORT | 8080 | 服务端口 |
| REDIS_HOST | localhost | Redis主机 |
| REDIS_PORT | 6379 | Redis端口 |
| REDIS_TTL_SECONDS | 86400 | 缓存过期时间（秒） |
| POSTGRES_HOST | localhost | PostgreSQL主机 |
| POSTGRES_PORT | 5432 | PostgreSQL端口 |
| POSTGRES_DB | rna_db | 数据库名 |

## 示例请求

```bash
curl -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": "AUGCAUCGUAUGCAUCG"}'
```
