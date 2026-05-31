import numpy as np
import pandas as pd
import os
import glob
from dataclasses import asdict
from typing import List, Optional, Dict, Any, Union, Tuple
from pathlib import Path

from .data_reader import SpectrumData, read_spectrum_file, read_batch_files
from .peak_detection import PeakResult, detect_peaks
from .peak_decomposition import DecompositionResult, decompose_spectrum
from .physical_calculations import PhysicalResult, compute_physical_quantities, compute_batch_physical_quantities
from .visualization import plot_fit_results, plot_method_comparison, plot_decomposition_comparison, plot_batch_summary


def find_spectrum_files(
    directory: str,
    extensions: Optional[List[str]] = None,
    recursive: bool = True,
) -> List[str]:
    """
    Find all spectrum files in a directory.

    Parameters:
    -----------
    directory : str
        Directory to search
    extensions : list of str, optional
        File extensions to search for (e.g., ['.txt', '.csv', '.spe']).
        If None, common extensions will be used.
    recursive : bool
        Whether to search subdirectories recursively

    Returns:
    --------
    list of str
        List of file paths
    """
    if extensions is None:
        extensions = [".txt", ".csv", ".dat", ".spe", ".spa", ".asc", ".prn"]

    extensions = [ext.lower() if ext.startswith(".") else "." + ext.lower() for ext in extensions]

    file_paths = []
    directory = os.path.abspath(directory)

    excluded_patterns = ["summary_report", "batch_summary", "_comparison", "_fit_results"]

    if recursive:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    base_lower = file.lower()
                    if not any(pattern in base_lower for pattern in excluded_patterns):
                        file_paths.append(os.path.join(root, file))
    else:
        for file in os.listdir(directory):
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                base_lower = file.lower()
                if not any(pattern in base_lower for pattern in excluded_patterns):
                    file_paths.append(os.path.join(directory, file))

    return sorted(file_paths)


def process_single_file(
    filepath: str,
    method: str = "gaussian",
    peak_detection_kwargs: Optional[Dict[str, Any]] = None,
    decomposition: bool = False,
    n_peaks: Optional[int] = None,
    line_profile: str = "lorentzian",
    decomposition_kwargs: Optional[Dict[str, Any]] = None,
    reference_wavelength: Optional[float] = None,
    calibration_coeffs: Optional[Dict[str, float]] = None,
    reference_temperature: float = 25.0,
    remove_baseline: bool = False,
    baseline_method: str = "poly",
    normalize: bool = False,
    crop_range: Optional[Tuple[float, float]] = None,
    plot: bool = False,
    plot_output_dir: Optional[str] = None,
    plot_methods: Optional[List[str]] = None,
    compare_decomposition: bool = False,
    **read_kwargs,
) -> Dict[str, Any]:
    """
    Process a single spectrum file.

    Parameters:
    -----------
    filepath : str
        Path to the spectrum file
    method : str
        Peak detection method: 'centroid', 'gaussian', 'polynomial', 'adaptive', 'auto'
    peak_detection_kwargs : dict, optional
        Additional keyword arguments for peak detection
    decomposition : bool
        Whether to perform peak decomposition
    n_peaks : int, optional
        Number of peaks for decomposition
    line_profile : str
        Line profile for decomposition: 'lorentzian', 'voigt', 'pseudo_voigt'
    decomposition_kwargs : dict, optional
        Additional keyword arguments for decomposition
    reference_wavelength : float, optional
        Reference wavelength for shift calculation
    calibration_coeffs : dict, optional
        Calibration coefficients for temperature/strain calculation
    reference_temperature : float
        Reference temperature in °C
    remove_baseline : bool
        Whether to remove baseline before processing
    baseline_method : str
        Baseline removal method: 'poly' or 'als'
    normalize : bool
        Whether to normalize spectrum
    crop_range : tuple, optional
        Wavelength range to crop (wl_min, wl_max)
    plot : bool
        Whether to generate plots
    plot_output_dir : str, optional
        Directory to save plots
    plot_methods : list of str, optional
        Methods to compare in plots
    compare_decomposition : bool
        Whether to compare different decomposition line profiles
    **read_kwargs
        Additional keyword arguments for file reading

    Returns:
    --------
    dict
        Processing results
    """
    peak_detection_kwargs = peak_detection_kwargs or {}
    decomposition_kwargs = decomposition_kwargs or {}

    result = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "success": False,
        "error": None,
        "spectrum": None,
        "peak_results": None,
        "decomposition_result": None,
        "physical_results": None,
        "plot_paths": [],
    }

    try:
        spectrum = read_spectrum_file(filepath, **read_kwargs)
        result["spectrum"] = spectrum

        if crop_range is not None:
            spectrum = spectrum.crop(crop_range[0], crop_range[1])

        if remove_baseline:
            spectrum = spectrum.remove_baseline(method=baseline_method)

        if normalize:
            spectrum = spectrum.normalize()

        peak_results = detect_peaks(spectrum, method=method, **peak_detection_kwargs)
        result["peak_results"] = peak_results

        decomposition_result = None
        if decomposition:
            try:
                decomposition_result = decompose_spectrum(
                    spectrum,
                    n_peaks=n_peaks,
                    line_profile=line_profile,
                    **decomposition_kwargs,
                )
                result["decomposition_result"] = decomposition_result
            except Exception as e:
                result["decomposition_error"] = str(e)
                print(f"Decomposition failed for {filepath}: {e}")

        physical_results = None
        if reference_wavelength is not None:
            all_peaks = peak_results.copy()
            if decomposition_result is not None:
                all_peaks.append(decomposition_result)
            physical_results = compute_batch_physical_quantities(
                all_peaks,
                reference_wavelength,
                calibration_coeffs=calibration_coeffs,
                reference_temperature=reference_temperature,
            )
            result["physical_results"] = physical_results

        if plot:
            plot_paths = _generate_plots(
                spectrum,
                peak_results,
                decomposition_result,
                physical_results[0] if physical_results else None,
                filepath,
                plot_output_dir,
                plot_methods,
                compare_decomposition,
                n_peaks,
            )
            result["plot_paths"] = plot_paths

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        print(f"Error processing {filepath}: {e}")
    finally:
        import gc
        for key in ["spectrum", "peak_results", "decomposition_result", "physical_results"]:
            if key in result and result[key] is not None and not result["success"]:
                result[key] = None
        gc.collect()

    return result


def _generate_plots(
    spectrum: SpectrumData,
    peak_results: List[PeakResult],
    decomposition_result: Optional[DecompositionResult],
    physical_result: Optional[PhysicalResult],
    filepath: str,
    plot_output_dir: Optional[str],
    plot_methods: Optional[List[str]],
    compare_decomposition: bool,
    n_peaks: Optional[int],
) -> List[str]:
    """Generate plots for processing results."""
    plot_paths = []
    filename_base = os.path.splitext(os.path.basename(filepath))[0]

    if plot_output_dir is None:
        plot_output_dir = os.path.join(os.path.dirname(filepath), "plots")

    os.makedirs(plot_output_dir, exist_ok=True)

    try:
        if plot_methods is not None:
            plot_path = os.path.join(plot_output_dir, f"{filename_base}_method_comparison.png")
            plot_method_comparison(spectrum, output_path=plot_path)
            plot_paths.append(plot_path)
        else:
            peak_dict = {p.method: p for p in peak_results} if len(peak_results) > 0 else {}
            if len(peak_results) == 1:
                peak_dict = {peak_results[0].method: peak_results[0]}

            plot_path = os.path.join(plot_output_dir, f"{filename_base}_fit_results.png")
            plot_fit_results(
                spectrum,
                peak_results=peak_dict,
                decomposition_result=decomposition_result,
                physical_result=physical_result,
                output_path=plot_path,
            )
            plot_paths.append(plot_path)

        if compare_decomposition and n_peaks is not None:
            plot_path = os.path.join(plot_output_dir, f"{filename_base}_decomposition_comparison.png")
            plot_decomposition_comparison(spectrum, n_peaks=n_peaks, output_path=plot_path)
            plot_paths.append(plot_path)

    except Exception as e:
        print(f"Plot generation failed for {filepath}: {e}")

    return plot_paths


def process_batch(
    input_dir: str,
    output_dir: Optional[str] = None,
    extensions: Optional[List[str]] = None,
    recursive: bool = True,
    **process_kwargs,
) -> List[Dict[str, Any]]:
    """
    Process all spectrum files in a directory.

    Parameters:
    -----------
    input_dir : str
        Input directory containing spectrum files
    output_dir : str, optional
        Output directory for reports and plots. If None, uses input_dir.
    extensions : list of str, optional
        File extensions to process
    recursive : bool
        Whether to process subdirectories recursively
    **process_kwargs
        Additional arguments passed to process_single_file

    Returns:
    --------
    list of dict
        List of processing results for each file
    """
    if output_dir is None:
        output_dir = input_dir

    process_kwargs["plot_output_dir"] = os.path.join(output_dir, "plots")

    filepaths = find_spectrum_files(input_dir, extensions=extensions, recursive=recursive)

    if not filepaths:
        print(f"No spectrum files found in {input_dir}")
        return []

    print(f"Found {len(filepaths)} spectrum files to process")

    results = []
    for i, filepath in enumerate(filepaths, 1):
        print(f"Processing {i}/{len(filepaths)}: {os.path.basename(filepath)}")
        result = process_single_file(filepath, **process_kwargs)
        results.append(result)

    return results


def generate_report(
    results: List[Dict[str, Any]],
    output_path: str,
    include_peak_details: bool = True,
    include_uncertainties: bool = True,
    generate_summary_plot: bool = True,
) -> str:
    """
    Generate CSV report from batch processing results.

    Parameters:
    -----------
    results : list of dict
        Batch processing results
    output_path : str
        Path for the output CSV file
    include_peak_details : bool
        Whether to include detailed peak information
    include_uncertainties : bool
        Whether to include uncertainty information
    generate_summary_plot : bool
        Whether to generate a summary plot

    Returns:
    --------
    str
        Path to the generated report
    """
    rows = []

    for file_result in results:
        if not file_result["success"]:
            row = {
                "filename": file_result["filename"],
                "filepath": file_result["filepath"],
                "success": False,
                "error": file_result.get("error", "Unknown error"),
            }
            rows.append(row)
            continue

        spectrum = file_result["spectrum"]
        peak_results = file_result["peak_results"]
        physical_results = file_result.get("physical_results")
        decomposition_result = file_result.get("decomposition_result")

        base_row = {
            "filename": file_result["filename"],
            "filepath": file_result["filepath"],
            "success": True,
            "n_points": spectrum.n_points if spectrum else None,
            "wavelength_min": spectrum.wavelength_range[0] if spectrum else None,
            "wavelength_max": spectrum.wavelength_range[1] if spectrum else None,
            "intensity_mean": spectrum.intensity_stats[2] if spectrum else None,
        }

        if peak_results:
            for i, peak in enumerate(peak_results):
                row = base_row.copy()
                row["peak_index"] = i + 1
                row["detection_method"] = peak.method
                row["peak_wavelength"] = peak.wavelength
                row["peak_intensity"] = peak.intensity
                row["peak_amplitude"] = peak.amplitude
                row["peak_fwhm"] = peak.fwhm
                row["peak_background"] = peak.background
                row["r_squared"] = peak.r_squared
                if include_uncertainties:
                    row["uncertainty_wavelength"] = peak.uncertainty

                if physical_results and i < len(physical_results):
                    phys = physical_results[i]
                    row["reference_wavelength"] = phys.reference_wavelength
                    row["wavelength_shift"] = phys.wavelength_shift
                    row["temperature"] = phys.temperature
                    row["strain"] = phys.strain
                    if include_uncertainties:
                        row["uncertainty_wavelength_shift"] = phys.uncertainty_wavelength
                        row["uncertainty_temperature"] = phys.uncertainty_temperature
                        row["uncertainty_strain"] = phys.uncertainty_strain

                if include_peak_details and peak.window:
                    row["window_min"] = peak.window[0]
                    row["window_max"] = peak.window[1]

                rows.append(row)

        if decomposition_result:
            for i, (wl, inten, amp, fwhm) in enumerate(zip(
                decomposition_result.wavelengths,
                decomposition_result.intensities,
                decomposition_result.amplitudes,
                decomposition_result.fwhms,
            )):
                row = base_row.copy()
                row["peak_index"] = i + 1
                row["detection_method"] = f"decomposition_{decomposition_result.line_profile}"
                row["peak_wavelength"] = wl
                row["peak_intensity"] = inten
                row["peak_amplitude"] = amp
                row["peak_fwhm"] = fwhm
                row["peak_background"] = decomposition_result.background
                row["r_squared"] = decomposition_result.r_squared
                row["chi_squared"] = decomposition_result.chi_squared

                if include_uncertainties and decomposition_result.uncertainties:
                    row["uncertainty_wavelength"] = decomposition_result.uncertainties[i]

                if physical_results and len(peak_results) + i < len(physical_results):
                    phys = physical_results[len(peak_results) + i]
                    row["reference_wavelength"] = phys.reference_wavelength
                    row["wavelength_shift"] = phys.wavelength_shift
                    row["temperature"] = phys.temperature
                    row["strain"] = phys.strain
                    if include_uncertainties:
                        row["uncertainty_wavelength_shift"] = phys.uncertainty_wavelength
                        row["uncertainty_temperature"] = phys.uncertainty_temperature
                        row["uncertainty_strain"] = phys.uncertainty_strain

                rows.append(row)

        if not peak_results and not decomposition_result:
            rows.append(base_row)

    df = pd.DataFrame(rows)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Report generated: {output_path}")

    if generate_summary_plot and any(r["success"] for r in results):
        summary_data = []
        for r in rows:
            if r.get("success") and "peak_wavelength" in r:
                summary_data.append({
                    "filename": r["filename"],
                    "wavelength": r["peak_wavelength"],
                    "wavelength_shift": r.get("wavelength_shift"),
                    "temperature": r.get("temperature"),
                    "strain": r.get("strain"),
                    "uncertainty_wavelength": r.get("uncertainty_wavelength"),
                    "uncertainty_wavelength_shift": r.get("uncertainty_wavelength_shift"),
                    "uncertainty_temperature": r.get("uncertainty_temperature"),
                    "uncertainty_strain": r.get("uncertainty_strain"),
                })

        if summary_data:
            plot_path = os.path.join(
                os.path.dirname(output_path),
                "batch_summary_plot.png"
            )
            try:
                plot_batch_summary(summary_data, output_path=plot_path)
            except Exception as e:
                print(f"Summary plot generation failed: {e}")

    return output_path
