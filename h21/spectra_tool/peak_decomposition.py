import numpy as np
from scipy.optimize import curve_fit
from scipy.special import wofz
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from .data_reader import SpectrumData
from .peak_detection import PeakResult, adaptive_threshold


def lorentzian(x: np.ndarray, amplitude: float, center: float, gamma: float, offset: float) -> np.ndarray:
    return amplitude * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2) + offset


def voigt(x: np.ndarray, amplitude: float, center: float, sigma: float, gamma: float, offset: float) -> np.ndarray:
    sigma_safe = max(sigma, 1e-10)
    gamma_safe = max(gamma, 1e-10)
    z = (x - center + 1j * gamma_safe) / (sigma_safe * np.sqrt(2))
    w = wofz(z)
    norm = 1.0 / (sigma_safe * np.sqrt(2 * np.pi))
    return amplitude * np.real(w) * norm + offset


def _voigt_derivatives(x: np.ndarray, amplitude: float, center: float, sigma: float, gamma: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate analytical derivatives of Voigt function with respect to parameters.
    Uses accurate analytical differentiation of the Faddeeva function.

    The Voigt function is:
    V(x; A, x0, σ, γ, y0) = A * Re[wofz((x - x0 + iγ)/(σ√2))] / (σ√(2π)) + y0

    Derivatives use the property: d/dz wofz(z) = -2z * wofz(z) + 2i/√π

    Returns:
    --------
    dV_dA, dV_dx0, dV_dsigma, dV_dgamma, dV_doffset : np.ndarray
        Derivatives with respect to amplitude, center, sigma, gamma, and offset
    """
    sigma_safe = max(sigma, 1e-10)
    gamma_safe = max(gamma, 1e-10)

    sqrt2 = np.sqrt(2)
    sqrt2pi = np.sqrt(2 * np.pi)
    sqrt_pi = np.sqrt(np.pi)
    inv_sigma_sqrt2 = 1.0 / (sigma_safe * sqrt2)

    z = (x - center + 1j * gamma_safe) * inv_sigma_sqrt2
    w = wofz(z)
    re_w = np.real(w)
    im_w = np.imag(w)

    norm = 1.0 / (sigma_safe * sqrt2pi)
    V = amplitude * re_w * norm

    dw_dz = -2.0 * z * w + 2.0j / sqrt_pi

    dz_dcenter = -inv_sigma_sqrt2
    dz_dsigma = -(x - center + 1j * gamma_safe) * inv_sigma_sqrt2 / sigma_safe
    dz_dgamma = 1.0j * inv_sigma_sqrt2

    dV_dA = V / amplitude if amplitude != 0 else np.zeros_like(x)

    dV_dcenter = amplitude * norm * np.real(dw_dz * dz_dcenter)

    dV_dsigma = amplitude * (
        np.real(dw_dz * dz_dsigma) * norm -
        re_w * norm / sigma_safe
    )

    dV_dgamma = amplitude * norm * np.real(dw_dz * dz_dgamma)

    dV_doffset = np.ones_like(x)

    return dV_dA, dV_dcenter, dV_dsigma, dV_dgamma, dV_doffset


def pseudo_voigt(x: np.ndarray, amplitude: float, center: float, sigma: float, gamma: float, mixing: float, offset: float) -> np.ndarray:
    sigma_safe = max(sigma, 1e-10)
    gamma_safe = max(gamma, 1e-10)
    g = np.exp(-np.log(2) * ((x - center) * 2 / sigma_safe) ** 2)
    l = 1 / (1 + ((x - center) * 2 / gamma_safe) ** 2)
    return amplitude * (mixing * g + (1 - mixing) * l) + offset


def multi_lorentzian(x: np.ndarray, *params) -> np.ndarray:
    n_peaks = (len(params) - 1) // 3
    offset = params[-1]
    y = np.zeros_like(x, dtype=float)
    for i in range(n_peaks):
        amp = params[3 * i]
        center = params[3 * i + 1]
        gamma = max(params[3 * i + 2], 1e-10)
        y += amp * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2)
    return y + offset


def multi_voigt(x: np.ndarray, *params) -> np.ndarray:
    n_peaks = (len(params) - 1) // 4
    offset = params[-1]
    y = np.zeros_like(x, dtype=float)
    for i in range(n_peaks):
        amp = params[4 * i]
        center = params[4 * i + 1]
        sigma = max(params[4 * i + 2], 1e-10)
        gamma = max(params[4 * i + 3], 1e-10)
        z = (x - center + 1j * gamma) / (sigma * np.sqrt(2))
        w = wofz(z)
        y += amp * np.real(w) / (sigma * np.sqrt(2 * np.pi))
    return y + offset


def multi_voigt_jacobian(x: np.ndarray, *params) -> np.ndarray:
    """
    Analytical Jacobian matrix for multi-Voigt function.

    Parameters:
    -----------
    x : np.ndarray
        Independent variable (wavelength)
    params : tuple
        Fit parameters: [amp1, center1, sigma1, gamma1, ..., offset]

    Returns:
    --------
    np.ndarray
        Jacobian matrix of shape (n_points, n_params)
    """
    n_peaks = (len(params) - 1) // 4
    n_points = len(x)
    n_params = len(params)

    jac = np.zeros((n_points, n_params), dtype=float)

    for i in range(n_peaks):
        amp = params[4 * i]
        center = params[4 * i + 1]
        sigma = max(params[4 * i + 2], 1e-10)
        gamma = max(params[4 * i + 3], 1e-10)

        dV_dA, dV_dx0, dV_dsigma, dV_dgamma, _ = _voigt_derivatives(x, amp, center, sigma, gamma)

        jac[:, 4 * i] = dV_dA
        jac[:, 4 * i + 1] = dV_dx0
        jac[:, 4 * i + 2] = dV_dsigma
        jac[:, 4 * i + 3] = dV_dgamma

    jac[:, -1] = 1.0

    return jac


def multi_pseudo_voigt(x: np.ndarray, *params) -> np.ndarray:
    n_peaks = (len(params) - 1) // 5
    offset = params[-1]
    y = np.zeros_like(x, dtype=float)
    for i in range(n_peaks):
        amp = params[5 * i]
        center = params[5 * i + 1]
        sigma = params[5 * i + 2]
        gamma = params[5 * i + 3]
        mixing = params[5 * i + 4]
        g = np.exp(-np.log(2) * ((x - center) * 2 / sigma) ** 2)
        l = 1 / (1 + ((x - center) * 2 / gamma) ** 2)
        y += amp * (mixing * g + (1 - mixing) * l)
    return y + offset


@dataclass
class DecompositionResult:
    wavelengths: List[float]
    intensities: List[float]
    amplitudes: List[float]
    fwhms: List[float]
    line_profile: str
    fit_curve: np.ndarray
    individual_peaks: List[np.ndarray]
    r_squared: float
    chi_squared: float
    background: float
    fit_params: np.ndarray
    uncertainties: Optional[List[float]] = None


def _estimate_initial_params(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    n_peaks: Optional[int] = None,
    line_profile: str = "lorentzian",
) -> Tuple[List[float], List[Tuple[float, float]]]:
    if n_peaks is None:
        peaks = adaptive_threshold(wavelength, intensity, min_peak_distance=10)
        n_peaks = max(len(peaks), 1)
        peak_centers = [p.wavelength for p in peaks]
        peak_heights = [p.intensity for p in peaks]
    else:
        from scipy.signal import find_peaks
        peak_indices, _ = find_peaks(intensity, distance=max(5, len(wavelength) // (n_peaks * 2)))
        if len(peak_indices) < n_peaks:
            peak_indices = np.argsort(intensity)[-n_peaks:]
            peak_indices = np.sort(peak_indices)
        peak_centers = [wavelength[i] for i in peak_indices]
        peak_heights = [intensity[i] for i in peak_indices]

    wl_range = wavelength[-1] - wavelength[0]
    avg_fwhm = wl_range / (n_peaks * 3)

    params = []
    bounds_lower = []
    bounds_upper = []

    baseline = np.min(intensity)
    max_intensity = np.max(intensity)
    amplitude_range = max_intensity - baseline
    if amplitude_range <= 0:
        amplitude_range = 1.0

    for i in range(n_peaks):
        center = peak_centers[i] if i < len(peak_centers) else wavelength[0] + (i + 0.5) * wl_range / n_peaks
        height = peak_heights[i] if i < len(peak_heights) else baseline + amplitude_range * 0.5

        amp = max(height - baseline, amplitude_range * 0.1, 0.01 * amplitude_range)
        params.append(amp)
        params.append(center)

        if line_profile in ["lorentzian"]:
            params.append(avg_fwhm / 2)
        elif line_profile in ["voigt"]:
            params.append(avg_fwhm / 4)
            params.append(avg_fwhm / 4)
        elif line_profile in ["pseudo_voigt"]:
            params.append(avg_fwhm / 4)
            params.append(avg_fwhm / 4)
            params.append(0.5)

        amp_lower = max(0, amplitude_range * 0.001)
        amp_upper = amplitude_range * 2.0
        bounds_lower.extend([amp_lower, wavelength[0]])
        bounds_upper.extend([amp_upper, wavelength[-1]])

        if line_profile in ["lorentzian"]:
            bounds_lower.append(max(0.1, avg_fwhm * 0.05))
            bounds_upper.append(avg_fwhm * 5)
        elif line_profile in ["voigt"]:
            bounds_lower.extend([max(0.05, avg_fwhm * 0.02), max(0.05, avg_fwhm * 0.02)])
            bounds_upper.extend([avg_fwhm * 3, avg_fwhm * 3])
        elif line_profile in ["pseudo_voigt"]:
            bounds_lower.extend([max(0.05, avg_fwhm * 0.02), max(0.05, avg_fwhm * 0.02), 0.0])
            bounds_upper.extend([avg_fwhm * 3, avg_fwhm * 3, 1.0])

    baseline_lower = baseline - abs(baseline) * 0.5 - amplitude_range * 0.2
    baseline_upper = baseline + abs(amplitude_range) * 0.5 + abs(baseline) * 0.5
    params.append(baseline)
    bounds_lower.append(baseline_lower)
    bounds_upper.append(baseline_upper)

    return params, (bounds_lower, bounds_upper)


def deconvolve_peaks(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    n_peaks: Optional[int] = None,
    line_profile: str = "lorentzian",
    initial_params: Optional[List[float]] = None,
    maxfev: int = 20000,
) -> DecompositionResult:
    line_profile = line_profile.lower()

    if line_profile == "lorentzian":
        fit_func = multi_lorentzian
        params_per_peak = 3
    elif line_profile == "voigt":
        fit_func = multi_voigt
        params_per_peak = 4
    elif line_profile == "pseudo_voigt":
        fit_func = multi_pseudo_voigt
        params_per_peak = 5
    else:
        raise ValueError(f"Unknown line profile: {line_profile}. Use 'lorentzian', 'voigt', or 'pseudo_voigt'.")

    if initial_params is None:
        p0, bounds = _estimate_initial_params(wavelength, intensity, n_peaks, line_profile)
    else:
        p0 = initial_params
        n_peaks = (len(p0) - 1) // params_per_peak
        bounds = (-np.inf, np.inf)

    jacobian = None
    if line_profile == "voigt":
        jacobian = multi_voigt_jacobian

    try:
        try:
            fit_kwargs = {
                "f": fit_func,
                "xdata": wavelength,
                "ydata": intensity,
                "p0": p0,
                "bounds": bounds,
                "maxfev": maxfev,
                "method": "trf",
            }
            if jacobian is not None:
                fit_kwargs["jac"] = jacobian
            popt, pcov = curve_fit(**fit_kwargs)
        except Exception as e:
            print(f"Constrained fit failed, retrying without bounds: {e}")
            fit_kwargs_lm = {
                "f": fit_func,
                "xdata": wavelength,
                "ydata": intensity,
                "p0": p0,
                "maxfev": maxfev * 2,
                "method": "lm",
            }
            if jacobian is not None:
                fit_kwargs_lm["jac"] = jacobian
            popt, pcov = curve_fit(**fit_kwargs_lm)

        fit_curve = fit_func(wavelength, *popt)

        ss_res = np.sum((intensity - fit_curve) ** 2)
        ss_tot = np.sum((intensity - np.mean(intensity)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        dof = max(len(intensity) - len(popt), 1)
        chi_squared = ss_res / dof

        individual_peaks = []
        wavelengths = []
        intensities = []
        amplitudes = []
        fwhms = []
        uncertainties = []

        baseline = popt[-1]

        for i in range(n_peaks):
            if line_profile == "lorentzian":
                amp = popt[3 * i]
                center = popt[3 * i + 1]
                gamma = popt[3 * i + 2]
                peak_curve = amp * (gamma ** 2) / ((wavelength - center) ** 2 + gamma ** 2)
                fwhm = 2 * gamma
                if pcov is not None and not np.isinf(pcov[3 * i + 1, 3 * i + 1]):
                    unc = np.sqrt(pcov[3 * i + 1, 3 * i + 1])
                else:
                    unc = None

            elif line_profile == "voigt":
                amp = popt[4 * i]
                center = popt[4 * i + 1]
                sigma = popt[4 * i + 2]
                gamma = popt[4 * i + 3]
                z = (wavelength - center + 1j * gamma) / (sigma * np.sqrt(2))
                peak_curve = amp * np.real(wofz(z)) / (sigma * np.sqrt(2 * np.pi))
                fwhm_g = 2 * sigma * np.sqrt(2 * np.log(2))
                fwhm_l = 2 * gamma
                fwhm = 0.5346 * fwhm_l + np.sqrt(0.2166 * fwhm_l ** 2 + fwhm_g ** 2)
                if pcov is not None and not np.isinf(pcov[4 * i + 1, 4 * i + 1]):
                    unc = np.sqrt(pcov[4 * i + 1, 4 * i + 1])
                else:
                    unc = None

            elif line_profile == "pseudo_voigt":
                amp = popt[5 * i]
                center = popt[5 * i + 1]
                sigma = popt[5 * i + 2]
                gamma = popt[5 * i + 3]
                mixing = popt[5 * i + 4]
                g = np.exp(-np.log(2) * ((wavelength - center) * 2 / sigma) ** 2)
                l = 1 / (1 + ((wavelength - center) * 2 / gamma) ** 2)
                peak_curve = amp * (mixing * g + (1 - mixing) * l)
                fwhm = max(sigma, gamma)
                if pcov is not None and not np.isinf(pcov[5 * i + 1, 5 * i + 1]):
                    unc = np.sqrt(pcov[5 * i + 1, 5 * i + 1])
                else:
                    unc = None

            individual_peaks.append(peak_curve + baseline / n_peaks)
            wavelengths.append(float(center))
            intensities.append(float(np.max(peak_curve) + baseline))
            amplitudes.append(float(amp))
            fwhms.append(float(fwhm))
            if unc is not None:
                uncertainties.append(float(unc))

        return DecompositionResult(
            wavelengths=wavelengths,
            intensities=intensities,
            amplitudes=amplitudes,
            fwhms=fwhms,
            line_profile=line_profile,
            fit_curve=fit_curve,
            individual_peaks=individual_peaks,
            r_squared=float(r_squared),
            chi_squared=float(chi_squared),
            background=float(baseline),
            fit_params=popt,
            uncertainties=uncertainties if uncertainties else None,
        )

    except Exception as e:
        print(f"Deconvolution failed: {e}")
        raise


def decompose_spectrum(
    spectrum: SpectrumData,
    n_peaks: Optional[int] = None,
    line_profile: str = "lorentzian",
    wl_range: Optional[Tuple[float, float]] = None,
    **kwargs,
) -> DecompositionResult:
    if wl_range is not None:
        spec = spectrum.crop(wl_range[0], wl_range[1])
    else:
        spec = spectrum

    return deconvolve_peaks(
        spec.wavelength,
        spec.intensity,
        n_peaks=n_peaks,
        line_profile=line_profile,
        **kwargs,
    )
