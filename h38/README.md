# CRISPR Off-Target Predictor

基于Python FastAPI + PyTorch的CRISPR sgRNA脱靶位点预测服务。

## 功能特性

- **深度学习预测**: 采用CNN + LSTM + Attention架构，训练自CRISOT和GUIDE-seq数据
- **灵活搜索**: 支持错配和碱基插入缺失检测
- **多维度分析**: 输出基因组坐标、错配数、评分、GC含量等信息
- **智能排序过滤**: 支持按评分、错配数等多字段排序，多维度结果过滤
- **IGV可视化**: 自动生成IGV基因组浏览器可视化链接
- **Redis缓存**: 缓存常见sgRNA结果，提升响应速度
- **批量处理**: 支持多sgRNA批量提交分析
- **RESTful API**: 完整的FastAPI接口，支持在线文档

## 技术栈

- **Web框架**: FastAPI 0.109+
- **深度学习**: PyTorch 2.1+
- **数据处理**: NumPy, Pandas, Biopython
- **基因组处理**: pyfaidx
- **缓存**: Redis 5.0+
- **API文档**: Swagger UI / ReDoc

## 项目结构

```
h38/
├── app/
│   ├── __init__.py
│   ├── config.py                 # 配置管理
│   ├── constants.py              # 常量定义
│   ├── api/
│   │   ├── __init__.py
│   │   ├── schemas.py            # 请求/响应模型
│   │   ├── dependencies.py       # 依赖注入
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── routes.py         # 主业务路由
│   │       └── health.py         # 健康检查路由
│   ├── data_processing/
│   │   ├── __init__.py
│   │   ├── sequence_utils.py     # 序列处理工具
│   │   ├── sequence_encoder.py   # 序列编码
│   │   └── genome_handler.py     # 基因组处理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── crispr_model.py       # CNN + LSTM模型
│   │   └── model_utils.py        # 模型工具
│   ├── offtarget_search/
│   │   ├── __init__.py
│   │   ├── offtarget_finder.py   # 脱靶位点查找器
│   │   └── search_algorithm.py   # 搜索算法
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis_cache.py        # Redis缓存
│   ├── visualization/
│   │   ├── __init__.py
│   │   └── igv_linker.py         # IGV链接生成
│   └── filtering/
│       ├── __init__.py
│       └── results_filter.py     # 结果过滤排序
├── scripts/
│   ├── download_genome.py        # 下载hg38基因组
│   └── train_model.py            # 模型训练脚本
├── tests/
│   ├── __init__.py
│   ├── test_api.py               # API测试
│   └── test_sequence_utils.py    # 序列工具测试
├── data/                         # 基因组数据目录
├── models/                       # 训练好的模型目录
├── main.py                       # FastAPI主入口
├── requirements.txt              # Python依赖
├── pyproject.toml                # 项目配置
├── .env.example                  # 环境变量示例
└── README.md
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，根据需要配置：
- `GENOME_REFERENCE_PATH`: hg38参考基因组路径
- `MODEL_PATH`: 训练好的模型路径
- `REDIS_HOST`/`REDIS_PORT`: Redis连接信息
- `IGV_BASE_URL`: IGV服务地址

### 3. 下载参考基因组

```bash
python scripts/download_genome.py --output-dir ./data
```

或手动从UCSC下载hg38.fa放入data目录。

### 4. 训练模型（可选）

使用虚拟数据训练测试模型：

```bash
python scripts/train_model.py --epochs 20 --num-samples 5000
```

生产环境请使用CRISOT和GUIDE-seq真实数据训练。

### 5. 启动Redis

```bash
# Docker方式
docker run -d -p 6379:6379 redis:alpine

# 或本地Redis
redis-server
```

### 6. 启动服务

```bash
python main.py

# 或使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API接口

### 1. sgRNA序列验证

```bash
curl -X POST "http://localhost:8000/api/v1/offtarget/validate?sgrna=GACCCCCTCCACCCCGCCTCCGGG"
```

响应：
```json
{
  "valid": true,
  "sgrna": "GACCCCCTCCACCCCGCCTCC",
  "pam": "GGG",
  "gc_content": 0.75,
  "errors": []
}
```

### 2. 单条sgRNA脱靶预测

```bash
curl -X POST "http://localhost:8000/api/v1/offtarget/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "sgrna": "GACCCCCTCCACCCCGCCTCCGGG",
    "max_mismatches": 6,
    "max_indel": 2,
    "use_cache": true,
    "include_igv_links": true
  }'
```

### 3. 带过滤和排序的预测

```bash
curl -X POST "http://localhost:8000/api/v1/offtarget/predict?page=1&page_size=50" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "sgrna": "GACCCCCTCCACCCCGCCTCCGGG",
      "max_mismatches": 4
    },
    "filter_params": {
      "min_score": 0.3,
      "max_mismatches": 3
    },
    "sort_params": {
      "field": "score",
      "order": "desc"
    },
    "pagination": {
      "page": 1,
      "page_size": 50
    }
  }'
```

### 4. 批量sgRNA预测

```bash
curl -X POST "http://localhost:8000/api/v1/offtarget/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "sgrnas": [
      {"sgrna": "GACCCCCTCCACCCCGCCTCCGGG"},
      {"sgrna": "ATCGAATCGATCGATCGATCGGG"}
    ],
    "max_mismatches": 4
  }'
```

### 5. 生成IGV链接

```bash
curl -X POST "http://localhost:8000/api/v1/offtarget/igv-link" \
  -H "Content-Type: application/json" \
  -d '{
    "chromosome": "chr1",
    "start": 1000000,
    "end": 1000023,
    "strand": "+",
    "expand": 100
  }'
```

### 6. 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

### 7. 缓存统计

```bash
curl http://localhost:8000/api/v1/health/stats
```

## 响应字段说明

### OffTargetSiteResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| sgrna | string | 输入的sgRNA序列 |
| target_sequence | string | 靶位点序列 |
| chromosome | string | 染色体 (chr1-chr22, chrX, chrY, chrM) |
| start | int | 起始坐标 |
| end | int | 终止坐标 |
| strand | string | 链 (+/-) |
| mismatches | int | 错配数 |
| insertions | int | 插入数 |
| deletions | int | 缺失数 |
| score | float | 综合评分 (0-1) |
| raw_score | float | 模型原始评分 |
| mismatch_details | array | 错配详情列表 |
| aligned_sgrna | string | 比对后的sgRNA |
| aligned_target | string | 比对后的靶序列 |
| off_target_type | string | 脱靶类型: exact/mismatch/insertion/deletion/mixed |
| gc_content | float | GC含量 |
| igv_link | string | IGV可视化链接 |
| pam_sequence | string | PAM序列 |
| genomic_coordinate | string | 基因组坐标字符串 |

### 评分说明

- **score**: 综合考虑模型预测、错配数、插入缺失的最终评分
- **0.7 - 1.0**: 高风险脱靶位点
- **0.3 - 0.7**: 中等风险脱靶位点
- **0.0 - 0.3**: 低风险脱靶位点

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_sequence_utils.py -v

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## 深度学习模型架构

### CRISPRModel

**输入**: sgRNA和靶序列的one-hot编码 + 错配特征 (shape: [batch, 12, 23])

**网络结构**:
1. **多尺度CNN层**: 3个并行卷积分支 (3x1, 5x1, 7x1)，提取不同尺度的序列特征
2. **双向LSTM层**: 2层双向LSTM，捕获序列上下文依赖
3. **注意力机制**: 学习关键位置的权重
4. **全连接层**: 融合CNN和LSTM特征，输出最终评分

**训练数据**:
- CRISOT数据集
- GUIDE-seq数据集
- 正负样本平衡处理
- 数据增强（错配、插入、缺失模拟）

## 性能优化建议

1. **基因组索引**: 预构建hg38.fai索引
2. **GPU加速**: 使用CUDA训练和推理
3. **缓存策略**: 热门sgRNA结果自动缓存到Redis
4. **批量处理**: 多sgRNA任务并行处理
5. **k-mer索引**: 对大基因组建立k-mer索引加速搜索

## 部署建议

### Docker部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 生产环境配置

```bash
# 使用多worker
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 使用gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## 常见问题

**Q: 基因组文件太大，下载慢怎么办？**
A: 可以使用UCSC的rsync服务器，或下载只包含主要染色体的版本。

**Q: Redis不可用怎么办？**
A: 系统会自动降级，不使用缓存继续工作，只是响应速度会变慢。

**Q: 如何使用真实数据训练模型？**
A: 修改scripts/train_model.py，替换create_dummy_training_data为真实数据加载逻辑。

**Q: 支持哪些PAM序列？**
A: 默认支持NGG、NAG、NGA，可在constants.py中配置。

## 引用

本项目参考了以下研究：
- CRISOT dataset
- GUIDE-seq technology
- Various CRISPR off-target prediction methods

## License

MIT License
