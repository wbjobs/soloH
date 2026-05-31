import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest
import tempfile
import os

from eddytester.identification import (
    SVMClassifier,
    SVMRegressor,
    CrackIdentifier
)
from eddytester.simulation import EddyCurrentSimulator
from eddytester.data_io import EddyCurrentData


@pytest.fixture
def simulated_data():
    simulator = EddyCurrentSimulator(random_seed=42)
    datasets = simulator.generate_dataset(
        n_samples=30,
        n_points=100,
        no_crack_ratio=0.3,
        seed=42
    )
    return datasets


def test_svm_classifier_fit_predict(simulated_data):
    classifier = SVMClassifier()
    
    train_data = simulated_data[:20]
    test_data = simulated_data[20:]
    
    classifier.fit(train_data)
    
    predictions = classifier.predict(test_data)
    assert len(predictions) == len(test_data)
    assert set(predictions).issubset({0, 1})
    
    proba = classifier.predict_proba(test_data)
    assert proba.shape == (len(test_data), 2)
    assert np.allclose(proba.sum(axis=1), 1.0)
    
    score = classifier.score(test_data)
    assert 0 <= score <= 1


def test_svm_classifier_save_load(simulated_data):
    classifier = SVMClassifier()
    classifier.fit(simulated_data[:10])
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, 'svm_classifier.joblib')
        classifier.save(model_path)
        assert os.path.exists(model_path)
        
        new_classifier = SVMClassifier()
        new_classifier.load(model_path)
        
        predictions1 = classifier.predict(simulated_data[10:15])
        predictions2 = new_classifier.predict(simulated_data[10:15])
        
        assert np.array_equal(predictions1, predictions2)


def test_svm_regressor_fit_predict(simulated_data):
    regressor = SVMRegressor()
    
    train_data = simulated_data[:20]
    test_data = simulated_data[20:]
    
    regressor.fit(train_data, targets=['depth', 'length'])
    
    depth_pred = regressor.predict(test_data, target='depth')
    length_pred = regressor.predict(test_data, target='length')
    
    assert len(depth_pred) == len(test_data)
    assert len(length_pred) == len(test_data)
    assert np.all(depth_pred >= 0)
    assert np.all(length_pred >= 0)
    
    all_pred = regressor.predict_all(test_data)
    assert 'depth' in all_pred
    assert 'length' in all_pred
    
    score = regressor.score(test_data, target='depth')
    assert isinstance(score, float)


def test_svm_regressor_save_load(simulated_data):
    regressor = SVMRegressor()
    regressor.fit(simulated_data[:10])
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, 'svm_regressor.joblib')
        regressor.save(model_path)
        assert os.path.exists(model_path)
        
        new_regressor = SVMRegressor()
        new_regressor.load(model_path)
        
        pred1 = regressor.predict(simulated_data[10:15], target='depth')
        pred2 = new_regressor.predict(simulated_data[10:15], target='depth')
        
        assert np.allclose(pred1, pred2)


def test_crack_identifier_fit_identify(simulated_data):
    identifier = CrackIdentifier()
    
    train_data = simulated_data[:20]
    test_data = simulated_data[20:]
    
    identifier.fit(train_data, use_cnn=False)
    
    result = identifier.identify(test_data[0], use_cnn=False)
    
    assert 'has_crack' in result
    assert 'confidence' in result
    assert 'depth' in result
    assert 'length' in result
    assert isinstance(result['has_crack'], bool)
    assert 0 <= result['confidence'] <= 1
    assert result['depth'] >= 0
    assert result['length'] >= 0


def test_crack_identifier_save_load(simulated_data):
    identifier = CrackIdentifier()
    identifier.fit(simulated_data[:10], use_cnn=False)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        identifier.save_models(tmpdir)
        
        assert os.path.exists(os.path.join(tmpdir, 'svm_classifier.joblib'))
        assert os.path.exists(os.path.join(tmpdir, 'svm_regressor.joblib'))
        
        new_identifier = CrackIdentifier()
        new_identifier.load_models(tmpdir)
        
        result1 = identifier.identify(simulated_data[10], use_cnn=False)
        result2 = new_identifier.identify(simulated_data[10], use_cnn=False)
        
        assert result1['has_crack'] == result2['has_crack']
        assert abs(result1['confidence'] - result2['confidence']) < 0.05


def test_svm_regressor_unknown_target(simulated_data):
    regressor = SVMRegressor()
    regressor.fit(simulated_data[:10], targets=['depth'])
    
    with pytest.raises(ValueError, match='No trained model'):
        regressor.predict(simulated_data[10:], target='unknown')


def test_find_crack_position(simulated_data):
    identifier = CrackIdentifier()
    
    crack_data = [d for d in simulated_data if d.labels is not None and np.max(d.labels[:, 0]) > 0]
    if crack_data:
        data = crack_data[0]
        idx = identifier._find_crack_position(data)
        
        assert idx is not None
        assert isinstance(idx, int)
        assert 0 <= idx < len(data.impedance)


def test_prepare_labels():
    classifier = SVMClassifier()
    
    data_with_crack = EddyCurrentData(
        impedance=np.random.randn(100, 4) + 1j * np.random.randn(100, 4),
        labels=np.column_stack([
            np.ones(100),
            np.ones(100) * 0.001,
            np.ones(100) * 0.01,
            np.ones(100) * 0.5
        ])
    )
    
    data_no_crack = EddyCurrentData(
        impedance=np.random.randn(100, 4) + 1j * np.random.randn(100, 4),
        labels=np.column_stack([
            np.zeros(100),
            np.zeros(100),
            np.zeros(100),
            np.zeros(100)
        ])
    )
    
    labels = classifier._prepare_labels([data_with_crack, data_no_crack])
    assert np.array_equal(labels, [1, 0])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
