#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速入门示例
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bearing_diagnosis.data_generator import generate_bearing_signal
from bearing_diagnosis import Preprocessor, BearingFaultFrequency, FeatureExtractor

# 1. 设置参数
fs = 25600.0  # 采样频率
duration = 1.0  # 信号时长

# 2. 生成模拟信号（内圈故障，早期）
print("生成模拟振动信号...")
signal = generate_bearing_signal(
    fs=fs,
    duration=duration,
    fault_type='inner_race',
    severity='early',
    n_channels=2,
    random_state=42
)
print(f"信号形状: {signal.shape}")

# 3. 保存信号文件
np.save('sample_signal.npy', signal)
print("信号已保存到 sample_signal.npy")

# 4. 预处理
print("\n信号预处理...")
bearing = BearingFaultFrequency(
    n_rolling_elements=9,
    pitch_diameter=39.04,
    rolling_element_diameter=7.94
)
fault_freqs = bearing.calculate(50.0)
low_freq, high_freq = bearing.get_filter_band(50.0)

preprocessor = Preprocessor(fs=fs)
processed = preprocessor.preprocess(signal, low_freq, high_freq)

# 5. 特征提取
print("\n特征提取...")
extractor = FeatureExtractor(fs=fs)
features, feature_names = extractor.extract(processed, fault_freqs)
print(f"提取了 {len(feature_names)} 个特征")

# 6. 打印部分特征
print("\n前10个特征值:")
for i, (name, value) in enumerate(zip(feature_names[:10], features[0][:10])):
    print(f"  {i+1:2d}. {name:30s} = {value:.6f}")

print("\n完成! 现在可以运行:")
print("  python -m bearing_diagnosis.cli predict sample_signal.npy")
