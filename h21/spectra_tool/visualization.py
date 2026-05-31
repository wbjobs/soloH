import numpy as np
import matplotlib
from matplotlib import rcParams
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
from typing import List, Optional, Tuple, Dict, Any, Union
import os

from .data_reader import SpectrumData
from .peak_detection import PeakResult, detect_peaks, centroid_method, gaussian_fit, polynomial_fit
from .peak_decomposition import DecompositionResult, deconvolve_peaks
from .physical_calculations import PhysicalResult

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


def _setup_matplotlib():
    """Setup matplotlib backend and fonts for Chinese support."""
    import matplotlib
    matplotlib.use("Agg")
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


def plot_fit_results(
    spectrum: SpectrumData,
    peak_results: Optional[Union[List[PeakResult], Dict[str, PeakResult]]] = None,
    decomposition_result: Optional[DecompositionResult] = None,
    physical_result: Optional[PhysicalResult] = None,
    methods: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    show_plot: bool = False,
    dpi: int = 150,
    figsize: Tuple[int, int] = (12, 8),
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Plot spectrum with peak detection and fitting results.

    Parameters:
    -----------
    spectrum : SpectrumData
        The spectrum data to plot
    peak_results : list or dict, optional
        Peak detection results from one or more methods
    decomposition_result : DecompositionResult, optional
        Peak deconvolution results
    physical_result : PhysicalResult, optional
        Physical quantity calculation results
    methods : list of str, optional
        List of methods to compare: ['centroid', 'gaussian', 'polynomial']
    output_path : str, optional
        Path to save the figure as PNG
    show_plot : bool
        Whether to display the plot (default: False)
    dpi : int
        DPI for saved figure
    figsize : tuple
        Figure size (width, height) in inches
    title : str, optional
        Plot title

    Returns:
    --------
    matplotlib.Figure
        The created figure object
    """
    if methods is not None and peak_results is None:
        peak_results = {}
        for method in methods:
            try:
                results = detect_peaks(spectrum, method=method, window=30)
                if results:
                    peak_results[method] = results[0]
            except Exception as e:
                print(f"Warning: Method {method} failed: {e}")

    fig = plt.figure(figsize=figsize)
    gs = GridSpec(2, 1, height_ratios=[3, 1], hspace=0.1)

    ax_main = fig.add_subplot(gs[0])
    ax_residual = fig.add_subplot(gs[1], sharex=ax_main)

    wl = spectrum.wavelength
    inten = spectrum.intensity

    ax_main.plot(wl, inten, "k-", label="原始数据", linewidth=1.5, alpha=0.8)

    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    method_colors = {
        "centroid": colors[0],
        "gaussian_fit": colors[1],
        "polynomial_fit_deg4": colors[2],
        "adaptive_threshold": colors[3],
        "decomposition_lorentzian": colors[4],
        "decomposition_voigt": colors[5],
        "decomposition_pseudo_voigt": colors[6],
    }

    if isinstance(peak_results, dict):
        for method, peak in peak_results.items():
            color = method_colors.get(method, colors[list(peak_results.keys()).index(method) % 10])
            _plot_peak_result(ax_main, wl, inten, peak, method, color)
    elif isinstance(peak_results, list):
        for i, peak in enumerate(peak_results):
            color = colors[i % len(colors)]
            _plot_peak_result(ax_main, wl, inten, peak, peak.method, color)

    if decomposition_result is not None:
        color = method_colors.get(f"decomposition_{decomposition_result.line_profile}", colors[4])
        _plot_decomposition(ax_main, wl, decomposition_result, color)

    if decomposition_result is not None or (isinstance(peak_results, dict) and "gaussian_fit" in peak_results):
        if decomposition_result is not None:
            fit_curve = decomposition_result.fit_curve
            label = f"{decomposition_result.line_profile.capitalize()}拟合"
            color = method_colors.get(f"decomposition_{decomposition_result.line_profile}", colors[4])
        else:
            peak = peak_results["gaussian_fit"]
            if peak.fit_curve is not None and peak.window is not None:
                mask = (wl >= peak.window[0]) & (wl <= peak.window[1])
                fit_wl = wl[mask]
                fit_curve = peak.fit_curve
                wl = fit_wl
                inten = spectrum.intensity[mask]
            else:
                fit_curve = None
            label = "高斯拟合"
            color = method_colors.get("gaussian_fit", colors[1])

        if fit_curve is not None and len(fit_curve) == len(wl):
            residual = inten - fit_curve
            ax_residual.plot(wl, residual, color=color, linewidth=1, label=label)
            ax_residual.axhline(y=0, color="k", linestyle="--", alpha=0.5, linewidth=0.8)
            ax_residual.fill_between(wl, residual, 0, alpha=0.2, color=color)

    ax_main.set_ylabel("强度 (a.u.)", fontsize=12)
    ax_main.grid(True, alpha=0.3, linestyle="--")
    ax_main.legend(loc="best", fontsize=10, framealpha=0.9)

    if title:
        ax_main.set_title(title, fontsize=14, pad=15)
    else:
        ax_main.set_title(f"光谱分析: {spectrum.filename}", fontsize=14, pad=15)

    ax_residual.set_xlabel("波长 (nm)", fontsize=12)
    ax_residual.set_ylabel("残差", fontsize=12)
    ax_residual.grid(True, alpha=0.3, linestyle="--")
    if np.any(np.abs(residual) > 0) if "residual" in locals() else True:
        ax_residual.legend(loc="best", fontsize=9)

    info_text = []
    if physical_result is not None:
        info_text.append(f"峰值波长: {physical_result.wavelength_peak:.4f} nm")
        if physical_result.uncertainty_wavelength is not None:
            info_text[-1] += f" ± {physical_result.uncertainty_wavelength:.2e} nm"
        info_text.append(f"波长偏移: {physical_result.wavelength_shift:.4f} nm")
        if physical_result.temperature is not None:
            temp_str = f"温度: {physical_result.temperature:.2f} °C"
            if physical_result.uncertainty_temperature is not None:
                temp_str += f" ± {physical_result.uncertainty_temperature:.2f} °C"
            info_text.append(temp_str)
        if physical_result.strain is not None:
            strain_str = f"应变: {physical_result.strain:.2f} με"
            if physical_result.uncertainty_strain is not None:
                strain_str += f" ± {physical_result.uncertainty_strain:.2f} με"
            info_text.append(strain_str)

    if decomposition_result is not None:
        info_text.append(f"拟合优度 R²: {decomposition_result.r_squared:.6f}")
        info_text.append(f"χ²: {decomposition_result.chi_squared:.4f}")
    elif isinstance(peak_results, dict):
        for method, peak in peak_results.items():
            if peak.r_squared is not None:
                info_text.append(f"{method} R²: {peak.r_squared:.6f}")

    if info_text:
        bbox_props = dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.9)
        ax_main.text(
            0.02,
            0.98,
            "\n".join(info_text),
            transform=ax_main.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=bbox_props,
            family="monospace",
        )

    plt.setp(ax_main.get_xticklabels(), visible=False)
    plt.tight_layout()

    if output_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        print(f"Figure saved to: {output_path}")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)
        del fig
        import gc
        gc.collect()

    return None if not show_plot else fig


def _plot_peak_result(
    ax: plt.Axes,
    wl: np.ndarray,
    inten: np.ndarray,
    peak: PeakResult,
    method_name: str,
    color: np.ndarray,
) -> None:
    display_name = {
        "centroid": "质心法",
        "gaussian_fit": "高斯拟合",
        "polynomial_fit_deg4": "多项式拟合",
        "adaptive_threshold": "自适应阈值",
    }.get(method_name, method_name)

    if peak.window is not None:
        mask = (wl >= peak.window[0]) & (wl <= peak.window[1])
        wl_window = wl[mask]
        if peak.fit_curve is not None:
            ax.plot(wl_window, peak.fit_curve, "--", color=color,
                    label=f"{display_name}拟合", linewidth=2)

    ax.axvline(
        x=peak.wavelength,
        color=color,
        linestyle=":",
        linewidth=2,
        label=f"{display_name}: {peak.wavelength:.4f} nm",
    )

    ax.plot(peak.wavelength, peak.intensity, "o", color=color, markersize=8,
            markeredgecolor="k", markeredgewidth=1)

    if peak.fwhm is not None and peak.window is not None:
        half_max = peak.background + peak.amplitude / 2 if peak.background and peak.amplitude else peak.intensity / 2
        ax.hlines(
            y=half_max,
            xmin=peak.wavelength - peak.fwhm / 2,
            xmax=peak.wavelength + peak.fwhm / 2,
            color=color,
            linewidth=2,
            alpha=0.7,
        )


def _plot_decomposition(
    ax: plt.Axes,
    wl: np.ndarray,
    result: DecompositionResult,
    color: np.ndarray,
) -> None:
    line_name = {
        "lorentzian": "洛伦兹",
        "voigt": "Voigt",
        "pseudo_voigt": "伪Voigt",
    }.get(result.line_profile, result.line_profile)

    ax.plot(wl, result.fit_curve, "--", color=color,
            label=f"{line_name}拟合 (R²={result.r_squared:.4f})", linewidth=2.5)

    for i, (peak_curve, center) in enumerate(zip(result.individual_peaks, result.wavelengths)):
        alpha = 0.5 + 0.5 * (i / max(len(result.individual_peaks), 1))
        ax.fill_between(wl, result.background, peak_curve,
                        alpha=alpha * 0.3, color=color)
        ax.plot(wl, peak_curve, ":", color=color, linewidth=1.5, alpha=0.8)
        ax.axvline(x=center, color=color, linestyle=":", linewidth=1.5, alpha=0.7,
                   label=f"峰{i+1}: {center:.4f} nm")


def plot_method_comparison(
    spectrum: SpectrumData,
    output_path: Optional[str] = None,
    show_plot: bool = False,
    **kwargs,
) -> plt.Figure:
    """
    Plot comparison of all peak detection methods.

    Parameters:
    -----------
    spectrum : SpectrumData
        The spectrum data to analyze
    output_path : str, optional
        Path to save the figure
    show_plot : bool
        Whether to display the plot
    **kwargs
        Additional arguments passed to plot_fit_results

    Returns:
    --------
    matplotlib.Figure
        The created figure
    """
    methods = ["centroid", "gaussian", "polynomial"]
    return plot_fit_results(
        spectrum,
        methods=methods,
        output_path=output_path,
        show_plot=show_plot,
        title=f"峰值检测方法对比: {spectrum.filename}",
        **kwargs,
    )


def plot_decomposition_comparison(
    spectrum: SpectrumData,
    n_peaks: int,
    output_path: Optional[str] = None,
    show_plot: bool = False,
    dpi: int = 150,
    figsize: Tuple[int, int] = (14, 10),
) -> plt.Figure:
    """
    Plot comparison of different line profiles for peak decomposition.

    Parameters:
    -----------
    spectrum : SpectrumData
        The spectrum data to analyze
    n_peaks : int
        Number of peaks to decompose
    output_path : str, optional
        Path to save the figure
    show_plot : bool
        Whether to display the plot
    dpi : int
        DPI for saved figure
    figsize : tuple
        Figure size

    Returns:
    --------
    matplotlib.Figure
        The created figure
    """
    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
    line_profiles = ["lorentzian", "voigt", "pseudo_voigt"]
    line_names = ["洛伦兹线型", "Voigt线型", "伪Voigt线型"]
    colors = plt.cm.tab10([0, 1, 2])

    wl = spectrum.wavelength
    inten = spectrum.intensity

    for ax, profile, name, color in zip(axes, line_profiles, line_names, colors):
        try:
            result = deconvolve_peaks(wl, inten, n_peaks=n_peaks, line_profile=profile)

            ax.plot(wl, inten, "k-", label="原始数据", linewidth=1.5, alpha=0.7)
            ax.plot(wl, result.fit_curve, "--", color=color,
                    label=f"{name}拟合 (R²={result.r_squared:.6f})", linewidth=2)

            for i, (peak_curve, center) in enumerate(zip(result.individual_peaks, result.wavelengths)):
                ax.fill_between(wl, result.background, peak_curve,
                                alpha=0.3, color=color)
                ax.plot(wl, peak_curve, ":", color=color, linewidth=1.5)
                ax.axvline(x=center, color=color, linestyle=":", linewidth=1.5, alpha=0.7,
                           label=f"峰{i+1}: {center:.4f} nm")

            ax.set_ylabel("强度 (a.u.)", fontsize=11)
            ax.set_title(f"{name}分解 (χ²={result.chi_squared:.4f})", fontsize=12)
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.legend(loc="best", fontsize=8, framealpha=0.9)
        except Exception as e:
            ax.text(0.5, 0.5, f"{name}拟合失败:\n{str(e)}",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=12, color="red")
            ax.set_ylabel("强度 (a.u.)", fontsize=11)
            ax.set_title(name, fontsize=12)
            ax.grid(True, alpha=0.3, linestyle="--")

    axes[-1].set_xlabel("波长 (nm)", fontsize=12)
    fig.suptitle(f"重叠峰分解方法对比: {spectrum.filename}\n{n_peaks}个峰", fontsize=14, y=0.995)
    plt.tight_layout()

    if output_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        print(f"Figure saved to: {output_path}")

    if show_plot:
        plt.show()

    return fig


def plot_batch_summary(
    results: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    show_plot: bool = False,
    dpi: int = 150,
    figsize: Tuple[int, int] = (14, 8),
) -> plt.Figure:
    """
    Plot summary of batch processing results.

    Parameters:
    -----------
    results : list of dict
        List of batch processing results with keys:
        'filename', 'wavelength', 'wavelength_shift', 'temperature', 'strain', etc.
    output_path : str, optional
        Path to save the figure
    show_plot : bool
        Whether to display the plot
    dpi : int
        DPI for saved figure
    figsize : tuple
        Figure size

    Returns:
    --------
    matplotlib.Figure
        The created figure
    """
    if not results:
        raise ValueError("No results to plot")

    has_shift = any("wavelength_shift" in r for r in results)
    has_temp = any("temperature" in r for r in results)
    has_strain = any("strain" in r for r in results)

    n_plots = 1 + sum([has_shift, has_temp, has_strain])

    fig, axes = plt.subplots(n_plots, 1, figsize=(figsize[0], figsize[1] * n_plots / 3), sharex=True)
    if n_plots == 1:
        axes = [axes]

    filenames = [r.get("filename", f"File {i}") for i, r in enumerate(results)]
    x = np.arange(len(results))

    axes[0].plot(x, [r.get("wavelength", np.nan) for r in results],
                 "bo-", label="峰值波长", linewidth=1.5, markersize=6)
    if any("uncertainty_wavelength" in r and r["uncertainty_wavelength"] for r in results):
        axes[0].errorbar(
            x,
            [r.get("wavelength", np.nan) for r in results],
            yerr=[r.get("uncertainty_wavelength", 0) or 0 for r in results],
            fmt="none", ecolor="r", capsize=3, alpha=0.7,
        )
    axes[0].set_ylabel("波长 (nm)", fontsize=11)
    axes[0].set_title("批量处理结果汇总", fontsize=13)
    axes[0].grid(True, alpha=0.3, linestyle="--")
    axes[0].legend(fontsize=10)

    plot_idx = 1

    if has_shift:
        axes[plot_idx].plot(x, [r.get("wavelength_shift", np.nan) for r in results],
                            "go-", label="波长偏移", linewidth=1.5, markersize=6)
        if any("uncertainty_wavelength_shift" in r and r["uncertainty_wavelength_shift"] for r in results):
            axes[plot_idx].errorbar(
                x,
                [r.get("wavelength_shift", np.nan) for r in results],
                yerr=[r.get("uncertainty_wavelength_shift", 0) or 0 for r in results],
                fmt="none", ecolor="r", capsize=3, alpha=0.7,
            )
        axes[plot_idx].set_ylabel("偏移量 (nm)", fontsize=11)
        axes[plot_idx].grid(True, alpha=0.3, linestyle="--")
        axes[plot_idx].legend(fontsize=10)
        plot_idx += 1

    if has_temp:
        axes[plot_idx].plot(x, [r.get("temperature", np.nan) for r in results],
                            "ro-", label="温度", linewidth=1.5, markersize=6)
        if any("uncertainty_temperature" in r and r["uncertainty_temperature"] for r in results):
            axes[plot_idx].errorbar(
                x,
                [r.get("temperature", np.nan) for r in results],
                yerr=[r.get("uncertainty_temperature", 0) or 0 for r in results],
                fmt="none", ecolor="k", capsize=3, alpha=0.7,
            )
        axes[plot_idx].set_ylabel("温度 (°C)", fontsize=11)
        axes[plot_idx].grid(True, alpha=0.3, linestyle="--")
        axes[plot_idx].legend(fontsize=10)
        plot_idx += 1

    if has_strain:
        axes[plot_idx].plot(x, [r.get("strain", np.nan) for r in results],
                            "mo-", label="应变", linewidth=1.5, markersize=6)
        if any("uncertainty_strain" in r and r["uncertainty_strain"] for r in results):
            axes[plot_idx].errorbar(
                x,
                [r.get("strain", np.nan) for r in results],
                yerr=[r.get("uncertainty_strain", 0) or 0 for r in results],
                fmt="none", ecolor="k", capsize=3, alpha=0.7,
            )
        axes[plot_idx].set_ylabel("应变 (με)", fontsize=11)
        axes[plot_idx].grid(True, alpha=0.3, linestyle="--")
        axes[plot_idx].legend(fontsize=10)
        plot_idx += 1

    axes[-1].set_xlabel("文件", fontsize=11)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(filenames, rotation=45, ha="right", fontsize=9)

    plt.tight_layout()

    if output_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        print(f"Figure saved to: {output_path}")

    if show_plot:
        plt.show()

    return fig
