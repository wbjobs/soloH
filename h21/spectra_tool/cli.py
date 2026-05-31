import click
import os
import sys
import json
from typing import Optional, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

import matplotlib
matplotlib.use("Agg")

from .version import __version__

console = Console()


def parse_calibration_coeffs(ctx, param, value) -> Optional[dict]:
    """Parse calibration coefficients from command line."""
    if not value:
        return None
    try:
        if os.path.exists(value):
            with open(value, "r") as f:
                return json.load(f)
        else:
            coeffs = {}
            for item in value.split(","):
                key, val = item.split("=")
                coeffs[key.strip()] = float(val.strip())
            return coeffs
    except Exception as e:
        raise click.BadParameter(f"Invalid calibration coefficients: {e}")


def parse_crop_range(ctx, param, value) -> Optional[Tuple[float, float]]:
    """Parse wavelength crop range."""
    if not value:
        return None
    try:
        parts = value.split(",")
        if len(parts) != 2:
            raise ValueError("Range must be min,max")
        return (float(parts[0].strip()), float(parts[1].strip()))
    except Exception as e:
        raise click.BadParameter(f"Invalid crop range: {e}")


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="spectra-tool")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx, verbose: bool):
    """
    光谱数据处理工具 - 峰值检测、重叠峰分解、温度应变计算

    支持的功能：
    - 读取多种格式的光谱数据文件
    - 多种峰值检测算法（质心法、高斯拟合、多项式拟合、自适应阈值）
    - 重叠峰分解（Lorentzian、Voigt、伪Voigt线型，LM算法）
    - 根据标定系数计算温度和应变
    - 输出波长偏移量和测量不确定度
    - 批量处理文件夹内所有文件
    - 生成汇总报告CSV和拟合结果对比图
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--method", "-m", default="gaussian",
              type=click.Choice(["centroid", "gaussian", "polynomial", "adaptive", "auto"]),
              help="峰值检测方法")
@click.option("--window", "-w", type=int, default=30, help="拟合窗口大小（数据点数）")
@click.option("--degree", type=int, default=4, help="多项式拟合阶数")
@click.option("--decomposition", "-d", is_flag=True, help="启用重叠峰分解")
@click.option("--n-peaks", "-n", type=int, help="重叠峰数量")
@click.option("--line-profile", default="lorentzian",
              type=click.Choice(["lorentzian", "voigt", "pseudo_voigt"]),
              help="重叠峰分解线型")
@click.option("--reference-wavelength", "-r", type=float, help="参考波长（nm）")
@click.option("--calibration", "-c", callback=parse_calibration_coeffs,
              help='标定系数: "k_T=0.01,k_eps=0.001" 或 JSON文件路径')
@click.option("--reference-temperature", type=float, default=25.0, help="参考温度（°C）")
@click.option("--remove-baseline", is_flag=True, help="去除基线")
@click.option("--baseline-method", default="poly",
              type=click.Choice(["poly", "als"]), help="基线去除方法")
@click.option("--normalize", is_flag=True, help="归一化光谱")
@click.option("--crop", callback=parse_crop_range, help="波长范围裁剪: min,max")
@click.option("--plot/--no-plot", default=True, help="生成拟合结果图")
@click.option("--compare-methods", is_flag=True, help="比较所有峰值检测方法")
@click.option("--compare-decomposition", is_flag=True, help="比较不同分解线型")
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--delimiter", help="文件分隔符（自动检测）")
@click.option("--skiprows", type=int, default=0, help="跳过的行数")
@click.option("--encoding", default="utf-8", help="文件编码")
def process(filepath: str, method: str, window: int, degree: int,
            decomposition: bool, n_peaks: int, line_profile: str,
            reference_wavelength: float, calibration: dict,
            reference_temperature: float, remove_baseline: bool,
            baseline_method: str, normalize: bool, crop: tuple,
            plot: bool, compare_methods: bool, compare_decomposition: bool,
            output_dir: str, delimiter: str, skiprows: int, encoding: str):
    """处理单个光谱数据文件"""
    from .batch_processor import process_single_file

    console.print(Panel.fit(
        f"[bold blue]处理文件:[/bold blue] {os.path.basename(filepath)}",
        border_style="blue"
    ))

    if output_dir is None:
        output_dir = os.path.dirname(filepath)

    peak_detection_kwargs = {"window": window}
    if method == "polynomial":
        peak_detection_kwargs["degree"] = degree

    read_kwargs = {
        "delimiter": delimiter,
        "skiprows": skiprows,
        "encoding": encoding,
    }

    plot_methods = ["centroid", "gaussian", "polynomial"] if compare_methods else None

    result = process_single_file(
        filepath,
        method=method,
        peak_detection_kwargs=peak_detection_kwargs,
        decomposition=decomposition,
        n_peaks=n_peaks,
        line_profile=line_profile,
        reference_wavelength=reference_wavelength,
        calibration_coeffs=calibration,
        reference_temperature=reference_temperature,
        remove_baseline=remove_baseline,
        baseline_method=baseline_method,
        normalize=normalize,
        crop_range=crop,
        plot=plot,
        plot_output_dir=output_dir,
        plot_methods=plot_methods,
        compare_decomposition=compare_decomposition,
        **read_kwargs,
    )

    _display_result(result)


@main.command()
@click.argument("input-dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--extensions", "-e", help="文件扩展名，逗号分隔（如 .txt,.csv）")
@click.option("--recursive/--no-recursive", default=True, help="递归处理子目录")
@click.option("--method", "-m", default="gaussian",
              type=click.Choice(["centroid", "gaussian", "polynomial", "adaptive", "auto"]),
              help="峰值检测方法")
@click.option("--window", "-w", type=int, default=30, help="拟合窗口大小")
@click.option("--degree", type=int, default=4, help="多项式拟合阶数")
@click.option("--decomposition", "-d", is_flag=True, help="启用重叠峰分解")
@click.option("--n-peaks", "-n", type=int, help="重叠峰数量")
@click.option("--line-profile", default="lorentzian",
              type=click.Choice(["lorentzian", "voigt", "pseudo_voigt"]),
              help="重叠峰分解线型")
@click.option("--reference-wavelength", "-r", type=float, help="参考波长（nm）")
@click.option("--calibration", "-c", callback=parse_calibration_coeffs,
              help='标定系数: "k_T=0.01,k_eps=0.001" 或 JSON文件路径')
@click.option("--reference-temperature", type=float, default=25.0, help="参考温度（°C）")
@click.option("--remove-baseline", is_flag=True, help="去除基线")
@click.option("--baseline-method", default="poly",
              type=click.Choice(["poly", "als"]), help="基线去除方法")
@click.option("--normalize", is_flag=True, help="归一化光谱")
@click.option("--crop", callback=parse_crop_range, help="波长范围裁剪: min,max")
@click.option("--plot/--no-plot", default=True, help="生成拟合结果图")
@click.option("--report-name", default="batch_report.csv", help="报告文件名")
@click.option("--delimiter", help="文件分隔符（自动检测）")
@click.option("--skiprows", type=int, default=0, help="跳过的行数")
@click.option("--encoding", default="utf-8", help="文件编码")
def batch(input_dir: str, output_dir: str, extensions: str, recursive: bool,
          method: str, window: int, degree: int, decomposition: bool,
          n_peaks: int, line_profile: str, reference_wavelength: float,
          calibration: dict, reference_temperature: float,
          remove_baseline: bool, baseline_method: str, normalize: bool,
          crop: tuple, plot: bool, report_name: str, delimiter: str,
          skiprows: int, encoding: str):
    """批量处理文件夹内所有光谱数据文件"""
    from .batch_processor import process_batch, generate_report

    if output_dir is None:
        output_dir = input_dir

    ext_list = extensions.split(",") if extensions else None

    console.print(Panel.fit(
        f"[bold green]批量处理目录:[/bold green] {input_dir}\n"
        f"[bold green]输出目录:[/bold green] {output_dir}",
        border_style="green"
    ))

    peak_detection_kwargs = {"window": window}
    if method == "polynomial":
        peak_detection_kwargs["degree"] = degree

    read_kwargs = {
        "delimiter": delimiter,
        "skiprows": skiprows,
        "encoding": encoding,
    }

    results = process_batch(
        input_dir,
        output_dir=output_dir,
        extensions=ext_list,
        recursive=recursive,
        method=method,
        peak_detection_kwargs=peak_detection_kwargs,
        decomposition=decomposition,
        n_peaks=n_peaks,
        line_profile=line_profile,
        reference_wavelength=reference_wavelength,
        calibration_coeffs=calibration,
        reference_temperature=reference_temperature,
        remove_baseline=remove_baseline,
        baseline_method=baseline_method,
        normalize=normalize,
        crop_range=crop,
        plot=plot,
        **read_kwargs,
    )

    if results:
        report_path = os.path.join(output_dir, report_name)
        generate_report(results, report_path)

        _display_batch_summary(results, report_path)
    else:
        console.print("[yellow]警告: 没有处理任何文件[/yellow]")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--n-peaks", "-n", type=int, default=3, help="重叠峰数量")
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
def compare_decomposition(filepath: str, n_peaks: int, output_dir: str):
    """比较不同线型的重叠峰分解结果"""
    from .data_reader import read_spectrum_file
    from .visualization import plot_decomposition_comparison

    console.print(Panel.fit(
        f"[bold magenta]分解方法对比:[/bold magenta] {os.path.basename(filepath)}\n"
        f"[bold magenta]峰数量:[/bold magenta] {n_peaks}",
        border_style="magenta"
    ))

    spectrum = read_spectrum_file(filepath)

    if output_dir is None:
        output_dir = os.path.dirname(filepath)

    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(filepath))[0]}_decomposition_comparison.png")

    plot_decomposition_comparison(spectrum, n_peaks=n_peaks, output_path=output_path)

    console.print(f"[green]✓ 分解对比图已保存:[/green] {output_path}")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
def compare_methods(filepath: str, output_dir: str):
    """比较不同峰值检测方法的结果"""
    from .data_reader import read_spectrum_file
    from .visualization import plot_method_comparison

    console.print(Panel.fit(
        f"[bold cyan]方法对比:[/bold cyan] {os.path.basename(filepath)}",
        border_style="cyan"
    ))

    spectrum = read_spectrum_file(filepath)

    if output_dir is None:
        output_dir = os.path.dirname(filepath)

    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(filepath))[0]}_method_comparison.png")

    plot_method_comparison(spectrum, output_path=output_path)

    console.print(f"[green]✓ 方法对比图已保存:[/green] {output_path}")


@main.command()
@click.option("--output-dir", "-o", default="test_data", help="测试数据输出目录")
@click.option("--n-files", type=int, default=5, help="生成测试文件数量")
@click.option("--n-peaks", type=int, default=3, help="每个文件的峰数量")
@click.option("--overlapping/--no-overlapping", default=True, help="生成重叠峰")
@click.option("--noise-level", type=float, default=0.05, help="噪声水平")
def generate_test_data(output_dir: str, n_files: int, n_peaks: int,
                       overlapping: bool, noise_level: float):
    """生成测试光谱数据文件"""
    from .data_reader import SpectrumData
    import numpy as np

    os.makedirs(output_dir, exist_ok=True)

    console.print(Panel.fit(
        f"[bold yellow]生成测试数据[/bold yellow]\n"
        f"文件数量: {n_files}\n"
        f"峰数量: {n_peaks}\n"
        f"重叠峰: {overlapping}\n"
        f"噪声水平: {noise_level}",
        border_style="yellow"
    ))

    wl = np.linspace(1500, 1600, 500)
    base_wavelengths = np.linspace(1520, 1580, n_peaks)

    for file_idx in range(n_files):
        intensity = np.zeros_like(wl)
        shift = (file_idx - n_files / 2) * 0.5

        for i, center in enumerate(base_wavelengths):
            if overlapping:
                spacing = 8 if n_peaks <= 3 else 15 / n_peaks
                actual_center = center + shift + i * spacing
                sigma = 2 + np.random.rand() * 1
            else:
                actual_center = center + shift + i * 15
                sigma = 1.5 + np.random.rand() * 0.5

            amplitude = 0.6 + np.random.rand() * 0.4
            intensity += amplitude * np.exp(-((wl - actual_center) ** 2) / (2 * sigma ** 2))

        noise = np.random.normal(0, noise_level, size=len(wl))
        intensity = intensity + noise + 0.1

        filename = f"spectrum_{file_idx + 1:03d}.txt"
        filepath = os.path.join(output_dir, filename)

        header = f"# Spectrum test data file {file_idx + 1}\n"
        header += f"# Generated with noise_level={noise_level}, n_peaks={n_peaks}\n"
        header += f"# Wavelength (nm)\tIntensity (a.u.)\n"

        with open(filepath, "w") as f:
            f.write(header)
            for w, i_val in zip(wl, intensity):
                f.write(f"{w:.4f}\t{i_val:.6f}\n")

        console.print(f"  [green]✓ 已生成:[/green] {filename}")

    calib_file = os.path.join(output_dir, "calibration.json")
    calib_data = {
        "k_T": 0.01,
        "u_k_T": 0.0005,
        "k_eps": 0.0012,
        "u_k_eps": 0.00005,
        "u_reference": 0.001,
    }
    with open(calib_file, "w") as f:
        json.dump(calib_data, f, indent=2)
    console.print(f"  [green]✓ 已生成标定文件:[/green] {os.path.basename(calib_file)}")

    console.print(f"\n[bold green]测试数据已生成到:[/bold green] {os.path.abspath(output_dir)}")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--n-peaks", "-n", type=int, default=3, help="要搜索的峰数量")
@click.option("--line-profile", default="gaussian",
              type=click.Choice(["gaussian", "lorentzian"]),
              help="PSO拟合使用的线型")
@click.option("--n-particles", type=int, default=50, help="PSO粒子群数量")
@click.option("--max-iterations", type=int, default=200, help="最大迭代次数")
@click.option("--inertia-weight", type=float, default=0.7, help="惯性权重")
@click.option("--cognitive-weight", type=float, default=1.5, help="认知权重")
@click.option("--social-weight", type=float, default=1.5, help="社会权重")
@click.option("--plot/--no-plot", default=True, help="绘制PSO收敛曲线和拟合结果")
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--remove-baseline", is_flag=True, help="去除基线")
@click.option("--normalize", is_flag=True, help="归一化光谱")
def pso_search(filepath: str, n_peaks: int, line_profile: str, n_particles: int,
               max_iterations: int, inertia_weight: float, cognitive_weight: float,
               social_weight: float, plot: bool, output_dir: str,
               remove_baseline: bool, normalize: bool):
    """基于粒子群优化(PSO)的全局峰值搜索"""
    from .data_reader import read_spectrum_file
    from .global_optimization import pso_peak_search
    from .visualization import _setup_matplotlib

    _setup_matplotlib()

    console.print(Panel.fit(
        f"[bold magenta]PSO全局峰值搜索[/bold magenta]\n"
        f"文件: {os.path.basename(filepath)}\n"
        f"峰数量: {n_peaks}\n"
        f"线型: {line_profile}\n"
        f"粒子数: {n_particles}\n"
        f"最大迭代: {max_iterations}",
        border_style="magenta"
    ))

    spectrum = read_spectrum_file(filepath)

    if remove_baseline:
        spectrum = spectrum.remove_baseline()
    if normalize:
        spectrum = spectrum.normalize()

    result = pso_peak_search(
        spectrum.wavelength,
        spectrum.intensity,
        n_peaks=n_peaks,
        line_profile=line_profile,
        n_particles=n_particles,
        max_iterations=max_iterations,
        inertia_weight=inertia_weight,
        cognitive_weight=cognitive_weight,
        social_weight=social_weight,
    )

    table = Table(title="PSO全局搜索结果")
    table.add_column("峰号", style="cyan")
    table.add_column("波长 (nm)", style="green", justify="right")
    table.add_column("强度", style="yellow", justify="right")
    table.add_column("FWHM (nm)", style="magenta", justify="right")
    table.add_column("振幅", style="blue", justify="right")

    for i in range(n_peaks):
        table.add_row(
            str(i + 1),
            f"{result.wavelengths[i]:.4f}",
            f"{result.intensities[i]:.4f}",
            f"{result.fwhms[i]:.4f}",
            f"{result.amplitudes[i]:.4f}",
        )
    console.print(table)

    console.print(f"\n[bold]拟合优度:[/bold]")
    console.print(f"  R² = [green]{result.r_squared:.6f}[/green]")
    console.print(f"  χ² = [green]{result.chi_squared:.4f}[/green]")
    console.print(f"  迭代次数 = [cyan]{result.n_iterations}[/cyan]")

    if plot:
        if output_dir is None:
            output_dir = os.path.dirname(filepath)
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(filepath))[0]

        import matplotlib.pyplot as plt

        optimizer = __import__("spectra_tool.global_optimization", fromlist=["ParticleSwarmOptimizer"])
        pso_opt = optimizer.ParticleSwarmOptimizer(
            n_particles=n_particles,
            max_iterations=max_iterations,
            inertia_weight=inertia_weight,
            cognitive_weight=cognitive_weight,
            social_weight=social_weight,
        )
        y_fit = pso_opt._multi_peak_model(
            spectrum.wavelength,
            [val for pair in zip(result.amplitudes, result.wavelengths, result.fwhms) for val in pair] + [0],
            n_peaks,
            line_profile,
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        ax1.plot(spectrum.wavelength, spectrum.intensity, "b.", label="原始数据", markersize=3)
        ax1.plot(spectrum.wavelength, y_fit, "r-", label="PSO拟合", linewidth=2)
        for wl, inten in zip(result.wavelengths, result.intensities):
            ax1.axvline(x=wl, color="k", linestyle="--", alpha=0.5)
            ax1.plot(wl, inten, "ro", markersize=8)
        ax1.set_xlabel("波长 (nm)")
        ax1.set_ylabel("强度 (a.u.)")
        ax1.set_title(f"PSO峰值拟合 (R² = {result.r_squared:.4f})")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        ax2.semilogy(result.convergence_history, "b-", linewidth=2)
        ax2.set_xlabel("迭代次数")
        ax2.set_ylabel("目标函数值 (log)")
        ax2.set_title(f"PSO收敛曲线 ({result.n_iterations} 次迭代)")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plot_path = os.path.join(output_dir, f"{base_name}_pso_results.png")
        plt.savefig(plot_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        console.print(f"\n[green]✓ PSO结果图已保存:[/green] {plot_path}")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--channel-config", "-c", required=True, type=click.Path(exists=True),
              help="FBG通道配置JSON文件路径")
@click.option("--method", "-m", default="auto",
              type=click.Choice(["centroid", "gaussian", "polynomial", "adaptive", "auto"]),
              help="峰值检测方法")
@click.option("--decomposition", "-d", is_flag=True, help="启用重叠峰分解")
@click.option("--line-profile", default="gaussian",
              type=click.Choice(["gaussian", "lorentzian", "voigt", "pseudo_voigt"]),
              help="重叠峰分解线型")
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--plot/--no-plot", default=True, help="绘制各通道结果")
@click.option("--remove-baseline", is_flag=True, help="去除基线")
@click.option("--normalize", is_flag=True, help="归一化光谱")
def multichannel_demod(filepath: str, channel_config: str, method: str,
                       decomposition: bool, line_profile: str, output_dir: str,
                       plot: bool, remove_baseline: bool, normalize: bool):
    """多通道FBG阵列同时解调（波长-空间编码）"""
    from .multichannel_fbg import load_channel_config, demodulate_file, generate_multichannel_report
    from .visualization import _setup_matplotlib

    _setup_matplotlib()

    configs = load_channel_config(channel_config)

    console.print(Panel.fit(
        f"[bold blue]多通道FBG解调[/bold blue]\n"
        f"文件: {os.path.basename(filepath)}\n"
        f"通道数: {len(configs)}\n"
        f"方法: {method}\n"
        f"分解: {decomposition}",
        border_style="blue"
    ))

    console.print("\n[bold]通道配置:[/bold]")
    for cfg in configs:
        console.print(f"  [cyan]{cfg.channel_id}[/cyan]: {cfg.name} "
                      f"({cfg.wavelength_window[0]:.1f}-{cfg.wavelength_window[1]:.1f} nm), "
                      f"参考: {cfg.reference_wavelength:.2f} nm")

    result = demodulate_file(
        filepath,
        configs,
        method=method,
        decomposition=decomposition,
        line_profile=line_profile,
    )

    table = Table(title="多通道解调结果")
    table.add_column("通道ID", style="cyan")
    table.add_column("通道名称", style="blue")
    table.add_column("波长窗口 (nm)", style="yellow")
    table.add_column("检测峰数", style="green", justify="right")
    table.add_column("主波长 (nm)", style="magenta", justify="right")
    table.add_column("偏移量 (nm)", style="red", justify="right")
    table.add_column("温度 (°C)", style="yellow", justify="right")
    table.add_column("应变 (με)", style="green", justify="right")

    for ch in result.channels:
        if len(ch.peak_results) > 0:
            main_peak = ch.peak_results[0]
            shift = ch.wavelength_shifts[0] if ch.wavelength_shifts else "-"
            temp = ch.temperatures[0] if ch.temperatures else None
            strain = ch.strains[0] if ch.strains else None

            table.add_row(
                ch.channel_id,
                ch.name,
                f"{ch.wavelength_window[0]:.1f}-{ch.wavelength_window[1]:.1f}",
                str(len(ch.peak_results)),
                f"{main_peak.wavelength:.4f}",
                f"{shift:.4f}" if isinstance(shift, float) else shift,
                f"{temp:.2f}" if temp is not None else "-",
                f"{strain:.2f}" if strain is not None else "-",
            )
        else:
            table.add_row(
                ch.channel_id,
                ch.name,
                f"{ch.wavelength_window[0]:.1f}-{ch.wavelength_window[1]:.1f}",
                "[red]0[/red]",
                "-",
                "-",
                "-",
                "-",
            )

    console.print(table)

    if output_dir is None:
        output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    report_path = os.path.join(output_dir, f"{base_name}_multichannel_report.csv")
    generate_multichannel_report([result], report_path)
    console.print(f"\n[green]✓ 多通道报告已保存:[/green] {report_path}")

    if plot:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        fig, ax = plt.subplots(figsize=(12, 6))

        if result.raw_spectrum:
            wl = result.raw_spectrum.wavelength
            inten = result.raw_spectrum.intensity
            ax.plot(wl, inten, "b-", linewidth=1.5, label="原始光谱")

            y_min, y_max = ax.get_ylim()
            colors = plt.cm.tab10(range(len(configs)))
            for i, cfg in enumerate(configs):
                rect = Rectangle(
                    (cfg.wavelength_window[0], y_min),
                    cfg.wavelength_window[1] - cfg.wavelength_window[0],
                    y_max - y_min,
                    alpha=0.2,
                    color=colors[i],
                    label=cfg.name,
                )
                ax.add_patch(rect)

                ch_result = next((ch for ch in result.channels if ch.channel_id == cfg.channel_id), None)
                if ch_result and ch_result.peak_results:
                    for peak in ch_result.peak_results:
                        ax.plot(peak.wavelength, peak.intensity, "o",
                                color=colors[i], markersize=8, markeredgecolor="k")

        ax.set_xlabel("波长 (nm)")
        ax.set_ylabel("强度 (a.u.)")
        ax.set_title("多通道FBG解调结果 - 波长空间编码")
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        plot_path = os.path.join(output_dir, f"{base_name}_multichannel_spectrum.png")
        plt.savefig(plot_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        console.print(f"[green]✓ 多通道结果图已保存:[/green] {plot_path}")


@main.command()
@click.option("--port", "-p", required=True, help="串口名称 (如 COM3, /dev/ttyUSB0) 或 'simulate' 进行模拟")
@click.option("--baudrate", "-b", type=int, default=115200, help="波特率")
@click.option("--duration", type=float, help="运行时长（秒），默认无限运行")
@click.option("--channel-config", "-c", type=click.Path(exists=True),
              help="FBG通道配置JSON文件（用于多通道解调）")
@click.option("--method", "-m", default="auto",
              type=click.Choice(["centroid", "gaussian", "polynomial", "adaptive", "auto"]),
              help="峰值检测方法")
@click.option("--reference-wavelength", "-r", type=float, help="参考波长（nm）")
@click.option("--calibration", callback=parse_calibration_coeffs,
              help='标定系数: "k_T=0.01,k_eps=0.001" 或 JSON文件路径')
@click.option("--decomposition", "-d", is_flag=True, help="启用重叠峰分解")
@click.option("--n-peaks", type=int, default=1, help="峰数量")
@click.option("--line-profile", default="gaussian",
              type=click.Choice(["gaussian", "lorentzian", "voigt", "pseudo_voigt"]),
              help="重叠峰分解线型")
@click.option("--output-file", "-o", type=click.Path(), help="输出CSV文件路径")
@click.option("--smoothing", type=int, default=5, help="移动平均平滑窗口大小")
@click.option("--list-ports", is_flag=True, help="列出可用串口")
def realtime_demod(port: str, baudrate: int, duration: float, channel_config: str,
                   method: str, reference_wavelength: float, calibration: dict,
                   decomposition: bool, n_peaks: int, line_profile: str,
                   output_file: str, smoothing: int, list_ports: bool):
    """动态解调模式 - 实时从串口读取光谱仪数据"""
    from .dynamic_demodulation import run_realtime_demodulation, SerialSpectrumReader

    if list_ports:
        ports = SerialSpectrumReader.list_available_ports()
        if ports:
            console.print("[bold cyan]可用串口:[/bold cyan]")
            for p in ports:
                console.print(f"  - {p}")
        else:
            console.print("[yellow]未检测到可用串口[/yellow]")
        return

    console.print(Panel.fit(
        f"[bold red]实时动态解调[/bold red]\n"
        f"端口: {port}\n"
        f"波特率: {baudrate}\n"
        f"方法: {method}\n"
        f"运行时长: {f'{duration} 秒' if duration else '无限'}\n"
        f"输出文件: {output_file if output_file else '不保存'}",
        border_style="red"
    ))

    if port == "simulate":
        console.print("[yellow]注意: 使用模拟数据模式[/yellow]")

    try:
        buffer = run_realtime_demodulation(
            serial_port=port,
            baudrate=baudrate,
            output_file=output_file,
            channel_config=channel_config,
            duration=duration,
            method=method,
            reference_wavelength=reference_wavelength,
            calibration_coeffs=calibration,
            decomposition=decomposition,
            n_peaks=n_peaks,
            line_profile=line_profile,
            smoothing_window=smoothing,
        )

        console.print(f"\n[green]✓ 解调完成，共采集 {len(buffer)} 组数据[/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")


def _display_result(result: dict):
    """Display single file processing result."""
    if not result["success"]:
        console.print(f"[red]✗ 处理失败:[/red] {result.get('error', '未知错误')}")
        return

    console.print("[green]✓ 处理成功[/green]")

    spectrum = result["spectrum"]
    if spectrum:
        console.print(f"\n[bold]光谱信息:[/bold]")
        console.print(f"  数据点数: {spectrum.n_points}")
        console.print(f"  波长范围: {spectrum.wavelength_range[0]:.2f} - {spectrum.wavelength_range[1]:.2f} nm")
        console.print(f"  强度范围: {spectrum.intensity_stats[0]:.4f} - {spectrum.intensity_stats[1]:.4f} a.u.")

    peak_results = result.get("peak_results")
    if peak_results:
        table = Table(title="峰值检测结果")
        table.add_column("方法", style="cyan")
        table.add_column("波长 (nm)", style="green", justify="right")
        table.add_column("强度", style="yellow", justify="right")
        table.add_column("FWHM (nm)", style="magenta", justify="right")
        table.add_column("R²", style="blue", justify="right")
        table.add_column("不确定度 (nm)", style="red", justify="right")

        for peak in peak_results:
            table.add_row(
                peak.method,
                f"{peak.wavelength:.4f}",
                f"{peak.intensity:.4f}",
                f"{peak.fwhm:.4f}" if peak.fwhm else "-",
                f"{peak.r_squared:.6f}" if peak.r_squared else "-",
                f"{peak.uncertainty:.2e}" if peak.uncertainty else "-",
            )
        console.print(table)

    decomposition = result.get("decomposition_result")
    if decomposition:
        table = Table(title=f"重叠峰分解结果 ({decomposition.line_profile})")
        table.add_column("峰号", style="cyan")
        table.add_column("波长 (nm)", style="green", justify="right")
        table.add_column("强度", style="yellow", justify="right")
        table.add_column("FWHM (nm)", style="magenta", justify="right")
        table.add_column("不确定度 (nm)", style="red", justify="right")

        for i, (wl, inten, fwhm) in enumerate(zip(
            decomposition.wavelengths,
            decomposition.intensities,
            decomposition.fwhms,
        )):
            unc = decomposition.uncertainties[i] if decomposition.uncertainties else None
            table.add_row(
                str(i + 1),
                f"{wl:.4f}",
                f"{inten:.4f}",
                f"{fwhm:.4f}",
                f"{unc:.2e}" if unc else "-",
            )
        console.print(table)
        console.print(f"  拟合优度 R² = {decomposition.r_squared:.6f}, χ² = {decomposition.chi_squared:.4f}")

    physical_results = result.get("physical_results")
    if physical_results:
        table = Table(title="物理量计算结果")
        table.add_column("峰值波长 (nm)", style="cyan", justify="right")
        table.add_column("波长偏移 (nm)", style="green", justify="right")
        table.add_column("温度 (°C)", style="yellow", justify="right")
        table.add_column("应变 (με)", style="magenta", justify="right")

        for phys in physical_results:
            table.add_row(
                f"{phys.wavelength_peak:.4f}",
                f"{phys.wavelength_shift:.4f}",
                f"{phys.temperature:.2f}" if phys.temperature else "-",
                f"{phys.strain:.2f}" if phys.strain else "-",
            )
        console.print(table)

    if result["plot_paths"]:
        console.print("\n[bold]生成的图像:[/bold]")
        for path in result["plot_paths"]:
            console.print(f"  [blue]→[/blue] {path}")


def _display_batch_summary(results: list, report_path: str):
    """Display batch processing summary."""
    n_success = sum(1 for r in results if r["success"])
    n_failed = len(results) - n_success

    console.print()
    console.print(Panel.fit(
        f"[bold]批量处理完成[/bold]\n"
        f"[green]成功: {n_success}[/green] | [red]失败: {n_failed}[/red]\n"
        f"[blue]报告文件:[/blue] {report_path}",
        border_style="green"
    ))

    if n_failed > 0:
        console.print("\n[red]失败的文件:[/red]")
        for r in results:
            if not r["success"]:
                console.print(f"  - {r['filename']}: {r.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
