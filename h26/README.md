# Protein Contact Map Prediction API

使用 PyTorch + FastAPI 实现的蛋白质接触图预测服务。

## 功能特性

- **FASTA 输入**: 接收标准 FASTA 格式的氨基酸序列
- **ResNet 架构**: 使用预训练的 ResNet 模型进行接触图预测
- **输入特征**: one-hot 编码 + 位置特异性打分矩阵 (PSSM)
- **输出**: LxL 接触图 (8Å 阈值)
- **后处理**:
  - 接触列表输出
  - Top-L 接触精度计算
  - 3D 坐标粗略重建 (多维缩放 MDS)
- **多个预训练模型**:
  - `resnet18_pdb`: ResNet-18, PDB 数据集训练
  - `resnet34_pdb`: ResNet-34, PDB 数据集训练
  - `resnet50_pdb`: ResNet-50, PDB 数据集训练 (默认)
  - `resnet101_pdb`: ResNet-101, PDB 数据集训练
  - `resnet50_casp14`: CASP14 竞赛冠军模型
  - `resnet50_casp15`: CASP15 竞赛冠军模型
- **PostgreSQL 存储**: 序列和预测任务状态持久化
- **Celery 后台任务**: 异步处理长时预测任务

## 项目结构

```
protein_contact_prediction/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 主入口
│   ├── config.py               # 配置管理
│   ├── database.py             # PostgreSQL 连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db.py               # 数据库 ORM 模型
│   │   └── resnet.py           # ResNet 模型架构
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── api.py              # Pydantic 数据模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── prediction.py       # 预测业务逻辑
│   │   └── model_loader.py     # 模型加载管理
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_config.py    # Celery 配置
│   │   └── celery_tasks.py     # Celery 任务
│   └── utils/
│       ├── __init__.py
│       ├── fasta_parser.py     # FASTA 解析
│       ├── encoding.py         # one-hot 编码
│       ├── pssm.py             # PSSM 生成
│       └── postprocessing.py   # 后处理 (MDS, Top-L 精度)
├── data/
│   ├── models/                 # 预训练模型权重目录
│   └── example.fasta           # 示例 FASTA 文件
├── requirements.txt
├── .env.example
├── init_db.py                  # 数据库初始化脚本
├── celery_worker.py            # Celery Worker 入口
├── start_server.bat            # 服务启动脚本 (Windows)
├── start_worker.bat            # Worker 启动脚本 (Windows)
└── test_api.py                 # API 测试脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置:

```bash
copy .env.example .env
```

关键配置:
- `DATABASE_URL`: PostgreSQL 连接地址
- `CELERY_BROKER_URL`: Redis 连接地址
- `MODEL_CACHE_DIR`: 预训练模型缓存目录
- `BLAST_DB_PATH`, `PSIBLAST_PATH`: BLAST 相关路径 (可选)

### 3. 启动服务依赖

确保 PostgreSQL 和 Redis 服务已启动:

```bash
# 启动 PostgreSQL
# 启动 Redis
```

### 4. 初始化数据库

```bash
python init_db.py
```

### 5. 启动 API 服务

```bash
# Windows
start_server.bat

# 或手动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 启动 Celery Worker (可选，用于异步任务)

```bash
# Windows
start_worker.bat

# 或手动
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2 -P solo
```

## API 使用

### 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要端点

#### 1. 健康检查
```http
GET /health
```

#### 2. 获取可用模型
```http
GET /models
```

#### 3. 异步预测 (推荐)
```http
POST /predict
Content-Type: application/json

{
    "fasta": ">protein1\nMALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA",
    "model_name": "resnet50_pdb"
}
```

返回任务 ID，用于后续查询结果。

#### 4. 查询任务状态
```http
GET /predict/{task_id}
```

#### 5. 获取预测结果
```http
GET /predict/{task_id}/result
```

返回格式:
```json
{
    "task_id": "uuid",
    "status": "completed",
    "model_name": "resnet50_pdb",
    "sequence_length": 51,
    "num_contacts": 45,
    "threshold_angstrom": 8.0,
    "contact_list": [
        {"i": 0, "j": 10, "probability": 0.95, "distance": 5.2},
        ...
    ],
    "precision_metrics": {
        "top_1L_count": 51,
        "top_1L_avg_prob": 0.78,
        "top_2L_count": 102,
        ...
    },
    "coordinates_3d": [
        [x1, y1, z1],
        [x2, y2, z2],
        ...
    ],
    "inference_time_ms": 1234.5
}
```

#### 6. 同步预测 (直接返回结果)
```http
POST /predict/sync
Content-Type: application/json

{
    "fasta": ">protein1\nMALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA",
    "model_name": "resnet18_pdb"
}
```

### 测试

运行 API 测试套件:

```bash
python test_api.py
```

## 技术细节

### 模型输入

- **one-hot 编码**: 20 维，对应标准氨基酸
- **PSSM**: 20 维，位置特异性打分矩阵
- **输入维度**: (batch, 80, L, L) - 40维特征外积拼接得到80通道

### 模型输出

- **接触图**: (L, L) 对称矩阵，值范围 [0, 1] 表示接触概率
- **阈值**: 8Å，Cβ-Cβ 距离小于 8Å 定义为接触

### 后处理

1. **接触列表**: 提取概率 > 0.5 且序列分离 > 6 的残基对
2. **Top-L 精度**: 计算 Top-L, Top-2L, Top-5L 的平均概率和数量
3. **MDS 重建**: 从接触概率矩阵反推 3D 坐标 (粗略估计)

### 预训练模型

将预训练的 `.pt` 权重文件放入 `data/models/` 目录，文件名需与模型名称一致:
- `resnet50_pdb.pt`
- `resnet50_casp14.pt`
- 等等

## License

MIT
