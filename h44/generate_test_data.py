"""
生成测试用的模拟干涉图数据
用于演示和测试相位解缠功能
"""

import numpy as np
from pathlib import Path
import rasterio
from rasterio.transform import from_origin


def generate_simulated_interferogram(size: int = 200,
                                     add_noise: bool = True,
                                     add_residues: bool = True) -> np.ndarray:
    """
    生成模拟的干涉图相位

    Args:
        size: 图像尺寸 (size x size)
        add_noise: 是否添加噪声
        add_residues: 是否添加残差点

    Returns:
        包裹相位图 [-π, π]
    """
    x = np.linspace(-5, 5, size)
    y = np.linspace(-5, 5, size)
    X, Y = np.meshgrid(x, y)

    phase = 2 * np.pi * (X ** 2 + Y ** 2) / 10
    phase += 1 * np.pi * np.sin(X) * np.cos(Y)

    phase += 3 * np.pi * np.exp(-((X - 2) ** 2 + (Y + 1) ** 2) / 2)
    phase -= 2 * np.pi * np.exp(-((X + 2) ** 2 + (Y - 1) ** 2) / 3)

    if add_noise:
        noise = np.random.normal(0, 0.3, phase.shape)
        phase += noise

    if add_residues:
        for _ in range(5):
            cx = np.random.randint(20, size - 20)
            cy = np.random.randint(20, size - 20)
            phase[cy, cx] += np.pi * 0.8
            phase[cy, cx + 1] -= np.pi * 0.3
            phase[cy + 1, cx + 1] += np.pi * 0.2

    wrapped_phase = np.arctan2(np.sin(phase), np.cos(phase))

    return wrapped_phase.astype(np.float32)


def generate_amplitude(size: int = 200) -> np.ndarray:
    """
    生成模拟振幅图

    Args:
        size: 图像尺寸

    Returns:
        振幅图
    """
    x = np.linspace(-5, 5, size)
    y = np.linspace(-5, 5, size)
    X, Y = np.meshgrid(x, y)

    amplitude = 100 + 50 * np.exp(-(X ** 2 + Y ** 2) / 10)

    amplitude += np.random.normal(0, 5, amplitude.shape)
    amplitude = np.clip(amplitude, 1, 200)

    water_mask = (X - 1) ** 2 + (Y + 2) ** 2 < 1.5 ** 2
    amplitude[water_mask] = np.random.normal(10, 3, amplitude[water_mask].shape)

    shadow_mask = (X > 2) & (Y < -1)
    amplitude[shadow_mask] = np.random.normal(5, 2, amplitude[shadow_mask].shape)

    return amplitude.astype(np.float32)


def save_as_geotiff(data: np.ndarray, filepath: str,
                    pixel_size: float = 1.0) -> None:
    """
    保存为GeoTIFF格式

    Args:
        data: 数据数组
        filepath: 输出文件路径
        pixel_size: 像素大小
    """
    rows, cols = data.shape
    transform = from_origin(0, 0, pixel_size, pixel_size)

    with rasterio.open(
        filepath,
        'w',
        driver='GTiff',
        height=rows,
        width=cols,
        count=1,
        dtype=data.dtype,
        crs='EPSG:4326',
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def main():
    """生成测试数据"""
    output_dir = Path('test_data')
    output_dir.mkdir(exist_ok=True)

    print('正在生成测试数据...')

    wrapped_phase = generate_simulated_interferogram(size=200)
    phase_path = output_dir / 'wrapped_phase.tif'
    save_as_geotiff(wrapped_phase, str(phase_path))
    print(f'已生成包裹相位图: {phase_path}')
    print(f'  尺寸: {wrapped_phase.shape}')
    print(f'  范围: [{wrapped_phase.min():.4f}, {wrapped_phase.max():.4f}]')

    amplitude = generate_amplitude(size=200)
    amp_path = output_dir / 'amplitude.tif'
    save_as_geotiff(amplitude, str(amp_path))
    print(f'已生成振幅图: {amp_path}')

    quality = 1 - (amplitude - amplitude.min()) / (amplitude.max() - amplitude.min() + 1e-10)
    quality[amplitude < 20] = 0.1
    quality_path = output_dir / 'quality_map.tif'
    save_as_geotiff(quality.astype(np.float32), str(quality_path))
    print(f'已生成质量图: {quality_path}')

    print('\n测试数据生成完成！')
    print(f'数据保存在: {output_dir.absolute()}')
    print('可以使用 main.py 启动应用程序，然后加载 test_data/wrapped_phase.tif 进行测试')


if __name__ == '__main__':
    main()
