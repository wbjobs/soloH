from .version import __version__
from .data_reader import SpectrumData, read_spectrum_file
from .peak_detection import (
    centroid_method,
    gaussian_fit,
    polynomial_fit,
    adaptive_threshold,
    detect_peaks,
)
from .peak_decomposition import deconvolve_peaks, lorentzian, voigt
from .physical_calculations import (
    calculate_temperature,
    calculate_strain,
    calculate_wavelength_shift,
    calculate_uncertainty,
)
from .visualization import plot_fit_results, _setup_matplotlib
from .batch_processor import process_batch, generate_report
from .global_optimization import pso_peak_search, ParticleSwarmOptimizer, PSOResult
from .multichannel_fbg import (
    FBGChannelConfig,
    FBGChannelResult,
    MultiChannelResult,
    load_channel_config,
    save_channel_config,
    demodulate_multichannel,
    demodulate_file,
    generate_multichannel_report,
)
from .dynamic_demodulation import (
    SerialConfig,
    DemodulationConfig,
    RealTimeResult,
    SerialSpectrumReader,
    RealTimeDemodulator,
    SimulatedSpectrumSource,
    run_realtime_demodulation,
)

__all__ = [
    "__version__",
    "SpectrumData",
    "read_spectrum_file",
    "centroid_method",
    "gaussian_fit",
    "polynomial_fit",
    "adaptive_threshold",
    "detect_peaks",
    "deconvolve_peaks",
    "lorentzian",
    "voigt",
    "calculate_temperature",
    "calculate_strain",
    "calculate_wavelength_shift",
    "calculate_uncertainty",
    "plot_fit_results",
    "process_batch",
    "generate_report",
    "pso_peak_search",
    "ParticleSwarmOptimizer",
    "PSOResult",
    "FBGChannelConfig",
    "FBGChannelResult",
    "MultiChannelResult",
    "load_channel_config",
    "save_channel_config",
    "demodulate_multichannel",
    "demodulate_file",
    "generate_multichannel_report",
    "SerialConfig",
    "DemodulationConfig",
    "RealTimeResult",
    "SerialSpectrumReader",
    "RealTimeDemodulator",
    "SimulatedSpectrumSource",
    "run_realtime_demodulation",
]

