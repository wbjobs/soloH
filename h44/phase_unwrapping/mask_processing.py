"""
掩膜处理模块
支持: 水体检测、阴影检测、手动掩膜编辑
"""

import numpy as np
from scipy import ndimage
from typing import Tuple, Optional, Dict, Any
from skimage import filters, morphology, segmentation


class MaskProcessor:
    """
    掩膜处理器
    提供多种掩膜生成和编辑功能
    """

    @staticmethod
    def create_valid_mask(data: np.ndarray,
                          nodata_value: Optional[float] = None) -> np.ndarray:
        """
        创建有效数据掩膜

        Args:
            data: 输入数据
            nodata_value: 无数据值

        Returns:
            有效区域掩膜 (1表示有效, 0表示无效)
        """
        mask = np.ones_like(data, dtype=bool)

        mask[np.isnan(data)] = False
        mask[np.isinf(data)] = False

        if nodata_value is not None:
            mask[data == nodata_value] = False

        return mask

    @staticmethod
    def detect_water(amplitude_image: np.ndarray,
                     threshold: Optional[float] = None,
                     window_size: int = 7) -> np.ndarray:
        """
        检测水体区域
        基于低振幅和高均匀性特征

        Args:
            amplitude_image: 振幅图像
            threshold: 水体阈值，None则自动计算
            window_size: 均匀性检测窗口大小

        Returns:
            水体掩膜 (1表示水体, 0表示非水体)
        """
        amp = amplitude_image.copy()
        amp[np.isnan(amp)] = np.nanmin(amp)
        amp[np.isinf(amp)] = np.nanmin(amp)

        if threshold is None:
            threshold = filters.threshold_otsu(amp) * 0.5

        low_amp_mask = amp < threshold

        kernel = np.ones((window_size, window_size), dtype=np.float64)
        kernel /= kernel.sum()

        mean_amp = ndimage.convolve(amp, kernel, mode='reflect')
        var_amp = ndimage.convolve((amp - mean_amp) ** 2, kernel, mode='reflect')

        low_variance_mask = var_amp < (np.nanmean(var_amp) * 0.3)

        water_mask = low_amp_mask & low_variance_mask

        water_mask = morphology.remove_small_objects(water_mask, min_size=100)
        water_mask = morphology.remove_small_holes(water_mask, area_threshold=100)

        return water_mask

    @staticmethod
    def detect_shadow(amplitude_image: np.ndarray,
                      wrapped_phase: Optional[np.ndarray] = None,
                      threshold: Optional[float] = None) -> np.ndarray:
        """
        检测阴影区域
        基于低振幅特征

        Args:
            amplitude_image: 振幅图像
            wrapped_phase: 包裹相位 (可选，用于辅助判断)
            threshold: 阴影阈值，None则自动计算

        Returns:
            阴影掩膜 (1表示阴影, 0表示非阴影)
        """
        amp = amplitude_image.copy()
        amp[np.isnan(amp)] = np.nanmin(amp)
        amp[np.isinf(amp)] = np.nanmin(amp)

        if threshold is None:
            threshold = np.percentile(amp[amp > 0], 10)

        shadow_mask = amp < threshold

        if wrapped_phase is not None:
            from .unwrapping_algorithms import phase_wrap
            dx = np.abs(phase_wrap(np.diff(wrapped_phase, axis=1)))
            dy = np.abs(phase_wrap(np.diff(wrapped_phase, axis=0)))
            dx_pad = np.hstack([dx, dx[:, -1:]])
            dy_pad = np.vstack([dy, dy[-1:, :]])
            high_gradient = (dx_pad > np.pi * 0.8) | (dy_pad > np.pi * 0.8)
            shadow_mask = shadow_mask | high_gradient

        shadow_mask = morphology.remove_small_objects(shadow_mask, min_size=50)

        return shadow_mask

    @staticmethod
    def detect_low_coherence(coherence_map: np.ndarray,
                             threshold: float = 0.3) -> np.ndarray:
        """
        检测低相干区域

        Args:
            coherence_map: 相干系数图 [0, 1]
            threshold: 低相干阈值

        Returns:
            低相干区域掩膜 (1表示低相干, 0表示正常)
        """
        low_coh_mask = coherence_map < threshold
        low_coh_mask = morphology.remove_small_objects(low_coh_mask, min_size=25)

        return low_coh_mask

    @staticmethod
    def detect_phase_discontinuity(wrapped_phase: np.ndarray,
                                   threshold: float = np.pi * 0.8) -> np.ndarray:
        """
        检测相位不连续区域

        Args:
            wrapped_phase: 包裹相位
            threshold: 不连续阈值

        Returns:
            相位不连续掩膜
        """
        from .unwrapping_algorithms import phase_wrap

        dx = np.abs(phase_wrap(np.diff(wrapped_phase, axis=1)))
        dy = np.abs(phase_wrap(np.diff(wrapped_phase, axis=0)))

        dx_pad = np.hstack([dx, dx[:, -1:]])
        dy_pad = np.vstack([dy, dy[-1:, :]])

        discontinuity_mask = (dx_pad > threshold) | (dy_pad > threshold)
        discontinuity_mask = morphology.binary_dilation(
            discontinuity_mask, morphology.square(3)
        )

        return discontinuity_mask

    @staticmethod
    def combine_masks(*masks: np.ndarray,
                      operation: str = 'or') -> np.ndarray:
        """
        组合多个掩膜

        Args:
            *masks: 多个掩膜
            operation: 组合方式 ('or', 'and')

        Returns:
            组合后的掩膜
        """
        if not masks:
            raise ValueError("至少需要提供一个掩膜")

        result = masks[0].astype(bool)

        if operation == 'or':
            for mask in masks[1:]:
                result = result | mask.astype(bool)
        elif operation == 'and':
            for mask in masks[1:]:
                result = result & mask.astype(bool)
        else:
            raise ValueError(f"不支持的组合方式: {operation}")

        return result

    @staticmethod
    def invert_mask(mask: np.ndarray) -> np.ndarray:
        """
        反转掩膜

        Args:
            mask: 输入掩膜

        Returns:
            反转后的掩膜
        """
        return ~mask.astype(bool)

    @staticmethod
    def dilate_mask(mask: np.ndarray,
                    radius: int = 1) -> np.ndarray:
        """
        膨胀掩膜

        Args:
            mask: 输入掩膜
            radius: 膨胀半径

        Returns:
            膨胀后的掩膜
        """
        if radius <= 0:
            return mask.astype(bool)

        selem = morphology.disk(radius)
        return morphology.binary_dilation(mask.astype(bool), selem)

    @staticmethod
    def erode_mask(mask: np.ndarray,
                   radius: int = 1) -> np.ndarray:
        """
        腐蚀掩膜

        Args:
            mask: 输入掩膜
            radius: 腐蚀半径

        Returns:
            腐蚀后的掩膜
        """
        if radius <= 0:
            return mask.astype(bool)

        selem = morphology.disk(radius)
        return morphology.binary_erosion(mask.astype(bool), selem)

    @staticmethod
    def smooth_mask(mask: np.ndarray,
                    radius: int = 2) -> np.ndarray:
        """
        平滑掩膜边缘

        Args:
            mask: 输入掩膜
            radius: 平滑半径

        Returns:
            平滑后的掩膜
        """
        if radius <= 0:
            return mask.astype(bool)

        mask_float = mask.astype(np.float64)
        kernel = np.ones((2 * radius + 1, 2 * radius + 1), dtype=np.float64)
        kernel /= kernel.sum()

        smoothed = ndimage.convolve(mask_float, kernel, mode='reflect')

        return smoothed > 0.5

    @staticmethod
    def manual_mask(shape: Tuple[int, int],
                    polygons: Optional[list] = None,
                    points: Optional[list] = None,
                    brush_radius: int = 5) -> np.ndarray:
        """
        创建手动掩膜

        Args:
            shape: 图像形状 (rows, cols)
            polygons: 多边形顶点列表，每个多边形是 [(y1,x1), (y2,x2), ...]
            points: 点坐标列表 [(y1,x1), (y2,x2), ...]
            brush_radius: 画笔半径

        Returns:
            手动掩膜
        """
        mask = np.zeros(shape, dtype=bool)

        if polygons is not None:
            for poly in polygons:
                if len(poly) < 3:
                    continue
                rr, cc = polygon2mask(shape, poly)
                mask[rr, cc] = True

        if points is not None:
            for (y, x) in points:
                if brush_radius > 0:
                    y_min = max(0, y - brush_radius)
                    y_max = min(shape[0], y + brush_radius + 1)
                    x_min = max(0, x - brush_radius)
                    x_max = min(shape[1], x + brush_radius + 1)

                    yy, xx = np.mgrid[y_min:y_max, x_min:x_max]
                    dist = np.sqrt((yy - y) ** 2 + (xx - x) ** 2)
                    mask[yy, xx] = mask[yy, xx] | (dist <= brush_radius)
                else:
                    if 0 <= y < shape[0] and 0 <= x < shape[1]:
                        mask[y, x] = True

        return mask

    @staticmethod
    def apply_mask(data: np.ndarray,
                   mask: np.ndarray,
                   fill_value: float = np.nan) -> np.ndarray:
        """
        应用掩膜到数据

        Args:
            data: 输入数据
            mask: 掩膜 (1表示保留, 0表示掩膜掉)
            fill_value: 掩膜区域填充值

        Returns:
            应用掩膜后的数据
        """
        result = data.copy()
        result[~mask.astype(bool)] = fill_value
        return result

    @staticmethod
    def get_mask_stats(mask: np.ndarray) -> Dict[str, Any]:
        """
        获取掩膜统计信息

        Args:
            mask: 输入掩膜

        Returns:
            统计信息字典
        """
        total_pixels = mask.size
        masked_pixels = np.sum(~mask.astype(bool))
        valid_pixels = np.sum(mask.astype(bool))
        masked_ratio = masked_pixels / total_pixels

        return {
            'total_pixels': total_pixels,
            'valid_pixels': valid_pixels,
            'masked_pixels': masked_pixels,
            'masked_ratio': masked_ratio,
        }


def polygon2mask(shape: Tuple[int, int], polygon: list) -> Tuple[np.ndarray, np.ndarray]:
    """
    将多边形转换为掩膜

    Args:
        shape: 图像形状 (rows, cols)
        polygon: 多边形顶点列表 [(y1,x1), (y2,x2), ...]

    Returns:
        (行索引, 列索引) 表示多边形内部的像素
    """
    from skimage.draw import polygon

    y_coords = [p[0] for p in polygon]
    x_coords = [p[1] for p in polygon]

    rr, cc = polygon(y_coords, x_coords, shape)

    return rr, cc


def generate_amplitude_from_phase(wrapped_phase: np.ndarray,
                                  quality_map: Optional[np.ndarray] = None) -> np.ndarray:
    """
    从相位和质量图生成模拟振幅图
    用于没有振幅数据时的水体/阴影检测

    Args:
        wrapped_phase: 包裹相位
        quality_map: 质量图 (可选)

    Returns:
        模拟振幅图
    """
    amplitude = np.ones_like(wrapped_phase, dtype=np.float64)

    if quality_map is not None:
        amplitude = quality_map.copy()
    else:
        from .quality_and_snaphu import QualityMapGenerator
        amplitude = QualityMapGenerator.pseudo_coherence(wrapped_phase)

    amplitude = amplitude * 100 + np.random.normal(0, 5, amplitude.shape)
    amplitude = np.clip(amplitude, 1, 200)

    return amplitude


class AutoMaskGenerator:
    """
    自动掩膜生成器
    整合多种检测方法生成综合掩膜
    """

    def __init__(self):
        self.masks = {}

    def generate(self, wrapped_phase: np.ndarray,
                 amplitude_image: Optional[np.ndarray] = None,
                 coherence_map: Optional[np.ndarray] = None,
                 enable_water: bool = True,
                 enable_shadow: bool = True,
                 enable_low_coherence: bool = True,
                 enable_discontinuity: bool = False,
                 water_threshold: Optional[float] = None,
                 shadow_threshold: Optional[float] = None,
                 coherence_threshold: float = 0.3,
                 dilation_radius: int = 2) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        生成综合掩膜

        Args:
            wrapped_phase: 包裹相位
            amplitude_image: 振幅图像 (可选)
            coherence_map: 相干系数图 (可选)
            enable_water: 是否启用水体检测
            enable_shadow: 是否启用阴影检测
            enable_low_coherence: 是否启用低相干检测
            enable_discontinuity: 是否启用相位不连续检测
            water_threshold: 水体检测阈值
            shadow_threshold: 阴影检测阈值
            coherence_threshold: 相干系数阈值
            dilation_radius: 掩膜膨胀半径

        Returns:
            (综合掩膜, 各检测结果字典)
        """
        results = {}

        if amplitude_image is None:
            amplitude_image = generate_amplitude_from_phase(wrapped_phase, coherence_map)

        if enable_water:
            water_mask = MaskProcessor.detect_water(
                amplitude_image, water_threshold
            )
            results['water'] = water_mask
        else:
            results['water'] = np.zeros_like(wrapped_phase, dtype=bool)

        if enable_shadow:
            shadow_mask = MaskProcessor.detect_shadow(
                amplitude_image, wrapped_phase, shadow_threshold
            )
            results['shadow'] = shadow_mask
        else:
            results['shadow'] = np.zeros_like(wrapped_phase, dtype=bool)

        if enable_low_coherence:
            if coherence_map is None:
                from .quality_and_snaphu import QualityMapGenerator
                coherence_map = QualityMapGenerator.pseudo_coherence(wrapped_phase)
            low_coh_mask = MaskProcessor.detect_low_coherence(
                coherence_map, coherence_threshold
            )
            results['low_coherence'] = low_coh_mask
        else:
            results['low_coherence'] = np.zeros_like(wrapped_phase, dtype=bool)

        if enable_discontinuity:
            discontinuity_mask = MaskProcessor.detect_phase_discontinuity(wrapped_phase)
            results['discontinuity'] = discontinuity_mask
        else:
            results['discontinuity'] = np.zeros_like(wrapped_phase, dtype=bool)

        invalid_mask = MaskProcessor.combine_masks(
            results['water'],
            results['shadow'],
            results['low_coherence'],
            results['discontinuity'],
            operation='or'
        )

        if dilation_radius > 0:
            invalid_mask = MaskProcessor.dilate_mask(invalid_mask, dilation_radius)

        valid_mask = MaskProcessor.invert_mask(invalid_mask)

        results['combined'] = invalid_mask
        results['valid'] = valid_mask

        return valid_mask, results
