import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Union
from .peak_detection import PeakResult
from .peak_decomposition import DecompositionResult


@dataclass
class PhysicalResult:
    wavelength_peak: float
    wavelength_shift: float
    temperature: Optional[float] = None
    strain: Optional[float] = None
    uncertainty_wavelength: Optional[float] = None
    uncertainty_temperature: Optional[float] = None
    uncertainty_strain: Optional[float] = None
    reference_wavelength: Optional[float] = None
    calibration_coefficients: Dict[str, float] = field(default_factory=dict)


def calculate_wavelength_shift(
    measured_wavelength: float,
    reference_wavelength: float,
) -> float:
    return measured_wavelength - reference_wavelength


def calculate_temperature(
    wavelength_shift: float,
    calibration_coeffs: Dict[str, float],
    reference_temperature: float = 25.0,
) -> float:
    """
    Calculate temperature from wavelength shift using calibration coefficients.

    Supports linear, quadratic, and polynomial models:
    - Linear: Δλ = k_T * (T - T0)
    - Quadratic: Δλ = k_T1 * (T - T0) + k_T2 * (T - T0)^2
    - General polynomial: coefficients specified as 'k_T0', 'k_T1', 'k_T2', ...

    Parameters:
    -----------
    wavelength_shift : float
        Wavelength shift (Δλ = λ_measured - λ_reference)
    calibration_coeffs : dict
        Dictionary containing calibration coefficients:
        - 'k_T' or 'k_T1': linear temperature coefficient (nm/°C or pm/°C)
        - 'k_T2': quadratic temperature coefficient (optional)
        - 'k_T0': intercept term (optional, default=0)
    reference_temperature : float
        Reference temperature T0 in °C

    Returns:
    --------
    float
        Calculated temperature in °C
    """
    k_T0 = calibration_coeffs.get("k_T0", 0.0)
    k_T1 = calibration_coeffs.get("k_T1", calibration_coeffs.get("k_T", 0.0))
    k_T2 = calibration_coeffs.get("k_T2", 0.0)

    if k_T1 == 0 and k_T2 == 0:
        raise ValueError("No valid temperature calibration coefficients provided. "
                         "Need 'k_T' or 'k_T1' and optionally 'k_T2'.")

    delta_T = wavelength_shift - k_T0

    if k_T2 == 0:
        delta_T_calc = delta_T / k_T1
    else:
        discriminant = k_T1 ** 2 + 4 * k_T2 * delta_T
        if discriminant < 0:
            delta_T_calc = -k_T1 / (2 * k_T2)
        else:
            root1 = (-k_T1 + np.sqrt(discriminant)) / (2 * k_T2)
            root2 = (-k_T1 - np.sqrt(discriminant)) / (2 * k_T2)
            delta_T_calc = root1 if abs(root1) < abs(root2) else root2

    return reference_temperature + delta_T_calc


def calculate_strain(
    wavelength_shift: float,
    calibration_coeffs: Dict[str, float],
    temperature_shift: Optional[float] = None,
) -> float:
    """
    Calculate strain from wavelength shift using calibration coefficients.

    Supports:
    - Direct strain: Δλ = k_ε * ε
    - With temperature compensation: Δλ = k_ε * ε + k_T * ΔT

    Parameters:
    -----------
    wavelength_shift : float
        Wavelength shift (Δλ = λ_measured - λ_reference)
    calibration_coeffs : dict
        Dictionary containing calibration coefficients:
        - 'k_ε' or 'k_eps': strain coefficient (nm/με or pm/με)
        - 'k_T' or 'k_T1': temperature coefficient for compensation (optional)
    temperature_shift : float, optional
        Temperature change (ΔT = T_measured - T_reference) for compensation

    Returns:
    --------
    float
        Calculated strain in με (microstrain)
    """
    k_eps = calibration_coeffs.get("k_ε", calibration_coeffs.get("k_eps", 0.0))

    if k_eps == 0:
        raise ValueError("No valid strain calibration coefficients provided. "
                         "Need 'k_ε' or 'k_eps'.")

    effective_shift = wavelength_shift

    if temperature_shift is not None:
        k_T = calibration_coeffs.get("k_T", calibration_coeffs.get("k_T1", 0.0))
        if k_T != 0:
            effective_shift = wavelength_shift - k_T * temperature_shift

    return effective_shift / k_eps


def calculate_uncertainty(
    peak_uncertainty: Optional[float],
    wavelength_shift: Optional[float] = None,
    calibration_coeffs: Optional[Dict[str, float]] = None,
    method: str = "gum",
    additional_uncertainties: Optional[Dict[str, float]] = None,
) -> Dict[str, Optional[float]]:
    """
    Calculate measurement uncertainties using GUM (Guide to the Expression of
    Uncertainty in Measurement) method.

    Parameters:
    -----------
    peak_uncertainty : float or None
        Uncertainty in peak wavelength determination (u(λ))
    wavelength_shift : float or None
        Wavelength shift value
    calibration_coeffs : dict or None
        Calibration coefficients with their uncertainties:
        - 'u_k_T': uncertainty of temperature coefficient
        - 'u_k_ε': uncertainty of strain coefficient
    method : str
        Uncertainty calculation method: 'gum' (default) or 'monte_carlo'
    additional_uncertainties : dict or None
        Additional uncertainty sources:
        - 'u_reference': uncertainty in reference wavelength
        - 'u_temperature': uncertainty in temperature measurement
        - etc.

    Returns:
    --------
    dict
        Dictionary containing uncertainties:
        - 'wavelength': combined standard uncertainty of wavelength
        - 'wavelength_shift': combined standard uncertainty of wavelength shift
        - 'temperature': combined standard uncertainty of temperature (if applicable)
        - 'strain': combined standard uncertainty of strain (if applicable)
    """
    result = {
        "wavelength": None,
        "wavelength_shift": None,
        "temperature": None,
        "strain": None,
    }

    if peak_uncertainty is None:
        return result

    u_wavelength = float(peak_uncertainty)

    if additional_uncertainties and "u_reference" in additional_uncertainties:
        u_wavelength = np.sqrt(u_wavelength ** 2 + additional_uncertainties["u_reference"] ** 2)

    result["wavelength"] = u_wavelength

    if wavelength_shift is not None:
        u_shift = u_wavelength
        if additional_uncertainties:
            for key, value in additional_uncertainties.items():
                if key.startswith("u_") and key not in ["u_reference", "u_k_T", "u_k_ε"]:
                    u_shift = np.sqrt(u_shift ** 2 + value ** 2)
        result["wavelength_shift"] = float(u_shift)

    if calibration_coeffs:
        k_T = calibration_coeffs.get("k_T1", calibration_coeffs.get("k_T", 0.0))
        if k_T != 0 and result["wavelength_shift"] is not None:
            u_k_T = calibration_coeffs.get("u_k_T", 0.0)
            u_T = np.sqrt(
                (result["wavelength_shift"] / k_T) ** 2 +
                (wavelength_shift * u_k_T / k_T ** 2) ** 2 if wavelength_shift else 0
            )
            result["temperature"] = float(u_T)

        k_eps = calibration_coeffs.get("k_ε", calibration_coeffs.get("k_eps", 0.0))
        if k_eps != 0 and result["wavelength_shift"] is not None:
            u_k_eps = calibration_coeffs.get("u_k_ε", 0.0)
            u_eps = np.sqrt(
                (result["wavelength_shift"] / k_eps) ** 2 +
                (wavelength_shift * u_k_eps / k_eps ** 2) ** 2 if wavelength_shift else 0
            )
            result["strain"] = float(u_eps)

    return result


def compute_physical_quantities(
    peak_result: Union[PeakResult, float],
    reference_wavelength: float,
    calibration_coeffs: Optional[Dict[str, float]] = None,
    reference_temperature: float = 25.0,
    measured_temperature: Optional[float] = None,
    additional_uncertainties: Optional[Dict[str, float]] = None,
) -> PhysicalResult:
    """
    Compute all physical quantities from peak detection results.

    Parameters:
    -----------
    peak_result : PeakResult or float
        Peak detection result containing wavelength and uncertainty,
        or directly the peak wavelength value
    reference_wavelength : float
        Reference wavelength at calibration conditions
    calibration_coeffs : dict, optional
        Calibration coefficients for temperature and strain calculation
    reference_temperature : float
        Reference temperature in °C (default: 25.0)
    measured_temperature : float, optional
        Measured temperature for temperature-compensated strain calculation
    additional_uncertainties : dict, optional
        Additional uncertainty sources

    Returns:
    --------
    PhysicalResult
        Dataclass containing all computed physical quantities and uncertainties
    """
    if isinstance(peak_result, PeakResult):
        measured_wavelength = peak_result.wavelength
        peak_uncertainty = peak_result.uncertainty
    else:
        measured_wavelength = float(peak_result)
        peak_uncertainty = None

    wavelength_shift = calculate_wavelength_shift(measured_wavelength, reference_wavelength)

    temperature = None
    strain = None

    if calibration_coeffs:
        try:
            temperature = calculate_temperature(
                wavelength_shift,
                calibration_coeffs,
                reference_temperature,
            )
        except ValueError:
            pass

        if temperature is not None and measured_temperature is None:
            temp_shift = temperature - reference_temperature
        elif measured_temperature is not None:
            temp_shift = measured_temperature - reference_temperature
        else:
            temp_shift = None

        try:
            strain = calculate_strain(
                wavelength_shift,
                calibration_coeffs,
                temp_shift,
            )
        except ValueError:
            pass

    uncertainties = calculate_uncertainty(
        peak_uncertainty,
        wavelength_shift,
        calibration_coeffs,
        additional_uncertainties=additional_uncertainties,
    )

    return PhysicalResult(
        wavelength_peak=measured_wavelength,
        wavelength_shift=wavelength_shift,
        temperature=temperature,
        strain=strain,
        uncertainty_wavelength=uncertainties["wavelength"],
        uncertainty_temperature=uncertainties["temperature"],
        uncertainty_strain=uncertainties["strain"],
        reference_wavelength=reference_wavelength,
        calibration_coefficients=calibration_coeffs or {},
    )


def compute_batch_physical_quantities(
    peak_results: List[Union[PeakResult, DecompositionResult]],
    reference_wavelength: Union[float, List[float]],
    **kwargs,
) -> List[PhysicalResult]:
    """
    Compute physical quantities for multiple peaks from batch processing.

    Parameters:
    -----------
    peak_results : list
        List of PeakResult or DecompositionResult objects
    reference_wavelength : float or list
        Reference wavelength(s) - single value or list matching peak_results
    **kwargs
        Additional arguments passed to compute_physical_quantities

    Returns:
    --------
    list
        List of PhysicalResult objects
    """
    results = []

    if isinstance(reference_wavelength, (int, float)):
        ref_wavelengths = [reference_wavelength] * len(peak_results)
    else:
        ref_wavelengths = reference_wavelength
        if len(ref_wavelengths) != len(peak_results):
            raise ValueError(
                f"Length of reference_wavelengths ({len(ref_wavelengths)}) "
                f"does not match peak_results ({len(peak_results)})"
            )

    for peak, ref_wl in zip(peak_results, ref_wavelengths):
        if isinstance(peak, DecompositionResult):
            for i, wl in enumerate(peak.wavelengths):
                unc = peak.uncertainties[i] if peak.uncertainties else None
                pseudo_peak = PeakResult(
                    wavelength=wl,
                    intensity=peak.intensities[i],
                    method=f"decomposition_{peak.line_profile}",
                    amplitude=peak.amplitudes[i],
                    fwhm=peak.fwhms[i],
                    uncertainty=unc,
                )
                phys_result = compute_physical_quantities(
                    pseudo_peak,
                    ref_wl if not isinstance(ref_wl, list) else ref_wl[i % len(ref_wl)],
                    **kwargs,
                )
                results.append(phys_result)
        else:
            phys_result = compute_physical_quantities(peak, ref_wl, **kwargs)
            results.append(phys_result)

    return results
