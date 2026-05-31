import click
import numpy as np
import os
import json
from typing import Optional
import warnings

from .preprocessing import Preprocessor, BearingFaultFrequency
from .feature_extraction import FeatureExtractor
from .classifier import BearingClassifier, FAULT_TYPES, SEVERITY_LEVELS
from .explainability import FeatureExplainer
from .utils import load_signal, save_results, load_model, save_model


warnings.filterwarnings('ignore')


@click.group()
@click.version_option(version='1.0.0')
def main():
    """轴承故障诊断工具 - 基于振动信号的智能故障诊断"""
    pass


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='diagnosis_result.json',
              help='结果输出文件路径')
@click.option('--model-path', '-m', type=click.Path(exists=True),
              help='训练好的模型路径')
@click.option('--classifier-type', '-c', type=click.Choice(['random_forest', 'cnn']),
              default='random_forest', help='分类器类型')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--n-rolling-elements', type=int, default=9, help='滚动体数量')
@click.option('--pitch-diameter', type=float, default=39.04, help='节径 (mm)')
@click.option('--rolling-diameter', type=float, default=7.94, help='滚动体直径 (mm)')
@click.option('--contact-angle', type=float, default=0.0, help='接触角 (度)')
@click.option('--rotational-speed', type=float, default=50.0, help='转速 (Hz)')
@click.option('--low-freq', type=float, default=None, help='带通滤波低截止频率 (Hz)')
@click.option('--high-freq', type=float, default=None, help='带通滤波高截止频率 (Hz)')
@click.option('--wavelet', type=str, default='db4', help='小波基函数')
@click.option('--wavelet-level', type=int, default=4, help='小波包分解层数')
@click.option('--explain/--no-explain', default=True, help='是否生成可解释性报告')
@click.option('--top-k', type=int, default=10, help='显示前K个重要特征')
@click.option('--format', type=click.Choice(['json', 'csv', 'pickle']),
              default='json', help='输出格式')
@click.option('--enhance-early/--no-enhance-early', default=True,
              help='是否启用早期故障增强处理')
@click.option('--multi-fault-threshold', type=float, default=0.15,
              help='多故障检测概率阈值 (默认0.15)')
@click.option('--use-spectral-kurtosis/--no-use-spectral-kurtosis', default=True,
              help='是否使用谱峭度寻找最优滤波频带（推荐启用）')
@click.option('--use-adaptive-filter/--no-use-adaptive-filter', default=False,
              help='是否使用自适应滤波增强信号（可能削除微弱信号，谨慎使用）')
def predict(input_file, output, model_path, classifier_type, fs,
            n_rolling_elements, pitch_diameter, rolling_diameter,
            contact_angle, rotational_speed, low_freq, high_freq,
            wavelet, wavelet_level, explain, top_k, format,
            enhance_early, multi_fault_threshold,
            use_spectral_kurtosis, use_adaptive_filter):
    """对振动信号进行故障诊断预测"""
    
    click.echo("=" * 60)
    click.echo("轴承故障诊断系统 (增强版)")
    click.echo("=" * 60)
    
    click.echo(f"\n[1/5] 加载信号数据: {input_file}")
    signal_data = load_signal(input_file)
    click.echo(f"  数据形状: {signal_data.shape} (样本数 x 通道数)")
    
    click.echo(f"\n[2/5] 计算轴承故障特征频率")
    bearing = BearingFaultFrequency(
        n_rolling_elements=n_rolling_elements,
        pitch_diameter=pitch_diameter,
        rolling_element_diameter=rolling_diameter,
        contact_angle=contact_angle
    )
    fault_freqs = bearing.calculate(rotational_speed)
    
    click.echo("  实际频率 (Hz):")
    for name in ['rotational_frequency', 'ftf', 'bpfi', 'bpfo', 'bsf']:
        click.echo(f"    {name:22s}: {fault_freqs[name]:.2f} Hz")
    
    click.echo("\n  归一化频率系数 (×转速):")
    normalized = fault_freqs.get('normalized', {})
    for name in ['ftf', 'bpfi', 'bpfo', 'bsf']:
        coeff = normalized.get(name, 0)
        click.echo(f"    {name:22s}: {coeff:.4f}")
    
    if low_freq is None or high_freq is None:
        low_freq, high_freq = bearing.get_filter_band(rotational_speed)
        click.echo(f"\n  自动计算滤波范围: [{low_freq:.2f}, {high_freq:.2f}] Hz")
    
    click.echo(f"\n[3/5] 信号预处理")
    preprocessor = Preprocessor(
        fs=fs,
        use_spectral_kurtosis=use_spectral_kurtosis,
        use_adaptive_filter=use_adaptive_filter
    )
    processed_data = preprocessor.preprocess(
        signal_data,
        low_freq=low_freq,
        high_freq=high_freq,
        rotational_speed=rotational_speed,
        enhance_early_fault=enhance_early
    )
    
    steps = []
    steps.append("去趋势")
    if enhance_early:
        steps.append("同步平均")
    if use_adaptive_filter:
        steps.append("自适应滤波")
    if use_spectral_kurtosis:
        steps.append("谱峭度选带")
    steps.append("带通滤波")
    click.echo(f"  预处理流程: {' → '.join(steps)}")
    
    if preprocessor.optimal_band_:
        click.echo(f"  谱峭度最优频带: [{preprocessor.optimal_band_[0]:.2f}, "
                  f"{preprocessor.optimal_band_[1]:.2f}] Hz")
    
    click.echo(f"\n[4/5] 特征提取")
    extractor = FeatureExtractor(
        fs=fs,
        wavelet=wavelet,
        wavelet_level=wavelet_level
    )
    features, feature_names = extractor.extract(processed_data, fault_freqs)
    click.echo(f"  提取特征数量: {len(feature_names)}")
    click.echo(f"  其中包含归一化特征（转速无关）")
    
    click.echo(f"\n[5/5] 故障诊断")
    classifier = BearingClassifier(classifier_type=classifier_type)
    
    if model_path and os.path.exists(model_path):
        click.echo(f"  加载模型: {model_path}")
        n_features = features.shape[1]
        classifier.load(model_path, n_features=n_features)
    else:
        click.echo("  警告: 未加载预训练模型，使用模拟预测结果")
        classifier._init_model(n_features=features.shape[1])
        mock_result = _mock_prediction(fault_freqs, features, multi_fault=True)
    
    if model_path and os.path.exists(model_path):
        prediction = classifier.predict_single(
            features,
            multi_fault_threshold=multi_fault_threshold,
            detect_multiple=True
        )
        
        rule_based = classifier.detect_multi_fault_from_features(
            features.flatten(), feature_names
        )
        prediction['rule_based_detection'] = rule_based
    else:
        prediction = mock_result
    
    click.echo("\n" + "=" * 60)
    click.echo("诊断结果")
    click.echo("=" * 60)
    
    if prediction.get('is_multi_fault', False):
        click.echo("\n⚠️  检测到多个故障同时存在!")
    
    click.echo(f"\n主故障类型: {_format_fault_type(prediction['fault_type'])}")
    click.echo(f"置信度: {prediction['fault_type_probability']:.2%}")
    click.echo(f"\n严重程度: {_format_severity(prediction['severity'])}")
    click.echo(f"置信度: {prediction['severity_probability']:.2%}")
    
    if 'all_detected_faults' in prediction:
        click.echo("\n所有检测到的故障:")
        for i, (fault, prob) in enumerate(zip(
                prediction['all_detected_faults'],
                prediction['all_detected_probabilities']
        )):
            marker = "★" if i == 0 else "  "
            bar = '█' * int(prob * 30)
            click.echo(f"  {marker} {i+1}. {_format_fault_type(fault):15s}: "
                      f"{bar} {prob:.2%}")
    
    click.echo("\n各类别概率:")
    for cls, prob in prediction['fault_type_probabilities'].items():
        bar = '█' * int(prob * 30)
        click.echo(f"  {_format_fault_type(cls):15s}: {bar} {prob:.2%}")
    
    if 'rule_based_detection' in prediction:
        click.echo("\n基于特征规则的辅助检测:")
        rule_based = prediction['rule_based_detection']
        for fault, score in rule_based['fault_scores'].items():
            bar = '█' * int(score * 30)
            detected = "✓" if score >= 0.5 else " "
            click.echo(f"  {detected} {_format_fault_type(fault):15s}: "
                      f"{bar} {score:.2f}")
        
        if len(rule_based['detected_faults']) > 1:
            click.echo(f"\n  规则检测识别到 {len(rule_based['detected_faults'])} 个潜在故障:")
            for item in rule_based['detected_faults']:
                click.echo(f"    • {_format_fault_type(item['fault_type'])} "
                          f"(得分: {item['score']:.2f})")
    
    if explain and model_path and os.path.exists(model_path):
        click.echo("\n" + "=" * 60)
        click.echo("可解释性分析")
        click.echo("=" * 60)
        
        explainer = FeatureExplainer(feature_names=feature_names)
        importance_results = explainer.analyze_importance(
            classifier, top_k=top_k)
        
        report = explainer.generate_explanation_report(prediction, top_k=top_k)
        
        click.echo(f"\nTop {top_k} 重要特征:")
        for i, feat in enumerate(report['top_features'][:top_k]):
            click.echo(f"  {i+1:2d}. {feat['feature']:35s} - "
                      f"重要性: {feat['importance']:.4f} "
                      f"({feat['relative_importance']:.2%})")
        
        click.echo("\n特征类别贡献:")
        for cat, stats in report['category_summary'].items():
            bar = '█' * int(stats['relative_importance'] * 30)
            click.echo(f"  {_format_category(cat):15s}: {bar} "
                      f"{stats['relative_importance']:.2%}")
        
        click.echo("\n关键驱动因素:")
        for driver in report['key_drivers']:
            click.echo(f"  • {driver['feature']}")
            click.echo(f"    {driver['interpretation']}")
        
        click.echo(f"\n建议: {report['recommendation']}")
        
        prediction['feature_importance'] = importance_results
        prediction['explanation_report'] = report
    
    click.echo(f"\n保存结果到: {output}")
    save_results(prediction, output, format=format)
    
    click.echo("\n" + "=" * 60)
    click.echo("诊断完成!")
    click.echo("=" * 60)


@main.command()
@click.option('--data-path', '-d', type=click.Path(exists=True), required=True,
              help='训练数据路径（包含特征矩阵和标签）')
@click.option('--output-model', '-o', type=click.Path(),
              default='bearing_classifier.pkl', help='模型保存路径')
@click.option('--classifier-type', '-c', type=click.Choice(['random_forest', 'cnn']),
              default='random_forest', help='分类器类型')
@click.option('--n-estimators', type=int, default=200, help='随机森林树的数量')
@click.option('--epochs', type=int, default=50, help='CNN训练轮数')
@click.option('--batch-size', type=int, default=32, help='批次大小')
@click.option('--learning-rate', type=float, default=1e-3, help='学习率')
@click.option('--test-size', type=float, default=0.2, help='测试集比例')
@click.option('--cv', type=int, default=5, help='交叉验证折数（仅随机森林）')
def train(data_path, output_model, classifier_type, n_estimators, epochs,
          batch_size, learning_rate, test_size, cv):
    """训练故障诊断模型"""
    
    click.echo("=" * 60)
    click.echo("模型训练")
    click.echo("=" * 60)
    
    click.echo(f"\n[1/4] 加载训练数据: {data_path}")
    data = np.load(data_path, allow_pickle=True).item()
    X = data['X']
    y_type = data['y_type']
    y_severity = data['y_severity']
    feature_names = data.get('feature_names', None)
    
    click.echo(f"  样本数量: {X.shape[0]}")
    click.echo(f"  特征数量: {X.shape[1]}")
    click.echo(f"  故障类型分布: {np.unique(y_type, return_counts=True)}")
    click.echo(f"  严重程度分布: {np.unique(y_severity, return_counts=True)}")
    
    click.echo(f"\n[2/4] 初始化分类器: {classifier_type}")
    if classifier_type == 'random_forest':
        classifier = BearingClassifier(
            classifier_type='random_forest',
            n_estimators=n_estimators
        )
    else:
        classifier = BearingClassifier(
            classifier_type='cnn',
            n_features=X.shape[1],
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate
        )
    
    click.echo(f"\n[3/4] 训练模型...")
    if classifier_type == 'random_forest':
        results = classifier.fit(X, y_type, y_severity, cv=cv)
        click.echo(f"  交叉验证类型准确率: {results['cv_type_accuracy']:.4f} ± {results['cv_type_std']:.4f}")
        click.echo(f"  交叉验证严重程度准确率: {results['cv_severity_accuracy']:.4f} ± {results['cv_severity_std']:.4f}")
        click.echo(f"  训练集类型准确率: {results['train_type_accuracy']:.4f}")
        click.echo(f"  训练集严重程度准确率: {results['train_severity_accuracy']:.4f}")
    else:
        from .utils import train_test_split_data
        X_train, X_val, y_type_train, y_type_val, y_sev_train, y_sev_val = \
            train_test_split_data(X, y_type, y_severity, test_size=test_size)
        results = classifier.fit(
            X_train, y_type_train, y_sev_train,
            X_val=X_val, y_val_type=y_type_val, y_val_severity=y_sev_val
        )
        click.echo(f"  最终验证类型准确率: {results['val_type_acc'][-1]:.4f}")
        click.echo(f"  最终验证严重程度准确率: {results['val_severity_acc'][-1]:.4f}")
    
    click.echo(f"\n[4/4] 保存模型: {output_model}")
    classifier.save(output_model)
    
    if feature_names is not None and classifier_type == 'random_forest':
        click.echo("\n特征重要性 Top 10:")
        importance = classifier.get_feature_importance()
        if importance is not None:
            top_indices = np.argsort(importance)[::-1][:10]
            for i, idx in enumerate(top_indices):
                click.echo(f"  {i+1:2d}. {feature_names[idx]:35s} - {importance[idx]:.4f}")
    
    click.echo("\n训练完成!")


@main.command()
@click.option('--n-samples', type=int, default=100, help='生成样本数量')
@click.option('--n-channels', type=int, default=2, help='通道数量')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--duration', type=float, default=1.0, help='信号时长 (秒)')
@click.option('--output', '-o', type=click.Path(), default='sample_data.npy',
              help='输出文件路径')
@click.option('--seed', type=int, default=42, help='随机种子')
@click.option('--include-multi-fault/--no-include-multi-fault', default=True,
              help='是否包含多故障样本')
@click.option('--multi-fault-ratio', type=float, default=0.2,
              help='多故障样本占比 (默认0.2)')
def generate_data(n_samples, n_channels, fs, duration, output, seed,
                  include_multi_fault, multi_fault_ratio):
    """生成模拟轴承故障数据（支持多故障）"""
    
    click.echo("生成模拟轴承故障数据...")
    
    from .data_generator import generate_bearing_dataset
    
    X, y_type, y_severity, feature_names, y_type_multi = generate_bearing_dataset(
        n_samples=n_samples,
        n_channels=n_channels,
        fs=fs,
        duration=duration,
        include_multi_fault=include_multi_fault,
        multi_fault_ratio=multi_fault_ratio,
        random_state=seed
    )
    
    data = {
        'X': X,
        'y_type': y_type,
        'y_severity': y_severity,
        'y_type_multi': y_type_multi,
        'feature_names': feature_names,
        'fs': fs,
        'n_channels': n_channels,
        'duration': duration,
        'include_multi_fault': include_multi_fault,
        'multi_fault_ratio': multi_fault_ratio
    }
    
    np.save(output, data, allow_pickle=True)
    click.echo(f"数据已保存到: {output}")
    click.echo(f"  样本数: {n_samples}, 特征数: {len(feature_names)}")
    
    if include_multi_fault:
        n_multi = sum(1 for y in y_type_multi if len(y) > 1)
        click.echo(f"  其中多故障样本: {n_multi} ({n_multi/n_samples:.1%})")


def _mock_prediction(fault_freqs: dict, features: np.ndarray,
                     multi_fault: bool = True) -> dict:
    """生成模拟预测结果（支持多故障）"""
    np.random.seed(42)
    
    type_probs = np.random.dirichlet(np.ones(5))
    type_probs = type_probs / type_probs.sum()
    
    type_probs[2] = 0.45
    type_probs[4] = 0.25
    type_probs = type_probs / type_probs.sum()
    type_idx = np.argmax(type_probs)
    
    severity_probs = np.random.dirichlet(np.ones(4))
    severity_probs = severity_probs / severity_probs.sum()
    severity_probs[1] = 0.6
    severity_probs = severity_probs / severity_probs.sum()
    severity_idx = np.argmax(severity_probs)
    
    result = {
        'fault_type': FAULT_TYPES[type_idx],
        'fault_type_probability': float(type_probs[type_idx]),
        'fault_type_probabilities': {
            cls: float(prob) for cls, prob in zip(FAULT_TYPES, type_probs)
        },
        'severity': SEVERITY_LEVELS[severity_idx],
        'severity_probability': float(severity_probs[severity_idx]),
        'severity_probabilities': {
            cls: float(prob) for cls, prob in zip(SEVERITY_LEVELS, severity_probs)
        },
        'note': '这是模拟结果，请使用预训练模型获得真实预测'
    }
    
    if multi_fault:
        fault_classes = [c for c in FAULT_TYPES if c != 'normal']
        fault_probs = np.array([type_probs[FAULT_TYPES.index(c)] for c in fault_classes])
        
        threshold = 0.15
        detected_idx = np.where(fault_probs >= threshold)[0]
        sorted_idx = np.argsort(fault_probs[detected_idx])[::-1]
        
        all_faults = [fault_classes[i] for i in detected_idx[sorted_idx]]
        all_probs = [float(fault_probs[i]) for i in detected_idx[sorted_idx]]
        
        if len(all_faults) == 0:
            all_faults = ['normal']
            all_probs = [float(type_probs[0])]
        
        result['all_detected_faults'] = all_faults
        result['all_detected_probabilities'] = all_probs
        result['multi_fault_details'] = [
            {'fault_type': f, 'probability': p}
            for f, p in zip(all_faults, all_probs)
        ]
        result['is_multi_fault'] = len(all_faults) > 1
    
    return result


def _format_fault_type(fault_type: str) -> str:
    """格式化故障类型显示"""
    mapping = {
        'normal': '正常',
        'inner_race': '内圈故障',
        'outer_race': '外圈故障',
        'rolling_element': '滚动体故障',
        'cage': '保持架故障'
    }
    return mapping.get(fault_type, fault_type)


def _format_severity(severity: str) -> str:
    """格式化严重程度显示"""
    mapping = {
        'normal': '正常',
        'early': '早期',
        'medium': '中期',
        'late': '晚期'
    }
    return mapping.get(severity, severity)


def _format_category(category: str) -> str:
    """格式化特征类别"""
    mapping = {
        'time_domain': '时域特征',
        'frequency_domain': '频域特征',
        'time_frequency_domain': '时频域特征'
    }
    return mapping.get(category, category)


@main.command()
@click.option('--data-path', '-d', type=click.Path(exists=True), required=True,
              help='原始数据文件路径')
@click.option('--output', '-o', type=click.Path(), default='balanced_data.npy',
              help='平衡后数据输出路径')
@click.option('--target-count', type=int, default=None,
              help='目标样本数（None则使用最多类的数量）')
@click.option('--epochs-per-class', type=int, default=200,
              help='每个类的GAN训练轮数')
@click.option('--use-gan/--no-use-gan', default=True,
              help='是否使用GAN增强（False则使用传统增强）')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--n-channels', type=int, default=1, help='通道数')
def augment_data(data_path, output, target_count, epochs_per_class, use_gan, fs, n_channels):
    """使用GAN进行数据增强，缓解样本不平衡"""
    
    click.echo("=" * 60)
    click.echo("GAN数据增强 - 样本平衡")
    click.echo("=" * 60)
    
    from .gan_augmentation import GANDataAugmenter
    
    click.echo(f"\n[1/4] 加载原始数据: {data_path}")
    data = np.load(data_path, allow_pickle=True).item()
    X = data['X']
    y_type = data['y_type']
    feature_names = data.get('feature_names', None)
    
    click.echo(f"  样本数: {len(X)}, 特征数: {X.shape[1]}")
    unique, counts = np.unique(y_type, return_counts=True)
    click.echo("  原始分布:")
    for u, c in zip(unique, counts):
        click.echo(f"    {u}: {c}")
    
    click.echo(f"\n[2/4] 初始化数据增强器")
    data_n_channels = data.get('n_channels', n_channels)
    augmenter = GANDataAugmenter(
        fs=fs,
        n_channels=data_n_channels,
        use_feature_space=True
    )
    
    click.echo(f"\n[3/4] 平衡数据集（{epochs_per_class}轮/类）...")
    X_balanced, y_balanced = augmenter.balance_dataset(
        X=X,
        y=y_type,
        target_count=target_count,
        epochs_per_class=epochs_per_class,
        verbose=True
    )
    
    click.echo(f"\n[4/4] 保存平衡后数据: {output}")
    balanced_data = {
        'X': X_balanced,
        'y_type': y_balanced,
        'y_severity': data.get('y_severity', np.array(['normal']*len(y_balanced))),
        'feature_names': feature_names,
        'original_X': X,
        'original_y': y_type,
        'augmented': True,
        'augment_method': 'GAN' if use_gan else 'traditional',
        'fs': fs
    }
    np.save(output, balanced_data, allow_pickle=True)
    
    unique_bal, counts_bal = np.unique(y_balanced, return_counts=True)
    click.echo("\n✓ 数据增强完成!")
    click.echo(f"  总样本数: {len(X_balanced)}")
    click.echo(f"  新增样本: {len(X_balanced) - len(X)}")
    click.echo("  平衡后分布:")
    for u, c in zip(unique_bal, counts_bal):
        click.echo(f"    {u}: {c}")


@main.command()
@click.option('--data-path', '-d', type=click.Path(exists=True), required=False,
              help='RUL训练数据路径（--generate-data时不需要）')
@click.option('--output-model', '-o', type=click.Path(), default='rul_model.joblib',
              help='RUL模型保存路径')
@click.option('--model-type', '-m', type=click.Choice(['random_forest', 'gradient_boosting', 'ridge', 'cnn']),
              default='random_forest', help='回归模型类型')
@click.option('--n-estimators', type=int, default=100, help='集成学习树的数量')
@click.option('--epochs', type=int, default=50, help='CNN训练轮数')
@click.option('--batch-size', type=int, default=32, help='批次大小')
@click.option('--max-rul', type=float, default=100.0, help='最大RUL值')
@click.option('--generate-data/--no-generate-data', default=False,
              help='是否生成模拟RUL数据')
@click.option('--n-samples', type=int, default=200, help='生成样本数')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--n-channels', type=int, default=1, help='通道数')
@click.option('--cv', type=int, default=5, help='交叉验证折数')
def train_rul(data_path, output_model, model_type, n_estimators, epochs, batch_size,
              max_rul, generate_data, n_samples, fs, n_channels, cv):
    """训练剩余寿命预测（RUL）模型"""
    
    if not generate_data and data_path is None:
        raise click.UsageError("需要提供 --data-path 或启用 --generate-data")
    
    click.echo("=" * 60)
    click.echo("剩余寿命预测 (RUL) - 模型训练")
    click.echo("=" * 60)
    
    from .rul_prediction import RULPredictor
    from .utils import train_test_split_data
    
    predictor = RULPredictor(
        model_type=model_type,
        fs=fs,
        max_rul=max_rul,
        n_estimators=n_estimators
    )
    
    if generate_data:
        click.echo(f"\n[1/4] 生成模拟RUL数据集（{n_samples}样本）...")
        X, y = predictor.generate_rul_dataset(
            n_samples=n_samples,
            n_channels=n_channels,
            verbose=True
        )
    else:
        click.echo(f"\n[1/4] 加载RUL数据: {data_path}")
        data = np.load(data_path, allow_pickle=True).item()
        X = data['X']
        y = data['y_rul']
    
    click.echo(f"  样本数: {len(X)}, 特征数: {X.shape[1]}")
    click.echo(f"  RUL范围: {y.min():.2f} ~ {y.max():.2f}")
    
    click.echo(f"\n[2/4] 划分训练/测试集（测试集20%）")
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    click.echo(f"\n[3/4] 训练 {model_type} 模型...")
    predictor.fit(
        X=X_train,
        y=y_train,
        X_test=X_test,
        y_test=y_test,
        epochs=epochs,
        batch_size=batch_size,
        cv=cv,
        verbose=True
    )
    
    click.echo(f"\n[4/4] 保存模型: {output_model}")
    predictor.save(output_model)
    
    metrics = predictor.evaluate(X_test, y_test)
    click.echo("\n✓ RUL模型训练完成!")
    click.echo("  测试集性能:")
    click.echo(f"    RMSE: {metrics['rmse']:.4f}")
    click.echo(f"    MAE:  {metrics['mae']:.4f}")
    click.echo(f"    MAPE: {metrics['mape']:.2f}%")
    click.echo(f"    R²:   {metrics['r2']:.4f}")


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--model-path', '-m', type=click.Path(exists=True), required=True,
              help='训练好的RUL模型路径')
@click.option('--output', '-o', type=click.Path(), default='rul_result.json',
              help='结果输出文件路径')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--n-rolling-elements', type=int, default=9, help='滚动体数量')
@click.option('--pitch-diameter', type=float, default=39.04, help='节径 (mm)')
@click.option('--rolling-diameter', type=float, default=7.94, help='滚动体直径 (mm)')
@click.option('--contact-angle', type=float, default=0.0, help='接触角 (度)')
@click.option('--rotational-speed', type=float, default=50.0, help='转速 (Hz)')
@click.option('--return-confidence/--no-return-confidence', default=True,
              help='是否返回置信区间')
def predict_rul(input_file, model_path, output, fs,
                n_rolling_elements, pitch_diameter, rolling_diameter,
                contact_angle, rotational_speed, return_confidence):
    """预测剩余寿命（RUL）"""
    
    click.echo("=" * 60)
    click.echo("剩余寿命预测 (RUL)")
    click.echo("=" * 60)
    
    from .rul_prediction import RULPredictor
    from .preprocessing import Preprocessor, BearingFaultFrequency
    from .feature_extraction import FeatureExtractor
    from .utils import load_signal, save_results
    
    click.echo(f"\n[1/5] 加载信号数据: {input_file}")
    signal_data = load_signal(input_file)
    click.echo(f"  数据形状: {signal_data.shape} (样本数 x 通道数)")
    
    click.echo(f"\n[2/5] 加载RUL模型: {model_path}")
    predictor = RULPredictor(fs=fs)
    predictor.load(model_path)
    click.echo(f"  模型类型: {predictor.model_type}")
    click.echo(f"  最大RUL: {predictor.max_rul:.2f}")
    
    click.echo(f"\n[3/5] 信号预处理")
    bearing = BearingFaultFrequency(
        n_rolling_elements=n_rolling_elements,
        pitch_diameter=pitch_diameter,
        rolling_element_diameter=rolling_diameter,
        contact_angle=contact_angle
    )
    fault_freqs = bearing.calculate(rotational_speed)
    
    preprocessor = Preprocessor(fs=fs)
    feature_extractor = FeatureExtractor(fs=fs)
    
    processed_data = preprocessor.preprocess(
        signal_data,
        rotational_speed=rotational_speed
    )
    
    click.echo(f"\n[4/5] 特征提取与RUL预测")
    features, feature_names = feature_extractor.extract(
        processed_data,
        fault_freqs=fault_freqs
    )
    
    if return_confidence:
        rul_pred, rul_lower, rul_upper = predictor.predict(
            features,
            return_confidence=True
        )
        rul = float(rul_pred[0])
        lower = float(rul_lower[0])
        upper = float(rul_upper[0])
    else:
        rul_pred = predictor.predict(features)
        rul = float(rul_pred[0])
    
    click.echo(f"\n[5/5] 预测结果")
    click.echo("=" * 60)
    click.echo(f"\n剩余寿命预测:")
    click.echo(f"  RUL: {rul:.2f} 小时")
    if return_confidence:
        click.echo(f"  95%置信区间: [{lower:.2f}, {upper:.2f}] 小时")
    
    if rul > predictor.max_rul * 0.7:
        health_status = "良好"
        color = "green"
    elif rul > predictor.max_rul * 0.3:
        health_status = "中等"
        color = "yellow"
    else:
        health_status = "危险"
        color = "red"
    
    click.echo(f"\n健康状态: {health_status}")
    
    if rul < 20:
        click.echo("\n⚠️  警告: 剩余寿命不足20小时，建议尽快安排维护!")
    
    result = {
        'rul_hours': rul,
        'rul_unit': 'hours',
        'health_status': health_status,
        'confidence_level': 0.95 if return_confidence else None,
        'lower_bound': lower if return_confidence else None,
        'upper_bound': upper if return_confidence else None,
        'max_rul': predictor.max_rul,
        'features_used': len(feature_names),
        'model_type': predictor.model_type
    }
    
    save_results(result, output)
    click.echo(f"\n结果已保存到: {output}")
    click.echo("\n✓ RUL预测完成!")


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--model-path', '-m', type=click.Path(exists=True), default=None,
              help='训练好的分类模型路径')
@click.option('--rul-model-path', type=click.Path(exists=True), default=None,
              help='RUL模型路径')
@click.option('--output', '-o', type=click.Path(), default='streaming_result.json',
              help='结果输出文件路径')
@click.option('--fs', type=float, default=25600.0, help='采样频率 (Hz)')
@click.option('--window-size', type=int, default=12800,
              help='滑动窗口大小（样本点数，默认0.5秒）')
@click.option('--step-size', type=int, default=2560,
              help='滑动步长（样本点数，默认0.1秒）')
@click.option('--rotational-speed', type=float, default=50.0, help='转速 (Hz)')
@click.option('--n-rolling-elements', type=int, default=9, help='滚动体数量')
@click.option('--pitch-diameter', type=float, default=39.04, help='节径 (mm)')
@click.option('--rolling-diameter', type=float, default=7.94, help='滚动体直径 (mm)')
@click.option('--alarm-threshold', type=float, default=0.5,
              help='告警阈值（故障概率）')
@click.option('--smoothing-window', type=int, default=5,
              help='结果平滑窗口大小')
@click.option('--show-progress/--no-show-progress', default=True,
              help='是否显示处理进度')
@click.option('--enable-rul/--no-enable-rul', default=True,
              help='是否启用RUL预测')
@click.option('--enable-explain/--no-enable-explain', default=False,
              help='是否启用可解释性分析')
def stream_diagnose(input_file, model_path, rul_model_path, output, fs,
                    window_size, step_size, rotational_speed,
                    n_rolling_elements, pitch_diameter, rolling_diameter,
                    alarm_threshold, smoothing_window, show_progress,
                    enable_rul, enable_explain):
    """流式故障诊断 - 滑动窗口实时处理"""
    
    click.echo("=" * 60)
    click.echo("流式故障诊断系统")
    click.echo("=" * 60)
    
    from .streaming import StreamingDiagnostics
    from .classifier import BearingClassifier
    from .rul_prediction import RULPredictor
    from .utils import load_signal
    
    click.echo(f"\n[1/6] 加载信号数据: {input_file}")
    signal_data = load_signal(input_file)
    click.echo(f"  数据形状: {signal_data.shape}")
    click.echo(f"  总时长: {len(signal_data)/fs:.2f} 秒")
    
    n_channels = signal_data.shape[1] if signal_data.ndim > 1 else 1
    
    click.echo(f"\n[2/6] 加载模型")
    classifier = None
    if model_path:
        classifier = BearingClassifier(classifier_type='random_forest')
        classifier.load(model_path)
        click.echo(f"  ✓ 分类模型: {model_path}")
    else:
        click.echo("  ⚠  未加载分类模型，将使用模拟预测")
    
    rul_predictor = None
    if enable_rul and rul_model_path:
        rul_predictor = RULPredictor(fs=fs)
        rul_predictor.load(rul_model_path)
        click.echo(f"  ✓ RUL模型: {rul_model_path}")
    
    bearing_params = {
        'n_rolling_elements': n_rolling_elements,
        'pitch_diameter': pitch_diameter,
        'rolling_element_diameter': rolling_diameter,
        'contact_angle': 0.0
    }
    
    click.echo(f"\n[3/6] 初始化流式诊断系统")
    click.echo(f"  窗口大小: {window_size} 样本 ({window_size/fs:.2f}秒)")
    click.echo(f"  滑动步长: {step_size} 样本 ({step_size/fs:.2f}秒)")
    click.echo(f"  告警阈值: {alarm_threshold:.0%}")
    
    stream = StreamingDiagnostics(
        fs=fs,
        window_size=window_size,
        step_size=step_size,
        n_channels=n_channels,
        classifier=classifier,
        rul_predictor=rul_predictor,
        bearing_params=bearing_params,
        rotational_speed=rotational_speed,
        smoothing_window=smoothing_window,
        alarm_threshold=alarm_threshold,
        enable_explainability=enable_explain
    )
    
    def alarm_callback(fault_type, alarm_info):
        click.echo(f"\n{'!'*60}")
        click.echo(f"⚠️  告警: {_format_fault_type(fault_type)}")
        click.echo(f"   概率: {alarm_info['probability']:.2%}")
        click.echo(f"   时间: {alarm_info['timestamp']}")
        click.echo(f"{'!'*60}\n")
    
    stream.add_alarm_callback(alarm_callback)
    
    click.echo(f"\n[4/6] 开始流式处理...")
    
    total_windows = (len(signal_data) - window_size) // step_size + 1
    window_count = 0
    
    def progress_callback(result):
        nonlocal window_count
        window_count += 1
        
        if show_progress and window_count % max(1, total_windows // 20) == 0:
            progress = window_count / total_windows * 100
            fd = result.get('fault_diagnosis', {})
            main_fault = fd.get('main_fault', 'unknown')
            prob = fd.get('main_fault_probability', 0)
            rul = result.get('rul_prediction', {}).get('rul', None)
            
            status = f"处理中: {progress:.0f}% | 窗口 {window_count}/{total_windows}"
            status += f" | 故障: {_format_fault_type(main_fault)} ({prob:.0%})"
            if rul is not None:
                status += f" | RUL: {rul:.1f}h"
            
            click.echo(f"\r{status}", nl=False)
    
    results = stream.process_file(
        input_file,
        batch_size=step_size * 10,
        callback=progress_callback
    )
    
    if show_progress:
        click.echo(f"\r处理中: 100% | 窗口 {total_windows}/{total_windows}")
    
    click.echo(f"\n[5/6] 处理完成，共处理 {len(results)} 个窗口")
    
    summary = stream.get_summary()
    
    click.echo(f"\n[6/6] 处理摘要")
    click.echo("-" * 60)
    click.echo(f"  总样本数: {summary['total_samples_processed']}")
    click.echo(f"  总窗口数: {summary['total_windows_processed']}")
    click.echo(f"  处理时长: {summary['processing_duration']:.2f} 秒")
    click.echo(f"\n  故障分布:")
    for ft, count in summary['fault_distribution'].items():
        if count > 0:
            click.echo(f"    {_format_fault_type(ft):12s}: {count:4d} ({count/len(results):.0%})")
    
    click.echo(f"\n  严重程度分布:")
    for sev, count in summary['severity_distribution'].items():
        if count > 0:
            click.echo(f"    {_format_severity(sev):6s}: {count:4d} ({count/len(results):.0%})")
    
    click.echo(f"\n  告警次数: {summary['alarm_count']}")
    click.echo(f"  多故障检测: {summary['multi_fault_count']} 次")
    
    if summary['average_rul'] is not None:
        click.echo(f"  平均RUL: {summary['average_rul']:.2f} 小时")
    
    active_alarms = [k for k, v in summary['alarm_status'].items() if v]
    if active_alarms:
        click.echo(f"\n⚠️  当前活跃告警:")
        for alarm in active_alarms:
            click.echo(f"    - {_format_fault_type(alarm)}")
    
    click.echo(f"\n保存完整结果: {output}")
    stream.save_results(output)
    
    click.echo("\n✓ 流式诊断完成!")


if __name__ == '__main__':
    main()
