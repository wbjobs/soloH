import numpy as np
import pandas as pd
import os
from typing import Tuple, List, Optional


class FOGDataReader:
    """
    光纤陀螺（FOG）数据读取器
    支持读取 .txt, .csv, .xlsx, .dat 格式的角速率时间序列数据
    """

    SUPPORTED_FORMATS = ['.txt', '.csv', '.xlsx', '.dat']

    def __init__(self, sample_rate: float = 100.0):
        """
        初始化数据读取器

        Args:
            sample_rate: 采样频率 (Hz)，默认100Hz
        """
        self.sample_rate = sample_rate
        self.sample_interval = 1.0 / sample_rate

    def read_file(self, file_path: str, data_col: Optional[int] = None,
                  time_col: Optional[int] = None,
                  skiprows: Optional[int] = None, delimiter: str = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        读取单个数据文件

        Args:
            file_path: 数据文件路径
            data_col: 角速率数据所在列索引（从0开始），如果为None则自动检测
            time_col: 时间列索引，如果为None则自动生成时间轴
            skiprows: 跳过的行数
            delimiter: 分隔符，默认自动检测

        Returns:
            (time_array, rate_array): 时间数组和角速率数组
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的文件格式: {ext}。支持格式: {self.SUPPORTED_FORMATS}")

        try:
            if skiprows is None:
                skiprows = self._detect_header(file_path, ext)

            if ext == '.xlsx':
                df = pd.read_excel(file_path, skiprows=skiprows, header=None)
                data = df.values
            else:
                if delimiter is None:
                    delimiter = self._detect_delimiter(file_path, skiprows)
                try:
                    data = np.loadtxt(file_path, skiprows=skiprows, delimiter=delimiter)
                except ValueError:
                    df = pd.read_csv(file_path, skiprows=skiprows, header=None,
                                     delimiter=delimiter, on_bad_lines='skip')
                    data = df.values
        except Exception as e:
            raise RuntimeError(f"读取文件失败: {e}")

        if data.ndim == 1:
            rate_data = data
            time_data = np.arange(len(rate_data)) * self.sample_interval
        else:
            if time_col is not None and time_col < data.shape[1]:
                time_data = data[:, time_col]
                self.sample_interval = np.mean(np.diff(time_data))
                self.sample_rate = 1.0 / self.sample_interval
            else:
                time_data = np.arange(data.shape[0]) * self.sample_interval

            if data_col is not None and data_col < data.shape[1]:
                rate_data = data[:, data_col]
            else:
                rate_data = self._detect_rate_column(data)

        return time_data, rate_data

    def read_batch(self, file_paths: List[str], **kwargs) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        批量读取多个数据文件

        Args:
            file_paths: 文件路径列表
            **kwargs: 传递给 read_file 的其他参数

        Returns:
            数据列表，每个元素为 (time_array, rate_array)
        """
        results = []
        for file_path in file_paths:
            try:
                t, r = self.read_file(file_path, **kwargs)
                results.append((t, r))
                print(f"成功读取: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"读取失败 {os.path.basename(file_path)}: {e}")
        return results

    def read_directory(self, directory: str, extensions: List[str] = None,
                       recursive: bool = False, **kwargs) -> List[Tuple[str, np.ndarray, np.ndarray]]:
        """
        读取目录下的所有数据文件

        Args:
            directory: 目录路径
            extensions: 需要读取的文件扩展名列表，默认读取所有支持的格式
            recursive: 是否递归读取子目录
            **kwargs: 传递给 read_file 的其他参数

        Returns:
            数据列表，每个元素为 (file_name, time_array, rate_array)
        """
        if extensions is None:
            extensions = self.SUPPORTED_FORMATS

        file_paths = []
        if recursive:
            for root, _, files in os.walk(directory):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in extensions:
                        file_paths.append(os.path.join(root, f))
        else:
            for f in os.listdir(directory):
                ext = os.path.splitext(f)[1].lower()
                if ext in extensions:
                    file_paths.append(os.path.join(directory, f))

        results = []
        for file_path in sorted(file_paths):
            try:
                t, r = self.read_file(file_path, **kwargs)
                results.append((os.path.basename(file_path), t, r))
                print(f"成功读取: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"读取失败 {os.path.basename(file_path)}: {e}")

        return results

    def _detect_header(self, file_path: str, ext: str) -> int:
        """自动检测文件是否有表头行"""
        if ext == '.xlsx':
            return 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if not first_line:
                    return 0

                parts = first_line.replace(',', '\t').replace(';', '\t').split('\t')
                parts = [p.strip() for p in parts if p.strip()]

                if not parts:
                    return 0

                has_header = False
                for part in parts:
                    try:
                        float(part)
                    except ValueError:
                        has_header = True
                        break

                return 1 if has_header else 0
        except:
            return 0

    def _detect_delimiter(self, file_path: str, skiprows: int = 0) -> str:
        """自动检测文件分隔符"""
        with open(file_path, 'r') as f:
            for _ in range(max(0, skiprows)):
                f.readline()
            line = f.readline()

        if ',' in line:
            return ','
        elif '\t' in line:
            return '\t'
        elif ';' in line:
            return ';'
        else:
            return None

    def _detect_rate_column(self, data: np.ndarray) -> np.ndarray:
        """自动检测角速率数据列"""
        stds = np.std(data, axis=0)
        rate_col = np.argmax(stds)
        return data[:, rate_col]


def load_sample_data(duration: float = 100.0, sample_rate: float = 100.0,
                     noise_level: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    生成示例光纤陀螺数据（用于测试）

    Args:
        duration: 数据时长 (秒)
        sample_rate: 采样频率 (Hz)
        noise_level: 噪声强度系数

    Returns:
        (time_array, rate_array): 时间和角速率数据
    """
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
