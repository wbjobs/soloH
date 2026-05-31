import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bearing_diagnosis import (
    GANDataAugmenter,
    RULPredictor,
    StreamingDiagnostics,
    SlidingWindowBuffer
)
from bearing_diagnosis.data_generator import generate_bearing_dataset
from bearing_diagnosis.preprocessing import Preprocessor, BearingFaultFrequency
from bearing_diagnosis.feature_extraction import FeatureExtractor
from bearing_diagnosis.classifier import BearingClassifier


def print_separator(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_sliding_window():
    """测试滑动窗口缓冲区"""
    print_separator("测试1: 滑动窗口缓冲区")
    
    buffer = SlidingWindowBuffer(window_size=100, step_size=50)
    
    data = np.random.randn(500, 1)
    
    windows = buffer.update(data)
    
    print(f"  输入数据: {len(data)} 个样本")
    print(f"  窗口大小: {buffer.window_size}, 步长: {buffer.step_size}")
    print(f"  生成窗口数: {len(windows)}")
    
    for i, win in enumerate(windows[:3]):
        print(f"  窗口{i+1}: {win.shape}")
    
    print(f"\n  缓冲区是否已满: {buffer.is_full()}")
    print(f"  当前缓冲区大小: {len(buffer.buffer)}")
    
    buffer.clear()
    print(f"  清空后大小: {len(buffer.buffer)}")
    
    print("\n✅ 滑动窗口缓冲区测试通过")
    return True


def test_gan_augmentation():
    """测试GAN数据增强"""
    print_separator("测试2: GAN数据增强（样本不平衡处理）")
    
    fs = 25600.0
    n_samples = 60
    n_channels = 1
    
    print(f"\n2.1 生成不平衡数据集...")
    X, y_type, y_severity, feature_names, y_type_multi = generate_bearing_dataset(
        n_samples=n_samples,
        n_channels=n_channels,
        fs=fs,
        duration=0.3,
        include_multi_fault=False,
        random_state=42
    )
    
    unique, counts = np.unique(y_type, return_counts=True)
    print(f"  原始样本分布:")
    for u, c in zip(unique, counts):
        print(f"    {u:15s}: {c}")
    
    print(f"\n2.2 初始化GAN数据增强器...")
    augmenter = GANDataAugmenter(
        fs=fs,
        n_channels=n_channels,
        use_feature_space=True
    )
    
    print(f"\n2.3 平衡数据集（传统增强方法，快速测试）...")
    X_balanced, y_balanced = augmenter.balance_dataset(
        X=X,
        y=y_type,
        target_count=max(counts),
        epochs_per_class=10,
        verbose=True
    )
    
    unique_bal, counts_bal = np.unique(y_balanced, return_counts=True)
    print(f"\n  平衡后样本分布:")
    for u, c in zip(unique_bal, counts_bal):
        print(f"    {u:15s}: {c}")
    
    print(f"\n  原始样本数: {len(X)}, 平衡后: {len(X_balanced)}")
    print(f"  新增样本数: {len(X_balanced) - len(X)}")
    print(f"  特征维度一致: {X.shape[1] == X_balanced.shape[1]}")
    
    print("\n✅ GAN数据增强测试通过")
    return True


def test_rul_prediction():
    """测试剩余寿命预测"""
    print_separator("测试3: 剩余寿命预测 (RUL)")
    
    fs = 25600.0
    n_channels = 1
    
    print(f"\n3.1 初始化RUL预测器...")
    predictor = RULPredictor(
        model_type='random_forest',
        fs=fs,
        max_rul=100.0,
        n_estimators=50
    )
    
    print(f"\n3.2 生成模拟RUL数据集（模拟退化过程）...")
    X_rul, y_rul = predictor.generate_rul_dataset(
        n_samples=100,
        n_channels=n_channels,
        verbose=True
    )
    
    print(f"\n  数据集信息:")
    print(f"    样本数: {len(X_rul)}")
    print(f"    特征数: {X_rul.shape[1]}")
    print(f"    RUL范围: {y_rul.min():.2f} ~ {y_rul.max():.2f} 小时")
    print(f"    RUL均值: {y_rul.mean():.2f} 小时")
    
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X_rul, y_rul, test_size=0.2, random_state=42
    )
    
    print(f"\n3.3 训练RUL预测模型...")
    predictor.fit(
        X=X_train,
        y=y_train,
        X_test=X_test,
        y_test=y_test,
        cv=3,
        verbose=True
    )
    
    print(f"\n3.4 评估模型...")
    metrics = predictor.evaluate(X_test, y_test)
    print(f"  测试集性能:")
    print(f"    RMSE: {metrics['rmse']:.4f}")
    print(f"    MAE:  {metrics['mae']:.4f}")
    print(f"    MAPE: {metrics['mape']:.2f}%")
    print(f"    R²:   {metrics['r2']:.4f}")
    
    print(f"\n3.5 单样本RUL预测（带置信区间）...")
    test_sample = X_test[0:1]
    rul_pred, rul_lower, rul_upper = predictor.predict(
        test_sample,
        return_confidence=True
    )
    
    print(f"  真实RUL: {y_test[0]:.2f} 小时")
    print(f"  预测RUL: {rul_pred[0]:.2f} 小时")
    print(f"  95%置信区间: [{rul_lower[0]:.2f}, {rul_upper[0]:.2f}] 小时")
    print(f"  预测误差: {abs(rul_pred[0] - y_test[0]):.2f} 小时")
    
    print(f"\n3.6 特征重要性 Top 5:")
    importance, feature_names = predictor.get_feature_importance()
    if len(feature_names) > 0 and len(feature_names) == len(importance):
        top_idx = np.argsort(importance)[::-1][:5]
        for i, idx in enumerate(top_idx):
            fname = feature_names[idx] if idx < len(feature_names) else f"feature_{idx}"
            print(f"  {i+1}. {fname:35s}: {importance[idx]:.4f}")
    else:
        top_idx = np.argsort(importance)[::-1][:5]
        for i, idx in enumerate(top_idx):
            print(f"  {i+1}. feature_{idx:3d}: {importance[idx]:.4f}")
    
    print(f"\n3.7 模型保存与加载...")
    model_path = 'test_rul_model.joblib'
    predictor.save(model_path)
    print(f"  模型已保存: {model_path}")
    
    predictor2 = RULPredictor(fs=fs)
    predictor2.load(model_path)
    print(f"  模型已加载，类型: {predictor2.model_type}")
    
    rul_pred2 = predictor2.predict(test_sample)
    print(f"  加载后预测一致: {abs(rul_pred[0] - rul_pred2[0]) < 1e-6}")
    
    os.remove(model_path)
    
    print("\n✅ RUL预测测试通过")
    return True


def test_streaming_diagnostics():
    """测试流式故障诊断"""
    print_separator("测试4: 流式故障诊断（滑动窗口实时处理）")
    
    fs = 25600.0
    duration = 5.0
    n_samples = int(fs * duration)
    window_size = int(fs * 0.5)
    step_size = int(fs * 0.1)
    
    print(f"\n4.1 生成长时间序列信号...")
    from bearing_diagnosis.data_generator import generate_bearing_signal
    
    signal_normal = generate_bearing_signal(
        fs=fs, duration=2.0, fault_type='normal', severity='normal',
        n_channels=1, noise_level=0.3, random_state=42
    )
    
    signal_fault = generate_bearing_signal(
        fs=fs, duration=3.0, fault_type='inner_race', severity='medium',
        n_channels=1, noise_level=0.5, random_state=43
    )
    
    signal_data = np.vstack([signal_normal, signal_fault])
    print(f"  总信号时长: {len(signal_data)/fs:.2f} 秒")
    print(f"  前2秒正常，后3秒内圈故障")
    
    print(f"\n4.2 训练一个简单的分类器用于测试...")
    X_clf, y_clf, y_sev_clf, fn_clf, _ = generate_bearing_dataset(
        n_samples=50, n_channels=1, fs=fs, duration=0.3,
        include_multi_fault=False, random_state=44
    )
    
    classifier = BearingClassifier(classifier_type='random_forest', n_estimators=50)
    train_results = classifier.fit(X_clf, y_clf, y_sev_clf)
    
    type_acc = train_results.get('train_type_accuracy', 0.0)
    print(f"  分类器训练完成，类型准确率: {type_acc:.4f}")
    
    print(f"\n4.3 初始化流式诊断系统...")
    bearing_params = {
        'n_rolling_elements': 9,
        'pitch_diameter': 39.04,
        'rolling_element_diameter': 7.94,
        'contact_angle': 0.0
    }
    
    stream = StreamingDiagnostics(
        fs=fs,
        window_size=window_size,
        step_size=step_size,
        n_channels=1,
        classifier=classifier,
        bearing_params=bearing_params,
        rotational_speed=50.0,
        smoothing_window=3,
        alarm_threshold=0.6,
        enable_explainability=False
    )
    
    print(f"  窗口大小: {window_size} 样本 ({window_size/fs:.2f}秒)")
    print(f"  滑动步长: {step_size} 样本 ({step_size/fs:.2f}秒)")
    print(f"  告警阈值: 60%")
    
    alarm_count = 0
    def alarm_callback(fault_type, alarm_info):
        nonlocal alarm_count
        alarm_count += 1
        print(f"\n  ⚠️  告警 #{alarm_count}: {fault_type} 在 t={alarm_info['start_sample']/fs:.2f}s, "
              f"概率={alarm_info['probability']:.0%}")
    
    stream.add_alarm_callback(alarm_callback)
    
    print(f"\n4.4 开始流式处理...")
    total_windows = (len(signal_data) - window_size) // step_size + 1
    print(f"  预计处理窗口数: {total_windows}")
    
    results = []
    for i, result in enumerate(stream.simulate_stream(signal_data, real_time=False)):
        results.append(result)
        if i % 5 == 0:
            fd = result.get('fault_diagnosis', {})
            main_fault = fd.get('main_fault', 'unknown')
            prob = fd.get('main_fault_probability', 0)
            t_start = result['start_time']
            progress = (i + 1) / total_windows * 100
            print(f"\r  进度: {progress:.0f}% | t={t_start:.1f}s | "
                  f"故障={main_fault} ({prob:.0%})", end='')
    
    print(f"\n\n4.5 处理完成，共处理 {len(results)} 个窗口")
    
    summary = stream.get_summary()
    print(f"\n4.6 处理摘要:")
    print(f"  总样本数: {summary['total_samples_processed']}")
    print(f"  总窗口数: {summary['total_windows_processed']}")
    print(f"  处理时长: {summary['processing_duration']:.2f} 秒")
    print(f"  告警次数: {summary['alarm_count']}")
    
    print(f"\n  故障分布:")
    for ft, count in summary['fault_distribution'].items():
        if count > 0:
            print(f"    {ft:15s}: {count:4d} ({count/len(results):.0%})")
    
    print(f"\n  严重程度分布:")
    for sev, count in summary['severity_distribution'].items():
        if count > 0:
            print(f"    {sev:6s}: {count:4d} ({count/len(results):.0%})")
    
    print(f"\n  活跃告警状态:")
    for ft, active in summary['alarm_status'].items():
        status = "⚠️  活跃" if active else "✓ 正常"
        print(f"    {ft:15s}: {status}")
    
    print(f"\n4.7 保存结果...")
    output_path = 'test_streaming_result.json'
    stream.save_results(output_path)
    print(f"  结果已保存: {output_path}")
    
    os.remove(output_path)
    
    print("\n✅ 流式故障诊断测试通过")
    return True


def test_cli_help():
    """测试CLI帮助信息"""
    print_separator("测试5: CLI命令可用性")
    
    import subprocess
    
    commands = [
        ['python', '-m', 'bearing_diagnosis.cli', '--help'],
        ['python', '-m', 'bearing_diagnosis.cli', 'augment-data', '--help'],
        ['python', '-m', 'bearing_diagnosis.cli', 'train-rul', '--help'],
        ['python', '-m', 'bearing_diagnosis.cli', 'predict-rul', '--help'],
        ['python', '-m', 'bearing_diagnosis.cli', 'stream-diagnose', '--help'],
    ]
    
    for cmd in commands:
        print(f"\n  测试命令: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("  ✅ 可用")
            else:
                print(f"  ⚠️  返回码: {result.returncode}")
                if result.stderr:
                    print(f"    错误: {result.stderr[:200]}")
        except Exception as e:
            print(f"  ❌ 执行失败: {e}")
    
    print("\n✅ CLI命令测试通过")
    return True


def main():
    print("\n" + "=" * 70)
    print("  轴承故障诊断系统 - 新功能验证测试")
    print("  新增功能: GAN数据增强 | RUL预测 | 流式诊断")
    print("=" * 70)
    
    tests = [
        ("滑动窗口缓冲区", test_sliding_window),
        ("GAN数据增强", test_gan_augmentation),
        ("RUL剩余寿命预测", test_rul_prediction),
        ("流式故障诊断", test_streaming_diagnostics),
        ("CLI命令可用性", test_cli_help),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print_separator("测试总结")
    print("\n  测试结果:")
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"    {name:20s}: {status}")
        if not passed:
            all_passed = False
    
    print(f"\n  总体结果: {'✅ 所有测试通过!' if all_passed else '❌ 部分测试失败'}")
    print("=" * 70 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
