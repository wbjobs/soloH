"""
相位解缠算法模块
包含: 分支切割法、最小二乘法(无权重/加权)
修复: 低质量区域错误传播、权重归一化错误、平地相位去除
"""

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.linalg import spsolve
from scipy.ndimage import label
from typing import Tuple, Optional, Dict, Any
from queue import Queue, PriorityQueue
import warnings

warnings.filterwarnings('ignore')


def phase_wrap(phi: np.ndarray) -> np.ndarray:
    """
    将相位包裹到[-π, π]区间

    Args:
        phi: 输入相位

    Returns:
        包裹后的相位
    """
    return np.arctan2(np.sin(phi), np.cos(phi))


def remove_flat_phase(wrapped_phase: np.ndarray,
                      mask: Optional[np.ndarray] = None,
                      quality_map: Optional[np.ndarray] = None,
                      degree: int = 1,
                      n_iter: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """
    去除平地相位 (线性/多项式相位趋势)
    使用迭代加权最小二乘 (IRLS) 和质量图引导的稳健拟合

    Args:
        wrapped_phase: 包裹相位 [-π, π]
        mask: 有效区域掩膜
        quality_map: 质量图 [0, 1]，用于选择高可信像素
        degree: 多项式拟合阶数 (1=线性, 2=二次)
        n_iter: 迭代次数 (用于IRLS)

    Returns:
        (去除平地相位后的包裹相位, 估计的平地相位)
    """
    rows, cols = wrapped_phase.shape

    if mask is None:
        mask = np.ones_like(wrapped_phase, dtype=bool)
    else:
        mask = mask.astype(bool)

    y, x = np.mgrid[0:rows, 0:cols]

    fit_mask = mask.copy()
    if quality_map is not None:
        quality_threshold = np.percentile(quality_map[mask], 30)
        fit_mask = fit_mask & (quality_map >= quality_threshold)

    y_flat = y[fit_mask].flatten()
    x_flat = x[fit_mask].flatten()
    phi_flat = wrapped_phase[fit_mask].flatten()

    if len(phi_flat) < (degree + 1) * (degree + 2) // 2:
        return wrapped_phase, np.zeros_like(wrapped_phase)

    cos_phi = np.cos(phi_flat)
    sin_phi = np.sin(phi_flat)

    if degree == 1:
        A = np.column_stack([np.ones_like(x_flat), x_flat, y_flat])
    elif degree == 2:
        A = np.column_stack([
            np.ones_like(x_flat), x_flat, y_flat,
            x_flat ** 2, x_flat * y_flat, y_flat ** 2
        ])
    else:
        raise ValueError(f"不支持的多项式阶数: {degree}")

    weights = np.ones_like(x_flat, dtype=np.float64)
    if quality_map is not None:
        weights = quality_map[fit_mask].flatten()

    try:
        coeffs_cos = None
        coeffs_sin = None

        for iteration in range(n_iter):
            w_sqrt = np.sqrt(weights)
            Aw = A * w_sqrt[:, np.newaxis]
            cos_phi_w = cos_phi * w_sqrt
            sin_phi_w = sin_phi * w_sqrt

            try:
                AtA = Aw.T @ Aw
                coeffs_cos = np.linalg.solve(AtA, Aw.T @ cos_phi_w)
                coeffs_sin = np.linalg.solve(AtA, Aw.T @ sin_phi_w)

                predicted_cos = A @ coeffs_cos
                predicted_sin = A @ coeffs_sin

                residuals_cos = cos_phi - predicted_cos
                residuals_sin = sin_phi - predicted_sin
                residuals = np.sqrt(residuals_cos ** 2 + residuals_sin ** 2)

                mad = np.median(np.abs(residuals - np.median(residuals)))
                if mad > 1e-10:
                    robust_std = 1.4826 * mad
                    weights = np.exp(-(residuals ** 2) / (2 * robust_std ** 2))
                    weights = np.clip(weights, 0.01, 1.0)
                else:
                    break

            except np.linalg.LinAlgError:
                break

        if coeffs_cos is None or coeffs_sin is None:
            coeffs_cos, _, _, _ = np.linalg.lstsq(A, cos_phi, rcond=None)
            coeffs_sin, _, _, _ = np.linalg.lstsq(A, sin_phi, rcond=None)

        if degree == 1:
            A_full = np.column_stack([np.ones(rows * cols), x.flatten(), y.flatten()])
        else:
            A_full = np.column_stack([
                np.ones(rows * cols), x.flatten(), y.flatten(),
                x.flatten() ** 2, x.flatten() * y.flatten(), y.flatten() ** 2
            ])

        flat_cos = A_full @ coeffs_cos
        flat_sin = A_full @ coeffs_sin
        flat_phase = np.arctan2(flat_sin, flat_cos).reshape(rows, cols)

    except np.linalg.LinAlgError:
        return wrapped_phase, np.zeros_like(wrapped_phase)

    phase_diff = phase_wrap(wrapped_phase - flat_phase)

    return phase_diff, flat_phase


def quality_weight_map(quality: np.ndarray,
                       mask: Optional[np.ndarray] = None,
                       power: float = 3.0,
                       min_weight: float = 0.01) -> np.ndarray:
    """
    非线性权重映射 - 修复权重归一化错误
    使用幂函数扩大高质量和低质量区域的权重差异

    Args:
        quality: 质量图 [0, 1]
        mask: 有效区域掩膜
        power: 幂指数 (越大权重差异越明显，推荐2-4)
        min_weight: 最小权重 (防止低质量区域权重为0)

    Returns:
        非线性权重图
    """
    if mask is None:
        mask = np.ones_like(quality, dtype=bool)
    else:
        mask = mask.astype(bool)

    quality_valid = np.where(mask, quality, 0)

    q_min = np.min(quality_valid[mask])
    q_max = np.max(quality_valid[mask])

    if q_max - q_min < 1e-10:
        weights = np.ones_like(quality)
    else:
        quality_norm = (quality_valid - q_min) / (q_max - q_min)
        quality_norm = np.clip(quality_norm, 0, 1)

        weights = np.where(mask, quality_norm ** power + min_weight, 0)

    return weights


def quality_guided_region_growing(wrapped_phase: np.ndarray,
                                  quality_map: np.ndarray,
                                  mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    质量引导的区域增长相位解缠 - 防止低质量区域错误传播
    从最高质量像素开始，按质量从高到低逐步扩展解缠区域

    Args:
        wrapped_phase: 包裹相位 [-π, π]
        quality_map: 质量图 [0, 1]
        mask: 有效区域掩膜

    Returns:
        解缠相位
    """
    rows, cols = wrapped_phase.shape

    if mask is None:
        mask = np.ones_like(wrapped_phase, dtype=bool)
    else:
        mask = mask.astype(bool)

    unwrapped = np.zeros_like(wrapped_phase, dtype=np.float64)
    unwrapped[:] = np.nan

    processed = np.zeros_like(mask, dtype=bool)

    border_queue = PriorityQueue()

    valid_y, valid_x = np.where(mask)
    if len(valid_y) == 0:
        return unwrapped

    start_idx = np.argmax(quality_map[valid_y, valid_x])
    start_y, start_x = valid_y[start_idx], valid_x[start_idx]

    unwrapped[start_y, start_x] = wrapped_phase[start_y, start_x]
    processed[start_y, start_x] = True

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for dy, dx in directions:
        ny, nx = start_y + dy, start_x + dx
        if (0 <= ny < rows and 0 <= nx < cols and
                mask[ny, nx] and not processed[ny, nx]):
            quality = quality_map[ny, nx]
            border_queue.put((-quality, (ny, nx, start_y, start_x)))

    while not border_queue.empty():
        neg_quality, (y, x, from_y, from_x) = border_queue.get()

        if processed[y, x]:
            continue

        phase_diff = phase_wrap(wrapped_phase[y, x] - wrapped_phase[from_y, from_x])
        unwrapped[y, x] = unwrapped[from_y, from_x] + phase_diff
        processed[y, x] = True

        for dy, dx in directions:
            ny, nx = y + dy, x + dx
            if (0 <= ny < rows and 0 <= nx < cols and
                    mask[ny, nx] and not processed[ny, nx]):
                quality = quality_map[ny, nx]
                border_queue.put((-quality, (ny, nx, y, x)))

    for i in range(rows):
        for j in range(cols):
            if mask[i, j] and not processed[i, j]:
                for dy, dx in directions:
                    ny, nx = i + dy, j + dx
                    if (0 <= ny < rows and 0 <= nx < cols and processed[ny, nx]):
                        phase_diff = phase_wrap(wrapped_phase[i, j] - wrapped_phase[ny, nx])
                        unwrapped[i, j] = unwrapped[ny, nx] + phase_diff
                        processed[i, j] = True
                        break

    return unwrapped


def detect_residues(wrapped_phase: np.ndarray, mask: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    检测残差点

    Args:
        wrapped_phase: 包裹相位
        mask: 有效区域掩膜 (1表示有效, 0表示无效)

    Returns:
        (正残差点位置, 负残差点位置, 残差电荷图)
    """
    rows, cols = wrapped_phase.shape

    if mask is None:
        mask = np.ones_like(wrapped_phase, dtype=bool)
    else:
        mask = mask.astype(bool)

    charge_map = np.zeros_like(wrapped_phase, dtype=np.int8)

    for i in range(rows - 1):
        for j in range(cols - 1):
            if not (mask[i, j] and mask[i + 1, j] and mask[i, j + 1] and mask[i + 1, j + 1]):
                continue

            phi1 = wrapped_phase[i, j]
            phi2 = wrapped_phase[i, j + 1]
            phi3 = wrapped_phase[i + 1, j + 1]
            phi4 = wrapped_phase[i + 1, j]

            d1 = phase_wrap(phi2 - phi1)
            d2 = phase_wrap(phi3 - phi2)
            d3 = phase_wrap(phi4 - phi3)
            d4 = phase_wrap(phi1 - phi4)

            residue = d1 + d2 + d3 + d4

            if abs(residue) > 0.1:
                charge = int(round(residue / (2 * np.pi)))
                charge_map[i, j] = charge

    pos_residues = np.column_stack(np.where(charge_map > 0))
    neg_residues = np.column_stack(np.where(charge_map < 0))

    return pos_residues, neg_residues, charge_map


class BranchCutUnwrapper:
    """
    分支切割相位解缠算法
    """

    def __init__(self, max_branch_length: int = 100):
        self.max_branch_length = max_branch_length

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        执行分支切割相位解缠

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            mask: 有效区域掩膜
            quality_map: 质量图 (可选，用于引导分支连接)

        Returns:
            (解缠相位, 分支切割掩膜)
        """
        rows, cols = wrapped_phase.shape

        if mask is None:
            mask = np.ones_like(wrapped_phase, dtype=bool)
        else:
            mask = mask.astype(bool)

        wrapped_phase = np.where(mask, wrapped_phase, 0)

        pos_residues, neg_residues, charge_map = detect_residues(wrapped_phase, mask)

        branch_cut = np.zeros_like(wrapped_phase, dtype=bool)

        connected = np.zeros(len(pos_residues) + len(neg_residues), dtype=bool)
        all_residues = np.vstack([pos_residues, neg_residues])
        charges = np.hstack([np.ones(len(pos_residues)), -np.ones(len(neg_residues))])

        for idx in range(len(all_residues)):
            if connected[idx]:
                continue

            start_pos = all_residues[idx]
            target_charge = -charges[idx]

            path = self._find_branch(start_pos, target_charge, all_residues,
                                     charges, connected, mask, quality_map, rows, cols)

            if path is not None:
                for pos in path:
                    if 0 <= pos[0] < rows and 0 <= pos[1] < cols:
                        branch_cut[pos[0], pos[1]] = True

        unwrapped = self._flood_fill_unwrap(wrapped_phase, mask, branch_cut)

        return unwrapped, branch_cut

    def _find_branch(self, start_pos: np.ndarray, target_charge: int,
                     all_residues: np.ndarray, charges: np.ndarray,
                     connected: np.ndarray, mask: np.ndarray,
                     quality_map: Optional[np.ndarray],
                     rows: int, cols: int) -> Optional[list]:
        """
        使用BFS寻找连接残差点的分支路径
        """
        visited = set()
        queue = Queue()
        queue.put((tuple(start_pos), [tuple(start_pos)]))
        visited.add(tuple(start_pos))

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while not queue.empty() and len(visited) < self.max_branch_length * 10:
            current_pos, path = queue.get()

            for idx, res in enumerate(all_residues):
                if tuple(res) == current_pos and charges[idx] == target_charge and not connected[idx]:
                    start_idx = np.where((all_residues == start_pos).all(axis=1))[0][0]
                    connected[start_idx] = True
                    connected[idx] = True
                    return path

            for dy, dx in directions:
                ny, nx = current_pos[0] + dy, current_pos[1] + dx
                new_pos = (ny, nx)

                if (0 <= ny < rows and 0 <= nx < cols and
                        new_pos not in visited and mask[ny, nx]):
                    visited.add(new_pos)
                    new_path = path + [new_pos]
                    if quality_map is not None:
                        priority = quality_map[ny, nx]
                        queue.put((new_pos, new_path))
                    else:
                        queue.put((new_pos, new_path))

        return None

    def _flood_fill_unwrap(self, wrapped_phase: np.ndarray,
                           mask: np.ndarray,
                           branch_cut: np.ndarray) -> np.ndarray:
        """
        使用洪水填充法进行相位解缠，避开分支切割
        """
        rows, cols = wrapped_phase.shape
        unwrapped = np.zeros_like(wrapped_phase)
        unwrapped[:] = np.nan

        start_y, start_x = 0, 0
        for i in range(rows):
            for j in range(cols):
                if mask[i, j] and not branch_cut[i, j]:
                    start_y, start_x = i, j
                    break
            else:
                continue
            break

        unwrapped[start_y, start_x] = wrapped_phase[start_y, start_x]

        visited = np.zeros_like(mask, dtype=bool)
        visited[start_y, start_x] = True

        queue = Queue()
        queue.put((start_y, start_x))

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        while not queue.empty():
            y, x = queue.get()

            for dy, dx in directions:
                ny, nx = y + dy, x + dx

                if (0 <= ny < rows and 0 <= nx < cols and
                        mask[ny, nx] and not visited[ny, nx] and
                        not branch_cut[ny, nx]):

                    phase_diff = phase_wrap(wrapped_phase[ny, nx] - wrapped_phase[y, x])
                    unwrapped[ny, nx] = unwrapped[y, x] + phase_diff
                    visited[ny, nx] = True
                    queue.put((ny, nx))

        for i in range(rows):
            for j in range(cols):
                if mask[i, j] and not visited[i, j]:
                    for dy, dx in directions:
                        ny, nx = i + dy, j + dx
                        if (0 <= ny < rows and 0 <= nx < cols and
                                visited[ny, nx] and not branch_cut[i, j]):
                            phase_diff = phase_wrap(wrapped_phase[i, j] - wrapped_phase[ny, nx])
                            unwrapped[i, j] = unwrapped[ny, nx] + phase_diff
                            visited[i, j] = True
                            break

        return unwrapped


class LeastSquaresUnwrapper:
    """
    最小二乘相位解缠算法 (支持无权重和加权)
    修复: 1. 平地相位去除 2. 非线性权重映射 3. 质量引导区域增长防止错误传播
    """

    def __init__(self, use_weight: bool = False,
                 remove_flat: bool = True,
                 use_region_growing: bool = False,
                 weight_power: float = 3.0,
                 flat_phase_degree: int = 1):
        """
        Args:
            use_weight: 是否使用权重
            remove_flat: 是否去除平地相位
            use_region_growing: 是否使用质量引导区域增长(防止错误传播)
            weight_power: 权重幂指数 (越大权重差异越明显)
            flat_phase_degree: 平地相位拟合阶数 (1=线性, 2=二次)
        """
        self.use_weight = use_weight
        self.remove_flat = remove_flat
        self.use_region_growing = use_region_growing
        self.weight_power = weight_power
        self.flat_phase_degree = flat_phase_degree
        self.estimated_flat_phase = None

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None) -> np.ndarray:
        """
        执行最小二乘相位解缠

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            mask: 有效区域掩膜
            quality_map: 质量图 (用于加权最小二乘)

        Returns:
            解缠相位
        """
        rows, cols = wrapped_phase.shape

        if mask is None:
            mask = np.ones_like(wrapped_phase, dtype=bool)
        else:
            mask = mask.astype(bool)

        if self.remove_flat:
            wrapped_phase, flat_phase = remove_flat_phase(
                wrapped_phase, mask, quality_map=quality_map,
                degree=self.flat_phase_degree
            )
            self.estimated_flat_phase = flat_phase
        else:
            self.estimated_flat_phase = None

        if self.use_region_growing and quality_map is not None:
            unwrapped = quality_guided_region_growing(
                wrapped_phase, quality_map, mask
            )
        else:
            wrapped_data = np.where(mask, wrapped_phase, 0)

            dx = phase_wrap(np.diff(wrapped_data, axis=1))
            dy = phase_wrap(np.diff(wrapped_data, axis=0))

            if self.use_weight and quality_map is not None:
                weights = quality_weight_map(
                    quality_map, mask,
                    power=self.weight_power,
                    min_weight=0.01
                )

                wx = np.zeros_like(dx)
                wy = np.zeros_like(dy)

                for i in range(rows):
                    for j in range(cols - 1):
                        if mask[i, j] and mask[i, j + 1]:
                            wx[i, j] = min(weights[i, j], weights[i, j + 1])

                for i in range(rows - 1):
                    for j in range(cols):
                        if mask[i, j] and mask[i + 1, j]:
                            wy[i, j] = min(weights[i, j], weights[i + 1, j])

                unwrapped = self._solve_weighted_laplacian(dx, dy, wx, wy, mask, rows, cols)
            else:
                unwrapped = self._solve_unweighted_laplacian(dx, dy, mask, rows, cols)

        unwrapped = np.where(mask, unwrapped, np.nan)

        return unwrapped

    def _solve_unweighted_laplacian(self, dx: np.ndarray, dy: np.ndarray,
                                    mask: np.ndarray, rows: int, cols: int) -> np.ndarray:
        """
        求解无权重的离散拉普拉斯方程
        使用傅里叶变换方法高效求解
        """
        laplacian = np.zeros((rows, cols), dtype=np.float64)

        laplacian[:, 1:-1] += dx[:, 1:] - dx[:, :-1]
        laplacian[1:-1, :] += dy[1:, :] - dy[:-1, :]

        laplacian[:, 0] += dx[:, 0]
        laplacian[:, -1] -= dx[:, -1]
        laplacian[0, :] += dy[0, :]
        laplacian[-1, :] -= dy[-1, :]

        u = np.zeros_like(laplacian)

        valid_mask = mask.astype(float)
        n_iter = 200

        for _ in range(n_iter):
            u_new = u.copy()

            u_new[1:-1, 1:-1] = (u[2:, 1:-1] + u[:-2, 1:-1] +
                                 u[1:-1, 2:] + u[1:-1, :-2] -
                                 laplacian[1:-1, 1:-1]) / 4.0

            u_new[0, 1:-1] = (u[1, 1:-1] + u[0, 2:] + u[0, :-2] - laplacian[0, 1:-1]) / 3.0
            u_new[-1, 1:-1] = (u[-2, 1:-1] + u[-1, 2:] + u[-1, :-2] - laplacian[-1, 1:-1]) / 3.0
            u_new[1:-1, 0] = (u[2:, 0] + u[:-2, 0] + u[1:-1, 1] - laplacian[1:-1, 0]) / 3.0
            u_new[1:-1, -1] = (u[2:, -1] + u[:-2, -1] + u[1:-1, -2] - laplacian[1:-1, -1]) / 3.0

            u_new[0, 0] = (u[1, 0] + u[0, 1] - laplacian[0, 0]) / 2.0
            u_new[0, -1] = (u[1, -1] + u[0, -2] - laplacian[0, -1]) / 2.0
            u_new[-1, 0] = (u[-2, 0] + u[-1, 1] - laplacian[-1, 0]) / 2.0
            u_new[-1, -1] = (u[-2, -1] + u[-1, -2] - laplacian[-1, -1]) / 2.0

            u = u_new * valid_mask + u * (1 - valid_mask)

        return u

    def _solve_weighted_laplacian(self, dx: np.ndarray, dy: np.ndarray,
                                  wx: np.ndarray, wy: np.ndarray,
                                  mask: np.ndarray, rows: int, cols: int) -> np.ndarray:
        """
        求解加权的离散拉普拉斯方程
        使用迭代法求解稀疏线性方程组
        """
        n_pixels = rows * cols
        indices = np.arange(n_pixels).reshape(rows, cols)

        row = []
        col = []
        data = []
        b = np.zeros(n_pixels)

        for i in range(rows):
            for j in range(cols):
                if not mask[i, j]:
                    continue

                idx = indices[i, j]
                coeff_sum = 0.0

                if j > 0 and mask[i, j - 1]:
                    w = wx[i, j - 1]
                    if w > 0:
                        row.append(idx)
                        col.append(indices[i, j - 1])
                        data.append(-w)
                        coeff_sum += w
                        b[idx] -= w * dx[i, j - 1]

                if j < cols - 1 and mask[i, j + 1]:
                    w = wx[i, j]
                    if w > 0:
                        row.append(idx)
                        col.append(indices[i, j + 1])
                        data.append(-w)
                        coeff_sum += w
                        b[idx] += w * dx[i, j]

                if i > 0 and mask[i - 1, j]:
                    w = wy[i - 1, j]
                    if w > 0:
                        row.append(idx)
                        col.append(indices[i - 1, j])
                        data.append(-w)
                        coeff_sum += w
                        b[idx] -= w * dy[i - 1, j]

                if i < rows - 1 and mask[i + 1, j]:
                    w = wy[i, j]
                    if w > 0:
                        row.append(idx)
                        col.append(indices[i + 1, j])
                        data.append(-w)
                        coeff_sum += w
                        b[idx] += w * dy[i, j]

                if coeff_sum > 0:
                    row.append(idx)
                    col.append(idx)
                    data.append(coeff_sum)

        A = sparse.csr_matrix((data, (row, col)), shape=(n_pixels, n_pixels))

        solution = spsolve(A, b)

        unwrapped = solution.reshape(rows, cols)
        unwrapped = np.where(mask, unwrapped, np.nan)

        return unwrapped


def estimate_unwrapping_error(unwrapped_phase: np.ndarray,
                              wrapped_phase: np.ndarray,
                              mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    估计解缠误差
    通过比较重新包裹的解缠相位与原始包裹相位

    Args:
        unwrapped_phase: 解缠相位
        wrapped_phase: 原始包裹相位
        mask: 有效区域掩膜

    Returns:
        误差估计图
    """
    if mask is None:
        mask = np.ones_like(unwrapped_phase, dtype=bool)
    else:
        mask = mask.astype(bool)

    rewrapped = phase_wrap(unwrapped_phase)
    error = np.abs(rewrapped - wrapped_phase)
    error = np.where(error > np.pi, 2 * np.pi - error, error)
    error = np.where(mask, error, np.nan)

    return error


class PhaseUnwrapper:
    """
    统一的相位解缠接口
    """

    ALGORITHMS = {
        'branch_cut': '分支切割法',
        'least_squares': '最小二乘法(无权重)',
        'weighted_least_squares': '最小二乘法(加权)',
    }

    def __init__(self, algorithm: str = 'least_squares', **kwargs):
        self.algorithm = algorithm
        self.kwargs = kwargs

        if algorithm == 'branch_cut':
            self.unwrapper = BranchCutUnwrapper(**kwargs)
        elif algorithm == 'least_squares':
            self.unwrapper = LeastSquaresUnwrapper(use_weight=False, **kwargs)
        elif algorithm == 'weighted_least_squares':
            self.unwrapper = LeastSquaresUnwrapper(use_weight=True, **kwargs)
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

    def unwrap(self, wrapped_phase: np.ndarray,
               mask: Optional[np.ndarray] = None,
               quality_map: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        执行相位解缠

        Args:
            wrapped_phase: 包裹相位 [-π, π]
            mask: 有效区域掩膜
            quality_map: 质量图

        Returns:
            (解缠相位, 结果信息字典)
        """
        info = {
            'algorithm': self.algorithm,
            'algorithm_name': self.ALGORITHMS[self.algorithm],
        }

        if self.algorithm == 'branch_cut':
            unwrapped, branch_cut = self.unwrapper.unwrap(wrapped_phase, mask, quality_map)
            info['branch_cut'] = branch_cut
        else:
            unwrapped = self.unwrapper.unwrap(wrapped_phase, mask, quality_map)
            if hasattr(self.unwrapper, 'estimated_flat_phase') and self.unwrapper.estimated_flat_phase is not None:
                info['flat_phase_removed'] = True
                info['estimated_flat_phase'] = self.unwrapper.estimated_flat_phase
            else:
                info['flat_phase_removed'] = False

        pos_res, neg_res, charge_map = detect_residues(wrapped_phase, mask)
        info['positive_residues'] = pos_res
        info['negative_residues'] = neg_res
        info['charge_map'] = charge_map
        info['num_positive_residues'] = len(pos_res)
        info['num_negative_residues'] = len(neg_res)

        error = estimate_unwrapping_error(unwrapped, wrapped_phase, mask)
        info['error_estimate'] = error

        valid_mask = ~np.isnan(unwrapped)
        if valid_mask.any():
            info['mean_error'] = np.nanmean(error)
            info['max_error'] = np.nanmax(error)
        else:
            info['mean_error'] = np.nan
            info['max_error'] = np.nan

        return unwrapped, info
