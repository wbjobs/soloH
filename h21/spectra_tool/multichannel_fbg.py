import numpy as np
import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from .data_reader import SpectrumData, read_spectrum_file
from .peak_detection import detect_peaks, PeakResult
from .peak_decomposition import deconvolve_peaks, DecompositionResult
from .physical_calculations import (
    calculate_wavelength_shift,
    calculate_temperature,
    calculate_strain,
    calculate_uncertainty,
)


@dataclass
class FBGChannelConfig:
    """Configuration for a single FBG channel."""
    channel_id: str
    name: str
    wavelength_window: Tuple[float, float]
    reference_wavelength: float
    n_peaks: int = 1
    expected_peak_wavelengths: Optional[List[float]] = None
    calibration_coeffs: Optional[Dict[str, float]] = None
    description: Optional[str] = None


@dataclass
class FBGChannelResult:
    """Result for a single FBG channel."""
    channel_id: str
    name: str
    wavelength_window: Tuple[float, float]
    peak_results: List[PeakResult]
    decomposition_result: Optional[DecompositionResult] = None
    wavelength_shifts: List[float] = field(default_factory=list)
    temperatures: List[Optional[float]] = field(default_factory=list)
    strains: List[Optional[float]] = field(default_factory=list)
    uncertainties: List[Optional[float]] = field(default_factory=list)
    spectrum: Optional[SpectrumData] = None


@dataclass
class MultiChannelResult:
    """Result for multi-channel FBG demodulation."""
    filename: str
    channels: List[FBGChannelResult]
    timestamp: Optional[float] = None
    raw_spectrum: Optional[SpectrumData] = None


def load_channel_config(config_path: str) -> List[FBGChannelConfig]:
    """
    Load FBG channel configuration from JSON file.

    Expected JSON format:
    [
        {
            "channel_id": "CH01",
            "name": "Temperature_Sensor_1",
            "wavelength_window": [1540, 1545],
            "reference_wavelength": 1542.5,
            "n_peaks": 1,
            "calibration_coeffs": {
                "k_T": 0.01,
                "k_eps": 0.0012
            }
        },
        ...
    ]
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    configs = []
    for item in config_data:
        config = FBGChannelConfig(
            channel_id=item["channel_id"],
            name=item.get("name", item["channel_id"]),
            wavelength_window=tuple(item["wavelength_window"]),
            reference_wavelength=item["reference_wavelength"],
            n_peaks=item.get("n_peaks", 1),
            expected_peak_wavelengths=item.get("expected_peak_wavelengths"),
            calibration_coeffs=item.get("calibration_coeffs"),
            description=item.get("description"),
        )
        configs.append(config)

    return configs


def save_channel_config(configs: List[FBGChannelConfig], output_path: str) -> None:
    """Save FBG channel configuration to JSON file."""
    config_data = []
    for config in configs:
        item = {
            "channel_id": config.channel_id,
            "name": config.name,
            "wavelength_window": list(config.wavelength_window),
            "reference_wavelength": config.reference_wavelength,
            "n_peaks": config.n_peaks,
        }
        if config.expected_peak_wavelengths:
            item["expected_peak_wavelengths"] = config.expected_peak_wavelengths
        if config.calibration_coeffs:
            item["calibration_coeffs"] = config.calibration_coeffs
        if config.description:
            item["description"] = config.description
        config_data.append(item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)


def extract_channel_spectrum(
    spectrum: SpectrumData,
    wavelength_window: Tuple[float, float],
) -> SpectrumData:
    """
    Extract a subset of the spectrum corresponding to a specific wavelength window.

    Parameters:
    -----------
    spectrum : SpectrumData
        Full spectrum data
    wavelength_window : tuple
        (wl_min, wl_max) defining the channel window

    Returns:
    --------
    SpectrumData
        Cropped spectrum for the specific channel
    """
    wl_min, wl_max = wavelength_window
    mask = (spectrum.wavelength >= wl_min) & (spectrum.wavelength <= wl_max)

    if not np.any(mask):
        raise ValueError(f"No data points in wavelength window {wavelength_window}")

    channel_wavelength = spectrum.wavelength[mask]
    channel_intensity = spectrum.intensity[mask]

    return SpectrumData(
        filename=f"{spectrum.filename}_channel_{wl_min}-{wl_max}",
        wavelength=channel_wavelength,
        intensity=channel_intensity,
        header=spectrum.header,
        metadata={
            **spectrum.metadata,
            "original_file": spectrum.filename,
            "wavelength_window": wavelength_window,
        },
    )


def demodulate_single_channel(
    spectrum: SpectrumData,
    config: FBGChannelConfig,
    method: str = "auto",
    decomposition: bool = False,
    line_profile: str = "gaussian",
    peak_detection_kwargs: Optional[Dict[str, Any]] = None,
    decomposition_kwargs: Optional[Dict[str, Any]] = None,
) -> FBGChannelResult:
    """
    Demodulate a single FBG channel.

    Parameters:
    -----------
    spectrum : SpectrumData
        Full spectrum data
    config : FBGChannelConfig
        Channel configuration
    method : str
        Peak detection method
    decomposition : bool
        Whether to perform peak decomposition
    line_profile : str
        Line profile for decomposition
    peak_detection_kwargs : dict, optional
        Additional peak detection parameters
    decomposition_kwargs : dict, optional
        Additional decomposition parameters

    Returns:
    --------
    FBGChannelResult
        Channel demodulation results
    """
    peak_detection_kwargs = peak_detection_kwargs or {}
    decomposition_kwargs = decomposition_kwargs or {}

    channel_spectrum = extract_channel_spectrum(spectrum, config.wavelength_window)

    peak_results = detect_peaks(
        channel_spectrum,
        method=method,
        **peak_detection_kwargs,
    )

    if len(peak_results) == 0:
        return FBGChannelResult(
            channel_id=config.channel_id,
            name=config.name,
            wavelength_window=config.wavelength_window,
            peak_results=[],
            spectrum=channel_spectrum,
        )

    decomposition_result = None
    if decomposition and len(peak_results) > 0:
        try:
            decomposition_result = deconvolve_peaks(
                channel_spectrum.wavelength,
                channel_spectrum.intensity,
                n_peaks=config.n_peaks,
                line_profile=line_profile,
                **decomposition_kwargs,
            )
        except Exception as e:
            print(f"Decomposition failed for channel {config.channel_id}: {e}")

    wavelength_shifts = []
    temperatures = []
    strains = []
    uncertainties = []

    for peak in peak_results:
        shift = calculate_wavelength_shift(peak.wavelength, config.reference_wavelength)
        wavelength_shifts.append(shift)

        if config.calibration_coeffs:
            try:
                temp = calculate_temperature(
                    peak.wavelength,
                    config.reference_wavelength,
                    config.calibration_coeffs.get("k_T", 0.01),
                )
                temperatures.append(temp)
            except Exception:
                temperatures.append(None)

            try:
                if "k_eps" in config.calibration_coeffs:
                    strain = calculate_strain(
                        peak.wavelength,
                        config.reference_wavelength,
                        config.calibration_coeffs.get("k_eps", 0.0012),
                        config.calibration_coeffs.get("k_T"),
                        temperature=temperatures[-1] if temperatures[-1] is not None else 25.0,
                        reference_temperature=25.0,
                    )
                    strains.append(strain)
                else:
                    strains.append(None)
            except Exception:
                strains.append(None)

            try:
                unc = calculate_uncertainty(
                    peak,
                    config.calibration_coeffs,
                    config.reference_wavelength,
                )
                uncertainties.append(unc)
            except Exception:
                uncertainties.append(None)
        else:
            temperatures.append(None)
            strains.append(None)
            uncertainties.append(None)

    return FBGChannelResult(
        channel_id=config.channel_id,
        name=config.name,
        wavelength_window=config.wavelength_window,
        peak_results=peak_results,
        decomposition_result=decomposition_result,
        wavelength_shifts=wavelength_shifts,
        temperatures=temperatures,
        strains=strains,
        uncertainties=uncertainties,
        spectrum=channel_spectrum,
    )


def demodulate_multichannel(
    spectrum: SpectrumData,
    channel_configs: List[FBGChannelConfig],
    method: str = "auto",
    decomposition: bool = False,
    line_profile: str = "gaussian",
    peak_detection_kwargs: Optional[Dict[str, Any]] = None,
    decomposition_kwargs: Optional[Dict[str, Any]] = None,
) -> MultiChannelResult:
    """
    Demodulate multiple FBG channels simultaneously (wavelength-space encoding).

    Parameters:
    -----------
    spectrum : SpectrumData
        Full spectrum data containing all channels
    channel_configs : list of FBGChannelConfig
        Configuration for each FBG channel
    method : str
        Peak detection method
    decomposition : bool
        Whether to perform peak decomposition
    line_profile : str
        Line profile for decomposition
    peak_detection_kwargs : dict, optional
        Additional peak detection parameters
    decomposition_kwargs : dict, optional
        Additional decomposition parameters

    Returns:
    --------
    MultiChannelResult
        Results for all channels
    """
    channel_results = []

    if peak_detection_kwargs is None:
        peak_detection_kwargs = {
            "remove_baseline": True,
            "min_snr": 1.5,
            "min_peak_height_ratio": 0.02,
            "prominence_ratio": 0.02,
        }

    for config in channel_configs:
        try:
            result = demodulate_single_channel(
                spectrum,
                config,
                method=method,
                decomposition=decomposition,
                line_profile=line_profile,
                peak_detection_kwargs=peak_detection_kwargs,
                decomposition_kwargs=decomposition_kwargs,
            )
            channel_results.append(result)
        except Exception as e:
            print(f"Error demodulating channel {config.channel_id}: {e}")
            channel_results.append(
                FBGChannelResult(
                    channel_id=config.channel_id,
                    name=config.name,
                    wavelength_window=config.wavelength_window,
                    peak_results=[],
                )
            )

    return MultiChannelResult(
        filename=spectrum.filename,
        channels=channel_results,
        raw_spectrum=spectrum,
    )


def demodulate_file(
    filepath: str,
    channel_configs: List[FBGChannelConfig],
    method: str = "auto",
    decomposition: bool = False,
    line_profile: str = "gaussian",
    **read_kwargs,
) -> MultiChannelResult:
    """
    Read and demodulate a spectrum file with multiple FBG channels.

    Parameters:
    -----------
    filepath : str
        Path to spectrum data file
    channel_configs : list of FBGChannelConfig
        Channel configurations
    method : str
        Peak detection method
    decomposition : bool
        Whether to perform peak decomposition
    line_profile : str
        Line profile for decomposition
    **read_kwargs
        Additional arguments for file reading

    Returns:
    --------
    MultiChannelResult
        Demodulation results for all channels
    """
    spectrum = read_spectrum_file(filepath, **read_kwargs)
    return demodulate_multichannel(
        spectrum,
        channel_configs,
        method=method,
        decomposition=decomposition,
        line_profile=line_profile,
    )


def generate_multichannel_report(
    results: List[MultiChannelResult],
    output_path: str,
) -> str:
    """
    Generate CSV report for multiple multi-channel demodulation results.

    Parameters:
    -----------
    results : list of MultiChannelResult
        List of demodulation results
    output_path : str
        Output CSV file path

    Returns:
    --------
    str
        Path to generated report
    """
    import pandas as pd

    rows = []
    for result in results:
        for channel in result.channels:
            if len(channel.peak_results) == 0:
                rows.append({
                    "filename": result.filename,
                    "channel_id": channel.channel_id,
                    "channel_name": channel.name,
                    "wavelength_window": f"{channel.wavelength_window[0]}-{channel.wavelength_window[1]}",
                    "peak_wavelength": None,
                    "intensity": None,
                    "wavelength_shift": None,
                    "temperature": None,
                    "strain": None,
                    "uncertainty": None,
                })
            else:
                for i, peak in enumerate(channel.peak_results):
                    rows.append({
                        "filename": result.filename,
                        "channel_id": channel.channel_id,
                        "channel_name": channel.name,
                        "wavelength_window": f"{channel.wavelength_window[0]}-{channel.wavelength_window[1]}",
                        "peak_index": i + 1,
                        "peak_wavelength": peak.wavelength,
                        "intensity": peak.intensity,
                        "fwhm": peak.fwhm,
                        "r_squared": peak.r_squared,
                        "wavelength_shift": channel.wavelength_shifts[i] if i < len(channel.wavelength_shifts) else None,
                        "temperature": channel.temperatures[i] if i < len(channel.temperatures) else None,
                        "strain": channel.strains[i] if i < len(channel.strains) else None,
                        "uncertainty": channel.uncertainties[i] if i < len(channel.uncertainties) else None,
                    })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path
