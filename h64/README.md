# LiDAR 点云树木分割与分析工具

基于 Python + PyTorch + Open3D 的地面 LiDAR 点云处理命令行工具，支持树木点云的预处理、分割、参数提取和可视化。

## 功能特性

### 数据输入输出
- 支持 PLY 和 LAS/LAZ 格式点云读取
- 支持 RGB 颜色信息处理
- 输出带标签的点云文件（PLY/LAS）
- 输出 CSV 格式的统计表格

### 预处理
- **CSF 布料模拟地面滤波**：精确分离地面和非地面点
- **简单网格地面滤波**：快速地面去除
- **高度归一化**：将点云高度归一化到地面
- **体素降采样**：减少点云数量，提高处理效率
- **统计去噪**：移除离群点

### 分割算法
- **PointNet++**：多尺度分组（MSG）的深度点云分割网络
- **图卷积网络（GCN）**：基于图结构的点云分割
- 支持 5 类分割：地面(0)、树干(1)、大枝(2)、小枝(3)、叶片(4)

### 单株树参数提取
- 树木位置（X, Y 坐标）
- 树高
- 冠幅（宽度、深度、投影面积）
- 树冠体积
- 胸径（DBH）
- 叶面积指数（LAI）
- 叶片总面积
- 各类点数量统计

### 可视化
- 根据分割标签着色
- 叶片半透明显示效果
- 单株树实例着色
- 原始数据与处理结果对比
- 渲染为 PNG 图像

### 批量处理
- 递归扫描目录
- 进度条显示
- 处理结果汇总
- 合并所有树木参数到单个 CSV

## 安装

### 环境要求
- Python >= 3.8
- PyTorch >= 1.12.0
- CUDA 支持（可选，推荐用于加速）

### 安装依赖
```bash
pip install -r requirements.txt
```

### 安装为包
```bash
pip install -e .
```

## 使用方法

### 基本命令格式
```bash
python -m lidar_tree_tool.main --input <输入路径> --output <输出目录> [选项]
```

### 常用示例

#### 1. 处理单个文件
```bash
python -m lidar_tree_tool.main \
  --input ./data/tree.ply \
  --output ./results \
  --model ./checkpoints/model.pth
```

#### 2. 批量处理目录
```bash
python -m lidar_tree_tool.main \
  --input ./data \
  --output ./results \
  --model ./checkpoints/model.pth \
  --batch
```

#### 3. 仅预处理（不进行分割）
```bash
python -m lidar_tree_tool.main \
  --input ./data/tree.ply \
  --output ./results \
  --preprocess-only
```

#### 4. 使用已有标签跳过分割
```bash
python -m lidar_tree_tool.main \
  --input ./data/labeled.ply \
  --output ./results \
  --skip-segmentation
```

#### 5. 可视化结果
```bash
python -m lidar_tree_tool.main \
  --input ./results/tree_labeled.ply \
  --visualize
```

#### 6. 完整流程 + 渲染图像
```bash
python -m lidar_tree_tool.main \
  --input ./data/tree.ply \
  --output ./results \
  --model ./checkpoints/model.pth \
  --visualize \
  --render-image \
  --leaf-alpha 0.5
```

## 命令行参数详解

### 输入输出
- `--input, -i`: 输入点云文件或目录（必需）
- `--output, -o`: 输出目录（默认: ./output）
- `--model, -m`: 训练好的模型权重路径

### 处理模式
- `--batch`: 批量处理模式
- `--file-pattern`: 文件匹配模式（默认: *.ply,*.las,*.laz）
- `--preprocess-only`: 仅运行预处理
- `--skip-segmentation`: 跳过分割（使用输入文件中的标签）
- `--skip-extraction`: 跳过单株树提取

### 预处理参数
- `--ground-filter`: 地面滤波方法 [csf/simple/none]（默认: csf）
- `--cloth-resolution`: CSF 布料分辨率（默认: 0.5）
- `--rigidness`: CSF 刚度参数（默认: 3）
- `--class-threshold`: 地面分类阈值（默认: 0.5）
- `--downsample`: 体素降采样大小，0 表示禁用（默认: 0.05）
- `--normalize-height`: 高度归一化（默认: True）

### 分割模型参数
- `--model-arch`: 模型架构 [pointnet2/gcn]（默认: pointnet2）
- `--num-classes`: 分割类别数（默认: 5）
- `--use-rgb`: 使用 RGB 特征（默认: True）
- `--use-normal`: 使用法向量特征（默认: False）
- `--batch-size`: 推理批次大小（默认: 4096）
- `--vote-sampling`: 投票采样次数，0 禁用（默认: 0）

### 树木提取参数
- `--cluster-method`: 聚类方法 [dbscan/horizontal]（默认: dbscan）
- `--min-points`: DBSCAN 最小点数（默认: 50）
- `--distance-threshold`: DBSCAN 距离阈值（默认: 0.5）
- `--min-tree-points`: 单株树最小点数（默认: 100）
- `--leaf-area-per-point`: 每点叶面积估计值（默认: 0.01）

### 可视化参数
- `--visualize`: 显示分割结果
- `--visualize-instances`: 显示单株树实例
- `--no-show-ground`: 不显示地面点
- `--leaf-alpha`: 叶片透明度（默认: 0.5）
- `--render-image`: 渲染为图像文件

### 其他
- `--save-intermediate`: 保存中间结果
- `--device`: 计算设备 [auto/cpu/cuda]（默认: auto）
- `--verbose, -v`: 详细输出

## 输出文件说明

### 单文件处理输出
```
output/
├── tree_preprocessed.ply    # 预处理后的点云（可选）
├── tree_labeled.ply         # 带分割标签的点云
├── tree_visualization.ply   # 着色后的可视化点云
├── tree_metrics.csv         # 单株树参数表
└── tree_render.png          # 渲染图像（可选）
```

### 批量处理输出
```
output/
├── processing_summary.csv      # 处理过程汇总
├── overall_statistics.csv      # 整体统计信息
├── all_tree_metrics.csv        # 所有树木参数合并表
├── file1_labeled.ply
├── file1_metrics.csv
├── file2_labeled.ply
└── file2_metrics.csv
```

### CSV 列说明
| 列名 | 说明 | 单位 |
|------|------|------|
| tree_id | 树木编号 | - |
| position_x | X 坐标 | m |
| position_y | Y 坐标 | m |
| tree_height | 树高 | m |
| crown_width | 冠幅宽度 | m |
| crown_depth | 冠幅深度 | m |
| crown_area | 树冠投影面积 | m² |
| crown_volume | 树冠体积 | m³ |
| lai | 叶面积指数 | - |
| leaf_area | 叶片总面积 | m² |
| trunk_diameter | 树干直径 | m |
| dbh | 胸径 | m |
| total_points | 总点数 | - |
| trunk_points | 树干点数 | - |
| large_branch_points | 大枝点数 | - |
| small_branch_points | 小枝点数 | - |
| leaf_points | 叶片点数 | - |

## 分割标签说明

| 标签值 | 类别 | 颜色 |
|--------|------|------|
| 0 | 地面 | 棕色 |
| 1 | 树干 | 深棕色 |
| 2 | 大枝 | 浅棕色 |
| 3 | 小枝 | 米色 |
| 4 | 叶片 | 绿色 |

## 项目结构

```
lidar_tree_tool/
├── __init__.py
├── main.py              # 命令行入口
├── data_io.py           # 数据读写
├── preprocessing.py     # 预处理模块
├── pointnet2.py         # PointNet++ 模型
├── tree_extraction.py   # 树木提取与参数计算
├── visualization.py     # 可视化模块
└── batch_processing.py  # 批量处理
```

## 模型训练

如需训练自己的分割模型，请准备以下格式的训练数据：
- 点云坐标 (N, 3)
- RGB 颜色 (N, 3) - 可选
- 分割标签 (N,) - 0-4 的整数

参考 PointNet++ 官方实现进行训练，训练完成后保存模型权重即可使用。

## 常见问题

### 1. 内存不足
- 增大 `--downsample` 参数进行更激进的降采样
- 减小 `--batch-size` 参数
- 使用 `--vote-sampling 0` 禁用投票采样

### 2. 地面滤波效果不好
- 调整 `--cloth-resolution`（更大的值适合平坦地形）
- 调整 `--class-threshold`（增大可减少误分类为地面的点）
- 对于复杂地形，尝试 `--ground-filter simple`

### 3. 树木分割不准确
- 调整 `--distance-threshold`（根据点云密度）
- 调整 `--min-tree-points` 过滤过小的聚类
- 确保模型在相似数据上训练过

## 许可证

本项目仅供科研和教育使用。
