# Satellite Ozone Data Analysis API

基于 FastAPI + Xarray + Dask 的卫星臭氧（TOMS/OMI）数据分析服务。

## 功能特性

- **NetCDF 数据读取**: 支持多文件合并、Dask 分布式计算
- **趋势分析**: Sen 斜率估计 + Mann-Kendall 显著性检验
- **季节分解**: STL (Seasonal-Trend decomposition using Loess)
- **臭氧空洞检测**: 基于 220 DU 阈值的南极臭氧空洞识别
- **GeoJSON 输出**: 为前端地图可视化提供标准 GeoJSON 格式
- **Parquet 缓存**: 自动缓存计算结果，提高响应速度
- **动态过滤**: 支持时间范围、纬度带、季节的灵活过滤

## 项目结构

```
h24/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 主应用
│   ├── api/
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic 数据模型
│   │   └── routes.py              # API 路由
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # 配置管理
│   │   └── dask_client.py         # Dask 客户端
│   ├── data/
│   │   ├── __init__.py
│   │   └── loader.py              # NetCDF 数据加载器
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── trend.py               # 趋势分析 (Sen斜率 + MK检验)
│   │   ├── stl.py                 # 季节分解
│   │   └── ozone_hole.py          # 臭氧空洞检测
│   └── cache/
│       ├── __init__.py
│       └── parquet_cache.py       # Parquet 缓存管理
├── scripts/
│   └── generate_sample_data.py    # 示例数据生成脚本
├── data/                          # NetCDF 数据目录
├── cache/                         # Parquet 缓存目录
├── requirements.txt
├── .env
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 生成示例数据

```bash
python scripts/generate_sample_data.py --start-year 1980 --end-year 2024
```

或生成年度文件：

```bash
python scripts/generate_sample_data.py --start-year 1980 --end-year 2024 --annual
```

### 3. 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或直接运行：

```bash
python app/main.py
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 网格信息

- `GET /api/v1/grid/info` - 获取数据集基本信息

### 趋势分析

- `POST /api/v1/trend/point` - 查询任意经纬度的趋势值和显著性
- `POST /api/v1/trend/grid` - 获取全球网格趋势的 GeoJSON

### 季节分解

- `POST /api/v1/stl/point` - 单点 STL 分解
- `POST /api/v1/stl/grid` - 全球季节振幅 GeoJSON

### 臭氧空洞

- `POST /api/v1/ozone-hole/timeseries` - 臭氧空洞面积时序
- `POST /api/v1/ozone-hole/geojson` - 臭氧空洞分布 GeoJSON
- `GET /api/v1/ozone-hole/climatology` - 臭氧空洞气候态统计

### 数据查询

- `POST /api/v1/data/point` - 查询单点原始数据

### 缓存管理

- `GET /api/v1/cache/info` - 缓存状态信息
- `GET /api/v1/cache/keys` - 缓存键列表
- `POST /api/v1/cache/clear` - 清除缓存

### 辅助信息

- `GET /api/v1/latitude-bands` - 可用纬度带列表
- `GET /api/v1/seasons` - 可用季节列表

## 请求示例

### 查询单点趋势

```bash
curl -X POST "http://localhost:8000/api/v1/trend/point" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -75.0,
    "lon": 0.0,
    "start_date": "1980-01-01",
    "end_date": "2024-12-31",
    "alpha": 0.05
  }'
```

### 获取全球趋势 GeoJSON

```bash
curl -X POST "http://localhost:8000/api/v1/trend/grid" \
  -H "Content-Type: application/json" \
  -d '{
    "value_field": "sen_slope",
    "latitude_band": "antarctic"
  }'
```

### 获取臭氧空洞面积时序

```bash
curl -X POST "http://localhost:8000/api/v1/ozone-hole/timeseries" \
  -H "Content-Type: application/json" \
  -d '{
    "threshold": 220.0,
    "lat_min": -90.0,
    "lat_max": -50.0,
    "season": "SON"
  }'
```

### 动态过滤示例

```bash
curl -X POST "http://localhost:8000/api/v1/trend/grid" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2000-01-01",
    "end_date": "2024-12-31",
    "lat_min": -60.0,
    "lat_max": 60.0,
    "latitude_band": "southern_hemisphere",
    "season": "JJA",
    "value_field": "significant"
  }'
```

## 核心算法说明

### Sen 斜率估计

Sen 斜率是一种非参数趋势估计方法，计算所有时间点对之间斜率的中位数：

```
slope = median((x_j - x_i) / (j - i)) for all i < j
```

### Mann-Kendall 检验

Mann-Kendall 检验用于检测时间序列的单调趋势，无需假设数据分布：

- 原假设 (H0): 数据中不存在单调趋势
- 备择假设 (H1): 数据中存在单调递增或递减趋势

### STL 季节分解

STL 使用局部加权回归 (Loess) 将时间序列分解为：
- 趋势分量 (Trend)
- 季节分量 (Seasonal)
- 残差分量 (Residual)

### 臭氧空洞检测

- 阈值: < 220 Dobson Units (DU)
- 区域: 南纬 50° 以南
- 面积计算: 基于球面积分的网格面积加权求和

## 配置说明

编辑 `.env` 文件进行配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATA_DIR` | NetCDF 数据目录 | `e:/soloH/h24/data` |
| `CACHE_DIR` | Parquet 缓存目录 | `e:/soloH/h24/cache` |
| `DASK_SCHEDULER` | Dask 调度器 | `threads` |
| `DASK_WORKERS` | Dask 工作进程数 | `4` |
| `OZONE_HOLE_THRESHOLD` | 臭氧空洞阈值 (DU) | `220.0` |
| `CACHE_TTL_HOURS` | 缓存过期时间 (小时) | `24` |
| `ENABLE_CACHE` | 是否启用缓存 | `true` |

## 性能优化

1. **Dask 分布式计算**: 大规模网格计算自动并行化
2. **Parquet 缓存**: 计算结果自动缓存，支持 TTL 过期
3. **按需加载**: 仅加载请求范围内的数据
4. **分块读取**: NetCDF 文件以 Dask 数组形式分块读取

## 技术栈

- **FastAPI**: 高性能 Web 框架
- **Xarray**: 多维数组处理
- **Dask**: 并行计算
- **NetCDF4**: NetCDF 文件读写
- **PyMannKendall**: Mann-Kendall 检验
- **StatsModels**: STL 季节分解
- **PyArrow**: Parquet 格式支持
- **GeoJSON**: 地理空间数据格式

## 数据来源

示例数据为合成数据。实际使用时请放置真实的 TOMS/OMI 臭氧数据到 `data/` 目录：

- TOMS: https://disc.gsfc.nasa.gov/datasets/TOMS_L3_TOZ_008/summary
- OMI: https://disc.gsfc.nasa.gov/datasets/OMI_Aura_L3_TOZ_003/summary

## License

MIT License
