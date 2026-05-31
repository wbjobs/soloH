import numpy as np
from typing import Dict, Tuple, Optional, List
from scipy.optimize import curve_fit, least_squares
from scipy.signal import lfilter
from enum import Enum


class CompensationModelType(Enum):
    """温度补偿模型类型枚举"""
    POLYNOMIAL = 'polynomial'
    ARMA = 'arma'
    LS_SVM = 'ls_svm'
    HYBRID = 'hybrid'


class TemperatureCompensator:
    """
    光纤陀螺温度补偿模型

    实现多种温度与噪声耦合的去除方法，包括：
    1. 多项式拟合模型 (Polynomial)
    2. 时序ARMA模型 (AutoRegressive Moving Average)
    3. 最小二乘支持向量机 (LS-SVM)
    4. 混合模型 (Hybrid)
    """

    def __init__(self, model_type: CompensationModelType = CompensationModelType.POLYNOMIAL):
        """
        初始化温度补偿器

        Args:
            model_type: 补偿模型类型
        """
        self.model_type = model_type
        self._model_params = None
        self._is_trained = False
        self._temperature_stats = None
        self._rate_stats = None

    def _normalize(self, data: np.ndarray, stats: Dict = None) -> Tuple[np.ndarray, Dict]:
        """数据归一化"""
        if stats is None:
            stats = {
                'mean': np.mean(data),
                'std': np.std(data) + 1e-10
            }
        normalized = (data - stats['mean']) / stats['std']
        return normalized, stats

    def _denormalize(self, data: np.ndarray, stats: Dict) -> np.ndarray:
        """数据反归一化"""
        return data * stats['std'] + stats['mean']

    def fit(self, temperature: np.ndarray, rate_data: np.ndarray,
            polynomial_order: int = 4,
            arma_order: Tuple[int, int] = (2, 1),
            svm_gamma: float = 10.0,
            svm_lambda: float = 1.0) -> Dict:
        """
        训练温度补偿模型

        Args:
            temperature: 温度数据 (°C)
            rate_data: 角速率数据 (deg/h)
            polynomial_order: 多项式阶数 (多项式模型)
            arma_order: ARMA模型阶数 (p, q)
            svm_gamma: LS-SVM核参数
            svm_lambda: LS-SVM正则化参数

        Returns:
            训练结果字典
        """
        if len(temperature) != len(rate_data):
            raise ValueError("温度数据和角速率数据长度必须一致")

        if len(temperature) < 10:
            raise ValueError("数据点数量不足，至少需要10个点")

        temperature = np.asarray(temperature, dtype=np.float64)
        rate_data = np.asarray(rate_data, dtype=np.float64)

        temp_norm, self._temperature_stats = self._normalize(temperature)
        rate_norm, self._rate_stats = self._normalize(rate_data)

        results = {}

        if self.model_type == CompensationModelType.POLYNOMIAL:
            results = self._fit_polynomial(temp_norm, rate_norm, polynomial_order)
        elif self.model_type == CompensationModelType.ARMA:
            results = self._fit_arma(rate_norm, temp_norm, arma_order)
        elif self.model_type == CompensationModelType.LS_SVM:
            results = self._fit_lssvm(temp_norm, rate_norm, svm_gamma, svm_lambda)
        elif self.model_type == CompensationModelType.HYBRID:
            results = self._fit_hybrid(temp_norm, rate_norm,
                                        polynomial_order, arma_order,
                                        svm_gamma, svm_lambda)
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

        self._is_trained = True

        results['temperature_stats'] = self._temperature_stats
        results['rate_stats'] = self._rate_stats

        return results

    def _fit_polynomial(self, temp_norm: np.ndarray, rate_norm: np.ndarray,
                         order: int) -> Dict:
        """
        多项式拟合模型

        模型: rate = a0 + a1*T + a2*T² + ... + an*Tⁿ
        """
        print(f"\n训练多项式模型 (阶数: {order})...")

        A = np.vander(temp_norm, order + 1, increasing=True)

        params, residuals, rank, singular_values = np.linalg.lstsq(A, rate_norm, rcond=None)

        fitted = A @ params
        error = rate_norm - fitted
        r_squared = 1 - np.sum(error ** 2) / np.sum((rate_norm - np.mean(rate_norm)) ** 2)

        self._model_params = {
            'type': 'polynomial',
            'order': order,
            'coefficients': params
        }

        print(f"  多项式系数: {[f'{p:.6f}' for p in params]}")
        print(f"  R² = {r_squared:.6f}")

        return {
            'coefficients': params,
            'fitted': fitted,
            'residuals': error,
            'r_squared': r_squared
        }

    def _fit_arma(self, rate_norm: np.ndarray, temp_norm: np.ndarray,
                   order: Tuple[int, int]) -> Dict:
        """
        ARMA时序模型（含温度外生变量的ARMAX模型）

        模型: rate(t) = c + Σa_i*rate(t-i) + Σb_j*ε(t-j) + Σd_k*T(t-k)
        """
        p, q = order
        print(f"\n训练ARMAX模型 (阶数: p={p}, q={q})...")

        n = len(rate_norm)

        X = np.zeros((n - max(p, q), p + 1))
        X[:, 0] = 1

        for i in range(1, p + 1):
            X[:, i] = rate_norm[max(p, q) - i:n - i]

        y = rate_norm[max(p, q):]

        if np.any(np.isnan(X)) or np.any(np.isnan(y)):
            raise ValueError("数据中存在NaN值")

        ar_params, residuals, rank, _ = np.linalg.lstsq(X, y, rcond=None)

        residuals_full = np.zeros(n)
        residuals_full[:max(p, q)] = y[:max(p, q)] if max(p, q) > 0 else []
        residuals_full[max(p, q):] = y - X @ ar_params

        if q > 0:
            X_ma = np.zeros((n - max(p, q), q))
            for i in range(1, q + 1):
                if max(p, q) - i >= 0:
                    X_ma[:, i - 1] = residuals_full[max(p, q) - i:n - i]

            X_full = np.hstack([X, X_ma])
            all_params, residuals, rank, _ = np.linalg.lstsq(X_full, y, rcond=None)

            ar_params = all_params[:p + 1]
            ma_params = all_params[p + 1:]
        else:
            ma_params = np.array([])

        fitted = X @ ar_params
        if q > 0:
            fitted += X_ma @ ma_params

        error = y - fitted
        r_squared = 1 - np.sum(error ** 2) / np.sum((y - np.mean(y)) ** 2)

        self._model_params = {
            'type': 'arma',
            'order': (p, q),
            'ar_params': ar_params,
            'ma_params': ma_params,
            'residuals': residuals_full
        }

        print(f"  AR参数: {[f'{p:.6f}' for p in ar_params]}")
        print(f"  MA参数: {[f'{p:.6f}' for p in ma_params]}")
        print(f"  R² = {r_squared:.6f}")

        return {
            'ar_params': ar_params,
            'ma_params': ma_params,
            'fitted': fitted,
            'residuals': error,
            'r_squared': r_squared
        }

    def _rbf_kernel(self, x1: np.ndarray, x2: np.ndarray, gamma: float) -> np.ndarray:
        """RBF核函数"""
        x1 = np.atleast_2d(x1)
        x2 = np.atleast_2d(x2)
        dist_sq = np.sum(x1 ** 2, axis=1)[:, None] + np.sum(x2 ** 2, axis=1)[None, :] - 2 * x1 @ x2.T
        return np.exp(-gamma * dist_sq)

    def _fit_lssvm(self, temp_norm: np.ndarray, rate_norm: np.ndarray,
                    gamma: float, lambda_reg: float) -> Dict:
        """
        最小二乘支持向量机 (LS-SVM)

        非线性温度漂移建模
        """
        print(f"\n训练LS-SVM模型 (γ={gamma:.2f}, λ={lambda_reg:.2f})...")

        n = len(temp_norm)
        X = temp_norm.reshape(-1, 1)
        y = rate_norm

        Omega = self._rbf_kernel(X, X, gamma)

        H = Omega + lambda_reg * np.eye(n)
        A = np.vstack([
            np.hstack([H, np.ones((n, 1))]),
            np.hstack([np.ones((1, n)), np.zeros((1, 1))])
        ])
        b = np.hstack([y, np.zeros(1)])

        try:
            solution = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            solution = np.linalg.lstsq(A, b, rcond=None)[0]

        alpha = solution[:n]
        bias = solution[n]

        fitted = Omega @ alpha + bias
        error = y - fitted
        r_squared = 1 - np.sum(error ** 2) / np.sum((y - np.mean(y)) ** 2)

        self._model_params = {
            'type': 'lssvm',
            'gamma': gamma,
            'lambda': lambda_reg,
            'alpha': alpha,
            'bias': bias,
            'support_vectors': X
        }

        n_sv = np.sum(np.abs(alpha) > 1e-6)
        print(f"  支持向量数量: {n_sv}/{n}")
        print(f"  R² = {r_squared:.6f}")

        return {
            'alpha': alpha,
            'bias': bias,
            'fitted': fitted,
            'residuals': error,
            'r_squared': r_squared,
            'n_support_vectors': n_sv
        }

    def _fit_hybrid(self, temp_norm: np.ndarray, rate_norm: np.ndarray,
                     poly_order: int, arma_order: Tuple[int, int],
                     svm_gamma: float, svm_lambda: float) -> Dict:
        """
        混合模型：多项式 + LS-SVM

        先用多项式拟合趋势项，再用LS-SVM拟合残差
        """
        print("\n训练混合模型 (多项式 + LS-SVM)...")

        print("  步骤1: 多项式拟合趋势项")
        poly_result = self._fit_polynomial(temp_norm, rate_norm, poly_order)
        poly_fitted = poly_result['fitted']
        residuals = rate_norm - poly_fitted

        print("\n  步骤2: LS-SVM拟合残差")
        svm_result = self._fit_lssvm(temp_norm, residuals, svm_gamma, svm_lambda)
        svm_fitted = svm_result['fitted']

        fitted = poly_fitted + svm_fitted
        error = rate_norm - fitted
        r_squared = 1 - np.sum(error ** 2) / np.sum((rate_norm - np.mean(rate_norm)) ** 2)

        self._model_params = {
            'type': 'hybrid',
            'poly_params': poly_result['coefficients'],
            'poly_order': poly_order,
            'svm_params': {
                'alpha': svm_result['alpha'],
                'bias': svm_result['bias'],
                'gamma': svm_gamma,
                'support_vectors': svm_result.get('support_vectors', temp_norm.reshape(-1, 1))
            }
        }

        print(f"\n  混合模型 R² = {r_squared:.6f}")
        print(f"  多项式 R² = {poly_result['r_squared']:.6f}")
        print(f"  LS-SVM R² = {svm_result['r_squared']:.6f}")

        return {
            'poly_result': poly_result,
            'svm_result': svm_result,
            'fitted': fitted,
            'residuals': error,
            'r_squared': r_squared
        }

    def predict(self, temperature: np.ndarray, rate_data: Optional[np.ndarray] = None) -> np.ndarray:
        """
        预测温度漂移，用于补偿

        Args:
            temperature: 温度数据
            rate_data: 角速率数据（仅ARMA模型需要）

        Returns:
            预测的温度漂移分量
        """
        if not self._is_trained:
            raise RuntimeError("模型尚未训练，请先调用fit()方法")

        temperature = np.asarray(temperature, dtype=np.float64)
        temp_norm, _ = self._normalize(temperature, self._temperature_stats)

        params = self._model_params
        model_type = params['type']

        if model_type == 'polynomial':
            A = np.vander(temp_norm, params['order'] + 1, increasing=True)
            drift_norm = A @ params['coefficients']

        elif model_type == 'arma':
            p, q = params['order']
            n = len(temp_norm)

            if rate_data is None:
                rate_norm = np.zeros(n)
            else:
                rate_data = np.asarray(rate_data, dtype=np.float64)
                rate_norm, _ = self._normalize(rate_data, self._rate_stats)

            drift_norm = np.zeros(n)
            ar_params = params['ar_params']

            for t in range(n):
                drift_norm[t] = ar_params[0]
                for i in range(1, p + 1):
                    if t - i >= 0:
                        drift_norm[t] += ar_params[i] * rate_norm[t - i]

            if q > 0 and params['ma_params'].size > 0:
                residuals = params.get('residuals', np.zeros(n))
                ma_params = params['ma_params']
                for t in range(n):
                    for j in range(1, q + 1):
                        if t - j >= 0 and t - j < len(residuals):
                            drift_norm[t] += ma_params[j - 1] * residuals[t - j]

        elif model_type == 'lssvm':
            X_new = temp_norm.reshape(-1, 1)
            X_sv = params['support_vectors']
            K = self._rbf_kernel(X_new, X_sv, params['gamma'])
            drift_norm = K @ params['alpha'] + params['bias']

        elif model_type == 'hybrid':
            A = np.vander(temp_norm, params['poly_order'] + 1, increasing=True)
            poly_drift = A @ params['poly_params']

            X_new = temp_norm.reshape(-1, 1)
            svm_params = params['svm_params']
            X_sv = svm_params['support_vectors']
            K = self._rbf_kernel(X_new, X_sv, svm_params['gamma'])
            svm_drift = K @ svm_params['alpha'] + svm_params['bias']

            drift_norm = poly_drift + svm_drift

        else:
            raise ValueError(f"未知模型类型: {model_type}")

        drift = self._denormalize(drift_norm, self._rate_stats)
        return drift

    def compensate(self, temperature: np.ndarray, rate_data: np.ndarray) -> np.ndarray:
        """
        对数据进行温度补偿

        Args:
            temperature: 温度数据
            rate_data: 原始角速率数据

        Returns:
            补偿后的角速率数据
        """
        drift = self.predict(temperature, rate_data)
        compensated = rate_data - drift
        return compensated

    def evaluate(self, temperature: np.ndarray, rate_data: np.ndarray) -> Dict:
        """
        评估补偿效果

        Args:
            temperature: 温度数据
            rate_data: 原始角速率数据

        Returns:
            评估结果字典
        """
        compensated = self.compensate(temperature, rate_data)
        drift = rate_data - compensated

        std_before = np.std(rate_data)
        std_after = np.std(compensated)

        allan_before = np.std(np.diff(rate_data))
        allan_after = np.std(np.diff(compensated))

        reduction_ratio = (std_before - std_after) / std_before * 100

        if np.any(np.abs(temperature - temperature[0]) > 1e-6):
            corr_before = np.corrcoef(temperature, rate_data)[0, 1]
            corr_after = np.corrcoef(temperature, compensated)[0, 1]
        else:
            corr_before = 0.0
            corr_after = 0.0

        results = {
            'std_before': std_before,
            'std_after': std_after,
            'std_reduction_percent': reduction_ratio,
            'allan_std_before': allan_before,
            'allan_std_after': allan_after,
            'allan_reduction_percent': (allan_before - allan_after) / allan_before * 100,
            'temperature_correlation_before': corr_before,
            'temperature_correlation_after': corr_after,
            'drift': drift,
            'compensated': compensated
        }

        print("\n" + "=" * 60)
        print("温度补偿效果评估")
        print("=" * 60)
        print(f"标准差: {std_before:.6f} -> {std_after:.6f} (降低 {reduction_ratio:.2f}%)")
        print(f"Allan方差: {allan_before:.6f} -> {allan_after:.6f}")
        print(f"温度相关性: {corr_before:.4f} -> {corr_after:.4f}")
        print("=" * 60)

        return results

    @staticmethod
    def compare_models(temperature: np.ndarray, rate_data: np.ndarray,
                        plot: bool = False, **kwargs) -> Dict:
        """
        对比不同补偿模型的效果

        Args:
            temperature: 温度数据
            rate_data: 角速率数据
            plot: 是否绘制对比图
            **kwargs: 各模型的参数

        Returns:
            各模型的评估结果
        """
        models = [
            (CompensationModelType.POLYNOMIAL, '多项式模型'),
            (CompensationModelType.ARMA, 'ARMAX模型'),
            (CompensationModelType.LS_SVM, 'LS-SVM模型'),
            (CompensationModelType.HYBRID, '混合模型')
        ]

        results = {}

        for model_type, name in models:
            print(f"\n{'=' * 60}")
            print(f"模型: {name}")
            print("=" * 60)

            compensator = TemperatureCompensator(model_type=model_type)

            train_kwargs = {}
            if model_type == CompensationModelType.POLYNOMIAL:
                train_kwargs['polynomial_order'] = kwargs.get('polynomial_order', 4)
            elif model_type == CompensationModelType.ARMA:
                train_kwargs['arma_order'] = kwargs.get('arma_order', (2, 1))
            elif model_type == CompensationModelType.LS_SVM:
                train_kwargs['svm_gamma'] = kwargs.get('svm_gamma', 10.0)
                train_kwargs['svm_lambda'] = kwargs.get('svm_lambda', 1.0)
            elif model_type == CompensationModelType.HYBRID:
                train_kwargs['polynomial_order'] = kwargs.get('polynomial_order', 4)
                train_kwargs['arma_order'] = kwargs.get('arma_order', (2, 1))
                train_kwargs['svm_gamma'] = kwargs.get('svm_gamma', 10.0)
                train_kwargs['svm_lambda'] = kwargs.get('svm_lambda', 1.0)

            fit_result = compensator.fit(temperature, rate_data, **train_kwargs)
            eval_result = compensator.evaluate(temperature, rate_data)

            results[name] = {
                'compensator': compensator,
                'fit_result': fit_result,
                'eval_result': eval_result
            }

        if plot:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            axes[0, 0].plot(temperature, rate_data, 'b.', alpha=0.5, label='原始数据')
            for name, res in results.items():
                axes[0, 0].plot(temperature, res['eval_result']['compensated'],
                                label=name, linewidth=1.5)
            axes[0, 0].set_xlabel('温度 (°C)', fontsize=12)
            axes[0, 0].set_ylabel('角速率 (deg/h)', fontsize=12)
            axes[0, 0].set_title('温度-角速率散点图', fontsize=14, fontweight='bold')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)

            axes[0, 1].bar(results.keys(),
                          [r['eval_result']['std_reduction_percent'] for r in results.values()],
                          color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'], alpha=0.7)
            axes[0, 1].set_ylabel('标准差降低 (%)', fontsize=12)
            axes[0, 1].set_title('各模型补偿效果对比', fontsize=14, fontweight='bold')
            axes[0, 1].grid(True, alpha=0.3, axis='y')
            for i, (name, res) in enumerate(results.items()):
                axes[0, 1].text(i, res['eval_result']['std_reduction_percent'],
                               f"{res['eval_result']['std_reduction_percent']:.1f}%",
                               ha='center', va='bottom')

            time_axis = np.arange(len(rate_data))
            axes[1, 0].plot(time_axis, rate_data, 'b-', alpha=0.5, label='原始')
            best_name = max(results.keys(),
                           key=lambda k: results[k]['eval_result']['std_reduction_percent'])
            axes[1, 0].plot(time_axis, results[best_name]['eval_result']['compensated'],
                           'r-', label=f'{best_name} 补偿后', linewidth=1.2)
            axes[1, 0].set_xlabel('样本点', fontsize=12)
            axes[1, 0].set_ylabel('角速率 (deg/h)', fontsize=12)
            axes[1, 0].set_title('时序对比', fontsize=14, fontweight='bold')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)

            axes[1, 1].plot(temperature, rate_data - np.mean(rate_data),
                           'b.', alpha=0.5, label='原始')
            axes[1, 1].plot(temperature,
                           results[best_name]['eval_result']['compensated'] - np.mean(results[best_name]['eval_result']['compensated']),
                           'r.', alpha=0.7, label='补偿后')
            axes[1, 1].set_xlabel('温度 (°C)', fontsize=12)
            axes[1, 1].set_ylabel('角速率 (去均值, deg/h)', fontsize=12)
            axes[1, 1].set_title('温度相关性对比', fontsize=14, fontweight='bold')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig('temperature_compensation_comparison.png', dpi=150, bbox_inches='tight')
            plt.close()

        return results
