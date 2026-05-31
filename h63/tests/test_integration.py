import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest
import tempfile
import os

from eddytester.simulation import EddyCurrentSimulator, CrackParams
from eddytester.data_io import DataLoader
from eddytester.preprocessing import Preprocessor
from eddytester.features import FeatureExtractor
from eddytester.identification import CrackIdentifier
from eddytester.reporting import ReportGenerator
from eddytester.annotation import AnnotationTool


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_full_workflow(temp_dir):
    print("\n=== Starting Full Integration Test ===")
    
    simulator = EddyCurrentSimulator(random_seed=42)
    
    print("\n1. Generating training data...")
    train_data = simulator.generate_dataset(
        n_samples=40,
        n_points=200,
        no_crack_ratio=0.3,
        seed=42
    )
    print(f"   Generated {len(train_data)} training samples")
    
    print("\n2. Generating test data...")
    test_data = simulator.generate_dataset(
        n_samples=10,
        n_points=200,
        no_crack_ratio=0.3,
        seed=123
    )
    print(f"   Generated {len(test_data)} test samples")
    
    train_dir = os.path.join(temp_dir, 'train_data')
    test_dir = os.path.join(temp_dir, 'test_data')
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    
    for i, data in enumerate(train_data):
        DataLoader.save(data, os.path.join(train_dir, f'train_{i:03d}.npy'))
    
    for i, data in enumerate(test_data):
        DataLoader.save(data, os.path.join(test_dir, f'test_{i:03d}.npy'))
    
    print("\n3. Loading saved data...")
    loaded_train = DataLoader.load_directory(train_dir)
    loaded_test = DataLoader.load_directory(test_dir)
    assert len(loaded_train) == 40
    assert len(loaded_test) == 10
    print(f"   Loaded {len(loaded_train)} training and {len(loaded_test)} test samples")
    
    print("\n4. Preprocessing data...")
    preprocessor = Preprocessor(normalize=True)
    processed_sample = preprocessor.process(loaded_train[0])
    assert processed_sample.impedance.shape == loaded_train[0].impedance.shape
    real = np.real(processed_sample.impedance)
    print(f"   Processed data: mean={np.mean(real):.4f}, std={np.std(real):.4f}")
    
    print("\n5. Extracting features...")
    extractor = FeatureExtractor()
    features = extractor.extract(processed_sample)
    assert 'amplitude' in features
    assert 'phase' in features
    assert 'fused' in features
    print(f"   Extracted {len(features)} feature types")
    
    print("\n6. Training crack identifier (SVM)...")
    identifier = CrackIdentifier()
    identifier.fit(loaded_train, use_cnn=False)
    print("   Training complete")
    
    model_dir = os.path.join(temp_dir, 'models')
    identifier.save_models(model_dir)
    assert os.path.exists(os.path.join(model_dir, 'svm_classifier.joblib'))
    print(f"   Models saved to {model_dir}")
    
    print("\n7. Running detection on test samples...")
    results = []
    correct = 0
    for i, data in enumerate(loaded_test):
        result = identifier.identify(data, use_cnn=False)
        
        true_has_crack = data.labels is not None and np.max(data.labels[:, 0]) > 0.5
        pred_has_crack = result['has_crack']
        
        if true_has_crack == pred_has_crack:
            correct += 1
        
        results.append((data, result))
        
        status = "✓" if true_has_crack == pred_has_crack else "✗"
        print(f"   Sample {i}: {status} true={'CRACK' if true_has_crack else 'OK'}, "
              f"pred={'CRACK' if pred_has_crack else 'OK'}, "
              f"conf={result['confidence']:.2%}")
    
    accuracy = correct / len(loaded_test)
    print(f"\n   Test accuracy: {accuracy:.1%}")
    assert accuracy >= 0.6
    
    print("\n8. Generating reports...")
    reporter = ReportGenerator(output_dir=os.path.join(temp_dir, 'reports'))
    
    report = reporter.generate_report(loaded_test[0], results[0][1])
    assert 'report_path' in report
    assert 'figures' in report
    print(f"   Report generated: {report['report_path']}")
    
    for fig_name, fig_path in report['figures'].items():
        assert os.path.exists(fig_path)
        print(f"   - {fig_name}: {os.path.basename(fig_path)}")
    
    print("\n9. Generating batch report...")
    batch_summary = reporter.generate_batch_report(results)
    assert batch_summary['total_samples'] == 10
    print(f"   Batch report summary: {batch_summary['cracks_detected']} cracks detected out of 10")
    
    print("\n10. Testing annotation tool...")
    annot_tool = AnnotationTool(output_dir=os.path.join(temp_dir, 'annotations'))
    annot_tool.add_unlabeled_data(loaded_test)
    assert len(annot_tool.dataset.unlabeled_data) == 10
    
    auto_count = annot_tool.auto_annotate(identifier, confidence_threshold=0.9)
    print(f"   Auto-annotated {auto_count} samples")
    
    stats = annot_tool.get_statistics()
    assert stats['total_annotations'] == auto_count
    print(f"   Total annotations: {stats['total_annotations']}")
    
    print("\n=== Full Integration Test PASSED ===")


def test_single_sample_analysis(temp_dir):
    print("\n=== Starting Single Sample Analysis Test ===")
    
    simulator = EddyCurrentSimulator(random_seed=42)
    
    crack = CrackParams(depth=1.5e-3, length=15e-3, position=0.5)
    data = simulator.simulate_scan(
        n_points=500,
        crack=crack,
        add_noise=True,
        add_lift_off_variation=True
    )
    
    print(f"Generated data: {data}")
    print(f"True crack: depth={crack.depth*1000:.1f}mm, length={crack.length*1000:.1f}mm")
    
    preprocessor = Preprocessor()
    processed = preprocessor.process(data)
    print("Preprocessing complete")
    
    extractor = FeatureExtractor()
    features = extractor.extract(processed)
    print(f"Extracted features: {list(features.keys())}")
    
    train_data = simulator.generate_dataset(n_samples=50, n_points=500, seed=42)
    
    identifier = CrackIdentifier()
    identifier.fit(train_data, use_cnn=False)
    print("Model trained")
    
    result = identifier.identify(data, use_cnn=False)
    
    print("\n=== Detection Results ===")
    print(f"Crack detected: {'YES' if result['has_crack'] else 'NO'}")
    print(f"Confidence: {result['confidence']:.1%}")
    if result['has_crack']:
        print(f"Estimated depth: {result['depth']*1000:.2f} mm (true: {crack.depth*1000:.1f} mm)")
        print(f"Estimated length: {result['length']*1000:.2f} mm (true: {crack.length*1000:.1f} mm)")
    
    reporter = ReportGenerator(output_dir=os.path.join(temp_dir, 'single_report'))
    report = reporter.generate_report(data, result)
    
    assert os.path.exists(report['report_path'])
    assert os.path.exists(os.path.join(report['report_path'], 'report.html'))
    assert os.path.exists(os.path.join(report['report_path'], 'report.json'))
    assert os.path.exists(os.path.join(report['report_path'], 'report.txt'))
    
    print(f"\nReport generated: {report['report_path']}")
    print("=== Single Sample Analysis Test PASSED ===")


def test_multi_frequency_fusion_in_pipeline(temp_dir):
    print("\n=== Starting Multi-Frequency Fusion Test ===")
    
    simulator = EddyCurrentSimulator(random_seed=42)
    datasets = simulator.generate_dataset(n_samples=30, n_points=200, seed=42)
    
    from eddytester.features import MultiFrequencyFusion
    
    X = np.array([d.impedance for d in datasets])
    print(f"Input shape: {X.shape}")
    
    fusion = MultiFrequencyFusion(n_components=3)
    fused = fusion.fit_transform(X)
    
    print(f"Fused shape: {fused.shape}")
    print(f"Explained variance ratio: {fusion.get_explained_variance_ratio()}")
    print(f"Total explained variance: {sum(fusion.get_explained_variance_ratio()):.1%}")
    
    assert fused.shape == (30, 3)
    assert sum(fusion.get_explained_variance_ratio()) > 0.25
    
    print("=== Multi-Frequency Fusion Test PASSED ===")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
