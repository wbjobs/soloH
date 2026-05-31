# Motif Discovery Tool - C++ Command Line Tool

## 项目概述

这是一个完整的C++命令行工具，用于从FASTA格式的序列数据中发现富集的DNA基序(motif)。该工具实现了生物信息学中常用的两种核心算法：期望最大化(EM)算法和Gibbs采样算法。

## 功能特性

### 核心算法
- **EM算法** (Expectation Maximization) - 基于ZOOPS模型的快速motif发现
- **Gibbs采样** - 基于马尔可夫链蒙特卡洛的motif发现
- **TCM模型** (Two Component Model) - 检测两个共现的motif

### 模型支持
- **ZOOPS模型** (Zero or One Occurrence Per Sequence) - 每条序列0个或1个motif
- **TCM模型** (Two Component Model) - 检测两个motif的共现模式

### 输出内容
- **PWM矩阵** (Position Weight Matrix) - 位置权重矩阵
- **信息量** (Information Content) - 以比特为单位
- **匹配位点位置** - 在每条序列中的精确位置
- **E-value** - 基于背景模型的统计显著性评估
- **P-value** - 单个位点的统计显著性
- **序列标识图** (WebLogo) - 彩色/纯文本可视化
- **MEME格式输出** - 标准的motif交换格式

### 高级特性 (v1.2)
- **先验知识整合** - 支持已知转录因子结合位点作为先验（BED格式输入）
- **RNA二级结构约束** - 基于茎环结构的motif发现，考虑可及性
- **OpenMP并行加速** - 多线程处理多序列，提升计算性能

## 项目结构

```
h55/
├── include/                     # 头文件目录
│   ├── sequence.h              # FASTA序列解析
│   ├── pwm.h                   # PWM矩阵和背景模型
│   ├── statistics.h            # 统计计算（log-sum-exp, E-value等）
│   ├── prior_knowledge.h       # 先验知识整合模块
│   ├── rna_structure.h         # RNA二级结构预测模块
│   ├── em_algorithm.h          # EM算法（ZOOPS模型）
│   ├── gibbs_sampler.h         # Gibbs采样算法
│   ├── tcm_model.h             # TCM双motif模型
│   └── output_formatter.h      # 输出格式化（WebLogo, MEME）
├── src/
│   └── main.cpp                # 主程序入口
├── CMakeLists.txt              # CMake构建脚本
├── build.bat                   # Windows构建脚本
├── build.sh                    # Linux/macOS构建脚本
├── example.fasta               # 示例FASTA文件
└── README.md                   # 本文件
```

## 高级功能详解 (v1.2新增)

### 1. 先验知识整合

**功能说明**: 允许用户提供已知的转录因子结合位点作为先验知识，引导算法在特定区域搜索motif。

**实现模块**: [prior_knowledge.h](file:///e:/soloH/h55/include/prior_knowledge.h)

**核心功能:
- **BED文件支持**: 加载标准BED格式的已知结合位点文件
- **多源先验**: 支持实验验证(experiment)、预测(prediction)、保守性(conservation)等多来源
- **高斯距离衰减**: 先验权重随距离高斯衰减，影响邻近位置
- **可配置权重**: `--prior-weight 控制先验与数据的相对权重

**数学原理**:
```
combined_prior[p] = w * prior_knowledge[p] + (1-w) * position_prior[p]
```

**先验位置权重计算:
```
weight[p] = 1.0 + (strength - 1.0) * exp(-distance² / (2 * σ²))
```

**使用示例**:
```bash
# 使用已知TF结合位点作为先验
motif_discovery -i sequences.fasta --prior-bed known_sites.bed --prior-weight 0.6

# TCM模型使用两个不同的先验
motif_discovery -i sequences.fasta -m TCM \
  --prior-bed tf1_sites.bed --prior-bed2 tf2_sites.bed
```

**BED文件格式**:
```
seq_name\tstart\tend\tname\tscore
promoter_1\t5\t13\tknown_TF\t2.5
```

---

### 2. RNA二级结构约束

**功能说明**: 预测RNA二级结构，在motif发现中考虑结构可及性，优先在单链区域寻找结合位点。

**实现模块**: [rna_structure.h](file:///e:/soloH/h55/include/rna_structure.h)

**核心功能:
- **Nussinov动态规划**: 预测最小自由能RNA二级结构
- **碱基配对概率**: 使用配分函数计算碱基配对概率
- **可及性计算**: 单链概率 = 1 - 配对概率
- **结构类型注释**: 茎区、环区、发夹、凸环等
- **高斯间距约束**: 茎环结构特征权重

**可及性权重**:
```
accessibility[pos] = 1.0 - pairing_probability[pos]

structure_weight[p] = accessibility[p] * (1 + hairpin_bonus * hairpin_score[p])
```

**使用示例**:
```bash
# 启用RNA结构约束
motif_discovery -i rna_sequences.fasta --rna-structure

# 调整结构权重和参数
motif_discovery -i rna_sequences.fasta --rna-structure \
  --structure-weight 0.7 --stem-bonus 1.5 --loop-penalty 0.3

# 禁用G-U配对
motif_discovery -i rna_sequences.fasta --rna-structure --no-gu-pairing
```

**结构权重公式:
```
total_weight[p] = sequence_score[p] * accessibility[p] * 
                 (1 + loop_bonus * loop_ratio[p] - 
                    stem_penalty * stem_ratio[p])
```

---

### 3. OpenMP并行加速

**功能说明**: 使用OpenMP多线程并行处理，显著提升大数据集的计算速度。

**实现位置**:
- [em_algorithm.h](file:///e:/soloH/h55/include/em_algorithm.h#L63-L70) - 多重启并行
- [em_algorithm.h](file:///e:/soloH/h55/include/em_algorithm.h#L181-L184) - E步并行
- [gibbs_sampler.h](file:///e:/soloH/h55/include/gibbs_sampler.h#L63-L70) - 多重启并行
- [tcm_model.h](file:///e:/soloH/h55/include/tcm_model.h#L73-L80) - 多重启并行
- [tcm_model.h](file:///e:/soloH/h55/include/tcm_model.h#L265-L268) - E步并行
- [rna_structure.h](file:///e:/soloH/h55/include/rna_structure.h#L266-L273) - 结构预测并行

**并行层次**:
1. **粗粒度并行**: 多个随机重启同时运行
2. **细粒度并行**: E步中多条序列同时处理
3. **结构预测并行**: RNA结构预测独立并行

**性能提升:
- 理想情况下接近线性加速
- 动态调度 (schedule(dynamic)) 负载均衡
- reduction子句确保线程安全

**使用示例**:
```bash
# 使用4线程
motif_discovery -i large_sequences.fasta -t 4

# 使用8线程，EM算法
motif_discovery -i large_sequences.fasta -a EM -t 8

# 结合所有高级功能
motif_discovery -i sequences.fasta -t 8 \
  --prior-bed known_sites.bed \
  --rna-structure \
  --structure-weight 0.6
```

**编译要求**:
- GCC/Clang: 需要 `-fopenmp` 编译选项
- MSVC: 需要 `/openmp` 编译选项
- CMake: 自动检测OpenMP并启用

---

## 编译方法

### 方法1：使用CMake（推荐）
```bash
mkdir build
cd build
cmake ..
cmake --build .
```

### 方法2：直接编译（Windows）
```bash
# 首先安装MinGW
winget install BrechtSanders.WinLibs.POSIX.UCRT

# 然后编译
build.bat
```

### 方法3：直接编译（Linux/macOS）
```bash
chmod +x build.sh
./build.sh
```

### 方法4：手动编译
```bash
g++ -std=c++17 -O2 -Wall -Wextra -Iinclude src/main.cpp -o motif_discovery -lpthread
```

## 编译器要求
- C++17 标准兼容编译器
- GCC 7+ 或 Clang 5+ 或 MSVC 2019+

## 使用方法

### 基本用法
```bash
# 使用EM算法，ZOOPS模型，motif长度12
motif_discovery -i input.fasta

# 使用Gibbs采样，motif长度8
motif_discovery -i input.fasta -a Gibbs -w 8

# 使用TCM模型，两个motif
motif_discovery -i input.fasta -m TCM -w 10 --width2 8
```

### 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i, --input <file>` | 输入FASTA文件（必需） | - |
| `-o, --output <prefix>` | 输出文件前缀 | motif_results |
| `-a, --algorithm <alg>` | 算法：EM 或 Gibbs | EM |
| `-m, --model <model>` | 模型：ZOOPS 或 TCM | ZOOPS |
| `-w, --width <int>` | Motif长度（6-20） | 12 |
| `--width2 <int>` | TCM模型第二个motif长度 | 12 |
| `--min-width <int>` | 最小motif长度 | 6 |
| `--max-width <int>` | 最大motif长度 | 20 |
| `--iter <int>` | 最大迭代次数 | 100 |
| `--starts <int>` | 重启次数 | 5 |
| `--seed <int>` | 随机种子 | 42 |
| `--tolerance <double>` | 收敛容差 | 1e-6 |
| `--lambda <double>` | 初始lambda值 | 0.5 |
| `--edge-penalty <double>` | 边缘位置惩罚（0-1） | 0.3 |
| `--tcm-min-spacing <int>` | TCM最小motif间距 | 0 |
| `--tcm-max-spacing <int>` | TCM最大motif间距 | 100 |
| `--tcm-preferred <int>` | TCM偏好motif间距 | 20 |
| `--tcm-sigma <double>` | TCM间距分布标准差 | 10.0 |
| `--no-color` | 禁用彩色输出 | 关闭 |
| `--no-meme` | 不生成MEME输出 | 关闭 |
| `--weblogo-height <int>` | WebLogo高度 | 12 |
| `-h, --help` | 显示帮助信息 | - |

## 输出示例

### 控制台输出
```
=============================================================================
Motif 1: ACGTGCGA
=============================================================================
Algorithm: EM
Model: ZOOPS
Width: 8 bp
Information Content: 12.3456 bits
E-value: 1.23e-10
Number of sites: 18

Position Weight Matrix (PWM):
A:    0.05    0.80    0.05    0.05    0.05    0.05    0.70    0.10
C:    0.05    0.05    0.80    0.05    0.05    0.10    0.05    0.05
G:    0.80    0.05    0.05    0.05    0.80    0.05    0.05    0.10
T:    0.10    0.10    0.10    0.85    0.10    0.80    0.20    0.75

Sequence Logo:
  +------------------------+
 2.0 |    A    C    G    T    |
 1.8 |    A    C    G    T    |
 ...
  +------------------------+
```

### MEME格式输出
生成标准的MEME XML格式文件，可被其他生物信息学工具识别。

## 算法说明

### EM算法（ZOOPS模型）
1. **E步**：计算每个序列中每个位置包含motif的后验概率
2. **M步**：根据后验概率更新PWM矩阵和模型参数lambda
3. 迭代直到收敛或达到最大迭代次数

### Gibbs采样
1. 随机初始化每个序列中的motif位置
2. 每次迭代中，对每条序列：
   - 暂时移除该序列
   - 基于剩余序列构建PWM
   - 根据PWM采样新的位置
3. Burn-in后收集样本估计最终PWM

### TCM模型
扩展的EM算法，同时拟合两个motif模型，考虑四种情况：
- 序列不包含任何motif
- 只包含第一个motif
- 只包含第二个motif
- 同时包含两个motif

## 输入格式

工具接受标准的FASTA格式：
```
>sequence_name
ATCGATCGATCGATCGATCGATCGATCG
>another_sequence
CGATCGATCGATCGATCGATCGATCGAT
```

## 测试

使用提供的示例文件进行测试：
```bash
motif_discovery -i example.fasta -w 8
```

## 许可证

本项目仅供学术研究使用。

## 参考文献

1. Bailey, T. L., & Elkan, C. (1994). Fitting a mixture model by expectation maximization to discover motifs in biopolymers.
2. Lawrence, C. E., et al. (1993). Detecting subtle sequence signals: a Gibbs sampling strategy for multiple alignment.
