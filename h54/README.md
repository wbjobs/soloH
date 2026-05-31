# 轴承故障诊断工具 (Bearing Fault Diagnosis)

基于Python的智能轴承故障诊断命令行工具，结合信号处理与机器学习技术，实现轴承故障的自动检测、分类与严重程度评估。

## 功能特性

### 🔧 信号预处理
- **去趋势处理**: 线性去趋势、常数去趋势
- **带通滤波**: 基于轴承参数自动计算最优滤波频带
- **包络检测**: 希尔伯特变换提取包络信号
- **包络谱分析**: 共振解调技术提取故障特征

### 📊 特征提取
- **时域特征** (12个): 峰峰值、均方根、峰值、峭度、偏度、峰值因子、脉冲因子、裕度因子、波形因子、均值、方差、标准差
- **频域特征** (N个): 频谱质心、扩展度、偏度、峭度、滚降点、能量、熵；故障特征频率及其谐波、边频带幅值
- **时频域特征**: 小波包能量（各节点）、小波包能量熵、小波包系数标准差

### 🤖 分类器
- **随机森林** (集成学习): 快速训练，内置特征重要性
- **CNN** (PyTorch): 支持原始信号或特征输入，双分支输出（故障类型 + 严重程度）

### 📋 诊断输出
- **故障类型**: 正常、内圈故障、外圈故障、滚动体故障、保持架故障
- **严重程度**: 正常、早期、中期、晚期
- **置信度**: 各类别概率输出

### 🔍 可解释性
- 特征重要性排序（模型内置 / 排列重要性 / SHAP）
- 特征类别贡献分析（时域/频域/时频域）
- 关键驱动因素解释
- 智能维护建议

## 项目结构

```
bearing_diagnosis/
├── __init__.py              # 包初始化
├── preprocessing.py         # 预处理模块
├── feature_extraction.py    # 特征提取模块
├── classifier.py            # 分类器模块
├── explainability.py        # 可解释性模块
├── data_generator.py        # 模拟数据生成
├── utils.py                 # 工具函数
└── cli.py                   # 命令行接口
examples/
├── quick_start.py           # 快速入门示例
└── basic_usage.py           # 完整使用示例
requirements.txt             # 依赖包
setup.py                     # 安装配置
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装包（可选）

```bash
pip install -e .
```

### 3. 快速测试

生成示例信号并进行诊断：

```bash
# 生成示例信号
python examples/quick_start.py

# 使用命令行工具诊断
python -m bearing_diagnosis.cli predict sample_signal.npy
```

或者直接运行完整示例：

```bash
python examples/basic_usage.py
```

## 命令行使用

### 预测诊断

```bash
bearing-diagnosis predict [信号文件] [选项]
```

**常用选项：**
```
--output, -o          结果输出文件 (默认: diagnosis_result.json)
--model-path, -m      训练好的模型路径
--classifier-type     分类器类型: random_forest / cnn (默认: random_forest)
--fs                  采样频率 Hz (默认: 25600.0)
--rotational-speed    转速 Hz (默认: 50.0)
--n-rolling-elements  滚动体数量 (默认: 9)
--pitch-diameter      节径 mm (默认: 39.04)
--rolling-diameter    滚动体直径 mm (默认: 7.94)
--contact-angle       接触角 度 (默认: 0.0)
--low-freq            带通滤波低截止频率 Hz
--high-freq           带通滤波高截止频率 Hz
--wavelet             小波基函数 (默认: db4)
--wavelet-level       小波包分解层数 (默认: 4)
--explain/--no-explain  是否生成可解释性报告 (默认: True)
--top-k               显示前K个重要特征 (默认: 10)
--format              输出格式: json/csv/pickle (默认: json)
```

**示例：**
```bash
# 基本使用
python -m bearing_diagnosis.cli predict signal.npy

# 指定轴承参数
python -m bearing_diagnosis.cli predict signal.npy \
  --n-rolling-elements 12 --pitch-diameter 45.0 --rolling-diameter 8.5

# 使用预训练模型并保存结果
python -m bearing_diagnosis.cli predict signal.npy \
  -m model.pkl -o result.json --format json

# 关闭可解释性分析
python -m bearing_diagnosis.cli predict signal.npy --no-explain
```

### 训练模型

```bash
bearing-diagnosis train [选项]
```

**常用选项：**
```
--data-path, -d       训练数据路径 (必需)
--output-model, -o    模型保存路径 (默认: bearing_classifier.pkl)
--classifier-type     分类器类型 (默认: random_forest)
--n-estimators        随机森林树的数量 (默认: 200)
--epochs              CNN训练轮数 (默认: 50)
--batch-size          批次大小 (默认: 32)
--learning-rate       学习率 (默认: 0.001)
--test-size           测试集比例 (默认: 0.2)
--cv                  交叉验证折数 (默认: 5)
```

**示例：**
```bash
# 生成训练数据
python -m bearing_diagnosis.cli generate-data --n-samples 500 -o train_data.npy

# 训练随机森林
python -m bearing_diagnosis.cli train -d train_data.npy -o rf_model.pkl

# 训练CNN
python -m bearing_diagnosis.cli train -d train_data.npy \
  -c cnn --epochs 30 --batch-size 64 -o cnn_model.pth
```

### 生成模拟数据

```bash
bearing-diagnosis generate-data [选项]
```

**常用选项：**
```
--n-samples           生成样本数量 (默认: 100)
--n-channels          通道数量 (默认: 2)
--fs                  采样频率 Hz (默认: 25600.0)
--duration            信号时长 秒 (默认: 1.0)
--output, -o          输出文件路径 (默认: sample_data.npy)
--seed                随机种子 (默认: 42)
```

## API 使用示例

### 完整诊断流程

```python
from bearing_diagnosis import (
    Preprocessor,
    BearingFaultFrequency,
    FeatureExtractor,
    BearingClassifier,
    FeatureExplainer,
    load_signal
)

# 1. 加载信号
signal = load_signal('vibration_data.npy')

# 2. 计算轴承故障频率
bearing = BearingFaultFrequency(
    n_rolling_elements=9,
    pitch_diameter=39.04,
    rolling_element_diameter=7.94
)
fault_freqs = bearing.calculate(rotational_speed=50.0)
low_freq, high_freq = bearing.get_filter_band(50.0)

# 3. 预处理
preprocessor = Preprocessor(fs=25600.0)
processed = preprocessor.preprocess(signal, low_freq, high_freq)

# 4. 特征提取
extractor = FeatureExtractor(fs=25600.0)
features, feature_names = extractor.extract(processed, fault_freqs)

# 5. 诊断预测
classifier = BearingClassifier(classifier_type='random_forest')
classifier.load('trained_model.pkl', n_features=features.shape[1])
prediction = classifier.predict_single(features)

print(f"故障类型: {prediction['fault_type']}")
print(f"置信度: {prediction['fault_type_probability']:.2%}")
print(f"严重程度: {prediction['severity']}")

# 6. 可解释性分析
explainer = FeatureExplainer(feature_names=feature_names)
importance = explainer.analyze_importance(classifier, top_k=10)
report = explainer.generate_explanation_report(prediction)
print(f"建议: {report['recommendation']}")
```

### 模型训练

```python
from bearing_diagnosis import BearingClassifier
from bearing_diagnosis.data_generator import generate_bearing_dataset

# 生成训练数据
X, y_type, y_severity, feature_names = generate_bearing_dataset(
    n_samples=500, n_channels=2, fs=25600.0
)

# 训练分类器
classifier = BearingClassifier(
    classifier_type='random_forest',
    n_estimators=200
)
results = classifier.fit(X, y_type, y_severity, cv=5)

print(f"交叉验证准确率: {results['cv_type_accuracy']:.4f}")

# 保存模型
classifier.save('bearing_model.pkl')
```

## 轴承参数说明

### 常见轴承参数示例

| 轴承型号 | 滚动体数 | 节径(mm) | 滚动体直径(mm) | 接触角(°) |
|---------|---------|---------|--------------|----------|
| 6205    | 9       | 39.04   | 7.94         | 0        |
| 6305    | 7       | 46.85   | 11.11        | 0        |
| 6206    | 9       | 46.80   | 9.53         | 0        |
| NJ205   | 12      | 45.00   | 8.50         | 0        |

### 故障特征频率计算公式

给定轴承参数和转速 $f_r$ (Hz):

- **保持架故障频率 (FTF)**: $f_{FTF} = \frac{f_r}{2} \left(1 - \frac{d}{D} \cos\theta\right)$
- **内圈故障频率 (BPFI)**: $f_{BPFI} = \frac{n f_r}{2} \left(1 + \frac{d}{D} \cos\theta\right)$
- **外圈故障频率 (BPFO)**: $f_{BPFO} = \frac{n f_r}{2} \left(1 - \frac{d}{D} \cos\theta\right)$
- **滚动体故障频率 (BSF)**: $f_{BSF} = \frac{D f_r}{2d} \left(1 - \left(\frac{d}{D} \cos\theta\right)^2\right)$

其中:
- $n$: 滚动体数量
- $d$: 滚动体直径
- $D$: 节径
- $\theta$: 接触角

## 故障类型说明

| 故障类型 | 英文标识 | 典型特征 |
|---------|---------|---------|
| 正常    | normal  | 无明显周期性冲击 |
| 内圈故障 | inner_race | 与内圈故障频率及其谐波相关的冲击，有明显的转速调制边带 |
| 外圈故障 | outer_race | 与外圈故障频率及其谐波相关的冲击，调制现象较弱 |
| 滚动体故障 | rolling_element | 滚动体自转频率及其谐波，通常伴随保持架频率调制 |
| 保持架故障 | cage | 保持架频率的低频调制，能量较弱 |

## 严重程度说明

| 严重程度 | 标识 | 典型特征 | 建议措施 |
|---------|------|---------|---------|
| 正常    | normal | 特征值在正常范围 | 正常运行 |
| 早期    | early | 峭度、脉冲因子轻微升高，故障频率分量初现 | 加强监测，安排近期检查 |
| 中期    | medium | 故障频率谐波明显，边频带丰富，振动幅值升高 | 尽快安排检修，考虑更换备件 |
| 晚期    | late | 强烈冲击，出现周期性脉冲，频谱噪声底抬高 | 立即停机检修，避免设备损坏 |

## 特征说明

### 时域特征

| 特征名称 | 说明 | 对故障敏感度 |
|---------|------|-------------|
| 峰峰值 (peak_to_peak) | 信号最大值与最小值之差 | 中 |
| 均方根 (RMS) | 振动能量的有效度量 | 中高 |
| 峭度 (kurtosis) | 信号分布的峭度，对冲击敏感 | 高（早期故障） |
| 脉冲因子 (impulse_factor) | 峰值与均值绝对值之比 | 高（早期故障） |
| 峰值因子 (crest_factor) | 峰值与RMS之比 | 高 |
| 裕度因子 (margin_factor) | 峰值与方根均值之比 | 高（早期故障） |
| 波形因子 (shape_factor) | RMS与均值绝对值之比 | 中 |

### 频域特征

- 频谱质心、扩展度、偏度、峭度、滚降点、能量、熵
- 各故障特征频率（BPFI、BPFO、BSF、FTF）及其1-3次谐波幅值
- 各谐波的转速调制边频带幅值

### 时频域特征

- 小波包各节点能量（默认4层分解，共16个节点）
- 小波包能量熵
- 小波包各节点系数标准差

## 可解释性输出示例

```json
{
  "top_features": [
    {
      "feature": "time_kurtosis_ch1",
      "importance": 0.085,
      "relative_importance": 0.123,
      "rank": 1
    },
    {
      "feature": "freq_bpfi_1x_amp_ch1",
      "importance": 0.072,
      "relative_importance": 0.104,
      "rank": 2
    }
  ],
  "category_summary": {
    "time_domain": {"relative_importance": 0.45, "n_features": 24},
    "frequency_domain": {"relative_importance": 0.35, "n_features": 60},
    "time_frequency_domain": {"relative_importance": 0.20, "n_features": 68}
  },
  "key_drivers": [
    {
      "feature": "time_kurtosis_ch1",
      "interpretation": "峭度反映冲击成分的多少，故障时会显著升高（通道1）"
    }
  ],
  "recommendation": "检测到内圈故障，严重程度：早期。建议加强监测，安排近期检查..."
}
```

## 常见问题

### Q: 如何准备训练数据？

A: 训练数据应为 `.npy` 格式的字典，包含：
- `X`: 特征矩阵 (n_samples, n_features)
- `y_type`: 故障类型标签数组
- `y_severity`: 严重程度标签数组
- `feature_names`: 特征名称列表（可选）

可以使用 `bearing-diagnosis generate-data` 生成模拟数据。

### Q: 支持哪些信号文件格式？

A: 支持 `.npy`, `.csv`, `.txt`, `.mat` 格式。多通道信号应为 (n_samples, n_channels) 形状。

### Q: 如何选择分类器？

A: 
- **随机森林**: 训练快，可解释性好，适合特征向量输入
- **CNN**: 可以处理原始信号，捕捉复杂模式，但训练较慢，需要更多数据

### Q: 没有预训练模型怎么办？

A: 首次使用需要先训练模型。可以使用 `generate-data` 命令生成模拟数据进行训练，或使用真实故障数据训练。

## 技术栈

- **信号处理**: NumPy, SciPy
- **时频分析**: PyWavelets
- **机器学习**: scikit-learn (Random Forest)
- **深度学习**: PyTorch (CNN)
- **命令行**: Click
- **数据处理**: pandas, joblib
- **进度显示**: tqdm

## License

MIT License
