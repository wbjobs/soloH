"""
系统测试文件
System Test File
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import unittest
from datetime import datetime, timedelta

from satellite_power_predictor import PowerPredictor, BatchProcessor
from satellite_power_predictor.orbit.tle_propagator import TLEData, TLEPropagator
from satellite_power_predictor.astronomy.celestial_calculator import CelestialCalculator
from satellite_power_predictor.occlusion.shadow_calculator import (
    ShadowCalculator, create_default_satellite_model, GeometryType, GeometryObject
)
from satellite_power_predictor.solar_cell.diode_model import (
    SolarCellModel, CellParameters, OperatingConditions, SolarArrayConfig, SolarArrayModel
)
from satellite_power_predictor.solar_cell.radiation_degradation import (
    RadiationDegradation, RadiationEnvironment, DegradationState
)
from satellite_power_predictor.power.power_predictor import (
    PowerPredictor, AttitudePoint, TemperatureModel
)


class TestTLEPropagator(unittest.TestCase):
    """测试TLE轨道传播器"""

    def setUp(self):
        """设置测试数据"""
        self.tle_name = "TEST_SAT"
        self.tle_line1 = "1 12345U 24001A   24001.00000000  .00000100  00000-0  10000-3 0  0001"
        self.tle_line2 = "2 12345  98.0000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
        self.tle_data = TLEData(name=self.tle_name, line1=self.tle_line1, line2=self.tle_line2)

    def test_tle_parsing(self):
        """测试TLE解析"""
        self.assertEqual(self.tle_data.name, self.tle_name)
        self.assertEqual(self.tle_data.norad_id, 12345)
        self.assertAlmostEqual(self.tle_data.inclination, 98.0, places=5)
        self.assertAlmostEqual(self.tle_data.eccentricity, 0.0001, places=5)
        self.assertAlmostEqual(self.tle_data.mean_motion, 15.0, places=5)

    def test_orbit_period(self):
        """测试轨道周期计算"""
        period = self.tle_data.get_orbital_period()
        expected = 86400.0 / 15.0
        self.assertAlmostEqual(period, expected, places=2)

    def test_propagation(self):
        """测试轨道传播"""
        propagator = TLEPropagator(self.tle_data)
        test_time = datetime(2024, 1, 1, 12, 0, 0)
        state = propagator.propagate(test_time)
        
        self.assertIsNotNone(state)
        self.assertEqual(state.time, test_time)
        self.assertEqual(state.position.shape, (3,))
        self.assertEqual(state.velocity.shape, (3,))
        self.assertGreater(state.altitude, 100)  # 至少100km

    def test_propagate_sequence(self):
        """测试时间序列传播"""
        propagator = TLEPropagator(self.tle_data)
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 1, 0, 10, 0)  # 10分钟
        
        times, states = propagator.propagate_sequence(start, end, step_sec=60.0)
        
        self.assertEqual(len(times), 11)
        self.assertEqual(len(states), 11)
        self.assertEqual(times[0], start)
        self.assertEqual(times[-1], end)


class TestCelestialCalculator(unittest.TestCase):
    """测试天体计算器"""

    def setUp(self):
        self.calculator = CelestialCalculator()

    def test_sun_position(self):
        """测试太阳位置计算"""
        test_time = datetime(2024, 3, 21, 12, 0, 0)  # 春分点
        sun_vec = self.calculator.calculate_sun_position(test_time)
        
        self.assertEqual(sun_vec.shape, (3,))
        self.assertAlmostEqual(np.linalg.norm(sun_vec), 1.0, places=6)
        # 春分时太阳赤纬接近0
        declination = np.arcsin(sun_vec[2]) * 180 / np.pi
        self.assertLess(abs(declination), 5.0)  # 应该小于5度

    def test_solar_irradiance(self):
        """测试太阳辐照度计算"""
        test_time = datetime(2024, 1, 1, 0, 0, 0)
        irradiance = self.calculator.calculate_solar_irradiance(test_time)
        
        self.assertGreater(irradiance, 1300)
        self.assertLess(irradiance, 1420)

    def test_eclipse_calculation(self):
        """测试地影计算"""
        # 卫星在地球向阳面
        sat_pos = np.array([7000, 0, 0])  # km
        sun_vec = np.array([1, 0, 0])
        sun_dist = 1.0
        
        factor, umbra, penumbra = self.calculator.calculate_eclipse(sat_pos, sun_vec, sun_dist)
        self.assertEqual(factor, 1.0)
        self.assertFalse(umbra)
        self.assertFalse(penumbra)
        
        # 卫星在地球背阳面
        sat_pos = np.array([-7000, 0, 0])
        factor, umbra, penumbra = self.calculator.calculate_eclipse(sat_pos, sun_vec, sun_dist)
        self.assertEqual(factor, 0.0)
        self.assertTrue(umbra)


class TestSolarCellModel(unittest.TestCase):
    """测试太阳能电池模型"""

    def setUp(self):
        self.cell_params = CellParameters()
        self.cell_model = SolarCellModel(self.cell_params)

    def test_operating_conditions(self):
        """测试工作条件创建"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        self.assertEqual(conditions.irradiance, 1361.0)
        self.assertEqual(conditions.temperature, 298.15)

    def test_short_circuit_current(self):
        """测试短路电流计算"""
        conditions = OperatingConditions(
            irradiance=1000.0,  # STC辐照度
            temperature=298.15  # STC温度
        )
        I_sc = self.cell_model.calculate_isc(conditions)
        
        self.assertGreater(I_sc, 0)
        self.assertAlmostEqual(I_sc, self.cell_params.I_sc_ref, delta=1.0)

    def test_open_circuit_voltage(self):
        """测试开路电压计算"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        V_oc = self.cell_model.calculate_voc(conditions)
        
        self.assertGreater(V_oc, 0)
        self.assertLess(V_oc, 1.0)

    def test_mpp_calculation(self):
        """测试最大功率点计算"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        I_mpp, V_mpp, P_mpp = self.cell_model.calculate_mpp(conditions)
        
        self.assertGreater(I_mpp, 0)
        self.assertGreater(V_mpp, 0)
        self.assertGreater(P_mpp, 0)
        self.assertAlmostEqual(P_mpp, I_mpp * V_mpp, places=3)

    def test_iv_curve(self):
        """测试I-V曲线计算"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        iv_curve = self.cell_model.calculate_iv_curve(conditions, num_points=50)
        
        self.assertEqual(len(iv_curve.voltage), 50)
        self.assertEqual(len(iv_curve.current), 50)
        self.assertEqual(len(iv_curve.power), 50)
        self.assertGreater(iv_curve.I_sc, 0)
        self.assertGreater(iv_curve.V_oc, 0)
        self.assertGreater(iv_curve.fill_factor, 0.5)

    def test_temperature_effect(self):
        """测试温度效应"""
        conditions_cold = OperatingConditions(irradiance=1361.0, temperature=253.15)  # -20°C
        conditions_hot = OperatingConditions(irradiance=1361.0, temperature=333.15)   # 60°C
        
        I_sc_cold = self.cell_model.calculate_isc(conditions_cold)
        I_sc_hot = self.cell_model.calculate_isc(conditions_hot)
        
        # 温度升高，I_sc应该略有增加
        self.assertGreater(I_sc_hot, I_sc_cold * 0.95)
        
        V_oc_cold = self.cell_model.calculate_voc(conditions_cold)
        V_oc_hot = self.cell_model.calculate_voc(conditions_hot)
        
        # 温度升高，V_oc应该降低
        self.assertLess(V_oc_hot, V_oc_cold)


class TestRadiationDegradation(unittest.TestCase):
    """测试辐射降解模型"""

    def setUp(self):
        self.rad_model = RadiationDegradation()

    def test_radiation_environment(self):
        """测试辐射环境创建"""
        env = RadiationEnvironment(
            altitude=400,
            inclination=51.6,
            f107=120.0,
            f107_avg=115.0
        )
        self.assertEqual(env.altitude, 400)
        self.assertEqual(env.inclination, 51.6)
        self.assertEqual(env.f107, 120.0)

    def test_flux_calculation(self):
        """测试通量计算"""
        env = RadiationEnvironment(
            altitude=400,
            inclination=51.6,
            f107=100.0,
            f107_avg=100.0
        )
        flux = self.rad_model.calculate_natural_environment_flux(env)
        
        self.assertGreater(len(flux.proton_flux), 0)
        self.assertGreater(len(flux.electron_flux), 0)
        self.assertEqual(len(flux.proton_flux), len(flux.proton_energies))

    def test_ddd_rate(self):
        """测试DDD率计算"""
        env = RadiationEnvironment(
            altitude=400,
            inclination=51.6,
            f107=100.0,
            f107_avg=100.0
        )
        flux = self.rad_model.calculate_natural_environment_flux(env)
        ddd_rate = self.rad_model.calculate_ddd_rate(flux)
        
        self.assertGreater(ddd_rate, 0)

    def test_remaining_factor(self):
        """测试剩余因子计算"""
        # 无剂量时剩余因子应为1
        rf, rf_isc, rf_voc, rf_pmax = self.rad_model.calculate_remaining_factor(0.0)
        self.assertAlmostEqual(rf, 1.0, places=6)
        self.assertAlmostEqual(rf_isc, 1.0, places=6)
        
        # 大剂量时剩余因子应小于1
        rf, rf_isc, rf_voc, rf_pmax = self.rad_model.calculate_remaining_factor(1e9)
        self.assertLess(rf, 1.0)
        self.assertGreater(rf, 0)

    def test_degradation_state_update(self):
        """测试退化状态更新"""
        initial_state = DegradationState(
            cumulative_ddd=0.0,
            remaining_factor=1.0,
            remaining_factor_isc=1.0,
            remaining_factor_voc=1.0,
            remaining_factor_pmax=1.0,
            elapsed_days=0.0
        )
        
        ddd_rate = 1e-10
        time_step = 86400  # 1天
        
        new_state = self.rad_model.update_degradation_state(
            initial_state, ddd_rate, time_step
        )
        
        self.assertGreater(new_state.cumulative_ddd, initial_state.cumulative_ddd)
        self.assertLess(new_state.remaining_factor, initial_state.remaining_factor)
        self.assertAlmostEqual(new_state.elapsed_days, 1.0, places=5)


class TestShadowCalculator(unittest.TestCase):
    """测试遮挡计算器"""

    def setUp(self):
        solar_array, occlusion_objects = create_default_satellite_model()
        self.shadow_calc = ShadowCalculator(solar_array, occlusion_objects)

    def test_occlusion_no_shadow(self):
        """测试无遮挡情况"""
        # 太阳从帆板正面入射，应该无遮挡
        sun_dir = np.array([1.0, 0.0, 0.0])  # 沿帆板法向
        sa_normal = np.array([1.0, 0.0, 0.0])
        
        result = self.shadow_calc.calculate_occlusion(sun_dir, sa_normal)
        
        self.assertGreater(result.visible_area_ratio, 0.8)
        self.assertLess(result.occlusion_factor, 0.2)

    def test_occlusion_back_side(self):
        """测试背面入射情况"""
        sun_dir = np.array([-1.0, 0.0, 0.0])  # 从背面入射
        sa_normal = np.array([1.0, 0.0, 0.0])
        
        result = self.shadow_calc.calculate_occlusion(sun_dir, sa_normal)
        
        self.assertEqual(result.visible_area_ratio, 0.0)
        self.assertEqual(result.occlusion_factor, 1.0)

    def test_effective_irradiance(self):
        """测试有效辐照度计算"""
        sun_dir = np.array([1.0, 0.0, 0.0])
        sa_normal = np.array([1.0, 0.0, 0.0])
        direct_irr = 1361.0
        
        eff_irr, occlusion = self.shadow_calc.calculate_effective_irradiance(
            sun_dir, direct_irr, sa_normal
        )
        
        self.assertGreater(eff_irr, 0)
        self.assertLessEqual(eff_irr, direct_irr)


class TestTemperatureModel(unittest.TestCase):
    """测试温度模型"""

    def setUp(self):
        self.temp_model = TemperatureModel()

    def test_equilibrium_temperature(self):
        """测试平衡温度计算"""
        # 完全日照条件
        T = self.temp_model.calculate_equilibrium_temperature(
            total_irradiance=1361.0,
            albedo_flux=50.0,
            earth_ir_flux=200.0,
            eclipse_factor=1.0
        )
        
        self.assertGreater(T, 250)
        self.assertLess(T, 400)  # 合理温度范围

    def test_eclipse_temperature(self):
        """测试地影中的温度"""
        T = self.temp_model.calculate_equilibrium_temperature(
            total_irradiance=0.0,
            albedo_flux=0.0,
            earth_ir_flux=200.0,
            eclipse_factor=0.0
        )
        
        self.assertGreater(T, 200)
        self.assertLess(T, 300)  # 地影中温度较低

    def test_transient_temperature(self):
        """测试瞬态温度计算"""
        current_T = 300.0
        # 突然进入地影
        T_new = self.temp_model.calculate_transient_temperature(
            current_temp=current_T,
            total_irradiance=0.0,
            albedo_flux=0.0,
            earth_ir_flux=200.0,
            eclipse_factor=0.0,
            time_step=60.0  # 1分钟
        )
        
        self.assertLess(T_new, current_T)  # 温度应该下降


class TestPowerPredictor(unittest.TestCase):
    """测试功率预测器"""

    def setUp(self):
        self.tle_data = TLEData(
            name="TEST_SAT",
            line1="1 12345U 24001A   24001.00000000  .00000100  00000-0  10000-3 0  0001",
            line2="2 12345  98.0000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
        )
        self.predictor = PowerPredictor(
            tle_data=self.tle_data,
            f107=100.0,
            f107_avg=100.0
        )

    def test_predict_single_orbit(self):
        """测试单轨道预测"""
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        
        result = self.predictor.predict_multi_orbit(
            n_orbits=1,
            start_time=start_time,
            time_step_sec=60.0  # 1分钟间隔，加快测试
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.satellite_name, "TEST_SAT")
        self.assertGreater(len(result.time_series), 0)
        
        # 检查轨道平均功率
        oa = result.orbit_average
        self.assertGreater(oa.average_power, 0)
        self.assertGreater(oa.peak_power, oa.average_power)
        self.assertGreater(oa.total_energy, 0)
        
        # 检查退化状态
        ds = result.degradation_state
        self.assertGreaterEqual(ds.remaining_factor, 0)
        self.assertLessEqual(ds.remaining_factor, 1.0)

    def test_attitude_sequence(self):
        """测试姿态序列"""
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        orbit_period = self.predictor.orbit_propagator.get_orbit_period()
        
        attitude_sequence = []
        for i in range(0, int(orbit_period), 300):
            t = start_time + timedelta(seconds=i)
            angle = (i / orbit_period) * 2 * np.pi
            normal = np.array([np.cos(angle), np.sin(angle), 0.1])
            normal = normal / np.linalg.norm(normal)
            attitude_sequence.append(AttitudePoint(time=t, sa_normal=normal))
        
        end_time = start_time + timedelta(seconds=orbit_period)
        result = self.predictor.predict(
            start_time=start_time,
            end_time=end_time,
            time_step_sec=120.0,
            attitude_sequence=attitude_sequence
        )
        
        self.assertIsNotNone(result)
        self.assertGreater(len(result.time_series), 0)

    def test_to_dataframe(self):
        """测试转换为DataFrame"""
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        result = self.predictor.predict_multi_orbit(
            n_orbits=1,
            start_time=start_time,
            time_step_sec=300.0
        )
        
        df = result.to_dataframe()
        self.assertEqual(len(df), len(result.time_series))
        self.assertIn('array_power_W', df.columns)
        self.assertIn('array_current_A', df.columns)
        self.assertIn('cell_temperature_K', df.columns)


class TestArrayModel(unittest.TestCase):
    """测试太阳能阵列模型"""

    def setUp(self):
        self.array_config = SolarArrayConfig(
            n_cells_series=40,
            n_strings_parallel=3,
            cell_params=CellParameters()
        )
        self.array_model = SolarArrayModel(self.array_config)

    def test_array_performance(self):
        """测试阵列性能计算"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        
        I_mpp, V_mpp, P_mpp, eff = self.array_model.calculate_array_performance(conditions)
        
        self.assertGreater(I_mpp, 0)
        self.assertGreater(V_mpp, 0)
        self.assertGreater(P_mpp, 0)
        self.assertGreater(eff, 0)
        
        # 检查电压是否接近总线电压
        expected_V = self.array_config.cell_params.V_mpp_ref * self.array_config.n_cells_series
        self.assertAlmostEqual(V_mpp, expected_V, delta=5.0)

    def test_operating_current(self):
        """测试工作电流计算"""
        conditions = OperatingConditions(
            irradiance=1361.0,
            temperature=298.15
        )
        
        I = self.array_model.calculate_operating_current(conditions, operating_voltage=25.0)
        self.assertGreater(I, 0)


def run_tests():
    """运行所有测试"""
    unittest.main(argv=['first-arg-is-ignored'], exit=False, verbosity=2)


if __name__ == "__main__":
    print("=" * 80)
    print("卫星太阳能电池板功率预测系统 - 系统测试")
    print("=" * 80)
    print()
    
    run_tests()
