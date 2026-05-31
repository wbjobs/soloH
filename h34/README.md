# 农业病害预警系统 (AgriDiseaseAlert)

基于地理信息的作物病害实时监测与预警平台，集成多源气象数据、田间传感器和病害预测模型，提供1km分辨率的风险地图和未来7天预测。

## 技术栈

### 后端
- **Python 3.10+** - 编程语言
- **FastAPI** - 高性能Web框架
- **PostgreSQL + PostGIS** - 空间数据库
- **SQLAlchemy + GeoAlchemy2** - ORM和空间扩展
- **Pydantic** - 数据验证
- **Alembic** - 数据库迁移

### 前端
- **React 18** - UI框架
- **TypeScript** - 类型安全
- **Mapbox GL JS** - 地图渲染
- **Tailwind CSS** - 样式框架
- **Recharts** - 数据可视化
- **Axios** - HTTP客户端

### 核心功能
1. **多源数据采集** - 气象站、物联网传感器、WRF数值预报
2. **病害模型** - 小麦锈病(Jensen)、马铃薯晚疫病(Blightcast)
3. **风险计算** - 1km格点分辨率的感染风险指数
4. **预测预报** - 未来7天风险预测
5. **预警通知** - 邮件和Webhook触发
6. **用户配置** - 作物品种、抗性级别、风险阈值
7. **历史分析** - 风险回溯和统计分析

## 项目结构

```
h34/
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 数据库模型
│   │   ├── models/         # 病害模型
│   │   ├── schemas/        # Pydantic模式
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   └── tests/
├── frontend/               # React前端
│   ├── src/
│   │   ├── components/     # UI组件
│   │   ├── pages/          # 页面
│   │   ├── services/       # API服务
│   │   ├── store/          # 状态管理
│   │   ├── types/          # TypeScript类型
│   │   └── utils/          # 工具函数
│   └── public/
└── docker/                 # Docker配置
```

## 快速开始

### 后端启动
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动
```bash
cd frontend
npm install
npm run dev
```

### Docker 启动（推荐）
```bash
docker-compose up -d
```

### 初始化示例数据
```bash
cd backend
python -m scripts.init_sample_data
```

## API文档

启动后端后访问: http://localhost:8000/docs

## License

MIT
