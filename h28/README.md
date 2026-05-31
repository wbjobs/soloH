# 古籍文字识别系统

基于深度学习的竖排古籍文字OCR识别系统，支持繁体异体字识别、版式智能还原、在线校对和多格式导出。

## 技术架构

### 前端
- **框架**: Vue 3 + Composition API + TypeScript
- **构建工具**: Vite 5
- **UI组件库**: Element Plus
- **状态管理**: Pinia
- **WebSocket**: socket.io-client
- **客户端OCR**: Tesseract.js (降级方案)
- **设计风格**: 宣纸米白 + 篆刻朱红，宋体字体

### 后端
- **Web框架**: Flask 3.0
- **WebSocket**: Flask-SocketIO 5.3
- **异步任务**: Celery 5.3 + Redis
- **ORM**: SQLAlchemy 2.0
- **数据库**: SQLite (开发) / PostgreSQL (生产)

### 深度学习
- **框架**: PyTorch 2.1
- **文字检测**: CTPN (Connectionist Text Proposal Network)
- **文字识别**: CRNN + Attention (支持繁体异体字)
- **自动标点**: BERT (bert-base-chinese 微调)
- **后处理**: 连通域分析 + 行列合并

## 功能特性

✅ **文件上传**: 支持图片(JPG/PNG/TIFF)和PDF上传，拖拽上传  
✅ **异步处理**: Celery任务队列，不阻塞用户操作  
✅ **实时进度**: WebSocket推送处理进度和阶段状态  
✅ **CTPN检测**: 支持竖排文字区域检测，四点坐标输出  
✅ **CRNN识别**: 支持繁体、简体、异体字识别，候选词输出  
✅ **智能版式**: 连通域分析，行列合并，还原原书竖排分栏  
✅ **自动标点**: BERT模型智能添加标点符号  
✅ **校对编辑**: 左右双栏编辑器，点击文字即可修改，候选词推荐  
✅ **多格式导出**: Markdown、TEI XML、TXT、JSON  
✅ **降级方案**: 后端不可用时使用Tesseract.js浏览器端识别  
✅ **响应式设计**: 支持桌面端、平板和移动端  

## 项目结构

```
h28/
├── frontend/                 # 前端Vue应用
│   ├── src/
│   │   ├── api/              # API接口定义
│   │   ├── components/       # Vue组件
│   │   ├── composables/      # 组合式函数
│   │   ├── router/           # 路由配置
│   │   ├── stores/           # Pinia状态管理
│   │   ├── types/            # TypeScript类型定义
│   │   ├── utils/            # 工具函数 (含Tesseract.js)
│   │   └── views/            # 页面组件
│   └── package.json
│
├── backend/                  # 后端Flask应用
│   ├── app/
│   │   ├── api/              # API路由
│   │   ├── controllers/      # 控制器层
│   │   ├── services/         # 业务逻辑层
│   │   ├── repositories/     # 数据访问层
│   │   ├── models/           # 数据模型
│   │   └── schemas/          # 序列化模式
│   ├── ml/                   # 深度学习模块
│   │   ├── detection/        # CTPN检测
│   │   ├── recognition/      # CRNN识别
│   │   ├── punctuation/      # BERT标点
│   │   └── postprocessing/   # 后处理与版式分析
│   ├── tasks/                # Celery任务
│   └── requirements.txt
│
├── storage/                  # 文件存储
│   ├── uploads/              # 上传文件
│   ├── processed/            # 处理结果
│   └── exports/              # 导出文件
│
├── docker-compose.yml        # Docker编排
├── start-all.bat             # Windows一键启动
├── start-backend.bat         # 后端启动脚本
└── start-frontend.bat        # 前端启动脚本
```

## 快速开始

### 方式一：Windows一键启动

```bash
# 启动全套服务
start-all.bat

# 或分别启动
start-backend.bat
start-frontend.bat
```

### 方式二：Docker启动

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

### 方式三：手动启动

#### 后端 (Python 3.10+)

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动Flask服务
python run.py

# 另起终端启动Celery Worker (需要Redis)
celery -A celery_worker.celery worker --loglevel=info --pool=solo
```

#### 前端 (Node.js 18+)

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 访问地址

- **前端应用**: http://localhost:5173
- **后端API**: http://localhost:5000
- **健康检查**: http://localhost:5000/api/health
- **WebSocket**: ws://localhost:5000/socket.io

## API文档

### 文件上传

```http
POST /api/files/upload
Content-Type: multipart/form-data

{
  "file": <binary>
}

Response: 201 Created
{
  "id": "task-uuid",
  "fileName": "example.pdf",
  "fileType": "pdf",
  "status": "pending",
  "progress": 0,
  "pageCount": 10
}
```

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tasks?page=1&perPage=10` | 获取任务列表 |
| GET | `/api/tasks/:id` | 获取任务详情 |
| GET | `/api/tasks/:id/result` | 获取识别结果 |
| PUT | `/api/tasks/:id/result` | 保存校对修改 |
| POST | `/api/tasks/:id/rerun` | 重新识别 |
| DELETE | `/api/tasks/:id` | 删除任务 |

### 导出

```http
GET /api/tasks/:id/export?format=markdown&include_confidence=true

# format: markdown | tei | txt | json
```

## WebSocket事件

### 客户端发送

```javascript
// 订阅任务进度
socket.emit('join-task', { taskId: 'task-uuid' })

// 取消订阅
socket.emit('leave-task', { taskId: 'task-uuid' })
```

### 服务端推送

| 事件 | 数据 | 描述 |
|------|------|------|
| `progress` | `{ taskId, status, progress, message, currentPage, totalPages }` | 处理进度 |
| `completed` | `{ taskId, result }` | 处理完成 |
| `failed` | `{ taskId, error }` | 处理失败 |

## 处理流程

```
用户上传文件
    ↓
文件解析 (PDF转图片 / 图片预处理)
    ↓
加入Celery任务队列
    ↓
WebSocket推送: 等待中
    ↓
CTPN文字检测 → 输出四点坐标检测框
    ↓
WebSocket推送: 检测完成 xx%
    ↓
CRNN文字识别 → 输出文本 + 候选词 + 置信度
    ↓
WebSocket推送: 识别完成 xx%
    ↓
连通域分析 + 行列合并 → 竖排版式重构
    ↓
WebSocket推送: 后处理完成 xx%
    ↓
BERT自动标点 → 智能添加标点符号
    ↓
WebSocket推送: 处理完成 100%
    ↓
进入校对编辑器
    ↓
用户点击修改，候选词推荐
    ↓
导出为 Markdown / TEI XML
```

## 核心模块说明

### 深度学习模块 (`backend/ml/`)

| 模块 | 文件 | 说明 |
|------|------|------|
| CTPN检测 | `detection/ctpn_detector.py` | 文字区域检测，支持Mock模式 |
| CRNN识别 | `recognition/crnn_recognizer.py` | 文字识别，支持繁体异体字 |
| BERT标点 | `punctuation/bert_punctuator.py` | 标点符号自动添加 |
| 后处理 | `postprocessing/post_processor.py` | 连通域分析、行列合并 |
| 版式分析 | `postprocessing/layout_analyzer.py` | 竖排分栏版式重构 |

> 💡 所有ML模块均支持Mock模式，在没有训练好的模型文件时也能正常运行，生成模拟数据用于测试和演示。

### 前端组件 (`frontend/src/components/`)

| 组件 | 文件 | 说明 |
|------|------|------|
| 上传区域 | `UploadArea.vue` | 拖拽上传、进度显示 |
| 进度面板 | `ProgressPanel.vue` | 实时进度、阶段展示 |
| 图片查看器 | `ImageViewer.vue` | 原图预览、检测框叠加 |
| 文本编辑器 | `TextEditor.vue` | 竖排版式、点击编辑 |
| 候选词下拉 | `CandidateDropdown.vue` | 候选词选择、键盘导航 |
| 导出对话框 | `ExportDialog.vue` | 格式选择、导出配置 |

## Tesseract.js降级方案

当后端服务不可用或用户选择本地识别时，系统自动降级使用Tesseract.js在浏览器端进行OCR识别。

```typescript
import { tesseractOCR } from '@/utils/tesseract';

// 识别竖排文字
const result = await tesseractOCR.recognizeVerticalText(
  imageFile,
  (progress, stage) => console.log(`${progress}% ${stage}`)
);

// 获取识别结果
console.log(result.text);           // 完整文本
console.log(result.textLines);      // 文本行（含坐标和置信度）
console.log(result.confidence);     // 整体置信度
```

## 数据库模型

### Tasks 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 |
| file_name | VARCHAR(255) | 文件名 |
| file_type | VARCHAR(10) | image / pdf |
| status | VARCHAR(20) | 任务状态 |
| progress | INTEGER | 进度 0-100 |
| created_at | DATETIME | 创建时间 |
| completed_at | DATETIME | 完成时间 |
| page_count | INTEGER | 总页数 |
| current_page | INTEGER | 当前处理页 |

### PageResults 表

存储每页识别结果，关联TextLines和TextBoxes。

## 设计规范

### 配色方案

| 名称 | 色值 | 用途 |
|------|------|------|
| 宣纸米白 | `#F5F0E6` | 主背景 |
| 篆刻朱红 | `#C41E3A` | 主色调、按钮、强调 |
| 墨黑 | `#1A1A1A` | 标题文字 |
| 深棕 | `#2C1810` | 正文文字 |
| 拓片灰 | `#8B8680` | 次要文字、边框 |

### 字体

- **标题**: Noto Serif SC (思源宋体)
- **正文**: Noto Sans SC (思源黑体)
- **代码**: JetBrains Mono

## 开发说明

### 添加新的导出格式

1. 在 `backend/app/services/export_service.py` 添加新方法
2. 在 `backend/app/controllers/export_controller.py` 注册格式
3. 在 `backend/app/api/tasks.py` 添加格式验证

### 替换真实模型

1. 将训练好的模型文件放入 `backend/ml/models/` 目录
2. 修改对应ML模块的 `use_mock=False`
3. 实现 `_load_model()` 和 `_infer()` 方法

## 常见问题

### Q: 没有Redis可以运行吗？

A: 可以，Celery会使用默认的消息队列，但建议生产环境使用Redis。无Redis时可直接调用处理函数而不通过Celery。

### Q: 如何处理大文件？

A: 系统默认支持最大50MB文件，可在 `config.py` 中修改 `MAX_CONTENT_LENGTH`。

### Q: Tesseract.js支持哪些语言？

A: 内置支持繁体中文(chi_tra)、简体中文(chi_sim)和英文(eng)，可根据需要添加其他语言包。

## License

MIT License
