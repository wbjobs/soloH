import numpy as np
from scipy.optimize import curve_fit
from typing import Dict, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


class AllanVarianceAnalyzer:
    """
    Allan方差分析器
    用于分析光纤陀螺的噪声特性，计算5种典型噪声系数
    """

    def __init__(self, sample_rate: float = 100.0):
        """
        初始化Allan方差分析器

        Args:
            sample_rate: 采样频率 (Hz)
        """
        self.sample_rate = sample_rate
        self.sample_interval = 1.0 / sample_rate

    def compute_allan_variance(self, rate_data: np.ndarray,
                               tau_min: Optional[int] = None,
                               tau_max: Optional[int] = None,
                               tau_points: int = 100,
                               overlapping: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算Allan方差（修复长相关时间估计偏差）

        Args:
            rate_data: 角速率数据 (rad/s 或 deg/h)
            tau_min: 最小聚类因子（采样点数），默认1
            tau_max: 最大聚类因子，默认数据长度的1/10
            tau_points: 聚类因子数量（对数分布）
            overlapping: 是否使用重叠窗口（推荐，可提高长τ估计精度）

        Returns:
            (tau_array, allan_var_array): 时间常数数组和对应的Allan方差数组
        """
        n_samples = len(rate_data)

        if tau_min is None:
            tau_min = 1
        if tau_max is None:
            if overlapping:
                tau_max = min(int(n_samples / 3), int(n_samples / 2))
            else:
                tau_max = min(int(n_samples / 10), int(n_samples / 2))

        tau_list = np.unique(np.logspace(np.log10(tau_min), np.log10(tau_max),
                                         tau_points).astype(int))
        tau_list = tau_list[tau_list >= 1]
        tau_list = tau_list[tau_list <= n_samples // 2]

        allan_vars = []
        valid_taus = []

        rate_data = np.asarray(rate_data, dtype=np.float64)

        if overlapping:
            cumsum = np.cumsum(np.concatenate(([0], rate_data)))

            for tau in tau_list:
                if tau >= n_samples - 1:
                    continue

                max_k = n_samples - 2 * tau
                if max_k < 1:
                    continue

                k_indices = np.arange(max_k + 1)
                theta_k_tau = cumsum[k_indices + tau] - cumsum[k_indices]
                theta_k_2tau = cumsum[k_indices + 2 * tau] - cumsum[k_indices + tau]

                diffs = (theta_k_2tau - theta_k_tau) / tau

                allan_var = 0.5 * np.mean(diffs ** 2)
                allan_vars.append(allan_var)
                valid_taus.append(tau)
        else:
            for tau in tau_list:
                if tau >= n_samples:
                    continue

                n_clusters = n_samples // tau
                if n_clusters < 2:
                    continue

                clusters = rate_data[:n_clusters * tau].reshape(n_clusters, tau)
                cluster_means = np.mean(clusters, axis=1)

                if len(cluster_means) >= 2:
                    allan_var = 0.5 * np.mean(np.diff(cluster_means) ** 2)
                    allan_vars.append(allan_var)
                    valid_taus.append(tau)

        tau_array = np.array(valid_taus) * self.sample_interval
        allan_var_array = np.array(allan_vars)
        allan_std_array = np.sqrt(allan_var_array)

        return tau_array, allan_std_array

    def _noise_model(self, tau: np.ndarray, Q: float, N: float, B: float, K: float, R: float) -> np.ndarray:
        """
        Allan方差噪声模型
        sigma(tau)^2 = (Q/tau)^2 * 3 + (N/sqrt(tau))^2 * 2 + (B*0.6648)^2 + (K*sqrt(tau))^2 * 2/3 + (R*tau)^2 / 2

        Args:
            tau: 时间常数数组
            Q: 量化噪声系数
            N: 角度随机游走系数
            B: 零偏不稳定性系数
            K: 速率随机游走系数
            R: 速率斜坡系数

        Returns:
            Allan标准差 (sigma)
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            term_q = np.where(tau > 0, (Q / tau) ** 2 * 3, 0)
            term_n = np.where(tau > 0, (N / np.sqrt(tau)) ** 2, 0)
            term_b = (B * 0.6648) ** 2
            term_k = (K * np.sqrt(tau)) ** 2 * (2.0 / 3.0)
            term_r = (R * tau) ** 2 * 0.5

            sigma_squared = term_q + term_n + term_b + term_k + term_r
            sigma_squared = np.maximum(sigma_squared, 1e-20)

        return np.sqrt(sigma_squared)

    def _linear_regions(self, tau: np.ndarray, allan_std: np.ndarray) -> Dict[str, float]:
        """
        通过不同斜率的线性区域估计噪声系数初值

        Args:
            tau: 时间常数数组
            allan_std: Allan标准差数组

        Returns:
            各噪声系数的估计值字典
        """
        log_tau = np.log10(tau)
        log_sigma = np.log10(allan_std)

        results = {}

        if len(tau) < 5:
            return {
                'Q': 1e-6, 'N': 1e-4, 'B': 1e-5,
                'K': 1e-7, 'R': 1e-8
            }

        try:
            idx_q = np.where(tau < tau[int(len(tau) * 0.1)] + 1e-10)[0]
            if len(idx_q) >= 2:
                coeff_q = np.polyfit(log_tau[idx_q], log_sigma[idx_q], 1)
                intercept_q = coeff_q[1]
                Q_est = 10 ** intercept_q / np.sqrt(3)
            else:
                Q_est = 1e-6
        except:
            Q_est = 1e-6

        try:
            n_points = len(tau)
            idx_n = np.arange(max(0, int(n_points * 0.05)), min(n_points, int(n_points * 0.25)))
            if len(idx_n) >= 2:
                coeff_n = np.polyfit(log_tau[idx_n], log_sigma[idx_n], 1)
                intercept_n = coeff_n[1] - 0.5 * np.log10(3)
                N_est = 10 ** intercept_n
            else:
                N_est = 1e-4
        except:
            N_est = 1e-4

        try:
            idx_b_region = np.where((tau >= 1.0) & (tau <= 10.0))[0]
            if len(idx_b_region) >= 3:
                B_est = np.min(allan_std[idx_b_region]) / 0.6648
            else:
                mid_idx = len(tau) // 2
                B_est = allan_std[mid_idx] / 0.6648
        except:
            B_est = 1e-5

        try:
            n_points = len(tau)
            idx_k = np.arange(max(0, int(n_points * 0.55)), min(n_points, int(n_points * 0.8)))
            if len(idx_k) >= 2:
                coeff_k = np.polyfit(log_tau[idx_k], log_sigma[idx_k], 1)
                intercept_k = coeff_k[1] - 0.5 * np.log10(3.0 / 2.0)
                K_est = 10 ** intercept_k
            else:
                K_est = 1e-7
        except:
            K_est = 1e-7

        try:
            idx_r = np.where(tau > tau[int(len(tau) * 0.75)])[0]
            if len(idx_r) >= 2:
                coeff_r = np.polyfit(log_tau[idx_r], log_sigma[idx_r], 1)
                intercept_r = coeff_r[1] - 0.5 * np.log10(2)
                R_est = 10 ** intercept_r
            else:
                R_est = 1e-8
        except:
            R_est = 1e-8

        return {
            'Q': max(Q_est, 1e-10),
            'N': max(N_est, 1e-10),
            'B': max(B_est, 1e-10),
            'K': max(K_est, 1e-10),
            'R': max(R_est, 1e-10)
        }

    def fit_noise_coefficients(self, tau: np.ndarray, allan_std: np.ndarray) -> Dict:
        """
        拟合噪声系数

        Args:
            tau: 时间常数数组
            allan_std: Allan标准差数组

        Returns:
            包含各噪声系数的字典
        """
        initial_params = self._linear_regions(tau, allan_std)
        p0 = [initial_params['Q'], initial_params['N'], initial_params['B'],
              initial_params['K'], initial_params['R']]

        try:
            bounds = (
                [1e-12, 1e-12, 1e-12, 1e-12, 1e-12],
                [1e-2, 1e-2, 1e-2, 1e-2, 1e-2]
            )

            valid_idx = np.isfinite(allan_std) & (allan_std > 0)
            tau_fit = tau[valid_idx]
            sigma_fit = allan_std[valid_idx]

            if len(tau_fit) < 10:
                return {
                    'quantization_noise': initial_params['Q'],
                    'angle_random_walk': initial_params['N'],
                    'bias_instability': initial_params['B'],
                    'rate_random_walk': initial_params['K'],
                    'rate_ramp': initial_params['R'],
                    'fitted_curve': self._noise_model(tau, *p0),
                    'tau': tau,
                    'allan_std': allan_std,
                    'success': False,
                    'message': '数据点不足，使用线性估计结果'
                }

            popt, pcov = curve_fit(
                self._noise_model, tau_fit, sigma_fit,
                p0=p0, bounds=bounds, maxfev=10000,
                ftol=1e-12, xtol=1e-12
            )

            Q, N, B, K, R = popt
            fitted_curve = self._noise_model(tau, *popt)

            residuals = sigma_fit - self._noise_model(tau_fit, *popt)
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((sigma_fit - np.mean(sigma_fit)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return {
                'quantization_noise': Q,
                'angle_random_walk': N,
                'bias_instability': B,
                'rate_random_walk': K,
                'rate_ramp': R,
                'fitted_curve': fitted_curve,
                'tau': tau,
                'allan_std': allan_std,
                'success': True,
                'r_squared': r_squared,
                'initial_estimates': initial_params
            }

        except Exception as e:
            return {
                'quantization_noise': initial_params['Q'],
                'angle_random_walk': initial_params['N'],
                'bias_instability': initial_params['B'],
                'rate_random_walk': initial_params['K'],
                'rate_ramp': initial_params['R'],
                'fitted_curve': self._noise_model(tau, *p0),
                'tau': tau,
                'allan_std': allan_std,
                'success': False,
                'message': f'拟合失败: {str(e)}，使用线性估计结果'
            }

    def analyze(self, rate_data: np.ndarray, **kwargs) -> Dict:
        """
        完整的Allan方差分析流程

        Args:
            rate_data: 角速率数据
            **kwargs: 传递给 compute_allan_variance 的参数

        Returns:
            分析结果字典，包含Allan方差数据和噪声系数
        """
        tau, allan_std = self.compute_allan_variance(rate_data, **kwargs)
        results = self.fit_noise_coefficients(tau, allan_std)
        return results

    @staticmethod
    def format_results(results: Dict, units: str = 'deg/h') -> str:
        """
        格式化输出结果

        Args:
            results: analyze() 返回的结果字典
            units: 单位说明

        Returns:
            格式化的结果字符串
        """
        unit_str = f"({units})"
        output = []
        output.append("=" * 60)
        output.append("Allan 方差噪声分析结果")
        output.append("=" * 60)
        output.append(f"量化噪声 (Quantization Noise):   {results['quantization_noise']:.6e} {unit_str}")
        output.append(f"角度随机游走 (Angle Random Walk): {results['angle_random_walk']:.6e} {unit_str}/√Hz")
        output.append(f"零偏不稳定性 (Bias Instability):  {results['bias_instability']:.6e} {unit_str}")
        output.append(f"速率随机游走 (Rate Random Walk):  {results['rate_random_walk']:.6e} {unit_str}·√Hz")
        output.append(f"速率斜坡 (Rate Ramp):            {results['rate_ramp']:.6e} {unit_str}/s")
        output.append("-" * 60)

        if 'success' in results:
            if results['success']:
                output.append(f"拟合状态: 成功 (R² = {results.get('r_squared', 0):.4f})")
            else:
                output.append(f"拟合状态: {results.get('message', '使用估计值')}")

        output.append("=" * 60)

        return "\n".join(output)

    @staticmethod
    def compare_results(results_before: Dict, results_after: Dict) -> str:
        """
        对比降噪前后的噪声系数

        Args:
            results_before: 降噪前的分析结果
            results_after: 降噪后的分析结果

        Returns:
            对比结果字符串
        """
        output = []
        output.append("=" * 80)
        output.append("降噪前后噪声系数对比")
        output.append("=" * 80)
        output.append(f"{'噪声类型':<20} {'降噪前':>15} {'降噪后':>15} {'变化率':>15}")
        output.append("-" * 80)

        params = [
            ('quantization_noise', '量化噪声'),
            ('angle_random_walk', '角度随机游走'),
            ('bias_instability', '零偏不稳定性'),
            ('rate_random_walk', '速率随机游走'),
            ('rate_ramp', '速率斜坡')
        ]

        for key, name in params:
            before = results_before.get(key, 0)
            after = results_after.get(key, 0)
            if before != 0:
                change = (after - before) / before * 100
            else:
                change = 0

            output.append(f"{name:<20} {before:>15.6e} {after:>15.6e} {change:>14.2f}%")

        output.append("=" * 80)

        return "\n".join(output)
