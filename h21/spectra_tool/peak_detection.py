import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, savgol_filter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from .data_reader import SpectrumData


@dataclass
class PeakResult:
    wavelength: float
    intensity: float
    method: str
    amplitude: Optional[float] = None
    fwhm: Optional[float] = None
    background: Optional[float] = None
    r_squared: Optional[float] = None
    uncertainty: Optional[float] = None
    fit_params: Optional[np.ndarray] = None
    fit_curve: Optional[np.ndarray] = None
    window: Optional[Tuple[float, float]] = None


def centroid_method(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    peak_idx: Optional[int] = None,
    window: Optional[int] = None,
) -> PeakResult:
    if peak_idx is None:
        peak_idx = np.argmax(intensity)

    if window is not None:
        start = max(0, peak_idx - window)
        end = min(len(wavelength), peak_idx + window + 1)
        wl = wavelength[start:end]
        inten = intensity[start:end]
        wl_window = (float(wavelength[start]), float(wavelength[end - 1]))
    else:
        wl = wavelength
        inten = intensity
        wl_window = (float(wavelength[0]), float(wavelength[-1]))

    inten_shift = inten - np.min(inten) + 1e-10
    total_intensity = np.sum(inten_shift)

    if total_intensity <= 0:
        return PeakResult(
            wavelength=float(wavelength[peak_idx]),
            intensity=float(intensity[peak_idx]),
            method="centroid",
            uncertainty=float(np.std(wavelength)),
            window=wl_window,
        )

    centroid = np.sum(wl * inten_shift) / total_intensity
    variance = np.sum(inten_shift * (wl - centroid) ** 2) / total_intensity
    fwhm = 2 * np.sqrt(2 * np.log(2) * variance) if variance > 0 else None

    return PeakResult(
        wavelength=float(centroid),
        intensity=float(np.max(inten)),
        method="centroid",
        amplitude=float(np.max(inten) - np.min(inten)),
        fwhm=float(fwhm) if fwhm else None,
        background=float(np.min(inten)),
        uncertainty=float(np.sqrt(variance) / np.sqrt(len(wl))) if variance > 0 else None,
        window=wl_window,
    )


def gaussian(x: np.ndarray, amplitude: float, center: float, sigma: float, offset: float) -> np.ndarray:
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2)) + offset


def gaussian_fit(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    peak_idx: Optional[int] = None,
    window: Optional[int] = None,
    initial_params: Optional[List[float]] = None,
) -> PeakResult:
    if peak_idx is None:
        peak_idx = np.argmax(intensity)

    if window is not None:
        start = max(0, peak_idx - window)
        end = min(len(wavelength), peak_idx + window + 1)
        wl = wavelength[start:end]
        inten = intensity[start:end]
        wl_window = (float(wavelength[start]), float(wavelength[end - 1]))
    else:
        wl = wavelength
        inten = intensity
        wl_window = (float(wavelength[0]), float(wavelength[-1]))

    if initial_params is None:
        amp_guess = np.max(inten) - np.min(inten)
        center_guess = wl[np.argmax(inten)]
        sigma_guess = (wl[-1] - wl[0]) / 6
        offset_guess = np.min(inten)
        p0 = [amp_guess, center_guess, sigma_guess, offset_guess]
    else:
        p0 = initial_params

    try:
        popt, pcov = curve_fit(
            gaussian,
            wl,
            inten,
            p0=p0,
            maxfev=10000,
        )

        amplitude, center, sigma, offset = popt
        fwhm = 2 * np.sqrt(2 * np.log(2)) * abs(sigma)

        fit_curve = gaussian(wl, *popt)
        ss_res = np.sum((inten - fit_curve) ** 2)
        ss_tot = np.sum((inten - np.mean(inten)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else None

        sigma_center = np.sqrt(pcov[1, 1]) if pcov is not None and not np.isinf(pcov[1, 1]) else None

        return PeakResult(
            wavelength=float(center),
            intensity=float(amplitude + offset),
            method="gaussian_fit",
            amplitude=float(amplitude),
            fwhm=float(fwhm),
            background=float(offset),
            r_squared=float(r_squared) if r_squared is not None else None,
            uncertainty=float(sigma_center) if sigma_center is not None else None,
            fit_params=popt,
            fit_curve=fit_curve,
            window=wl_window,
        )
    except Exception as e:
        print(f"Gaussian fit failed: {e}")
        return PeakResult(
            wavelength=float(wl[peak_idx if window is None else peak_idx - start]),
            intensity=float(np.max(inten)),
            method="gaussian_fit_failed",
            amplitude=float(np.max(inten) - np.min(inten)),
            background=float(np.min(inten)),
            window=wl_window,
        )


def polynomial_fit(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    peak_idx: Optional[int] = None,
    window: Optional[int] = None,
    degree: int = 4,
) -> PeakResult:
    if peak_idx is None:
        peak_idx = np.argmax(intensity)

    if window is not None:
        start = max(0, peak_idx - window)
        end = min(len(wavelength), peak_idx + window + 1)
        wl = wavelength[start:end]
        inten = intensity[start:end]
        wl_window = (float(wavelength[start]), float(wavelength[end - 1]))
    else:
        wl = wavelength
        inten = intensity
        wl_window = (float(wavelength[0]), float(wavelength[-1]))

    try:
        coeffs = np.polyfit(wl, inten, degree)
        fit_curve = np.polyval(coeffs, wl)

        deriv_coeffs = np.polyder(coeffs)
        roots = np.roots(deriv_coeffs)

        real_roots = roots[np.isreal(roots)].real
        valid_roots = real_roots[(real_roots >= wl[0]) & (real_roots <= wl[-1])]

        if len(valid_roots) == 0:
            return PeakResult(
                wavelength=float(wl[np.argmax(inten)]),
                intensity=float(np.max(inten)),
                method="polynomial_fit",
                window=wl_window,
            )

        second_deriv = np.polyder(deriv_coeffs)
        maxima = []
        for root in valid_roots:
            if np.polyval(second_deriv, root) < 0:
                maxima.append(root)

        if len(maxima) == 0:
            peak_wl = wl[np.argmax(inten)]
        else:
            peak_values = [np.polyval(coeffs, m) for m in maxima]
            peak_wl = maxima[np.argmax(peak_values)]

        peak_intensity = float(np.polyval(coeffs, peak_wl))

        ss_res = np.sum((inten - fit_curve) ** 2)
        ss_tot = np.sum((inten - np.mean(inten)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else None

        half_max = (peak_intensity + np.min(inten)) / 2
        idx_peak = np.argmin(np.abs(wl - peak_wl))

        try:
            left_idx = np.where((wl < peak_wl) & (fit_curve <= half_max))[0]
            left_idx = left_idx[-1] if len(left_idx) > 0 else 0
            right_idx = np.where((wl > peak_wl) & (fit_curve <= half_max))[0]
            right_idx = right_idx[0] if len(right_idx) > 0 else len(wl) - 1
            fwhm = wl[right_idx] - wl[left_idx]
        except:
            fwhm = None

        return PeakResult(
            wavelength=float(peak_wl),
            intensity=float(peak_intensity),
            method=f"polynomial_fit_deg{degree}",
            amplitude=float(peak_intensity - np.min(inten)),
            fwhm=float(fwhm) if fwhm else None,
            background=float(np.min(inten)),
            r_squared=float(r_squared) if r_squared is not None else None,
            fit_params=coeffs,
            fit_curve=fit_curve,
            window=wl_window,
        )
    except Exception as e:
        print(f"Polynomial fit failed: {e}")
        return PeakResult(
            wavelength=float(wl[peak_idx if window is None else peak_idx - start]),
            intensity=float(np.max(inten)),
            method="polynomial_fit_failed",
            window=wl_window,
        )


def _estimate_baseline(intensity: np.ndarray, method: str = "asymmetric_least_squares") -> np.ndarray:
    """
    Estimate baseline for peak detection.

    Parameters:
    -----------
    intensity : np.ndarray
        Intensity array
    method : str
        Baseline estimation method: 'asymmetric_least_squares' or 'rolling_ball'

    Returns:
    --------
    np.ndarray
        Estimated baseline
    """
    n = len(intensity)

    if n < 10:
        return np.ones(n) * np.median(intensity)

    if method == "asymmetric_least_squares":
        lam = 1e5
        p = 0.01
        niter = 20

        D = np.zeros((n - 2, n))
        D[:, 0:-2] += np.eye(n - 2)
        D[:, 1:-1] -= 2 * np.eye(n - 2)
        D[:, 2:] += np.eye(n - 2)
        w = np.ones(n)

        for _ in range(niter):
            W = np.diag(w)
            Z = W + lam * D.T @ D
            try:
                z = np.linalg.solve(Z, w * intensity)
            except np.linalg.LinAlgError:
                z = np.linalg.lstsq(Z, w * intensity, rcond=None)[0]
            w = p * (intensity > z) + (1 - p) * (intensity < z)

        return z
    else:
        window_size = max(11, n // 10)
        if window_size % 2 == 0:
            window_size += 1

        baseline = np.zeros(n)
        for i in range(n):
            start = max(0, i - window_size // 2)
            end = min(n, i + window_size // 2 + 1)
            baseline[i] = np.percentile(intensity[start:end], 15)

        return baseline


def _validate_peak(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    peak_idx: int,
    window_size: int,
    global_noise: float,
    global_max: float,
    min_snr: float,
    min_peak_height_ratio: float,
) -> bool:
    """
    Validate if a detected peak is a true peak (not noise).
    """
    n = len(wavelength)
    half_window = max(3, window_size // 4)

    left_start = max(0, peak_idx - window_size)
    left_end = max(0, peak_idx - half_window)
    right_start = min(n, peak_idx + half_window + 1)
    right_end = min(n, peak_idx + window_size + 1)

    left_region = intensity[left_start:left_end]
    right_region = intensity[right_start:right_end]

    if len(left_region) < 2 or len(right_region) < 2:
        return False

    noise_samples = np.concatenate([left_region, right_region])
    local_noise = np.std(noise_samples)
    local_noise = max(local_noise, global_noise)

    local_base = np.median(noise_samples)

    peak_height = intensity[peak_idx]
    peak_amplitude = peak_height - local_base

    if peak_amplitude <= 0:
        return False

    snr = peak_amplitude / local_noise
    if snr < min_snr:
        return False

    if peak_amplitude < min_peak_height_ratio * global_max:
        return False

    left_slope = intensity[peak_idx] - intensity[max(0, peak_idx - 3)]
    right_slope = intensity[peak_idx] - intensity[min(n - 1, peak_idx + 3)]
    if left_slope <= 0 or right_slope <= 0:
        return False

    return True


def adaptive_threshold(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    min_peak_distance: int = 5,
    min_peak_height_ratio: float = 0.02,
    noise_window: int = 20,
    remove_baseline: bool = True,
    min_snr: float = 2.0,
    prominence_ratio: float = 0.05,
) -> List[PeakResult]:
    """
    Adaptive threshold peak detection with baseline drift resistance.

    Parameters:
    -----------
    wavelength : np.ndarray
        Wavelength array
    intensity : np.ndarray
        Intensity array
    min_peak_distance : int
        Minimum distance between peaks (in data points)
    min_peak_height_ratio : float
        Minimum peak height relative to maximum intensity
    noise_window : int
        Window size for local noise estimation
    remove_baseline : bool
        Whether to remove baseline before peak detection
    min_snr : float
        Minimum signal-to-noise ratio for peak detection
    prominence_ratio : float
        Minimum prominence relative to peak height

    Returns:
    --------
    list of PeakResult
        Detected peaks
    """
    try:
        smoothed = savgol_filter(intensity, window_length=min(51, len(intensity) // 2 * 2 + 1), polyorder=3)
    except:
        smoothed = intensity.copy()

    if remove_baseline:
        try:
            baseline = _estimate_baseline(smoothed, method="asymmetric_least_squares")
            corrected = smoothed - baseline
            corrected = corrected - np.min(corrected)
        except Exception as e:
            print(f"Baseline removal failed: {e}, using original data")
            corrected = smoothed - np.min(smoothed)
            baseline = np.zeros_like(smoothed)
    else:
        corrected = smoothed - np.min(smoothed)
        baseline = np.zeros_like(smoothed)

    global_noise = np.median(np.abs(np.diff(smoothed))) * 1.4826
    global_noise = max(global_noise, 1e-10)

    global_max = np.max(corrected)
    if global_max <= 0:
        return []

    min_height = min(
        global_noise * min_snr,
        global_max * min_peak_height_ratio
    )
    min_height = max(min_height, global_noise * 2.0)

    try:
        local_max_indices, properties = find_peaks(
            corrected,
            distance=min_peak_distance,
            height=min_height,
            prominence=min(global_max * prominence_ratio, global_noise * 3.0),
        )
    except TypeError:
        local_max_indices, properties = find_peaks(
            corrected,
            distance=min_peak_distance,
            height=min_height,
        )

    peaks = []
    for idx in local_max_indices:
        window_size = min(noise_window, len(wavelength) // 4)

        is_valid = _validate_peak(
            wavelength, corrected, idx, window_size,
            global_noise, global_max, min_snr, min_peak_height_ratio
        )
        if not is_valid:
            continue

        half_window = max(3, window_size // 4)
        n = len(wavelength)
        left_start = max(0, idx - window_size)
        left_end = max(0, idx - half_window)
        right_start = min(n, idx + half_window + 1)
        right_end = min(n, idx + window_size + 1)
        noise_samples = np.concatenate([corrected[left_start:left_end], corrected[right_start:right_end]])
        local_noise = np.std(noise_samples) if len(noise_samples) > 2 else global_noise
        local_noise = max(local_noise, global_noise)

        peak_height = corrected[idx]

        result = centroid_method(wavelength, corrected, peak_idx=idx, window=window_size)
        result.method = "adaptive_threshold"
        result.uncertainty = float(local_noise / peak_height * np.mean(np.diff(wavelength)))
        result.intensity = float(smoothed[idx])
        result.background = float(baseline[idx]) if baseline is not None else 0.0
        result.amplitude = float(peak_height)

        peaks.append(result)

    if len(peaks) > 1:
        peaks.sort(key=lambda p: p.wavelength)
        merged = []
        i = 0
        while i < len(peaks):
            current = peaks[i]
            if i + 1 < len(peaks):
                next_peak = peaks[i + 1]
                distance = abs(next_peak.wavelength - current.wavelength)
                avg_fwhm = (current.fwhm + next_peak.fwhm) / 2 if current.fwhm and next_peak.fwhm else 1.0
                if distance < avg_fwhm * 0.5:
                    if current.amplitude >= next_peak.amplitude:
                        merged.append(current)
                    else:
                        merged.append(next_peak)
                    i += 2
                    continue
            merged.append(current)
            i += 1
        peaks = merged

    return peaks


def detect_peaks(
    spectrum: SpectrumData,
    method: str = "auto",
    **kwargs,
) -> List[PeakResult]:
    wl = spectrum.wavelength
    inten = spectrum.intensity

    adaptive_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ["min_peak_distance", "min_peak_height_ratio", "noise_window",
                 "remove_baseline", "min_snr", "prominence_ratio"]
    }

    fit_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ["peak_idx", "window", "initial_params", "degree"]
    }

    if method == "centroid":
        return [centroid_method(wl, inten, **fit_kwargs)]
    elif method == "gaussian":
        return [gaussian_fit(wl, inten, **fit_kwargs)]
    elif method == "polynomial":
        return [polynomial_fit(wl, inten, **fit_kwargs)]
    elif method == "adaptive":
        return adaptive_threshold(wl, inten, **adaptive_kwargs)
    elif method == "auto":
        peaks = adaptive_threshold(wl, inten, **adaptive_kwargs)
        results = []
        for peak in peaks:
            idx = np.argmin(np.abs(wl - peak.wavelength))
            window = kwargs.get("window", 20)
            result = gaussian_fit(wl, inten, peak_idx=idx, window=window)
            results.append(result)
        return results
    else:
        raise ValueError(f"Unknown method: {method}. Use 'centroid', 'gaussian', 'polynomial', 'adaptive', or 'auto'.")
