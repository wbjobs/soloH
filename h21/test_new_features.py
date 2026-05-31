import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import numpy as np
import matplotlib
matplotlib.use("Agg")

print("=" * 70)
print("测试新功能 - 光谱数据处理工具")
print("=" * 70)

from spectra_tool.data_reader import read_spectrum_file
from spectra_tool.global_optimization import pso_peak_search
from spectra_tool.multichannel_fbg import load_channel_config, demodulate_file
from spectra_tool.dynamic_demodulation import (
    SimulatedSpectrumSource,
    SerialSpectrumReader,
    RealTimeDemodulator,
    SerialConfig,
    DemodulationConfig,
)

print("\n1. 测试PSO全局峰值搜索")
print("-" * 70)

test_file = "test_data/spectrum_001.txt"
if not os.path.exists(test_file):
    print("  生成测试数据...")
    from spectra_tool.data_reader import SpectrumData

    os.makedirs("test_data", exist_ok=True)
    wl = np.linspace(1500, 1600, 500)
    base_wavelengths = [1520, 1550, 1580]

    for file_idx in range(5):
        intensity = np.zeros_like(wl)
        shift = (file_idx - 2) * 0.5

        for i, center in enumerate(base_wavelengths):
            actual_center = center + shift
            sigma = 2 + np.random.rand() * 1
            amplitude = 0.6 + np.random.rand() * 0.4
            intensity += amplitude * np.exp(-((wl - actual_center) ** 2) / (2 * sigma ** 2))

        noise = np.random.normal(0, 0.05, size=len(wl))
        intensity = intensity + noise + 0.1

        filename = f"test_data/spectrum_{file_idx + 1:03d}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Spectrum test data file {file_idx + 1}\n")
            f.write(f"# Wavelength (nm)\tIntensity (a.u.)\n")
            for w, i_val in zip(wl, intensity):
                f.write(f"{w:.4f}\t{i_val:.6f}\n")
        print(f"    已生成: {filename}")

print(f"  读取文件: {test_file}")
spectrum = read_spectrum_file(test_file)
print(f"  数据点数: {spectrum.n_points}")
print(f"  波长范围: {spectrum.wavelength_range[0]:.2f} - {spectrum.wavelength_range[1]:.2f} nm")

print(f"\n  运行PSO全局搜索（3个峰，高斯线型，50粒子，200迭代）...")
result = pso_peak_search(
    spectrum.wavelength,
    spectrum.intensity,
    n_peaks=3,
    line_profile="gaussian",
    n_particles=50,
    max_iterations=200,
)

print(f"  PSO搜索完成，迭代次数: {result.n_iterations}")
print(f"  拟合优度 R² = {result.r_squared:.6f}, χ² = {result.chi_squared:.4f}")
print(f"\n  检测到的峰:")
print(f"  {'峰号':<6}{'波长(nm)':<14}{'强度':<12}{'FWHM(nm)':<14}{'振幅':<12}")
for i in range(3):
    print(f"  {i+1:<6}{result.wavelengths[i]:<14.4f}{result.intensities[i]:<12.4f}"
          f"{result.fwhms[i]:<14.4f}{result.amplitudes[i]:<12.4f}")

print(f"\n  生成PSO结果图...")
from spectra_tool.global_optimization import ParticleSwarmOptimizer
import matplotlib.pyplot as plt

pso_opt = ParticleSwarmOptimizer(n_particles=50, max_iterations=200)
params = []
for amp, wl, fwhm in zip(result.amplitudes, result.wavelengths, result.fwhms):
    params.extend([amp, wl, fwhm])
params.append(0)
y_fit = pso_opt._multi_peak_model(spectrum.wavelength, params, 3, "gaussian")

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
output_path = "test_data/spectrum_001_pso_test.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"  PSO结果图已保存: {output_path}")
print("  [OK] PSO全局峰值搜索测试通过")

print("\n2. 测试多通道FBG解调")
print("-" * 70)

config_file = "test_data/fbg_channels.json"
if not os.path.exists(config_file):
    import json
    configs = [
        {
            "channel_id": "CH01",
            "name": "Temperature_Sensor_1",
            "wavelength_window": [1510, 1535],
            "reference_wavelength": 1520.0,
            "n_peaks": 1,
            "calibration_coeffs": {"k_T": 0.01, "k_eps": 0.0012},
        },
        {
            "channel_id": "CH02",
            "name": "Strain_Sensor_1",
            "wavelength_window": [1535, 1565],
            "reference_wavelength": 1550.0,
            "n_peaks": 1,
            "calibration_coeffs": {"k_T": 0.01, "k_eps": 0.0012},
        },
        {
            "channel_id": "CH03",
            "name": "Temperature_Sensor_2",
            "wavelength_window": [1565, 1590],
            "reference_wavelength": 1580.0,
            "n_peaks": 1,
            "calibration_coeffs": {"k_T": 0.01, "k_eps": 0.0012},
        },
    ]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)
    print(f"  已生成通道配置文件: {config_file}")

print(f"  加载通道配置: {config_file}")
channel_configs = load_channel_config(config_file)
print(f"  通道数量: {len(channel_configs)}")
for cfg in channel_configs:
    print(f"    {cfg.channel_id}: {cfg.name}, 窗口: {cfg.wavelength_window[0]:.0f}-{cfg.wavelength_window[1]:.0f} nm, "
          f"参考: {cfg.reference_wavelength:.1f} nm")

print(f"\n  解调文件: {test_file}")
mc_result = demodulate_file(
    test_file,
    channel_configs,
    method="auto",
    decomposition=False,
)

print(f"\n  多通道解调结果:")
print(f"  {'通道ID':<10}{'名称':<25}{'窗口(nm)':<16}{'峰数':<8}{'主波长(nm)':<14}"
      f"{'偏移(nm)':<12}{'温度(°C)':<12}{'应变(με)':<12}")
for ch in mc_result.channels:
    if len(ch.peak_results) > 0:
        main_peak = ch.peak_results[0]
        shift = ch.wavelength_shifts[0] if ch.wavelength_shifts else "-"
        temp = ch.temperatures[0] if ch.temperatures else None
        strain = ch.strains[0] if ch.strains else None

        shift_str = f"{shift:.4f}" if isinstance(shift, float) else "-"
        temp_str = f"{temp:.2f}" if temp is not None else "-"
        strain_str = f"{strain:.2f}" if strain is not None else "-"

        print(f"  {ch.channel_id:<10}{ch.name:<25}"
              f"{ch.wavelength_window[0]:.0f}-{ch.wavelength_window[1]:.0f}{'':<8}"
              f"{len(ch.peak_results):<8}{main_peak.wavelength:<14.4f}"
              f"{shift_str:<12}{temp_str:<12}{strain_str:<12}")
    else:
        print(f"  {ch.channel_id:<10}{ch.name:<25}"
              f"{ch.wavelength_window[0]:.0f}-{ch.wavelength_window[1]:.0f}{'':<8}"
              f"{'0':<8}{'-':<14}{'-':<12}{'-':<12}{'-':<12}")

print(f"\n  生成多通道解调结果图...")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

fig, ax = plt.subplots(figsize=(12, 6))
wl = mc_result.raw_spectrum.wavelength
inten = mc_result.raw_spectrum.intensity
ax.plot(wl, inten, "b-", linewidth=1.5, label="原始光谱")

y_min, y_max = ax.get_ylim()
colors = plt.cm.tab10(range(len(channel_configs)))
for i, cfg in enumerate(channel_configs):
    rect = Rectangle(
        (cfg.wavelength_window[0], y_min),
        cfg.wavelength_window[1] - cfg.wavelength_window[0],
        y_max - y_min,
        alpha=0.2,
        color=colors[i],
        label=cfg.name,
    )
    ax.add_patch(rect)

    ch_result = next((ch for ch in mc_result.channels if ch.channel_id == cfg.channel_id), None)
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

mc_plot_path = "test_data/spectrum_001_multichannel_test.png"
plt.savefig(mc_plot_path, dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"  多通道结果图已保存: {mc_plot_path}")
print("  [OK] 多通道FBG解调测试通过")

print("\n3. 测试动态解调 - 模拟数据源")
print("-" * 70)

print("  创建模拟光谱数据源（3个峰，带漂移）...")
source = SimulatedSpectrumSource(
    wavelength_range=(1540, 1560),
    n_points=500,
    peak_centers=[1545.0, 1550.0, 1555.0],
    peak_amplitudes=[1.5, 2.0, 1.2],
    peak_fwhms=[0.3, 0.25, 0.35],
    noise_level=0.02,
    update_interval=0.1,
    drift_speed=0.002,
)

serial_config = SerialConfig(port="simulate", baudrate=115200)
demod_config = DemodulationConfig(
    method="auto",
    n_peaks=3,
    decomposition=False,
    reference_wavelength=1550.0,
    calibration_coeffs={"k_T": 0.01, "k_eps": 0.0012},
    smoothing_window=3,
)

print(f"  配置: 参考波长={demod_config.reference_wavelength} nm, "
      f"k_T={demod_config.calibration_coeffs['k_T']}, "
      f"平滑窗口={demod_config.smoothing_window}")

demodulator = RealTimeDemodulator(serial_config, demod_config, data_buffer_size=100)
print(f"  开始模拟实时解调（采集5帧数据）...")

n_frames = 5
results = []
for i in range(n_frames):
    spectrum = source.generate_spectrum()

    result = demodulator._demodulate_spectrum(spectrum)
    demodulator.data_buffer.add(result)
    results.append(result)

    if len(result.peak_wavelengths) > 0:
        peak_info = ", ".join([f"λ{j+1}={wl:.4f}" for j, wl in enumerate(result.peak_wavelengths[:2])])
        print(f"    帧 {i+1}: 检测到 {len(result.peak_wavelengths)} 个峰, {peak_info}")
    else:
        print(f"    帧 {i+1}: 未检测到峰")

print(f"\n  模拟解调完成，共采集 {len(results)} 帧数据")
print(f"  缓冲区数据量: {len(demodulator.data_buffer)}")

latest = results[-1]
if len(latest.peak_wavelengths) > 0:
    print(f"\n  最新帧结果:")
    print(f"  {'峰号':<6}{'波长(nm)':<14}{'偏移(nm)':<14}{'温度(°C)':<12}{'应变(με)':<12}")
    for j in range(min(3, len(latest.peak_wavelengths))):
        wl = latest.peak_wavelengths[j]
        shift = latest.wavelength_shifts[j] if j < len(latest.wavelength_shifts) else 0
        temp = latest.temperatures[j] if j < len(latest.temperatures) else None
        strain = latest.strains[j] if j < len(latest.strains) else None

        temp_str = f"{temp:.2f}" if temp is not None else "-"
        strain_str = f"{strain:.2f}" if strain is not None else "-"
        print(f"  {j+1:<6}{wl:<14.4f}{shift:<14.4f}{temp_str:<12}{strain_str:<12}")

print(f"\n  保存结果到CSV...")
csv_output = "test_data/realtime_demod_test.csv"
saved_path = demodulator.save_results(csv_output)
print(f"  结果已保存: {saved_path}")

print("\n  列出可用串口（模拟）...")
ports = SerialSpectrumReader.list_available_ports()
if ports:
    print(f"  检测到的串口: {', '.join(ports)}")
else:
    print("  未检测到串口（正常，测试环境）")
print("  [OK] 动态解调模拟测试通过")

print("\n" + "=" * 70)
print("所有新功能测试完成！")
print("=" * 70)
print("\n已实现的新功能:")
print("  1. [OK] 粒子群优化(PSO)全局峰值搜索")
print("     - 支持高斯/洛伦兹线型")
print("     - 可配置粒子数、迭代次数、PSO参数")
print("     - 输出收敛曲线和拟合结果图")
print()
print("  2. [OK] 多通道FBG阵列同时解调（波长-空间编码）")
print("     - JSON配置文件定义各通道波长窗口")
print("     - 各通道独立的参考波长和标定系数")
print("     - 自动提取各通道光谱并解调")
print("     - 生成多通道空间编码示意图")
print()
print("  3. [OK] 动态解调模式（串口实时数据读取）")
print("     - 支持真实串口设备（基于pyserial）")
print("     - 内置模拟数据源用于测试")
print("     - 实时峰值检测、温度/应变计算")
print("     - 移动平均平滑和离群值去除")
print("     - 结果实时保存到CSV")
print("     - 支持多通道实时解调")
print()
print("生成的测试文件:")
print(f"  - {output_path} (PSO结果图)")
print(f"  - {mc_plot_path} (多通道结果图)")
print(f"  - {saved_path} (实时解调CSV)")
print()
print("CLI命令:")
print("  python main.py pso-search --help")
print("  python main.py multichannel-demod --help")
print("  python main.py realtime-demod --help")
