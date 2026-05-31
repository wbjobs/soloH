# SAR图像内孤立波检测与分析工具 (SARIW - SAR Internal Wave)

基于OpenCV和scikit-image的Python命令行工具，用于从SAR（合成孔径雷达）图像中检测、分析和追踪内孤立波。

## 功能特性

- **GeoTIFF读取**: 支持地理坐标转换和投影信息提取
- **图像预处理**: 去噪、对比度增强、背景估计
- **内波特征检测**: 亮暗相间条纹检测，Radon变换估计波峰线方向和间距
- **波前提取**: Canny边缘检测提取精确波前位置
- **振幅反演**: 基于KdV方程，利用图像对比度和海面背景风场反演内波振幅
- **多帧追踪**: 支持多时相图像追踪内波传播速度和衰减
- **KML输出**: 生成KML文件供Google Earth叠加显示

## 安装

```bash
pip install -r requirements.txt
python setup.py install
```

## 快速开始

### 单帧图像分析

```bash
sariw analyze input.sar.tif --output output_dir --wind-speed 5.0 --water-depth 100
```

### 多帧追踪

```bash
sariw track frames/*.tif --output track_output --time-interval 3600
```

### 详细参数

```bash
sariw --help
sariw analyze --help
sariw track --help
```

## 输出文件

- `*_detection.png`: 检测结果可视化图像
- `*_wavefronts.png`: 波前提取结果
- `*_radon.png`: Radon变换结果
- `*_results.json`: 详细分析结果（JSON格式）
- `*_output.kml`: Google Earth可视化文件

## 引用

如果使用本工具，请参考相关文献：
- KdV方程内波理论
- SAR图像内波检测算法
- Radon变换线性特征提取
