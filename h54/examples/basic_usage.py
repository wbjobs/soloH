#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用示例：轴承故障诊断完整流程
=================================
这个示例展示了如何使用轴承故障诊断工具进行完整的故障诊断流程
"""

import numpy as np
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bearing_diagnosis import (
    Preprocessor,
    BearingFaultFrequency,
    FeatureExtractor,
    BearingClassifier,
    FeatureExplainer,
    load_signal,
    save_results
)
from bearing_diagnosis.data_generator import generate_bearing_signal


def example_1_basic_prediction():
    """示例1: 基本预测流程"""
    print("=" * 70)
    print("示例1: 基本预测流程")
    print("=" * 70)
    
    fs = 25600.0
    duration = 1.0
    
    print("\n1. 生成模拟故障信号（外圈故障，中期）")
    signal = generate_bearing_signal(
        fs=fs,
        duration=duration,
        fault_type='outer_race',
        severity='medium',
        n_channels=2,
        random_state=42
    )
    print(f"   信号形状: {signal.shape} (样本数 x 通道数)")
    
    print("\n2. 计算轴承故障特征频率")
    bearing = BearingFaultFrequency(
        n_rolling_elements=9,
        pitch_diameter=39.04,
        rolling_element_diameter=7.94,
        contact_angle=0.0
    )
    fault_freqs = bearing.calculate(rotational_speed=50.0)
    for name, freq in fault_freqs.items():
        print(f"   {name:25s}: {freq:.2f} Hz")
    
    low_freq, high_freq = bearing.get_filter_band(50.0)
    print(f"   滤波范围: [{low_freq:.2f}, {high_freq:.2f}] Hz")
    
    print("\n3. 信号预处理")
    preprocessor = Preprocessor(fs=fs)
    processed = preprocessor.preprocess(
        signal, low_freq=low_freq, high_freq=high_freq
    )
    print("   完成: 去趋势 → 带通滤波")
    
    print("\n4. 特征提取")
    extractor = FeatureExtractor(
        fs=fs,
        wavelet='db4',
        wavelet_level=4
    )
    features, feature_names = extractor.extract(processed, fault_freqs)
    print(f"   提取特征数量: {len(feature_names)}")
    print(f"   特征矩阵形状: {features.shape}")
    
    print("\n5. 特征前10个名称:")
    for i, name in enumerate(feature_names[:10]):
        print(f"   {i+1:2d}. {name}")
    
    print("\n" + "=" * 70)
    print("示例1完成!")
    print("=" * 70 + "\n")


def example_2_model_training():
    """示例2: 模型训练流程"""
    print("=" * 70)
    print("示例2: 模型训练流程")
    print("=" * 70)
    
    from bearing_diagnosis.data_generator import generate_bearing_dataset
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    
    print("\n1. 生成训练数据集")
    X, y_type, y_severity, feature_names = generate_bearing_dataset(
        n_samples=200,
        n_channels=1,
        fs=25600.0,
        duration=0.5,
        random_state=42
    )
    print(f"   样本数: {X.shape[0]}, 特征数: {X.shape[1]}")
    
    unique_types, counts_type = np.unique(y_type, return_counts=True)
    unique_sev, counts_sev = np.unique(y_severity, return_counts=True)
    print(f"   故障类型分布: {dict(zip(unique_types, counts_type))}")
    print(f"   严重程度分布: {dict(zip(unique_sev, counts_sev))}")
    
    print("\n2. 划分训练集和测试集")
    X_train, X_test, y_type_train, y_type_test, y_sev_train, y_sev_test = \
        train_test_split(X, y_type, y_severity, test_size=0.3, random_state=42, stratify=y_type)
    print(f"   训练集: {X_train.shape[0]} 样本")
    print(f"   测试集: {X_test.shape[0]} 样本")
    
    print("\n3. 训练随机森林分类器")
    classifier = BearingClassifier(
        classifier_type='random_forest',
        n_estimators=100,
        random_state=42
    )
    results = classifier.fit(
        X_train, y_type_train, y_sev_train,
        cv=3
    )
    print(f"   交叉验证类型准确率: {results['cv_type_accuracy']:.4f} ± {results['cv_type_std']:.4f}")
    print(f"   交叉验证严重程度准确率: {results['cv_severity_accuracy']:.4f} ± {results['cv_severity_std']:.4f}")
    
    print("\n4. 测试集评估")
    predictions = classifier.predict(X_test)
    
    print("\n   故障类型分类报告:")
    print(classification_report(y_type_test, predictions['fault_type']))
    
    print("\n   严重程度分类报告:")
    print(classification_report(y_sev_test, predictions['severity']))
    
    print("\n5. 保存模型")
    model_path = 'example_model.pkl'
    classifier.save(model_path)
    print(f"   模型已保存到: {model_path}")
    
    print("\n" + "=" * 70)
    print("示例2完成!")
    print("=" * 70 + "\n")
    
    return classifier, X_test, y_type_test, y_sev_test, feature_names, model_path


def example_3_explainability(classifier, X_test, y_test, feature_names):
    """示例3: 可解释性分析"""
    print("=" * 70)
    print("示例3: 可解释性分析")
    print("=" * 70)
    
    print("\n1. 初始化可解释性分析器")
    explainer = FeatureExplainer(feature_names=feature_names)
    
    print("\n2. 分析特征重要性")
    importance_results = explainer.analyze_importance(
        classifier,
        X=X_test,
        y=y_test,
        method='model',
        top_k=15
    )
    
    print("\n3. Top 15 重要特征:")
    for i, feat in enumerate(importance_results['top_features'][:15]):
        print(f"   {i+1:2d}. {feat['feature']:35s} - "
              f"重要性: {feat['importance']:.4f} "
              f"({feat['relative_importance']:.2%})")
    
    print("\n4. 特征类别贡献:")
    for cat, stats in importance_results['feature_category_importance'].items():
        cat_name = {
            'time_domain': '时域特征',
            'frequency_domain': '频域特征',
            'time_frequency_domain': '时频域特征'
        }.get(cat, cat)
        print(f"   {cat_name:10s}: {stats['relative_importance']:.2%} "
              f"(共 {stats['n_features']} 个特征)")
    
    print("\n5. 单样本预测与解释:")
    sample_idx = 0
    sample = X_test[sample_idx:sample_idx+1]
    prediction = classifier.predict_single(sample)
    
    print(f"\n   真实类型: {y_test[sample_idx]}")
    print(f"   预测类型: {prediction['fault_type']} "
          f"(置信度: {prediction['fault_type_probability']:.2%})")
    print(f"   预测严重程度: {prediction['severity']} "
          f"(置信度: {prediction['severity_probability']:.2%})")
    
    print("\n6. 生成解释报告:")
    report = explainer.generate_explanation_report(prediction, top_k=10)
    print(f"\n   建议: {report['recommendation']}")
    
    print("\n   关键驱动因素:")
    for driver in report['key_drivers']:
        print(f"   • {driver['feature']}")
        print(f"     {driver['interpretation']}")
    
    print("\n" + "=" * 70)
    print("示例3完成!")
    print("=" * 70 + "\n")


def example_4_preprocessing_detail():
    """示例4: 预处理详细过程"""
    print("=" * 70)
    print("示例4: 预处理详细过程")
    print("=" * 70)
    
    fs = 25600.0
    duration = 1.0
    
    print("\n1. 生成含噪信号")
    signal = generate_bearing_signal(
        fs=fs,
        duration=duration,
        fault_type='inner_race',
        severity='early',
        n_channels=1,
        noise_level=1.0,
        random_state=42
    )
    print(f"   信号形状: {signal.shape}")
    print(f"   原始信号均值: {np.mean(signal):.4f}")
    print(f"   原始信号标准差: {np.std(signal):.4f}")
    
    print("\n2. 去趋势处理")
    preprocessor = Preprocessor(fs=fs, detrend_method='linear')
    detrended = preprocessor.remove_trend(signal)
    print(f"   去趋势后均值: {np.mean(detrended):.4f}")
    
    print("\n3. 带通滤波")
    bearing = BearingFaultFrequency(9, 39.04, 7.94)
    low_freq, high_freq = bearing.get_filter_band(50.0, fault_type='inner')
    print(f"   滤波范围: [{low_freq:.2f}, {high_freq:.2f}] Hz")
    
    filtered = preprocessor.bandpass_filter(detrended, low_freq, high_freq, order=4)
    print(f"   滤波后标准差: {np.std(filtered):.4f}")
    
    print("\n4. 包络检测")
    envelope = preprocessor.envelope_detection(filtered)
    print(f"   包络信号均值: {np.mean(envelope):.4f}")
    
    print("\n5. 包络谱分析")
    freq_axis, env_spec = preprocessor.envelope_spectrum(filtered, low_freq, high_freq)
    print(f"   包络谱频率分辨率: {freq_axis[1]-freq_axis[0]:.2f} Hz")
    print(f"   包络谱峰值频率: {freq_axis[np.argmax(env_spec)]:.2f} Hz")
    
    fault_freqs = bearing.calculate(50.0)
    print(f"\n   内圈故障理论频率: {fault_freqs['bpfi']:.2f} Hz")
    
    print("\n" + "=" * 70)
    print("示例4完成!")
    print("=" * 70 + "\n")


def example_5_feature_extraction_detail():
    """示例5: 特征提取详细过程"""
    print("=" * 70)
    print("示例5: 特征提取详细过程")
    print("=" * 70)
    
    from bearing_diagnosis.feature_extraction import (
        TimeDomainFeatures,
        FrequencyDomainFeatures,
        TimeFrequencyDomainFeatures
    )
    
    fs = 25600.0
    duration = 1.0
    
    print("\n1. 生成不同状态的信号")
    signals = {}
    for fault in ['normal', 'inner_race', 'outer_race']:
        signals[fault] = generate_bearing_signal(
            fs=fs,
            duration=duration,
            fault_type=fault,
            severity='medium' if fault != 'normal' else 'normal',
            n_channels=1,
            random_state=42
        )
    
    print("\n2. 时域特征对比:")
    time_feats = TimeDomainFeatures()
    features_to_show = [
        ('rms', '均方根值', time_feats.root_mean_square),
        ('kurtosis', '峭度', time_feats.kurtosis),
        ('impulse_factor', '脉冲因子', time_feats.impulse_factor),
        ('crest_factor', '峰值因子', time_feats.crest_factor),
    ]
    
    print(f"   {'特征':12s} {'正常':>10s} {'内圈故障':>10s} {'外圈故障':>10s}")
    print("   " + "-" * 46)
    for feat_name, display_name, func in features_to_show:
        values = [func(signals[fault])[0] for fault in signals]
        print(f"   {display_name:12s} {values[0]:10.4f} {values[1]:10.4f} {values[2]:10.4f}")
    
    print("\n3. 频域特征提取:")
    freq_feats = FrequencyDomainFeatures(fs=fs)
    bearing = BearingFaultFrequency(9, 39.04, 7.94)
    fault_freqs = bearing.calculate(50.0)
    
    for fault_name, signal in signals.items():
        freqs, spec = freq_feats.compute_spectrum(signal)
        print(f"\n   {fault_name}:")
        print(f"     频谱质心: {freq_feats._spectral_centroid(freqs, spec)[0]:.2f} Hz")
        print(f"     频谱峭度: {freq_feats._spectral_kurtosis(freqs, spec)[0]:.4f}")
        
        for key in ['bpfi', 'bpfo', 'bsf']:
            amp = freq_feats._get_amplitude_at_freq(freqs, spec, fault_freqs[key])
            print(f"     {key.upper()} ({fault_freqs[key]:6.2f} Hz) 幅值: {amp[0]:.4f}")
    
    print("\n4. 时频域特征 - 小波包能量:")
    tf_feats = TimeFrequencyDomainFeatures(wavelet='db4', level=3)
    
    for fault_name, signal in signals.items():
        energy = tf_feats.wavelet_packet_energy(signal, normalize=True)
        print(f"\n   {fault_name} 小波包能量分布 (8个频段):")
        energy_str = "  ".join([f"{e[0]:.3f}" for e in energy])
        print(f"     {energy_str}")
        
        entropy = tf_feats.wavelet_energy_entropy(signal)
        print(f"     能量熵: {entropy[0]:.4f}")
    
    print("\n" + "=" * 70)
    print("示例5完成!")
    print("=" * 70 + "\n")


def main():
    """运行所有示例"""
    print("\n" + "=" * 70)
    print("轴承故障诊断工具 - 使用示例")
    print("=" * 70)
    
    try:
        example_1_basic_prediction()
        classifier, X_test, y_type_test, y_sev_test, feature_names, model_path = \
            example_2_model_training()
        example_3_explainability(classifier, X_test, y_type_test, feature_names)
        example_4_preprocessing_detail()
        example_5_feature_extraction_detail()
        
        print("\n" + "=" * 70)
        print("所有示例运行完成!")
        print("=" * 70)
        print("\n提示:")
        print("  1. 使用命令行工具: bearing-diagnosis predict [信号文件]")
        print("  2. 生成模拟数据: bearing-diagnosis generate-data")
        print("  3. 训练模型: bearing-diagnosis train --data-path [数据文件]")
        
        for f in ['example_model.pkl']:
            if os.path.exists(f):
                os.remove(f)
                print(f"\n已清理临时文件: {f}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
