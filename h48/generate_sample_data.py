import numpy as np
import os
import pandas as pd


def generate_fog_data(sample_rate: float = 100.0, duration: float = 100.0,
                      noise_level: float = 1.0, seed: int = None) -> tuple:
    """
    生成模拟的光纤陀螺角速率数据

    Args:
        sample_rate: 采样频率 (Hz)
        duration: 数据时长 (秒)
        noise_level: 噪声强度系数
        seed: 随机种子

    Returns:
        (time_array, rate_array): 时间和角速率数据
    """
    if seed is not None:
        np.random.seed(seed)

    n_samples = int(duration * sample_rate)
    t = np.arange(n_samples) / sample_rate

    angle_random_walk = np.cumsum(np.random.randn(n_samples)) * np.sqrt(1.0 / sample_rate) * 0.01
    quantization_noise = np.round(np.random.randn(n_samples) * 0.001 * noise_level, 3)
    bias_instability = np.cumsum(np.random.randn(n_samples) * 0.0001)
    rate_random_walk = np.cumsum(np.random.randn(n_samples)) * np.sqrt(1.0 / sample_rate) * 0.00001
    rate_ramp = 0.00001 * t
    high_freq_noise = np.random.randn(n_samples) * 0.01 * noise_level

    rate_data = (angle_random_walk + quantization_noise + bias_instability +
                 rate_random_walk + rate_ramp + high_freq_noise)

    return t, rate_data


def generate_multiple_samples(output_dir: str = 'sample_data',
                              num_files: int = 3,
                              sample_rate: float = 100.0,
                              duration: float = 100.0):
    """
    生成多组示例数据

    Args:
        output_dir: 输出目录
        num_files: 生成的文件数量
        sample_rate: 采样频率
        duration: 每组数据时长
    """
    os.makedirs(output_dir, exist_ok=True)

    noise_levels = [0.8, 1.0, 1.5, 0.5, 2.0]

    for i in range(num_files):
        noise_level = noise_levels[i % len(noise_levels)]
        seed = i * 100 + 42

        t, rate_data = generate_fog_data(
            sample_rate=sample_rate,
            duration=duration,
            noise_level=noise_level,
            seed=seed
        )

        base_name = f'fog_sample_{i+1:02d}_noise{noise_level:.1f}'

        csv_file = os.path.join(output_dir, f'{base_name}.csv')
        df = pd.DataFrame({'时间(s)': t, '角速率(deg/h)': rate_data})
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"已生成: {csv_file}")

        txt_file = os.path.join(output_dir, f'{base_name}.txt')
        np.savetxt(txt_file, np.column_stack((t, rate_data)),
                   fmt='%.6f', header='时间(s) 角速率(deg/h)', comments='')
        print(f"已生成: {txt_file}")

    print(f"\n共生成 {num_files} 组示例数据，保存在: {output_dir}")


if __name__ == '__main__':
    print("=" * 60)
    print("光纤陀螺示例数据生成器")
    print("=" * 60)

    generate_multiple_samples(
        output_dir='sample_data',
        num_files=3,
        sample_rate=100.0,
        duration=100.0
    )

    print("\n" + "=" * 60)
    print("数据生成完成！")
    print("=" * 60)
