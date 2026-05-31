import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest

from eddytester.preprocessing import (
    WaveletDenoiser,
    SavGolDenoiser,
    LiftOffCompensator,
    Preprocessor
)
from eddytester.data_io import EddyCurrentData


@pytest.fixture
def noisy_signal():
    np.random.seed(42)
    n_samples = 500
    t = np.linspace(0, 1, n_samples)
    
    clean_signal = np.sin(2 * np.pi * 5 * t) + 0.5 * np.sin(2 * np.pi * 10 * t)
    noise = 0.1 * np.random.randn(n_samples)
    noisy = clean_signal + noise
    
    return clean_signal, noisy


@pytest.fixture
def sample_impedance():
    np.random.seed(42)
    n_samples = 500
    n_freqs = 4
    
    t = np.linspace(0, 1, n_samples)
    impedance = np.zeros((n_samples, n_freqs), dtype=complex)
    
    for i in range(n_freqs):
        real = np.sin(2 * np.pi * (i + 1) * t) + 0.1 * np.random.randn(n_samples)
        imag = np.cos(2 * np.pi * (i + 1) * t) + 0.1 * np.random.randn(n_samples)
        impedance[:, i] = real + 1j * imag
    
    lift_off = np.linspace(0, 0.1, n_samples).reshape(-1, 1)
    impedance += lift_off * (1 + 0.5j)
    
    return impedance


@pytest.fixture
def sample_data(sample_impedance):
    return EddyCurrentData(
        impedance=sample_impedance,
        frequencies=[10e3, 50e3, 100e3, 200e3],
        positions=np.linspace(0, 0.1, 500).reshape(-1, 1)
    )


def test_wavelet_denoiser_1d(noisy_signal):
    clean, noisy = noisy_signal
    denoiser = WaveletDenoiser(wavelet='db4', level=3)
    
    denoised = denoiser.denoise_signal(noisy)
    
    assert denoised.shape == noisy.shape
    noise_before = np.mean((noisy - clean)**2)
    noise_after = np.mean((denoised - clean)**2)
    assert noise_after < noise_before


def test_wavelet_denoiser_2d(sample_impedance):
    denoiser = WaveletDenoiser()
    denoised = denoiser.denoise_signal(sample_impedance)
    
    assert denoised.shape == sample_impedance.shape
    assert np.iscomplexobj(denoised)


def test_savgol_denoiser(noisy_signal):
    clean, noisy = noisy_signal
    denoiser = SavGolDenoiser(window_length=51, polyorder=3)
    
    denoised = denoiser.denoise_signal(noisy)
    
    assert denoised.shape == noisy.shape
    noise_before = np.mean((noisy - clean)**2)
    noise_after = np.mean((denoised - clean)**2)
    assert noise_after < noise_before


def test_savgol_denoiser_2d(sample_impedance):
    denoiser = SavGolDenoiser()
    denoised = denoiser.denoise_signal(sample_impedance)
    
    assert denoised.shape == sample_impedance.shape
    assert np.iscomplexobj(denoised)


def test_lift_off_compensator_pca(sample_impedance):
    compensator = LiftOffCompensator(method='pca')
    compensated = compensator.fit_transform(sample_impedance)
    
    assert compensated.shape == sample_impedance.shape
    
    real_var_before = np.var(np.real(sample_impedance))
    real_var_after = np.var(np.real(compensated))
    assert real_var_after < real_var_before


def test_lift_off_compensator_mean(sample_impedance):
    compensator = LiftOffCompensator(method='mean')
    compensated = compensator.fit_transform(sample_impedance)
    
    assert compensated.shape == sample_impedance.shape


def test_lift_off_compensator_reference(sample_impedance):
    compensator = LiftOffCompensator(method='reference')
    compensated = compensator.fit_transform(sample_impedance)
    
    assert compensated.shape == sample_impedance.shape


def test_lift_off_compensator_invalid_method():
    with pytest.raises(ValueError, match='Unknown method'):
        LiftOffCompensator(method='invalid').fit(np.zeros((10, 2)))


def test_lift_off_compensator_not_fitted():
    compensator = LiftOffCompensator()
    with pytest.raises(ValueError, match='not fitted'):
        compensator.transform(np.zeros((10, 2)))


def test_preprocessor_process(sample_data):
    preprocessor = Preprocessor(normalize=True)
    processed = preprocessor.process(sample_data)
    
    assert processed.impedance.shape == sample_data.impedance.shape
    assert processed.metadata.get('preprocessed') == True
    
    real = np.real(processed.impedance)
    assert np.abs(np.mean(real)) < 0.1
    assert np.abs(np.std(real) - 1.0) < 0.1


def test_preprocessor_denoise_only(sample_data):
    preprocessor = Preprocessor()
    denoised = preprocessor.denoise(sample_data)
    
    assert denoised.impedance.shape == sample_data.impedance.shape
    assert denoised.metadata.get('denoised') == True


def test_preprocessor_compensate_only(sample_data):
    preprocessor = Preprocessor()
    compensated = preprocessor.compensate_lift_off(sample_data)
    
    assert compensated.impedance.shape == sample_data.impedance.shape
    assert compensated.metadata.get('lift_off_compensated') == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
