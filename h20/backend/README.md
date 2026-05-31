# Bitcoin Transaction Graph Analysis Backend

比特币交易图谱分析后端服务，用于分析比特币交易网络、识别可疑交易模式、进行地址聚类和风险评估。

## 项目结构

```
backend/
├── app/                          # 主应用目录
│   ├── api/                      # API路由层
│   │   ├── __init__.py
│   │   ├── addresses.py          # 地址相关API
│   │   ├── analysis.py           # 分析相关API
│   │   ├── dependencies.py       # 依赖注入
│   │   ├── tasks.py              # 任务相关API
│   │   └── transactions.py       # 交易相关API
│   ├── core/                     # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py             # 配置管理
│   │   └── database.py           # 数据库连接
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   ├── analysis.py           # 分析模型（聚类、可疑模式）
│   │   ├── base.py               # 基础模型
│   │   ├── blockchain.py         # 区块链模型（区块、交易、地址）
│   │   └── task.py               # 任务模型
│   ├── repositories/             # 数据访问层
│   │   ├── __init__.py
│   │   ├── address_repository.py
│   │   ├── base.py
│   │   ├── cluster_repository.py
│   │   ├── graph_repository.py
│   │   ├── pattern_repository.py
│   │   ├── task_repository.py
│   │   └── transaction_repository.py
│   ├── schemas/                  # Pydantic模式
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   ├── blockchain.py
│   │   ├── common.py
│   │   ├── graph.py
│   │   └── task.py
│   ├── services/                 # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── address_service.py
│   │   ├── base.py
│   │   ├── clustering_service.py
│   │   ├── graph_service.py
│   │   ├── pattern_service.py
│   │   ├── task_service.py
│   │   └── transaction_service.py
│   ├── tasks/                    # 异步任务
│   │   ├── __init__.py
│   │   ├── analysis_tasks.py
│   │   ├── base_task.py
│   │   ├── celery_app.py
│   │   └── import_tasks.py
│   ├── utils/                    # 工具函数
│   │   ├── __init__.py
│   │   └── mock_data_generator.py  # Mock数据生成器
│   ├── __init__.py
│   └── main.py                   # FastAPI应用入口
├── scripts/                      # 脚本目录
│   ├── __init__.py
│   └── generate_mock_data.py     # Mock数据生成脚本
├── data/                         # 数据目录
│   └── sample_transactions.csv   # 示例交易数据CSV
├── migrations/                   # 数据库迁移
│   ├── 001_init.sql
│   └── __init__.py
├── run.py                        # 启动脚本
├── requirements.txt              # Python依赖
├── pyproject.toml                # Poetry配置
├── .env.example                  # 环境变量示例
└── README.md                     # 项目说明文档
```

## 功能特性

- **区块链数据管理**：支持区块、交易、地址、输入输出的完整数据模型
- **交易图谱分析**：构建地址间的交易关系图谱，支持图遍历和分析
- **地址聚类**：基于共同输入、找零地址等启发式算法进行地址聚类
- **可疑模式检测**：识别分层转账、循环交易、结构化拆分等可疑模式
- **风险评估**：对地址进行风险评分和风险等级划分
- **异步任务处理**：基于Celery的异步任务队列，支持大规模数据处理
- **WebSocket实时推送**：任务进度实时推送

## 环境要求

- Python 3.11+
- PostgreSQL 13+ （推荐使用TimescaleDB以获得更好的时序数据性能）
- Redis 6+ （用于Celery任务队列和缓存）

## 环境安装

### 方式一：使用pip

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 方式二：使用Poetry

```bash
cd backend

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

## 配置说明

复制环境变量示例文件并修改配置：

```bash
cp .env.example .env
```

主要配置项：

```env
# 数据库连接
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/bitcoin_trade_analysis

# Redis连接
REDIS_URL=redis://localhost:6379/0

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# API配置
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# 安全配置
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 数据库初始化

### 创建数据库

```sql
CREATE DATABASE bitcoin_trade_analysis;
```

### 执行数据库迁移

```bash
# 方式一：使用初始化脚本
python -c "from app.core.database import init_db; import asyncio; asyncio.run(init_db())"

# 方式二：使用SQL脚本
psql -U postgres -d bitcoin_trade_analysis -f migrations/001_init.sql
```

### 生成Mock数据（开发环境）

项目提供了完整的Mock数据生成器，用于开发和测试：

```bash
# 查看帮助
python scripts/generate_mock_data.py --help

# 生成所有Mock数据（100个地址，500笔交易）
python scripts/generate_mock_data.py all

# 生成指定数量的数据
python scripts/generate_mock_data.py all --addresses 200 --transactions 1000

# 生成数据前清空现有数据
python scripts/generate_mock_data.py all --clear

# 仅生成交易数据
python scripts/generate_mock_data.py transactions

# 仅生成可疑模式数据
python scripts/generate_mock_data.py patterns

# 仅生成地址聚类数据
python scripts/generate_mock_data.py clusters

# 仅生成任务数据
python scripts/generate_mock_data.py tasks

# 生成示例CSV文件
python scripts/generate_mock_data.py csv --count 20 --output data/sample_transactions.csv
```

Mock数据特性：
- 真实的比特币地址格式（P2PKH以1开头、P2SH以3开头、Bech32以bc1开头）
- 交易金额范围：0.0001 - 10 BTC
- 包含找零地址模式、共同输入等真实交易特征
- 内置8种可疑模式：分层转账、循环交易、结构化拆分等
- 完整的交易链路追踪（UTXO消耗追踪）

### 导入CSV数据

项目提供了示例CSV文件 `data/sample_transactions.csv`，格式如下：

```
txid,block_height,block_time,input_addresses,input_values,output_addresses,output_values,fee
```

其中多个地址和金额使用分号 `;` 分隔。

## 启动方式

### 方式一：使用启动脚本

```bash
python run.py
```

### 方式二：使用uvicorn直接运行

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 方式三：使用FastAPI CLI

```bash
fastapi run app/main.py --reload
```

### 启动Celery Worker（可选，用于异步任务）

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

## API文档访问方式

启动服务后，可以通过以下地址访问API文档：

1. **Swagger UI**（交互式文档）：
   - 地址：`http://localhost:8000/docs`
   - 功能：可以直接在浏览器中测试API接口

2. **ReDoc**（美观的文档）：
   - 地址：`http://localhost:8000/redoc`
   - 功能：适合阅读和分享的API文档

3. **OpenAPI JSON**：
   - 地址：`http://localhost:8000/openapi.json`
   - 功能：可以导入到Postman等API工具中

### 主要API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/v1/addresses` | GET | 获取地址列表 |
| `/api/v1/addresses/{address}` | GET | 获取地址详情 |
| `/api/v1/transactions` | GET | 获取交易列表 |
| `/api/v1/transactions/{txid}` | GET | 获取交易详情 |
| `/api/v1/analysis/clusters` | GET | 获取地址聚类 |
| `/api/v1/analysis/patterns` | GET | 获取可疑模式 |
| `/api/v1/analysis/graph` | GET | 获取交易图谱 |
| `/api/v1/tasks` | GET | 获取任务列表 |
| `/api/v1/tasks/{task_id}` | GET | 获取任务详情 |
| `/ws/task/{task_id}` | WS | 任务进度WebSocket |

## 开发指南

### 代码风格

项目使用以下工具保证代码质量：
- **Black**：代码格式化
- **Ruff**：代码检查和导入排序

```bash
# 格式化代码
black .

# 代码检查
ruff check .

# 自动修复
ruff check --fix .
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/ -v

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

## 常见问题

### 1. 数据库连接失败

确保PostgreSQL服务已启动，并且配置的用户名、密码、数据库名正确。

### 2. Mock数据生成失败

检查数据库表是否已正确创建，可以尝试重新初始化数据库：

```bash
python -c "from app.core.database import init_db; import asyncio; asyncio.run(init_db())"
```

### 3. 导入CSV数据时格式错误

确保CSV文件格式正确，多个地址和金额之间使用分号 `;` 分隔，金额为8位小数的BTC数值。

## License

MIT License
