"""
新功能测试
测试原子氧侵蚀、瞬态响应、贝叶斯老化预测三个新功能
"""

import unittest
import numpy as np
from datetime import datetime, timedelta

from satellite_power_predictor.solar_cell import (
    AtomicOxygenErosionModel, DegradationState,
    TransientResponseModel, TransientState,
    SolarArrayConfig
)
from satellite_power_predictor.analysis import (
    BayesianAgingPredictor, TelemetryObservation,
    AgingParameters
)


class TestAtomicOxygenErosion(unittest.TestCase):
    """原子氧侵蚀与表面除尘效应测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.ao_model = AtomicOxygenErosionModel(
            surface_material='sio2',
            initial_transmittance=0.95,
            initial_roughness=1.0
        )
        self.initial_state = DegradationState(
            cumulative_ddd=0.0,
            remaining_factor=1.0,
            remaining_factor_isc=1.0,
            remaining_factor_voc=1.0,
            remaining_factor_pmax=1.0,
            elapsed_days=0.0,
            cumulative_atomic_oxygen=0.0,
            surface_transmittance=0.95,
            contamination_thickness=0.0,
            surface_roughness=1.0
        )
    
    def test_atomic_oxygen_flux_vs_altitude(self):
        """测试原子氧通量随轨道高度的变化"""
        # 低轨道通量高，高轨道通量低
        flux_200km = self.ao_model.calculate_atomic_oxygen_flux(200.0)
        flux_400km = self.ao_model.calculate_atomic_oxygen_flux(400.0)
        flux_1000km = self.ao_model.calculate_atomic_oxygen_flux(1000.0)
        
        print(f"\n=== 原子氧通量 vs 轨道高度 ===")
        print(f"200km: {flux_200km:.2e} atoms/cm^2/s")
        print(f"400km: {flux_400km:.2e} atoms/cm^2/s")
        print(f"1000km: {flux_1000km:.2e} atoms/cm^2/s")
        
        self.assertGreater(flux_200km, flux_400km)
        self.assertGreater(flux_400km, flux_1000km)
        # 400km LEO典型通量应该在1e13-1e15量级
        self.assertGreater(flux_400km, 1e12)
        self.assertLess(flux_400km, 1e16)
    
    def test_solar_activity_effect(self):
        """测试太阳活动对原子氧通量的影响"""
        flux_min = self.ao_model.calculate_atomic_oxygen_flux(400.0, solar_f107=70.0)
        flux_max = self.ao_model.calculate_atomic_oxygen_flux(400.0, solar_f107=200.0)
        
        print(f"\n=== 太阳活动影响 ===")
        print(f"太阳活动极小年 (F10.7=70): {flux_min:.2e} atoms/cm^2/s")
        print(f"太阳活动极大年 (F10.7=200): {flux_max:.2e} atoms/cm^2/s")
        print(f"比值: {flux_max/flux_min:.2f}x")
        
        self.assertGreater(flux_max, flux_min)
        self.assertLess(flux_max / flux_min, 3.0)  # 不应超过3倍
    
    def test_surface_contamination_cleaning(self):
        """测试表面除尘效应（原子氧清除污染物）"""
        # 初始状态：有10nm厚的污染物
        initial_contamination = 10.0
        state = DegradationState(
            cumulative_ddd=0.0,
            remaining_factor=1.0,
            remaining_factor_isc=1.0,
            remaining_factor_voc=1.0,
            remaining_factor_pmax=1.0,
            elapsed_days=0.0,
            cumulative_atomic_oxygen=0.0,
            surface_transmittance=0.85,
            contamination_thickness=initial_contamination,
            surface_roughness=1.0
        )
        
        print(f"\n=== 表面除尘效应 ===")
        print(f"初始污染物厚度: {state.contamination_thickness:.2f} nm")
        print(f"初始透射率: {state.surface_transmittance:.4f}")
        print(f"初始表面粗糙度: {state.surface_roughness:.2f} nm")
        
        # 先计算如果没有侵蚀，只有污染物被清除后的理论透射率
        theoretical_clean_transmittance = self.ao_model.calculate_surface_transmittance(
            0.0, 1.0, 0.0  # 无侵蚀，初始粗糙度，无污染物
        )
        print(f"理论清洁后透射率（无侵蚀）: {theoretical_clean_transmittance:.4f}")
        
        # 模拟在400km轨道暴露30天
        time_step = 86400.0  # 1天
        for day in range(30):
            state = self.ao_model.update_state(
                state,
                altitude_km=400.0,
                incidence_angle_deg=0.0,
                time_step_seconds=time_step,
                solar_f107=150.0
            )
        
        print(f"\n30天后污染物厚度: {state.contamination_thickness:.2f} nm")
        print(f"30天后透射率: {state.surface_transmittance:.4f}")
        print(f"30天后表面粗糙度: {state.surface_roughness:.2f} nm")
        print(f"累积原子氧通量: {state.cumulative_atomic_oxygen:.2e} atoms/cm^2")
        
        # 污染物应该被清除（从10nm降到接近0）
        self.assertLess(state.contamination_thickness, initial_contamination * 0.5)
        # 累积通量应该很大
        self.assertGreater(state.cumulative_atomic_oxygen, 1e20)
        # 粗糙度应该增加
        self.assertGreater(state.surface_roughness, 1.0)
    
    def test_erosion_rate_incidence_angle(self):
        """测试侵蚀率随入射角的变化"""
        flux = 1e14  # atoms/cm²/s
        
        erosion_normal = self.ao_model.calculate_erosion_rate(flux, 0.0)
        erosion_45deg = self.ao_model.calculate_erosion_rate(flux, 45.0)
        erosion_90deg = self.ao_model.calculate_erosion_rate(flux, 90.0)
        
        print(f"\n=== 侵蚀率 vs 入射角 ===")
        print(f"法线入射: {erosion_normal:.2e} μm/s")
        print(f"45度入射: {erosion_45deg:.2e} μm/s")
        print(f"90度入射: {erosion_90deg:.2e} μm/s")
        
        self.assertGreater(erosion_normal, erosion_45deg)
        self.assertAlmostEqual(erosion_90deg, 0.0, places=20)
    
    def test_surface_transmittance_degradation(self):
        """测试表面透射率随侵蚀的退化"""
        # 无侵蚀、无粗糙度、无污染（理想状态）
        t0 = self.ao_model.calculate_surface_transmittance(0.0, 0.0, 0.0)
        # 无侵蚀，有初始粗糙度
        t0_rough = self.ao_model.calculate_surface_transmittance(0.0, 1.0, 0.0)
        # 严重侵蚀（5μm）
        t_heavy = self.ao_model.calculate_surface_transmittance(5.0, 15.0, 0.0)
        # 有污染物
        t_dirty = self.ao_model.calculate_surface_transmittance(0.0, 1.0, 50.0)
        
        print(f"\n=== 表面透射率 ===")
        print(f"理想初始状态: {t0:.4f}")
        print(f"有初始粗糙度: {t0_rough:.4f}")
        print(f"严重侵蚀后: {t_heavy:.4f}")
        print(f"有50nm污染物: {t_dirty:.4f}")
        
        # 理想状态下应该等于初始透射率
        self.assertAlmostEqual(t0, 0.95, places=4)
        # 有粗糙度和侵蚀后应该下降
        self.assertLess(t0_rough, t0)
        self.assertLess(t_heavy, t0_rough)
        self.assertLess(t_dirty, t0_rough)
    
    def test_irradiance_factor(self):
        """测试有效辐照度因子"""
        state = DegradationState(
            cumulative_ddd=0.0,
            remaining_factor=1.0,
            remaining_factor_isc=1.0,
            remaining_factor_voc=1.0,
            remaining_factor_pmax=1.0,
            elapsed_days=0.0,
            cumulative_atomic_oxygen=0.0,
            surface_transmittance=0.85,
            contamination_thickness=5.0,
            surface_roughness=5.0
        )
        
        factor = self.ao_model.get_effective_irradiance_factor(state)
        print(f"\n=== 有效辐照度因子 ===")
        print(f"透射率: {state.surface_transmittance:.4f}")
        print(f"辐照度因子: {factor:.4f}")
        
        self.assertAlmostEqual(factor, 0.85 / 0.95, places=4)


class TestTransientResponse(unittest.TestCase):
    """阴影区电压跌落和再入影恢复瞬态响应测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.array_config = SolarArrayConfig(
            n_cells_series=40,
            n_strings_parallel=3
        )
        self.transient_model = TransientResponseModel(
            array_config=self.array_config,
            junction_capacitance_per_cell=1.0e-6,
            bypass_capacitance=100.0e-6,
            voltage_settling_time=0.5,
            current_settling_time=0.1
        )
    
    def test_eclipse_voltage_decay(self):
        """测试阴影区电压跌落"""
        initial_v = 28.0
        initial_i = 10.0
        
        print(f"\n=== 阴影区电压跌落 ===")
        print(f"初始电压: {initial_v:.2f} V, 初始电流: {initial_i:.2f} A")
        
        for t in [0.1, 0.5, 1.0, 2.0, 5.0]:
            v, i, settled = self.transient_model.calculate_eclipse_voltage_decay(
                initial_v, initial_i, t
            )
            print(f"t={t:.1f}s: V={v:.2f} V, I={i:.2f} A, 稳定={settled}")
        
        # 长时间后电压应该接近0
        v_final, i_final, _ = self.transient_model.calculate_eclipse_voltage_decay(
            initial_v, initial_i, 10.0
        )
        self.assertLess(v_final, 1.0)
        self.assertLess(i_final, 0.1)
    
    def test_illumination_recovery(self):
        """测试再入影电压恢复"""
        initial_v = 0.5
        initial_i = 0.0
        steady_v = 28.0
        steady_i = 10.0
        
        print(f"\n=== 再入影电压恢复 ===")
        print(f"初始电压: {initial_v:.2f} V, 初始电流: {initial_i:.2f} A")
        print(f"稳态电压: {steady_v:.2f} V, 稳态电流: {steady_i:.2f} A")
        
        for t in [0.1, 0.5, 1.0, 2.0, 5.0]:
            v, i, settled = self.transient_model.calculate_illumination_recovery(
                initial_v, initial_i, steady_v, steady_i, t
            )
            print(f"t={t:.1f}s: V={v:.2f} V, I={i:.2f} A, 稳定={settled}")
        
        # 长时间后应该接近稳态
        v_final, i_final, settled = self.transient_model.calculate_illumination_recovery(
            initial_v, initial_i, steady_v, steady_i, 10.0
        )
        self.assertGreater(v_final, steady_v * 0.95)
        self.assertGreater(i_final, steady_i * 0.95)
        self.assertTrue(settled)
    
    def test_full_eclipse_transit(self):
        """测试完整的阴影-再入影过渡过程"""
        pre_eclipse_v = 28.0
        pre_eclipse_i = 10.0
        eclipse_duration = 30.0  # 30秒阴影
        post_eclipse_v = 28.0
        post_eclipse_i = 10.0
        
        times, voltages, currents = self.transient_model.simulate_eclipse_transit(
            pre_eclipse_v, pre_eclipse_i,
            eclipse_duration, post_eclipse_v, post_eclipse_i,
            num_points=200
        )
        
        # 计算性能指标
        metrics = self.transient_model.get_transient_performance_metrics(
            times, voltages, currents
        )
        
        print(f"\n=== 完整阴影-再入影过渡 ===")
        print(f"恢复时间: {metrics['recovery_time_s']:.2f} s")
        print(f"电压跌落深度: {metrics['voltage_drop_V']:.2f} V ({metrics['voltage_drop_ratio']*100:.1f}%)")
        print(f"过冲: {metrics['overshoot_V']:.3f} V ({metrics['overshoot_ratio']*100:.2f}%)")
        print(f"瞬态能量损失: {metrics['transient_energy_loss_J']:.2f} J")
        print(f"阴影前功率: {metrics['pre_eclipse_power_W']:.2f} W")
        print(f"阴影后功率: {metrics['post_eclipse_power_W']:.2f} W")
        
        self.assertGreater(metrics['voltage_drop_V'], 20.0)  # 电压应该大幅跌落
        self.assertGreater(metrics['recovery_time_s'], 0.0)
    
    def test_transient_state_update(self):
        """测试瞬态状态更新"""
        state = TransientState(
            voltage=28.0,
            current=10.0,
            steady_state_voltage=28.0,
            steady_state_current=10.0,
            time_since_transition=0.0,
            is_in_eclipse=False,
            settling_complete=True,
            junction_charge=0.0
        )
        
        # 进入阴影0.1秒（约2个时间常数，还没完全稳定）
        new_state = self.transient_model.update_transient_state(
            state, 0.0, 0.0, True, 0.1
        )
        
        print(f"\n=== 进入阴影0.1秒后 ===")
        print(f"电压: {new_state.voltage:.2f} V")
        print(f"电流: {new_state.current:.2f} A")
        print(f"结电容电荷: {new_state.junction_charge:.4f} C")
        print(f"距状态切换时间: {new_state.time_since_transition:.2f} s")
        print(f"是否稳定: {new_state.settling_complete}")
        
        self.assertLess(new_state.voltage, state.voltage)
        self.assertLess(new_state.current, state.current)
        self.assertTrue(new_state.is_in_eclipse)
        # 0.1秒约2个时间常数，还没完全稳定（稳定判据是0.01倍）
        self.assertFalse(new_state.settling_complete)
        
        # 再更新2秒，应该稳定了
        new_state2 = self.transient_model.update_transient_state(
            new_state, 0.0, 0.0, True, 2.0
        )
        self.assertTrue(new_state2.settling_complete)
        self.assertAlmostEqual(new_state2.voltage, 0.0, places=1)
    
    def test_time_constant_calculation(self):
        """测试时间常数计算"""
        tau_eclipse = self.transient_model._calculate_effective_time_constant(
            load_resistance=1.0, is_eclipse=True
        )
        tau_light = self.transient_model._calculate_effective_time_constant(
            load_resistance=1.0, is_eclipse=False
        )
        
        print(f"\n=== 时间常数 ===")
        print(f"阴影区放电时间常数: {tau_eclipse:.4f} s")
        print(f"光照区充电时间常数: {tau_light:.4f} s")
        
        self.assertGreater(tau_eclipse, 0.0)
        self.assertGreater(tau_light, 0.0)


class TestBayesianAgingPrediction(unittest.TestCase):
    """贝叶斯老化预测测试"""
    
    def setUp(self):
        """设置测试环境"""
        params = AgingParameters(
            remaining_factor_prior_mean=0.95,
            remaining_factor_prior_std=0.05
        )
        self.predictor = BayesianAgingPredictor(
            initial_parameters=params,
            array_area=3.0,
            reference_efficiency=0.225,
            failure_threshold=0.7
        )
    
    def test_power_prediction(self):
        """测试功率预测"""
        obs = TelemetryObservation(
            time=datetime.now(),
            array_power=900.0,
            array_current=30.0,
            array_voltage=30.0,
            cell_temperature=298.15,
            solar_irradiance=1361.0,
            incidence_angle=0.0,
            eclipse_factor=0.0
        )
        
        predicted_power = self.predictor.predict_power(obs)
        print(f"\n=== 功率预测 ===")
        print(f"观测功率: {obs.array_power:.1f} W")
        print(f"预测功率: {predicted_power:.1f} W")
        print(f"剩余因子: {self.predictor.parameters.remaining_factor_prior_mean:.3f}")
        
        self.assertGreater(predicted_power, 0.0)
    
    def test_ekf_update(self):
        """测试扩展卡尔曼滤波更新"""
        # 模拟明显的功率下降趋势
        np.random.seed(42)
        
        # 初始预测功率
        initial_obs = TelemetryObservation(
            time=datetime.now(),
            array_power=872.7,
            array_current=872.7 / 30.0,
            array_voltage=30.0,
            cell_temperature=298.15,
            solar_irradiance=1361.0,
            incidence_angle=0.0,
            eclipse_factor=0.0
        )
        initial_predicted = self.predictor.predict_power(initial_obs)
        
        print(f"\n=== EKF更新结果 ===")
        print(f"初始预测功率: {initial_predicted:.1f} W")
        print(f"初始剩余因子: {self.predictor.parameters.remaining_factor_prior_mean:.4f} ± "
              f"{self.predictor.parameters.remaining_factor_prior_std:.4f}")
        
        # 连续10次观测，每次功率比预测值低2%（模拟老化）
        for i in range(10):
            predicted = self.predictor.predict_power(initial_obs)
            # 观测值比预测值低2%，并有小噪声
            observed_power = predicted * 0.98 + np.random.normal(0, 2.0)
            
            obs = TelemetryObservation(
                time=datetime.now() + timedelta(days=i),
                array_power=observed_power,
                array_current=observed_power / 30.0,
                array_voltage=30.0,
                cell_temperature=298.15,
                solar_irradiance=1361.0,
                incidence_angle=0.0,
                eclipse_factor=0.0,
                measurement_uncertainty=0.01
            )
            
            result = self.predictor.update_with_ekf(obs)
        
        print(f"\n更新次数: {len(self.predictor.update_history)}")
        print(f"最终剩余因子: {self.predictor.parameters.remaining_factor_prior_mean:.4f} ± "
              f"{self.predictor.parameters.remaining_factor_prior_std:.4f}")
        print(f"最终新息: {self.predictor.update_history[-1].innovation:.2f} W")
        print(f"参数不确定度降低: {self.predictor.update_history[-1].parameter_uncertainty_reduction}")
        
        # 剩余因子应该有所下降
        self.assertLess(self.predictor.parameters.remaining_factor_prior_mean, 0.95)
        self.assertGreater(self.predictor.parameters.remaining_factor_prior_mean, 0.85)
        # 不确定性应该降低
        self.assertLess(self.predictor.parameters.remaining_factor_prior_std, 0.05)
    
    def test_rul_prediction(self):
        """测试剩余使用寿命预测"""
        # 先进行一些更新以积累数据
        for i in range(30):
            true_power = 900.0 * (0.95 - 0.0005 * i) + np.random.normal(0, 10.0)
            obs = TelemetryObservation(
                time=datetime.now() + timedelta(days=i),
                array_power=true_power,
                array_current=true_power / 30.0,
                array_voltage=30.0,
                cell_temperature=298.15,
                solar_irradiance=1361.0,
                incidence_angle=0.0,
                eclipse_factor=0.0
            )
            self.predictor.update_with_ekf(obs)
        
        # 预测RUL
        rul = self.predictor.predict_rul(
            cumulative_degradation_rate=5e-5,
            mission_days_elapsed=30.0,
            n_samples=5000
        )
        
        print(f"\n=== 剩余使用寿命预测 ===")
        print(f"平均RUL: {rul.mean_rul_days:.0f} 天")
        print(f"中位RUL: {rul.median_rul_days:.0f} 天")
        print(f"RUL标准差: {rul.std_rul_days:.0f} 天")
        print(f"95%置信区间: [{rul.confidence_95_low:.0f}, {rul.confidence_95_high:.0f}] 天")
        print(f"失效阈值: {rul.failure_threshold:.2f}")
        
        self.assertGreater(rul.mean_rul_days, 0.0)
        self.assertGreater(rul.median_rul_days, 0.0)
        self.assertLess(rul.confidence_95_low, rul.confidence_95_high)
    
    def test_aging_rate_estimate(self):
        """测试老化速率估计"""
        # 直接构造老化趋势数据来测试速率估计
        # 真实老化速率：每天0.001 (0.1%)
        np.random.seed(42)
        true_rate = 1e-3
        n_days = 100
        
        # 手动设置老化趋势数据
        for i in range(n_days):
            # 剩余因子线性下降
            rf = 0.95 - true_rate * i
            
            # 添加到老化趋势中
            self.predictor.aging_trend.times.append(
                datetime.now() + timedelta(days=i)
            )
            self.predictor.aging_trend.remaining_factor_mean.append(rf)
            self.predictor.aging_trend.remaining_factor_std.append(0.01)
            self.predictor.aging_trend.predicted_power.append(800.0 * rf)
            self.predictor.aging_trend.measured_power.append(800.0 * rf + np.random.normal(0, 2.0))
            self.predictor.aging_trend.parameter_evolution.append({
                'ddd_coefficient': 1e-9,
                'ao_erosion_coefficient': 1e-24,
                'thermal_cycle_factor': 1e-6,
                'uv_degradation_rate': 1e-9
            })
        
        rate, rate_std = self.predictor.get_aging_rate_estimate()
        
        print(f"\n=== 老化速率估计 ===")
        print(f"估计老化速率: {rate:.2e} ± {rate_std:.2e} /天")
        print(f"真实老化速率: {true_rate:.2e} /天")
        print(f"相对误差: {abs(rate - true_rate) / true_rate * 100:.1f}%")
        print(f"初始剩余因子: 0.95, 最终剩余因子: {0.95 - true_rate * n_days:.3f}")
        
        # 估计值应该为正（老化速率）
        self.assertGreater(rate, 0.0)
        # 估计值应该在真实值的20%误差范围内（因为数据是精确的）
        self.assertLess(abs(rate - true_rate) / true_rate, 0.2)
    
    def test_aging_forecast(self):
        """测试老化趋势预测"""
        # 先更新一些数据
        for i in range(20):
            power = 900.0 * (0.95 - 0.001 * i) + np.random.normal(0, 8.0)
            obs = TelemetryObservation(
                time=datetime.now() + timedelta(days=i),
                array_power=power,
                array_current=power / 30.0,
                array_voltage=30.0,
                cell_temperature=298.15,
                solar_irradiance=1361.0,
                incidence_angle=0.0,
                eclipse_factor=0.0
            )
            self.predictor.update_with_ekf(obs)
        
        # 预测未来100天
        times, rf_mean, rf_std = self.predictor.forecast_aging(n_days=100, time_step_days=10)
        
        print(f"\n=== 老化趋势预测 ===")
        print(f"当前剩余因子: {rf_mean[0]:.4f} ± {rf_std[0]:.4f}")
        print(f"100天后预测: {rf_mean[-1]:.4f} ± {rf_std[-1]:.4f}")
        
        # 剩余因子应该下降
        self.assertLess(rf_mean[-1], rf_mean[0])
        # 不确定性应该增加
        self.assertGreater(rf_std[-1], rf_std[0])
    
    def test_particle_filter_update(self):
        """测试粒子滤波器更新"""
        self.predictor.initialize_particle_filter(n_particles=200)
        
        for i in range(5):
            power = 900.0 * 0.95 + np.random.normal(0, 5.0)
            obs = TelemetryObservation(
                time=datetime.now() + timedelta(hours=i),
                array_power=power,
                array_current=power / 30.0,
                array_voltage=30.0,
                cell_temperature=298.15,
                solar_irradiance=1361.0,
                incidence_angle=0.0,
                eclipse_factor=0.0
            )
            result = self.predictor.update_with_particle_filter(obs)
        
        print(f"\n=== 粒子滤波器更新 ===")
        print(f"粒子数: {len(self.predictor.particles)}")
        print(f"剩余因子后验: {result.remaining_factor_posterior_mean:.4f} ± "
              f"{result.remaining_factor_posterior_std:.4f}")
        
        self.assertIsNotNone(self.predictor.particles)
        self.assertEqual(len(self.predictor.particles), 200)
    
    def test_batch_update(self):
        """测试批量更新"""
        observations = []
        for i in range(10):
            power = 900.0 * (0.95 - 0.0005 * i) + np.random.normal(0, 5.0)
            obs = TelemetryObservation(
                time=datetime.now() + timedelta(days=i),
                array_power=power,
                array_current=power / 30.0,
                array_voltage=30.0,
                cell_temperature=298.15,
                solar_irradiance=1361.0,
                incidence_angle=0.0,
                eclipse_factor=0.0
            )
            observations.append(obs)
        
        results = self.predictor.batch_update(observations)
        
        print(f"\n=== 批量更新 ===")
        print(f"处理观测数: {len(results)}")
        print(f"初始剩余因子: {results[0].remaining_factor_posterior_mean:.4f}")
        print(f"最终剩余因子: {results[-1].remaining_factor_posterior_mean:.4f}")
        
        self.assertEqual(len(results), 10)
        self.assertLess(results[-1].remaining_factor_posterior_mean, 
                       results[0].remaining_factor_posterior_mean)


if __name__ == '__main__':
    unittest.main(verbosity=2)
