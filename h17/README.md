# 弹性波动方程数值模拟系统

一个功能完整的二维弹性波动方程有限差分数值模拟系统，使用Python + NumPy + SciPy实现，并通过Numba进行高性能加速。

## 功能特性

### 核心求解器
- **波动方程**: 速度-应力形式的弹性波动方程
- **差分格式**: 交错网格有限差分
- **时间离散**: 二阶精度
- **空间离散**: 2-12阶可变高阶精度
- **加速方式**: Numba JIT编译（支持并行和快速数学）

### 边界条件
- **CPML (卷积完美匹配层)**: 高效的吸收边界条件，有效消除边界反射

### 介质模型
- **各向同性介质**: 常规弹性介质
- **VTI介质**: 垂直横向各向同性
- **TTI介质**: 倾斜横向各向同性
- **支持非均匀介质**: 可自定义速度和密度模型

### 震源类型
- **Ricker子波**: 常用的地震子波
- **爆炸源**: 同时激发P波
- **剪切源**: 主要激发S波
- **力源**: 单向力源（x或z方向）

### 数据采集
- **接收器阵列**: 支持地表、垂直井或任意位置
- **多分量记录**: vx, vz, tau_xx, tau_zz, tau_xz, 压力

### 可视化输出
- **地震剖面 (Wiggle图)**: 显示多道地震记录
- **波场快照**: 显示波场传播过程
- **动画生成**: GIF/MP4格式的波场动画
- **偏振分析**: 质点运动轨迹和偏振属性

### 高性能计算
- **MPI并行**: 使用mpi4py实现区域分解并行
- **GPU加速**: 使用cupy实现GPU加速计算
- **Numba并行**: 自动CPU多线程加速

## 项目结构

```
e:\soloH\h17\
├── __init__.py          # 包初始化和导出
├── config.py            # 配置类
├── fd_coefficients.py   # 有限差分系数
├── cpml.py              # CPML边界条件
├── medium.py            # 介质模型
├── source.py            # 震源模块
├── receiver.py          # 接收器阵列
├── solver.py            # 核心求解器
├── visualization.py     # 可视化模块
├── parallel.py          # 并行/GPU支持
├── main.py              # 主程序入口
├── requirements.txt     # 依赖包
└── README.md            # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行示例

```bash
# 运行各向同性介质模拟
python main.py --mode isotropic

# 运行VTI介质模拟
python main.py --mode vti

# 运行TTI介质模拟
python main.py --mode tti

# 运行剪切源模拟
python main.py --mode shear

# 运行非均匀介质模拟
python main.py --mode heterogeneous

# 运行对比研究（各向同性 vs VTI vs TTI）
python main.py --mode comparison

# 运行所有模拟
python main.py --mode all

# 不显示图形窗口（适合服务器运行）
python main.py --mode isotropic --no-plots

# 不保存结果
python main.py --mode isotropic --no-save
```

### 3. 自定义使用

```python
import numpy as np
from config import SimulationConfig
from solver import ElasticSolver
from visualization import create_summary_figure

# 创建配置
config = SimulationConfig(
    nx=301,
    nz=301,
    dx=10.0,
    dz=10.0,
    dt=0.001,
    nt=500,
    space_order=12,
    vp=3000.0,
    vs=1732.0,
    rho=2500.0,
    anisotropy_type='isotropic',
    source_type='explosive',
    source_x=150,
    source_z=150,
    output_dir='output/custom'
)

# 创建求解器
solver = ElasticSolver(config)

# 运行模拟
def progress(current, total, elapsed):
    print(f"\r{current}/{total}", end='')

results = solver.solve(progress_callback=progress)

# 生成结果图形
create_summary_figure(results, config.output_dir)
```

## 核心类说明

### SimulationConfig
模拟配置类，包含所有模拟参数：
- 网格参数：nx, nz, dx, dz, dt, nt
- 数值参数：space_order, time_order
- 边界参数：cpml_width, cpml_max_power
- 介质参数：vp, vs, rho, epsilon, delta, gamma
- 震源参数：source_type, source_x, source_z, source_f0
- 接收参数：receiver_x_start, receiver_x_end, receiver_z
- 输出参数：snapshot_interval, output_dir
- 计算参数：use_mpi, use_gpu, numba_parallel

### ElasticSolver
核心求解器类：
- `solve()`: 运行完整模拟
- `reset()`: 重置求解器状态
- `set_particle_motion_points()`: 设置偏振分析点

### Medium
介质模型类：
- 支持各向同性、VTI、TTI介质
- `set_heterogeneous_model()`: 设置非均匀模型
- `get_velocity()`: 获取P波或S波速度

### CPML
吸收边界类：
- `apply_velocity_correction()`: 应用速度场CPML
- `apply_stress_correction()`: 应用应力场CPML

### Source
震源类：
- `add_source()`: 向波场添加震源项
- `get_wavelet_spectrum()`: 获取子波频谱
- `ricker_wavelet()`: 生成Ricker子波

### ReceiverArray
接收器阵列类：
- `record()`: 记录波场值
- `get_seismogram()`: 获取地震记录
- `apply_agc()`: 应用自动增益控制
- `apply_bandpass()`: 应用带通滤波
- `save()` / `load()`: 保存/加载记录

### ParticleMotionRecorder
质点运动记录类：
- `get_particle_motion()`: 获取质点运动轨迹
- `get_polarization_attributes()`: 计算偏振属性
  - 长轴、短轴长度
  - 椭圆率
  - 偏振方向角
  - 直线度

## 可视化函数

### plot_wiggle()
绘制地震剖面（wiggle图）
- 支持正负填充
- 可调节道间距和幅度比例

### plot_snapshot()
绘制波场快照
- 支持多种colormap
- 自动幅度裁剪

### animate_snapshots()
生成波场动画
- 支持GIF和MP4格式
- 可调节帧率和分辨率

### plot_particle_motion()
绘制质点运动轨迹
- 时间颜色编码
- 显示起点终点
- 偏振椭圆拟合

### plot_seismogram()
绘制单道地震记录
- 支持多分量对比
- 自动归一化

### create_summary_figure()
生成完整的结果图集

## 并行计算

### MPI并行
```python
from parallel import ParallelManager

pm = ParallelManager(use_mpi=True)
if pm.is_main_process():
    print("主进程")

# 区域分解
x_start, x_end, z_start, z_end = pm.split_domain_1d(nx, nz, axis='x')
```

### GPU加速
```python
from parallel import ParallelManager

pm = ParallelManager(use_gpu=True)
xp = pm.get_array_module()

# 数据会自动在CPU和GPU间传输
```

## 数值稳定性

### CFL条件
程序会自动检查CFL稳定性条件：
```
CFL = dt * vmax / min(dx, dz) < CFL_max
```

对于2阶时间差分，CFL_max ≈ 0.707

### 空间采样
程序会自动检查每波长点数（PPW）：
```
PPW = λ_min / min(dx, dz) = (vmin / fmax) / min(dx, dz)
```
推荐PPW ≥ 5

## 性能建议

1. **空间阶数**: 
   - 小模型（<200x200）: 4-8阶
   - 中等模型（200-500x200-500）: 8-12阶
   - 大模型: 12阶

2. **Numba线程**:
   - 设置环境变量 `NUMBA_NUM_THREADS` 控制CPU线程数
   - 最佳为物理核心数

3. **GPU使用**:
   - 模型越大GPU加速效果越明显
   - 需安装对应CUDA版本的cupy

## 参考文献

1. Virieux, J. (1986). P-SV wave propagation in heterogeneous media: 
   Velocity-stress finite-difference method. Geophysics, 51(4), 889-901.

2. Levander, A. R. (1988). Fourth-order finite-difference P-SV seismograms. 
   Geophysics, 53(11), 1425-1436.

3. Komatitsch, D., & Martin, R. (2007). An unsplit convolutional perfectly 
   matched layer improved at grazing incidence for the seismic wave equation. 
   Geophysics, 72(5), SM155-SM167.

4. Thomsen, L. (1986). Weak elastic anisotropy. Geophysics, 51(10), 1954-1966.

## 许可证

本项目用于学术研究和教学目的。
