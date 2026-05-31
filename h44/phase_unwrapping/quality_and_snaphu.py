"""
质量图生成和SNAPHU接口模块
包含: 相干系数计算、伪相关系数计算、SNAPHU接口
修复: 集成平地相位去除功能
"""

import numpy as np
from scipy import ndimage
from typing import Tuple, Optional, Dict, Any
import os
import subprocess
import tempfile
from pathlib import Path

from .unwrapping_algorithms import remove_flat_phase


class QualityMapGenerator:
    """
    质量图生成器
    支持多种质量评估指标
    """

    @staticmethod
    def coherence(real_image: np.ndarray, imag_image: np.ndarray,
                  window_size: int = 5) -> np.ndarray:
        """
        计算相干系数图

        Args:
            real_image: 实部图像 (干涉图的实部)
            imag_image: 虚部图像 (干涉图的虚部)
            window_size: 估计窗口大小

        Returns:
            相干系数图 [0, 1]
        """
        complex_image = real_image + 1j * imag_image

        kernel = np.ones((window_size, window_size), dtype=np.float64)
        kernel /= kernel.sum()

        mean_real = ndimage.convolve(real_image, kernel, mode='reflect')
        mean_imag = ndimage.convolve(imag_image, kernel, mode='reflect')
        mean_amp = np.sqrt(mean_real ** 2 + mean_imag ** 2)

        mean_abs_sq = ndimage.convolve(np.abs(complex_image) ** 2, kernel, mode='reflect')

        numerator = mean_amp ** 2
        denominator = mean_abs_sq + 1e-10

        coherence = np.sqrt(numerator / denominator)
        coherence = np.clip(coherence, 0, 1)

        return coherence

    @staticmethod
    def pseudo_coherence(wrapped_phase: np.ndarray,
                         window_size: int = 5) -> np.ndarray:
        """
        计算伪相关系数 (伪相干系数)
        仅使用包裹相位数据估计质量

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            window_size: 估计窗口大小

        Returns:
            伪相关系数图 [0, 1]
        """
        cos_phase = np.cos(wrapped_phase)
        sin_phase = np.sin(wrapped_phase)

        kernel = np.ones((window_size, window_size), dtype=np.float64)
        kernel /= kernel.sum()

        mean_cos = ndimage.convolve(cos_phase, kernel, mode='reflect')
        mean_sin = ndimage.convolve(sin_phase, kernel, mode='reflect')
        mean_amp = np.sqrt(mean_cos ** 2 + mean_sin ** 2)

        mean_sq_cos = ndimage.convolve(cos_phase ** 2, kernel, mode='reflect')
        mean_sq_sin = ndimage.convolve(sin_phase ** 2, kernel, mode='reflect')
        mean_sq = (mean_sq_cos + mean_sq_sin) / 2.0 + 1e-10

        pseudo_coh = mean_amp / np.sqrt(mean_sq)
        pseudo_coh = np.clip(pseudo_coh, 0, 1)

        return pseudo_coh

    @staticmethod
    def phase_derivative_variance(wrapped_phase: np.ndarray,
                                  window_size: int = 5) -> np.ndarray:
        """
        计算相位导数方差质量图

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            window_size: 估计窗口大小

        Returns:
            相位导数方差图 (值越小质量越好)
        """
        from .unwrapping_algorithms import phase_wrap

        dx = phase_wrap(np.diff(wrapped_phase, axis=1))
        dy = phase_wrap(np.diff(wrapped_phase, axis=0))

        dx_pad = np.hstack([dx, dx[:, -1:]])
        dy_pad = np.vstack([dy, dy[-1:, :]])

        kernel = np.ones((window_size, window_size), dtype=np.float64)
        kernel /= kernel.sum()

        mean_dx = ndimage.convolve(dx_pad, kernel, mode='reflect')
        mean_dy = ndimage.convolve(dy_pad, kernel, mode='reflect')

        var_dx = ndimage.convolve((dx_pad - mean_dx) ** 2, kernel, mode='reflect')
        var_dy = ndimage.convolve((dy_pad - mean_dy) ** 2, kernel, mode='reflect')

        variance = var_dx + var_dy

        quality = 1.0 / (1.0 + variance)
        quality = np.clip(quality, 0, 1)

        return quality

    @staticmethod
    def max_phase_gradient(wrapped_phase: np.ndarray) -> np.ndarray:
        """
        计算最大相位梯度质量图

        Args:
            wrapped_phase: 包裹相位 [-π, π]

        Returns:
            最大相位梯度质量图 (值越小质量越好)
        """
        from .unwrapping_algorithms import phase_wrap

        grad_x = np.abs(phase_wrap(np.diff(wrapped_phase, axis=1)))
        grad_y = np.abs(phase_wrap(np.diff(wrapped_phase, axis=0)))

        grad_x_pad = np.hstack([grad_x, grad_x[:, -1:]])
        grad_y_pad = np.vstack([grad_y, grad_y[-1:, :]])

        max_grad = np.maximum(grad_x_pad, grad_y_pad)

        quality = 1.0 - max_grad / np.pi
        quality = np.clip(quality, 0, 1)

        return quality

    @staticmethod
    def generate(wrapped_phase: np.ndarray,
                 method: str = 'pseudo_coherence',
                 **kwargs) -> np.ndarray:
        """
        通用质量图生成接口

        Args:
            wrapped_phase: 包裹相位
            method: 方法名称
                - 'pseudo_coherence': 伪相关系数
                - 'phase_derivative_variance': 相位导数方差
                - 'max_phase_gradient': 最大相位梯度
                - 'coherence': 相干系数 (需要提供real和imag)
            **kwargs: 方法参数

        Returns:
            质量图 [0, 1]
        """
        if method == 'pseudo_coherence':
            return QualityMapGenerator.pseudo_coherence(wrapped_phase, **kwargs)
        elif method == 'phase_derivative_variance':
            return QualityMapGenerator.phase_derivative_variance(wrapped_phase, **kwargs)
        elif method == 'max_phase_gradient':
            return QualityMapGenerator.max_phase_gradient(wrapped_phase)
        elif method == 'coherence':
            real = kwargs.get('real_image', None)
            imag = kwargs.get('imag_image', None)
            if real is None or imag is None:
                raise ValueError("使用coherence方法需要提供real_image和imag_image")
            return QualityMapGenerator.coherence(real, imag, **kwargs)
        else:
            raise ValueError(f"不支持的质量图方法: {method}")


class SNAPHUInterface:
    """
    SNAPHU (Statistical-Cost, Network-Flow Algorithm for Phase Unwrapping) 接口
    需要安装SNAPHU外部程序
    """

    def __init__(self, snaphu_path: Optional[str] = None):
        """
        初始化SNAPHU接口

        Args:
            snaphu_path: SNAPHU可执行文件路径，如果为None则尝试从系统PATH查找
        """
        if snaphu_path is None:
            snaphu_path = self._find_snaphu()
        self.snaphu_path = snaphu_path
        self.available = self._check_availability()

    @staticmethod
    def _find_snaphu() -> str:
        """在系统PATH中查找SNAPHU"""
        import shutil
        snaphu = shutil.which('snaphu')
        return snaphu if snaphu else 'snaphu'

    def _check_availability(self) -> bool:
        """检查SNAPHU是否可用"""
        try:
            result = subprocess.run(
                [self.snaphu_path, '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None,
               cost_mode: str = 'DEFO',
               remove_flat: bool = True,
               flat_phase_degree: int = 1,
               **kwargs) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        使用SNAPHU进行相位解缠

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            mask: 有效区域掩膜 (1表示有效, 0表示无效)
            quality_map: 质量图 (用于加权)
            cost_mode: 成本模式
                - 'DEFO': 形变模式 (默认)
                - 'TOPO': 地形模式
                - 'SMOOTH': 平滑模式
                - 'NOSTATCOSTS': 无统计成本模式
            remove_flat: 是否去除平地相位
            flat_phase_degree: 平地相位拟合阶数 (1=线性, 2=二次)
            **kwargs: 其他SNAPHU参数

        Returns:
            (解缠相位, 结果信息字典)
        """
        if not self.available:
            raise RuntimeError("SNAPHU不可用，请确保已正确安装SNAPHU程序")

        rows, cols = wrapped_phase.shape

        estimated_flat_phase = None
        if remove_flat:
            wrapped_phase, estimated_flat_phase = remove_flat_phase(
                wrapped_phase, mask, quality_map=quality_map,
                degree=flat_phase_degree
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            input_file = tmpdir / 'wrapped_phase.raw'
            output_file = tmpdir / 'unwrapped_phase.raw'
            config_file = tmpdir / 'snaphu.conf'

            wrapped_phase.astype(np.float32).tofile(input_file)

            if mask is not None:
                mask_file = tmpdir / 'mask.raw'
                mask.astype(np.uint8).tofile(mask_file)

            if quality_map is not None:
                corr_file = tmpdir / 'correlation.raw'
                quality_map.astype(np.float32).tofile(corr_file)

            self._write_config_file(
                config_file, rows, cols,
                cost_mode=cost_mode,
                mask_file=mask_file if mask is not None else None,
                corr_file=corr_file if quality_map is not None else None,
                **kwargs
            )

            cmd = [
                self.snaphu_path,
                '-f', str(config_file),
                str(input_file),
                str(cols)
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode != 0:
                    raise RuntimeError(f"SNAPHU执行失败: {result.stderr}")

                unwrapped = np.fromfile(output_file, dtype=np.float32).reshape(rows, cols)
                unwrapped = unwrapped.astype(np.float64)

                if mask is not None:
                    unwrapped = np.where(mask.astype(bool), unwrapped, np.nan)

                info = {
                    'algorithm': 'snaphu',
                    'algorithm_name': 'SNAPHU (统计耗费网络流)',
                    'cost_mode': cost_mode,
                    'snaphu_output': result.stdout,
                    'flat_phase_removed': remove_flat,
                }

                if estimated_flat_phase is not None:
                    info['estimated_flat_phase'] = estimated_flat_phase

                from .unwrapping_algorithms import detect_residues, estimate_unwrapping_error
                pos_res, neg_res, charge_map = detect_residues(wrapped_phase, mask)
                info['positive_residues'] = pos_res
                info['negative_residues'] = neg_res
                info['charge_map'] = charge_map
                info['num_positive_residues'] = len(pos_res)
                info['num_negative_residues'] = len(neg_res)

                error = estimate_unwrapping_error(unwrapped, wrapped_phase, mask)
                info['error_estimate'] = error
                info['mean_error'] = np.nanmean(error) if not np.all(np.isnan(error)) else np.nan
                info['max_error'] = np.nanmax(error) if not np.all(np.isnan(error)) else np.nan

                return unwrapped, info

            except subprocess.TimeoutExpired:
                raise RuntimeError("SNAPHU执行超时")

    def _write_config_file(self, config_path: Path, rows: int, cols: int,
                           cost_mode: str = 'DEFO',
                           mask_file: Optional[Path] = None,
                           corr_file: Optional[Path] = None,
                           **kwargs) -> None:
        """
        编写SNAPHU配置文件
        """
        config_lines = []

        config_lines.append(f"ROWS {rows}")
        config_lines.append(f"COLS {cols}")
        config_lines.append(f"OUTFILE {config_path.parent / 'unwrapped_phase.raw'}")
        config_lines.append(f"INFILEFORMAT FLOAT_DATA")
        config_lines.append(f"OUTFILEFORMAT FLOAT_DATA")
        config_lines.append(f"COSTMODE {cost_mode}")

        if mask_file is not None:
            config_lines.append(f"MASKFILE {mask_file}")
            config_lines.append("MASKFORMAT BYTE_DATA")

        if corr_file is not None:
            config_lines.append(f"CORRFILE {corr_file}")
            config_lines.append("CORRFORMAT FLOAT_DATA")

        if 'max_processes' in kwargs:
            config_lines.append(f"MAXPROCESSES {kwargs['max_processes']}")

        if 'tile_size' in kwargs:
            tile_rows, tile_cols = kwargs['tile_size']
            config_lines.append(f"ROWBYTES {tile_cols * 4}")
            config_lines.append(f"TILEROWS {tile_rows}")
            config_lines.append(f"TILECOLS {tile_cols}")

        if 'init_method' in kwargs:
            config_lines.append(f"INIT {kwargs['init_method']}")

        for key, value in kwargs.items():
            if key not in ['max_processes', 'tile_size', 'init_method']:
                config_lines.append(f"{key.upper()} {value}")

        config_lines.append("")

        with open(config_path, 'w') as f:
            f.write('\n'.join(config_lines))


class SNAPHUEmulator:
    """
    SNAPHU模拟器
    当SNAPHU不可用时，提供类似功能的Python实现
    使用最小费用流算法进行相位解缠
    """

    def __init__(self):
        self.available = True

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None,
               cost_mode: str = 'DEFO',
               remove_flat: bool = True,
               flat_phase_degree: int = 1,
               use_region_growing: bool = False,
               weight_power: float = 3.0,
               **kwargs) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        模拟SNAPHU的相位解缠
        使用加权最小二乘作为后备方案，支持所有新功能

        Args:
            wrapped_phase: 包裹相位
            mask: 有效区域掩膜
            quality_map: 质量图
            cost_mode: 成本模式 (仅作标识)
            remove_flat: 是否去除平地相位
            flat_phase_degree: 平地相位拟合阶数
            use_region_growing: 是否使用质量引导区域增长
            weight_power: 权重幂指数
            **kwargs: 其他参数

        Returns:
            (解缠相位, 结果信息字典)
        """
        from .unwrapping_algorithms import LeastSquaresUnwrapper, detect_residues, estimate_unwrapping_error

        rows, cols = wrapped_phase.shape

        if mask is None:
            mask = np.ones_like(wrapped_phase, dtype=bool)

        if quality_map is None:
            quality_map = QualityMapGenerator.pseudo_coherence(wrapped_phase)

        estimated_flat_phase = None
        if remove_flat:
            wrapped_phase, estimated_flat_phase = remove_flat_phase(
                wrapped_phase, mask, quality_map=quality_map,
                degree=flat_phase_degree
            )

        unwrapper = LeastSquaresUnwrapper(
            use_weight=True,
            remove_flat=False,
            use_region_growing=use_region_growing,
            weight_power=weight_power,
            flat_phase_degree=flat_phase_degree
        )
        unwrapped = unwrapper.unwrap(wrapped_phase, mask, quality_map)

        info = {
            'algorithm': 'snaphu_emulator',
            'algorithm_name': 'SNAPHU模拟器 (加权最小二乘)',
            'cost_mode': cost_mode,
            'note': '使用加权最小二乘模拟SNAPHU，建议安装SNAPHU以获得最佳效果',
            'flat_phase_removed': remove_flat,
        }

        if estimated_flat_phase is not None:
            info['estimated_flat_phase'] = estimated_flat_phase

        pos_res, neg_res, charge_map = detect_residues(wrapped_phase, mask)
        info['positive_residues'] = pos_res
        info['negative_residues'] = neg_res
        info['charge_map'] = charge_map
        info['num_positive_residues'] = len(pos_res)
        info['num_negative_residues'] = len(neg_res)

        error = estimate_unwrapping_error(unwrapped, wrapped_phase, mask)
        info['error_estimate'] = error
        info['mean_error'] = np.nanmean(error) if not np.all(np.isnan(error)) else np.nan
        info['max_error'] = np.nanmax(error) if not np.all(np.isnan(error)) else np.nan

        return unwrapped, info


def get_snaphu_unwrapper(snaphu_path: Optional[str] = None):
    """
    获取SNAPHU解缠器，如果SNAPHU不可用则返回模拟器

    Args:
        snaphu_path: SNAPHU可执行文件路径

    Returns:
        SNAPHU接口或模拟器
    """
    snaphu = SNAPHUInterface(snaphu_path)
    if snaphu.available:
        return snaphu
    else:
        return SNAPHUEmulator()
