"""
高级干涉处理模块
包含: 1. 深度学习分阶段解缠 2. 多基线联合解缠 3. 时序InSAR SBAS形变速率反演
"""

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.linalg import lsqr, spsolve
from scipy.ndimage import label, binary_dilation
from typing import List, Tuple, Optional, Dict, Any
import warnings
from collections import defaultdict

from .unwrapping_algorithms import (
    phase_wrap, detect_residues, estimate_unwrapping_error,
    quality_weight_map, quality_guided_region_growing, remove_flat_phase,
    LeastSquaresUnwrapper, PhaseUnwrapper
)
from .quality_and_snaphu import QualityMapGenerator

warnings.filterwarnings('ignore')


# ============================================================================
# 1. 深度学习分阶段相位解缠
# ============================================================================

class DLPhaseUnwrapper:
    """
    基于深度学习策略的分阶段相位解缠
    采用"分而治之"策略，先处理高质量区域，再逐步扩展到高噪声区域
    模拟深度学习的分层特征学习过程

    阶段1: 高质量种子区域解缠 (置信度 > high_threshold)
    阶段2: 中等质量区域扩展解缠 (置信度 > mid_threshold)
    阶段3: 低质量区域填充解缠 (置信度 > low_threshold)
    阶段4: 残差修复与全局优化
    """

    def __init__(self,
                 high_threshold: float = 0.7,
                 mid_threshold: float = 0.4,
                 low_threshold: float = 0.15,
                 num_stages: int = 4,
                 use_multiscale: bool = True):
        """
        Args:
            high_threshold: 高质量区域阈值
            mid_threshold: 中等质量区域阈值
            low_threshold: 低质量区域阈值
            num_stages: 解缠阶段数
            use_multiscale: 是否使用多尺度策略
        """
        self.high_threshold = high_threshold
        self.mid_threshold = mid_threshold
        self.low_threshold = low_threshold
        self.num_stages = num_stages
        self.use_multiscale = use_multiscale

        self.stage_info = []
        self.unwrapped_stages = []

    def _segment_quality_layers(self, quality_map: np.ndarray,
                                mask: np.ndarray) -> List[np.ndarray]:
        """
        按质量分层，生成多个质量层级

        Args:
            quality_map: 质量图 [0, 1]
            mask: 有效区域掩膜

        Returns:
            质量层级列表，从高到低
        """
        layers = []

        if self.num_stages == 4:
            thresholds = [
                self.high_threshold,
                self.mid_threshold,
                self.low_threshold,
                0.0
            ]
        else:
            thresholds = np.linspace(self.high_threshold, 0, self.num_stages)

        for i in range(len(thresholds)):
            layer = mask & (quality_map >= thresholds[i])
            if i > 0:
                layer = layer & (~layers[i - 1])
            layers.append(layer)

        return layers

    def _multiscale_unwrap(self, wrapped_phase: np.ndarray,
                           quality_map: np.ndarray,
                           mask: np.ndarray) -> np.ndarray:
        """
        多尺度解缠策略 - 从粗到细逐步解缠

        Args:
            wrapped_phase: 包裹相位
            quality_map: 质量图
            mask: 有效区域掩膜

        Returns:
            多尺度融合的解缠相位
        """
        rows, cols = wrapped_phase.shape
        scales = [4, 2, 1] if self.use_multiscale else [1]

        unwrapped = None

        for scale in scales:
            if scale > 1:
                ds_rows = rows // scale
                ds_cols = cols // scale

                ds_wrapped = wrapped_phase[:ds_rows * scale, :ds_cols * scale].reshape(
                    ds_rows, scale, ds_cols, scale
                ).mean(axis=(1, 3))
                ds_quality = quality_map[:ds_rows * scale, :ds_cols * scale].reshape(
                    ds_rows, scale, ds_cols, scale
                ).mean(axis=(1, 3))
                ds_mask = mask[:ds_rows * scale, :ds_cols * scale].reshape(
                    ds_rows, scale, ds_cols, scale
                ).any(axis=(1, 3))

                unwrapper = LeastSquaresUnwrapper(
                    use_weight=True, remove_flat=True, weight_power=3.0
                )
                ds_unwrapped = unwrapper.unwrap(ds_wrapped, ds_mask, ds_quality)

                if unwrapped is None:
                    unwrapped = np.repeat(np.repeat(ds_unwrapped, scale, axis=0), scale, axis=1)
                    unwrapped = unwrapped[:rows, :cols]
                else:
                    upsampled = np.repeat(np.repeat(ds_unwrapped, scale, axis=0), scale, axis=1)
                    upsampled = upsampled[:rows, :cols]
                    valid = ~np.isnan(upsampled)
                    unwrapped[valid] = upsampled[valid]

            else:
                if unwrapped is None:
                    unwrapper = LeastSquaresUnwrapper(
                        use_weight=True, remove_flat=True, weight_power=3.0
                    )
                    unwrapped = unwrapper.unwrap(wrapped_phase, mask, quality_map)
                else:
                    unwrapper = LeastSquaresUnwrapper(
                        use_weight=True, remove_flat=False, weight_power=2.0
                    )
                    refined = unwrapper.unwrap(wrapped_phase, mask, quality_map)

                    quality_weights = quality_weight_map(quality_map, mask, power=2.0)
                    blend_mask = quality_map >= self.mid_threshold
                    unwrapped[blend_mask] = refined[blend_mask]

        return unwrapped

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        执行分阶段相位解缠

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            mask: 有效区域掩膜
            quality_map: 质量图

        Returns:
            (解缠相位, 结果信息字典)
        """
        rows, cols = wrapped_phase.shape

        if mask is None:
            mask = np.ones_like(wrapped_phase, dtype=bool)
        else:
            mask = mask.astype(bool)

        if quality_map is None:
            quality_map = QualityMapGenerator.pseudo_coherence(wrapped_phase)

        self.stage_info = []
        self.unwrapped_stages = []

        info = {
            'algorithm': 'dl_stage_unwrap',
            'algorithm_name': '深度学习分阶段解缠',
            'high_threshold': self.high_threshold,
            'mid_threshold': self.mid_threshold,
            'low_threshold': self.low_threshold,
            'num_stages': self.num_stages,
            'use_multiscale': self.use_multiscale,
        }

        try:
            unwrapped = self._multiscale_unwrap(wrapped_phase, quality_map, mask)

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

            layers = self._segment_quality_layers(quality_map, mask)
            for i, layer in enumerate(layers):
                layer_pixels = np.sum(layer)
                layer_error = error[layer] if np.any(layer) else np.array([])
                layer_mean_error = np.nanmean(layer_error) if len(layer_error) > 0 else np.nan
                self.stage_info.append({
                    'stage': i + 1,
                    'pixels': layer_pixels,
                    'mean_error': layer_mean_error
                })
                info[f'stage_{i + 1}_pixels'] = layer_pixels
                info[f'stage_{i + 1}_mean_error'] = layer_mean_error

            info['stage_details'] = self.stage_info

        except Exception as e:
            unwrapper = PhaseUnwrapper('weighted_least_squares', remove_flat=True)
            unwrapped, fallback_info = unwrapper.unwrap(wrapped_phase, mask, quality_map)
            info.update(fallback_info)
            info['algorithm'] = 'dl_stage_unwrap_fallback'
            info['algorithm_name'] = '分阶段解缠(降级到加权最小二乘)'
            info['fallback_reason'] = str(e)

        return unwrapped, info


# ============================================================================
# 2. 多基线干涉图联合解缠
# ============================================================================

class MultiBaselineUnwrapper:
    """
    多基线干涉图联合解缠
    利用不同垂直基线的干涉图进行联合解缠，提高解缠精度

    原理:
    - 不同基线对地形高度的敏感度不同
    - 短基线对地形不敏感，但对形变敏感
    - 长基线对地形敏感，但解缠难度大
    - 联合解缠可以利用不同基线的互补信息
    """

    def __init__(self,
                 use_baseline_weighting: bool = True,
                 combine_method: str = 'weighted_average'):
        """
        Args:
            use_baseline_weighting: 是否使用基线长度加权
            combine_method: 解缠结果组合方法
                - 'weighted_average': 加权平均
                - 'quality_best': 选择各像素最优解
                - 'sequential': 顺序解缠（从短到长）
        """
        self.use_baseline_weighting = use_baseline_weighting
        self.combine_method = combine_method

    def _baseline_weight(self, perpendicular_baselines: np.ndarray) -> np.ndarray:
        """
        计算基线权重 - 短基线权重更高（解缠更可靠）

        Args:
            perpendicular_baselines: 垂直基线数组

        Returns:
            基线权重数组
        """
        if not self.use_baseline_weighting:
            return np.ones_like(perpendicular_baselines, dtype=np.float64)

        abs_b = np.abs(perpendicular_baselines)
        weights = 1.0 / (abs_b + 10.0)
        weights = weights / np.sum(weights)

        return weights

    def _sequential_unwrap(self, wrapped_phases: List[np.ndarray],
                           baselines: np.ndarray,
                           quality_maps: List[np.ndarray],
                           mask: np.ndarray) -> np.ndarray:
        """
        顺序解缠：从最短基线开始，逐步向长基线扩展

        Args:
            wrapped_phases: 包裹相位列表
            baselines: 垂直基线数组
            quality_maps: 质量图列表
            mask: 有效区域掩膜

        Returns:
            最终解缠相位
        """
        n_ifg = len(wrapped_phases)
        rows, cols = wrapped_phases[0].shape

        sort_idx = np.argsort(np.abs(baselines))
        sorted_baselines = baselines[sort_idx]
        sorted_wrapped = [wrapped_phases[i] for i in sort_idx]
        sorted_quality = [quality_maps[i] for i in sort_idx]

        unwrapped = None
        reference_unwrapped = None

        for i in range(n_ifg):
            current_wrapped = sorted_wrapped[i]
            current_quality = sorted_quality[i]
            current_b = sorted_baselines[i]

            if i == 0:
                unwrapper = quality_guided_region_growing(
                    current_wrapped, current_quality, mask
                )
                reference_unwrapped = unwrapper.copy()
                unwrapped = unwrapper.copy()
            else:
                ratio = current_b / sorted_baselines[0]
                expected_unwrapped = reference_unwrapped * ratio

                expected_wrapped = phase_wrap(expected_unwrapped)
                phase_diff = phase_wrap(current_wrapped - expected_wrapped)

                unwrapper = PhaseUnwrapper(
                    'weighted_least_squares',
                    remove_flat=False,
                    weight_power=3.0
                )
                residual_unwrapped, _ = unwrapper.unwrap(
                    phase_diff, mask, current_quality
                )

                current_unwrapped = expected_unwrapped + residual_unwrapped
                unwrapped = current_unwrapped

        return unwrapped

    def _weighted_average_unwrap(self, wrapped_phases: List[np.ndarray],
                                  baselines: np.ndarray,
                                  quality_maps: List[np.ndarray],
                                  mask: np.ndarray) -> np.ndarray:
        """
        加权平均解缠：各干涉图独立解缠后按质量加权平均

        Args:
            wrapped_phases: 包裹相位列表
            baselines: 垂直基线数组
            quality_maps: 质量图列表
            mask: 有效区域掩膜

        Returns:
            最终解缠相位
        """
        n_ifg = len(wrapped_phases)
        rows, cols = wrapped_phases[0].shape

        baseline_weights = self._baseline_weight(baselines)

        unwrapped_list = []
        weights_list = []

        for i in range(n_ifg):
            unwrapper = PhaseUnwrapper(
                'weighted_least_squares',
                remove_flat=True,
                weight_power=3.0
            )
            unwrapped, info = unwrapper.unwrap(
                wrapped_phases[i], mask, quality_maps[i]
            )

            quality_weight = quality_maps[i]
            combined_weight = quality_weight * baseline_weights[i]

            unwrapped_list.append(unwrapped)
            weights_list.append(combined_weight)

        unwrapped_stack = np.stack(unwrapped_list, axis=0)
        weight_stack = np.stack(weights_list, axis=0)

        reference_phase = unwrapped_stack[0]
        for i in range(1, n_ifg):
            phase_diff = unwrapped_stack[i] - reference_phase
            k = np.round(phase_diff / (2 * np.pi))
            unwrapped_stack[i] -= k * 2 * np.pi

        total_weight = np.sum(weight_stack, axis=0)
        total_weight[total_weight < 1e-10] = 1e-10

        weighted_sum = np.sum(unwrapped_stack * weight_stack, axis=0)
        unwrapped = weighted_sum / total_weight

        unwrapped = np.where(mask, unwrapped, np.nan)

        return unwrapped

    def _quality_best_unwrap(self, wrapped_phases: List[np.ndarray],
                             baselines: np.ndarray,
                             quality_maps: List[np.ndarray],
                             mask: np.ndarray) -> np.ndarray:
        """
        质量最优解缠：为每个像素选择质量最高的解缠结果

        Args:
            wrapped_phases: 包裹相位列表
            baselines: 垂直基线数组
            quality_maps: 质量图列表
            mask: 有效区域掩膜

        Returns:
            最终解缠相位
        """
        n_ifg = len(wrapped_phases)
        rows, cols = wrapped_phases[0].shape

        unwrapped_list = []
        error_list = []

        for i in range(n_ifg):
            unwrapper = PhaseUnwrapper(
                'weighted_least_squares',
                remove_flat=True,
                weight_power=3.0
            )
            unwrapped, info = unwrapper.unwrap(
                wrapped_phases[i], mask, quality_maps[i]
            )

            unwrapped_list.append(unwrapped)
            error_list.append(info['error_estimate'])

        error_stack = np.stack(error_list, axis=0)
        best_idx = np.argmin(error_stack, axis=0)

        unwrapped = np.zeros((rows, cols), dtype=np.float64)
        for i in range(n_ifg):
            idx_mask = best_idx == i
            unwrapped[idx_mask] = unwrapped_list[i][idx_mask]

        reference = unwrapped_list[0]
        for i in range(n_ifg):
            idx_mask = best_idx == i
            if np.any(idx_mask):
                phase_diff = unwrapped[idx_mask] - reference[idx_mask]
                k = np.round(phase_diff / (2 * np.pi))
                unwrapped[idx_mask] -= k * 2 * np.pi

        unwrapped = np.where(mask, unwrapped, np.nan)

        return unwrapped

    def unwrap(self, wrapped_phases: List[np.ndarray],
               perpendicular_baselines: np.ndarray,
               masks: Optional[List[np.ndarray]] = None,
               quality_maps: Optional[List[np.ndarray]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        执行多基线联合相位解缠

        Args:
            wrapped_phases: 包裹相位列表，每个是2D数组
            perpendicular_baselines: 垂直基线数组 (米)
            masks: 有效区域掩膜列表
            quality_maps: 质量图列表

        Returns:
            (联合解缠相位, 结果信息字典)
        """
        n_ifg = len(wrapped_phases)
        if n_ifg < 2:
            raise ValueError("多基线解缠需要至少2个干涉图")

        if len(perpendicular_baselines) != n_ifg:
            raise ValueError("基线数量与干涉图数量不匹配")

        rows, cols = wrapped_phases[0].shape
        for i in range(1, n_ifg):
            if wrapped_phases[i].shape != (rows, cols):
                raise ValueError("所有干涉图必须具有相同的尺寸")

        if masks is None:
            masks = [np.ones((rows, cols), dtype=bool) for _ in range(n_ifg)]
        if quality_maps is None:
            quality_maps = [
                QualityMapGenerator.pseudo_coherence(wp)
                for wp in wrapped_phases
            ]

        combined_mask = masks[0].copy()
        for m in masks[1:]:
            combined_mask = combined_mask & m

        info = {
            'algorithm': 'multi_baseline_unwrap',
            'algorithm_name': '多基线联合解缠',
            'num_interferograms': n_ifg,
            'perpendicular_baselines': perpendicular_baselines.tolist(),
            'combine_method': self.combine_method,
            'use_baseline_weighting': self.use_baseline_weighting,
        }

        try:
            if self.combine_method == 'sequential':
                unwrapped = self._sequential_unwrap(
                    wrapped_phases, perpendicular_baselines, quality_maps, combined_mask
                )
            elif self.combine_method == 'quality_best':
                unwrapped = self._quality_best_unwrap(
                    wrapped_phases, perpendicular_baselines, quality_maps, combined_mask
                )
            else:
                unwrapped = self._weighted_average_unwrap(
                    wrapped_phases, perpendicular_baselines, quality_maps, combined_mask
                )

            reference_wrapped = wrapped_phases[0]
            reference_mask = masks[0]
            reference_quality = quality_maps[0]

            pos_res, neg_res, charge_map = detect_residues(reference_wrapped, reference_mask)
            info['positive_residues'] = pos_res
            info['negative_residues'] = neg_res
            info['charge_map'] = charge_map
            info['num_positive_residues'] = len(pos_res)
            info['num_negative_residues'] = len(neg_res)

            error = estimate_unwrapping_error(unwrapped, reference_wrapped, combined_mask)
            info['error_estimate'] = error
            info['mean_error'] = np.nanmean(error) if not np.all(np.isnan(error)) else np.nan
            info['max_error'] = np.nanmax(error) if not np.all(np.isnan(error)) else np.nan

            baseline_weights = self._baseline_weight(perpendicular_baselines)
            info['baseline_weights'] = baseline_weights.tolist()

            for i in range(n_ifg):
                info[f'ifg_{i}_baseline'] = perpendicular_baselines[i]
                info[f'ifg_{i}_mean_quality'] = np.nanmean(quality_maps[i][masks[i]])

        except Exception as e:
            unwrapper = PhaseUnwrapper('weighted_least_squares', remove_flat=True)
            unwrapped, fallback_info = unwrapper.unwrap(
                wrapped_phases[0], combined_mask, quality_maps[0]
            )
            info.update(fallback_info)
            info['algorithm'] = 'multi_baseline_fallback'
            info['algorithm_name'] = '多基线解缠(降级到单基线)'
            info['fallback_reason'] = str(e)

        return unwrapped, info


# ============================================================================
# 3. 时序InSAR SBAS形变速率反演
# ============================================================================

class SBASInverter:
    """
    小基线子集 (Small Baseline Subset) 时序InSAR形变速率反演

    方法原理:
    1. 构建小基线干涉图网络
    2. 对每个干涉图进行相位解缠
    3. 建立观测方程，通过最小二乘求解各时刻的相位
    4. 从相位时间序列中估计形变速率

    参考: Berardino et al. (2002) IEEE TGRS
    """

    def __init__(self,
                 wavelength: float = 0.056,
                 max_temporal_baseline: Optional[int] = None,
                 max_perpendicular_baseline: Optional[float] = None,
                 ref_pixel: Optional[Tuple[int, int]] = None):
        """
        Args:
            wavelength: 雷达波长 (米)，默认C波段 (Sentinel-1)
            max_temporal_baseline: 最大时间基线 (天)，None表示不限制
            max_perpendicular_baseline: 最大垂直基线 (米)，None表示不限制
            ref_pixel: 参考像素坐标 (row, col)，None表示自动选择
        """
        self.wavelength = wavelength
        self.max_temporal_baseline = max_temporal_baseline
        self.max_perpendicular_baseline = max_perpendicular_baseline
        self.ref_pixel = ref_pixel

        self.ifg_network = []
        self.time_series = None
        self.velocity = None
        self.velocity_std = None

    def build_ifg_network(self, acquisition_dates: np.ndarray,
                          perpendicular_baselines: np.ndarray) -> List[Tuple[int, int]]:
        """
        构建小基线干涉图网络

        Args:
            acquisition_dates: 获取日期，格式为datetime64[D]数组
            perpendicular_baselines: 各图像的垂直基线

        Returns:
            干涉图对列表 [(master_idx, slave_idx), ...]
        """
        n_images = len(acquisition_dates)
        ifg_pairs = []

        for i in range(n_images):
            for j in range(i + 1, n_images):
                temporal_baseline = (acquisition_dates[j] - acquisition_dates[i]).astype(int)

                if self.max_temporal_baseline is not None:
                    if temporal_baseline > self.max_temporal_baseline:
                        continue

                if self.max_perpendicular_baseline is not None:
                    baseline_diff = abs(perpendicular_baselines[j] - perpendicular_baselines[i])
                    if baseline_diff > self.max_perpendicular_baseline:
                        continue

                ifg_pairs.append((i, j))

        self.ifg_network = ifg_pairs

        return ifg_pairs

    def _select_reference_pixel(self, unwrapped_phases: List[np.ndarray],
                                quality_maps: List[np.ndarray],
                                mask: np.ndarray) -> Tuple[int, int]:
        """
        自动选择参考像素 - 选择质量最高且稳定的像素

        Args:
            unwrapped_phases: 解缠相位列表
            quality_maps: 质量图列表
            mask: 有效区域掩膜

        Returns:
            参考像素坐标 (row, col)
        """
        mean_quality = np.mean(np.stack(quality_maps), axis=0)
        phase_std = np.std(np.stack(unwrapped_phases), axis=0)

        score = mean_quality / (phase_std + 0.1)
        score[~mask] = -1

        best_idx = np.unravel_index(np.argmax(score), score.shape)

        return best_idx

    def invert(self, unwrapped_phases: List[np.ndarray],
               acquisition_dates: np.ndarray,
               perpendicular_baselines: np.ndarray,
               masks: Optional[List[np.ndarray]] = None,
               quality_maps: Optional[List[np.ndarray]] = None) -> Dict[str, Any]:
        """
        执行SBAS时序反演

        Args:
            unwrapped_phases: 解缠干涉图相位列表
            acquisition_dates: 获取日期数组 (datetime64[D])
            perpendicular_baselines: 各图像的垂直基线
            masks: 有效区域掩膜列表
            quality_maps: 质量图列表

        Returns:
            反演结果字典
        """
        n_ifg = len(unwrapped_phases)
        n_images = len(acquisition_dates)
        rows, cols = unwrapped_phases[0].shape

        if self.ifg_network is None or len(self.ifg_network) != n_ifg:
            auto_network = self.build_ifg_network(acquisition_dates, perpendicular_baselines)
            if len(auto_network) != n_ifg:
                ifg_pairs = []
                seen = set()
                for i in range(n_images):
                    for j in range(i + 1, n_images):
                        if (i, j) not in seen and len(ifg_pairs) < n_ifg:
                            ifg_pairs.append((i, j))
                            seen.add((i, j))
                self.ifg_network = ifg_pairs[:n_ifg]

        if masks is None:
            masks = [np.ones((rows, cols), dtype=bool) for _ in range(n_ifg)]
        if quality_maps is None:
            quality_maps = [np.ones((rows, cols)) for _ in range(n_ifg)]

        combined_mask = masks[0].copy()
        for m in masks[1:]:
            combined_mask = combined_mask & m

        if self.ref_pixel is None:
            self.ref_pixel = self._select_reference_pixel(
                unwrapped_phases, quality_maps, combined_mask
            )

        ref_row, ref_col = self.ref_pixel

        G = np.zeros((n_ifg, n_images - 1), dtype=np.float64)
        for k, (i, j) in enumerate(self.ifg_network):
            if i > 0:
                G[k, i - 1] = -1
            if j > 0:
                G[k, j - 1] = 1

        self.time_series = np.zeros((n_images, rows, cols), dtype=np.float64)
        self.time_series[0, :, :] = 0

        self.velocity = np.zeros((rows, cols), dtype=np.float64)
        self.velocity_std = np.zeros((rows, cols), dtype=np.float64)

        time_days = (acquisition_dates - acquisition_dates[0]).astype(float)

        valid_pixels = np.where(combined_mask)

        results = {
            'algorithm': 'sbas_inversion',
            'algorithm_name': 'SBAS时序InSAR形变速率反演',
            'n_images': n_images,
            'n_ifgs': n_ifg,
            'wavelength': self.wavelength,
            'ref_pixel': (ref_row, ref_col),
            'ifg_network': self.ifg_network,
            'acquisition_dates': acquisition_dates.tolist(),
            'perpendicular_baselines': perpendicular_baselines.tolist(),
            'time_days': time_days.tolist(),
        }

        try:
            for idx in range(len(valid_pixels[0])):
                row, col = valid_pixels[0][idx], valid_pixels[1][idx]

                d = np.zeros(n_ifg, dtype=np.float64)
                weights = np.ones(n_ifg, dtype=np.float64)

                for k in range(n_ifg):
                    ref_phase = unwrapped_phases[k][ref_row, ref_col]
                    d[k] = unwrapped_phases[k][row, col] - ref_phase
                    weights[k] = quality_maps[k][row, col]

                w_sqrt = np.sqrt(weights)
                Gw = G * w_sqrt[:, np.newaxis]
                dw = d * w_sqrt
                GtWG = Gw.T @ Gw

                try:
                    x = spsolve(GtWG, Gw.T @ dw)
                except Exception:
                    x, _, _, _ = np.linalg.lstsq(Gw, dw, rcond=None)

                self.time_series[1:, row, col] = x

                valid_ts = ~np.isnan(self.time_series[:, row, col])
                if np.sum(valid_ts) >= 2:
                    A = np.column_stack([
                        np.ones(n_images),
                        time_days
                    ])
                    A = A[valid_ts]
                    y = self.time_series[:, row, col][valid_ts]

                    coeffs, cov = np.polyfit(
                        time_days[valid_ts], y, 1, cov=True
                    )

                    phase_velocity = coeffs[0]
                    self.velocity[row, col] = (phase_velocity * self.wavelength) / (4 * np.pi) * 1000
                    self.velocity_std[row, col] = np.sqrt(cov[0, 0]) * self.wavelength / (4 * np.pi) * 1000

            self.velocity = np.where(combined_mask, self.velocity, np.nan)
            self.velocity_std = np.where(combined_mask, self.velocity_std, np.nan)
            self.time_series = np.where(combined_mask, self.time_series, np.nan)

            results['time_series'] = self.time_series
            results['velocity'] = self.velocity
            results['velocity_std'] = self.velocity_std
            results['velocity_unit'] = 'mm/year'

            valid_vel = self.velocity[combined_mask]
            if len(valid_vel) > 0:
                results['mean_velocity'] = np.nanmean(valid_vel)
                results['std_velocity'] = np.nanstd(valid_vel)
                results['min_velocity'] = np.nanmin(valid_vel)
                results['max_velocity'] = np.nanmax(valid_vel)

            results['inversion_success'] = True

        except Exception as e:
            results['inversion_success'] = False
            results['error_message'] = str(e)
            raise

        return results


def generate_sbas_test_data(n_images: int = 8,
                            size: int = 100) -> Dict[str, Any]:
    """
    生成SBAS测试数据

    Args:
        n_images: 图像数量
        size: 图像尺寸

    Returns:
        测试数据字典
    """
    import datetime

    start_date = np.datetime64('2023-01-01')
    dates = start_date + np.arange(n_images) * np.timedelta64(12, 'D')

    baselines = np.random.normal(0, 50, n_images)

    x = np.linspace(-3, 3, size)
    y = np.linspace(-3, 3, size)
    X, Y = np.meshgrid(x, y)

    true_velocity = -10 * np.exp(-(X ** 2 + Y ** 2) / 2)

    time_days = (dates - dates[0]).astype(float)
    deformation = np.outer(time_days, true_velocity.flatten()).reshape(n_images, size, size)
    deformation = deformation * (4 * np.pi) / 0.056 / 1000

    topography = 5 * np.sin(X) * np.cos(Y)

    unwrapped_ifgs = []
    wrapped_ifgs = []
    masks = []
    quality_maps = []
    ifg_pairs = []

    for i in range(n_images):
        for j in range(i + 1, n_images):
            temporal_baseline = (dates[j] - dates[i]).astype(int)
            if temporal_baseline > 60:
                continue

            baseline_diff = baselines[j] - baselines[i]
            if abs(baseline_diff) > 100:
                continue

            phase_diff = deformation[j] - deformation[i]
            topo_phase = baseline_diff * 0.01 * topography
            total_phase = phase_diff + topo_phase

            noise = np.random.normal(0, 0.3, total_phase.shape)
            unwrapped = total_phase + noise

            wrapped = phase_wrap(unwrapped)

            unwrapped_ifgs.append(unwrapped)
            wrapped_ifgs.append(wrapped)
            masks.append(np.ones_like(wrapped, dtype=bool))

            quality = np.exp(-noise ** 2 / 2)
            quality = (quality - quality.min()) / (quality.max() - quality.min() + 1e-10)
            quality_maps.append(quality)

            ifg_pairs.append((i, j))

    return {
        'wrapped_ifgs': wrapped_ifgs,
        'unwrapped_ifgs': unwrapped_ifgs,
        'masks': masks,
        'quality_maps': quality_maps,
        'ifg_pairs': ifg_pairs,
        'acquisition_dates': dates,
        'perpendicular_baselines': baselines,
        'true_velocity': true_velocity,
        'deformation': deformation,
    }
