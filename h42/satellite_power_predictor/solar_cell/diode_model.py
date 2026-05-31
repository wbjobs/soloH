"""
太阳能电池模型模块
Solar Cell Model Module

功能：
- 单二极管等效电路模型 (Single Diode Model, SDM)
- 双二极管等效电路模型 (Double Diode Model, DDM)
- I-V特性曲线计算
- 最大功率点 (MPP) 追踪
- 温度修正模型
- 辐照度修正模型
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict
import numpy as np
from scipy.optimize import fsolve, minimize_scalar
from enum import Enum

from ..utils.constants import (
    STC_TEMPERATURE, STC_IRRADIANCE,
    BOLTZMANN_CONSTANT, ELEMENTARY_CHARGE,
    DEFAULT_TEMP_COEFF_VOC, DEFAULT_TEMP_COEFF_ISC,
    DEFAULT_TEMP_COEFF_PMAX
)


class CellFailureMode(Enum):
    """电池失效模式"""
    NORMAL = "normal"          # 正常工作
    OPEN_CIRCUIT = "open"      # 开路失效
    SHORT_CIRCUIT = "short"    # 短路失效
    PARTIAL = "partial"        # 部分失效（效率降低）


@dataclass
class CellParameters:
    """太阳能电池参数"""
    I_sc_ref: float = 8.6  # 短路电流 (A), STC条件下
    V_oc_ref: float = 0.65  # 开路电压 (V), STC条件下
    I_mpp_ref: float = 8.1  # 最大功率点电流 (A), STC条件下
    V_mpp_ref: float = 0.54  # 最大功率点电压 (V), STC条件下
    n: float = 1.3  # 二极管理想因子
    R_s: float = 0.004  # 串联电阻 (Ω)
    R_sh: float = 500.0  # 并联电阻 (Ω)
    alpha_isc: float = DEFAULT_TEMP_COEFF_ISC  # 短路电流温度系数 (1/K)
    beta_voc: float = DEFAULT_TEMP_COEFF_VOC  # 开路电压温度系数 (1/K)
    gamma_pmax: float = DEFAULT_TEMP_COEFF_PMAX  # 最大功率温度系数 (1/K)
    area: float = 0.025  # 电池面积 (m^2)
    efficiency_ref: float = 0.225  # 参考转换效率

    @property
    def P_max_ref(self) -> float:
        """参考最大功率 (STC) 最大功率 (W)"""
        return self.I_mpp_ref * self.V_mpp_ref


@dataclass
class CellFailureState:
    """电池失效状态"""
    failure_mode: CellFailureMode = CellFailureMode.NORMAL
    partial_degradation: float = 1.0  # 部分失效时的剩余因子 (0-1)
    bypass_diode_active: bool = False  # 旁路二极管是否激活
    
    @property
    def is_failed(self) -> bool:
        return self.failure_mode != CellFailureMode.NORMAL


@dataclass
class OperatingConditions:
    """电池工作条件"""
    irradiance: float  # 辐照度 (W/m^2)
    temperature: float  # 温度 (K)
    remaining_factor: float = 1.0  # 剩余因子 (辐射降解后)
    
    # 单片电池不均匀辐照度 (可选, 长度为总电池片数)
    cell_irradiances: Optional[np.ndarray] = None
    # 单片电池失效状态 (可选, 长度为总电池片数)
    cell_failures: Optional[List[CellFailureState]] = None


@dataclass
class IVCurve:
    """I-V曲线数据"""
    voltage: np.ndarray
    current: np.ndarray
    power: np.ndarray
    I_sc: float
    V_oc: float
    I_mpp: float
    V_mpp: float
    P_mpp: float
    fill_factor: float
    efficiency: float


class SolarCellModel:
    """
    太阳能电池模型
    基于单二极管等效电路模型
    """

    def __init__(self, cell_params: CellParameters):
        """
        初始化太阳能电池模型
        
        参数:
            cell_params: 电池参数
        """
        self.params = cell_params
        self._k = BOLTZMANN_CONSTANT
        self._q = ELEMENTARY_CHARGE

    def _thermal_voltage(self, T: float) -> float:
        """
        计算热电压 V_t = kT/q
        
        参数:
            T: 温度 (K)
            
        返回:
            热电压 (V)
        """
        return self._k * T / self._q

    def _saturation_current(self, T: float, T_ref: float = STC_TEMPERATURE) -> float:
        """
        计算反向饱和电流 I_0
        
        参数:
            T: 工作温度 (K)
            T_ref: 参考温度 (K)
            
        返回:
            反向饱和电流 (A)
        """
        V_t = self._thermal_voltage(T)
        V_t_ref = self._thermal_voltage(T_ref)
        
        I_0_ref = (self.params.I_sc_ref / 
                   (np.exp(self.params.V_oc_ref / (self.params.n * V_t_ref) - 1)))
        
        E_g = 1.12  # eV, 硅的带隙
        delta_T = T - T_ref
        
        I_0 = I_0_ref * (T / T_ref) ** 3 * np.exp(
            E_g * self._q / (self._k * self.params.n) * (
                1 / T_ref - 1 / T))
        
        return I_0

    def _photocurrent(self, 
                       G: float, 
                       T: float, 
                       T_ref: float = STC_TEMPERATURE) -> float:
        """
        计算光生电流 I_ph
        
        参数:
            G: 辐照度 (W/m^2)
            T: 工作温度 (K)
            T_ref: 参考温度 (K)
            
        返回:
            光生电流 (A)
        """
        delta_T = T - T_ref
        I_ph = (G / STC_IRRADIANCE) * self.params.I_sc_ref * (1 + self.params.alpha_isc * delta_T)
        
        return I_ph

    def calculate_current(self, 
                          V: float, 
                          conditions: OperatingConditions,
                          remaining_factor: float = 1.0) -> float:
        """
        根据单二极管模型计算电流 I(V)
        
        参数:
            V: 电压 (V)
            conditions: 工作条件
            remaining_factor: 辐射降解剩余因子
            
        返回:
            电流 (A)
        """
        G = conditions.irradiance
        T = conditions.temperature
        
        if G <= 0:
            return 0.0
        
        V_t = self._thermal_voltage(T)
        I_0 = self._saturation_current(T)
        I_ph = self._photocurrent(G, T)
        
        I_ph *= remaining_factor
        I_0 /= remaining_factor ** 0.5

        def diode_eq(I):
            return (I_ph - I - I_0 * (np.exp((V + I * self.params.R_s) / (self.params.n * V_t) - 1))
                    - (V + I * self.params.R_s) / self.params.R_sh)
        
        I_initial = I_ph * 0.9
        try:
            I_solution = fsolve(diode_eq, I_initial, full_output=False)
            I = float(I_solution[0])
            # 不截断为0，允许负电流（用于正确计算MPP）
            return I
        except:
            # 退化模型：当求解失败时使用简化模型
            I = I_ph - V / self.params.R_sh - I_0 * (np.exp(V / (self.params.n * V_t)) - 1)
            return float(I)

    def calculate_iv_curve(self,
                            conditions: OperatingConditions,
                            remaining_factor: float = 1.0,
                            num_points: int = 200) -> IVCurve:
        """
        计算完整的I-V曲线
        
        参数:
            conditions: 工作条件
            remaining_factor: 剩余因子
            num_points: 曲线点数
            
        返回:
            IVCurve对象
        """
        V_oc = self.calculate_voc(conditions, remaining_factor)
        voltages = np.linspace(0, V_oc * 1.05, num_points)
        
        currents = np.array([
            self.calculate_current(v, conditions, remaining_factor)
            for v in voltages
        ])
        
        powers = voltages * currents
        
        I_sc = self.calculate_isc(conditions, remaining_factor)
        max_idx = np.argmax(powers)
        P_mpp = powers[max_idx]
        V_mpp = voltages[max_idx]
        I_mpp = currents[max_idx]
        
        fill_factor = (I_mpp * V_mpp / (I_sc * V_oc)) if (I_sc * V_oc) > 0 else 0
        efficiency = P_mpp / (conditions.irradiance * self.params.area) if conditions.irradiance > 0 else 0
        
        return IVCurve(
            voltage=voltages,
            current=currents,
            power=powers,
            I_sc=I_sc,
            V_oc=V_oc,
            I_mpp=I_mpp,
            V_mpp=V_mpp,
            P_mpp=P_mpp,
            fill_factor=fill_factor,
            efficiency=efficiency
        )

    def calculate_isc(self,
                       conditions: OperatingConditions,
                       remaining_factor: float = 1.0) -> float:
        """
        计算短路电流 I_sc
        
        参数:
            conditions: 工作条件
            remaining_factor: 剩余因子
            
        返回:
            短路电流 (A)
        """
        if conditions.irradiance <= 0:
            return 0.0
        
        I_ph = self._photocurrent(conditions.irradiance, conditions.temperature)
        return I_ph * remaining_factor

    def calculate_voc(self,
                       conditions: OperatingConditions,
                       remaining_factor: float = 1.0) -> float:
        """
        计算开路电压 V_oc
        
        参数:
            conditions: 工作条件
            remaining_factor: 剩余因子
            
        返回:
            开路电压 (V)
        """
        if conditions.irradiance <= 0:
            return 0.0
        
        T = conditions.temperature
        V_t = self._thermal_voltage(T)
        I_0 = self._saturation_current(T)
        I_ph = self._photocurrent(conditions.irradiance, T) * remaining_factor
        I_0_eff = I_0 / remaining_factor ** 0.5
        
        V_oc = self.params.n * V_t * np.log(I_ph / I_0_eff + 1)
        
        return V_oc

    def calculate_mpp(self,
                      conditions: OperatingConditions,
                      remaining_factor: float = 1.0) -> Tuple[float, float, float]:
        """
        计算最大功率点 (MPP)
        
        参数:
            conditions: 工作条件
            remaining_factor: 剩余因子
            
        返回:
            (I_mpp, V_mpp, P_mpp)
        """
        if conditions.irradiance <= 0:
            return 0.0, 0.0, 0.0
        
        def power_neg(V):
            I = self.calculate_current(V, conditions, remaining_factor)
            return -V * I
        
        V_oc = self.calculate_voc(conditions, remaining_factor)
        
        try:
            result = minimize_scalar(
                power_neg,
                bounds=(0, V_oc),
                method='bounded'
            )
            V_mpp = result.x
            I_mpp = self.calculate_current(V_mpp, conditions, remaining_factor)
            P_mpp = V_mpp * I_mpp
            return I_mpp, V_mpp, P_mpp
        except:
            iv = self.calculate_iv_curve(conditions, remaining_factor, num_points=100)
            return iv.I_mpp, iv.V_mpp, iv.P_mpp

    def apply_temperature_correction(self,
                                     base_current: float,
                                     base_temperature: float,
                                     target_temperature: float,
                                     parameter_type: str = 'pmax') -> float:
        """
        应用温度修正
        
        参数:
            base_current: 基准电流
            base_temperature: 基准温度 (K)
            target_temperature: 目标温度 (K)
            parameter_type: 参数类型 ('isc', 'voc', 'pmax'
            
        返回:
            修正后的值
        """
        delta_T = target_temperature - base_temperature
        
        if parameter_type == 'isc':
            coeff = self.params.alpha_isc
        elif parameter_type == 'voc':
            coeff = self.params.beta_voc
        else:
            coeff = self.params.gamma_pmax
        
        return base_current * (1 + coeff * delta_T)

    def apply_irradiance_correction(self,
                                 base_value: float,
                                 base_irradiance: float,
                                 target_irradiance: float) -> float:
        """
        应用辐照度修正
        
        参数:
            base_value: 基准值
            base_irradiance: 基准辐照度 (W/m^2)
            target_irradiance: 目标辐照度 (W/m^2)
            
        返回:
            修正后的值
        """
        if base_irradiance <= 0:
            return 0.0
        return base_value * (target_irradiance / base_irradiance)


@dataclass
class SolarArrayConfig:
    """太阳能帆板配置"""
    n_cells_series: int = 40  # 串联电池片数
    n_strings_parallel: int = 3  # 并联支路数
    cell_params: CellParameters = field(default_factory=CellParameters)
    bus_voltage: float = 28.0  # 总线电压 (V)
    degradation_factor: float = 0.98  # 布线损耗因子
    blocking_diode_drop: float = 0.7  # 阻塞二极管压降 (V)
    
    # 二极管参数
    bypass_diode_threshold: float = 0.6  # 旁路二极管导通阈值电压 (V)
    bypass_diode_drop: float = 0.4  # 旁路二极管导通压降 (V)
    bypass_diode_group_size: int = 10  # 每组串联电池片的旁路二极管数量
    string_blocking_diode_drop: float = 0.7  # 支路阻塞二极管压降 (V)
    
    # 热斑保护
    hot_spot_protection: bool = True
    reverse_bias_voltage_limit: float = 15.0  # 反向偏压极限 (V)

    @property
    def total_cells(self) -> int:
        """总电池片数"""
        return self.n_cells_series * self.n_strings_parallel

    @property
    def total_area(self) -> float:
        """总面积 (m^2)"""
        return self.total_cells * self.cell_params.area

    def calculate_array_voltage(self, V_cell: float) -> float:
        """计算阵列电压"""
        return V_cell * self.n_cells_series - self.blocking_diode_drop

    def calculate_array_current(self, I_cell: float) -> float:
        """计算阵列电流"""
        return I_cell * self.n_strings_parallel * self.degradation_factor


@dataclass
class ArrayReconfigurationResult:
    """阵列电路重配结果"""
    effective_series_cells: int  # 有效串联电池片数
    effective_parallel_strings: int  # 有效并联支路数
    bypass_diodes_active: List[bool]  # 各旁路二极管状态
    blocked_strings: List[bool]  # 各支路阻塞状态
    string_currents: np.ndarray  # 各支路电流 (A)
    string_voltages: np.ndarray  # 各支路电压 (V)
    reconfigured: bool  # 是否发生了电路重配
    failure_summary: Dict[str, int]  # 失效统计


class SolarArrayModel:
    """
    太阳能帆板阵列模型
    多个电池片串并联组成的阵列
    支持单片电池失效的电路重配逻辑
    """

    def __init__(self, array_config: SolarArrayConfig):
        """
        初始化太阳能帆板阵列模型
        
        参数:
            array_config: 阵列配置
        """
        self.config = array_config
        self.cell_model = SolarCellModel(array_config.cell_params)
        
        # 初始化电池失效状态（全部正常）
        self.cell_failures = [
            CellFailureState(failure_mode=CellFailureMode.NORMAL)
            for _ in range(self.config.total_cells)
        ]
        
        # 旁路二极管状态
        n_groups = int(np.ceil(self.config.n_cells_series / self.config.bypass_diode_group_size))
        self.bypass_diodes = [False] * n_groups * self.config.n_strings_parallel
        
        # 支路阻塞状态
        self.string_blocked = [False] * self.config.n_strings_parallel

    def set_cell_failure(self, cell_index: int, failure_mode: CellFailureMode, 
                         partial_degradation: float = 0.0):
        """
        设置单片电池的失效状态
        
        参数:
            cell_index: 电池片索引 (0到total_cells-1)
            failure_mode: 失效模式
            partial_degradation: 部分失效时的剩余因子 (0-1)
        """
        if 0 <= cell_index < self.config.total_cells:
            self.cell_failures[cell_index] = CellFailureState(
                failure_mode=failure_mode,
                partial_degradation=partial_degradation,
                bypass_diode_active=False
            )
        else:
            raise ValueError(f"cell_index {cell_index} out of range [0, {self.config.total_cells})")

    def reset_cell_failures(self):
        """重置所有电池片为正常状态"""
        self.cell_failures = [
            CellFailureState(failure_mode=CellFailureMode.NORMAL)
            for _ in range(self.config.total_cells)
        ]
        self.bypass_diodes = [False] * len(self.bypass_diodes)
        self.string_blocked = [False] * self.config.n_strings_parallel

    def _analyze_string_reconfiguration(self, 
                                       string_idx: int,
                                       string_voltage: float,
                                       conditions: OperatingConditions,
                                       remaining_factor: float) -> Tuple[float, bool, List[bool]]:
        """
        分析单条支路的电路重配
        
        参数:
            string_idx: 支路索引
            string_voltage: 支路电压 (V)
            conditions: 工作条件
            remaining_factor: 剩余因子
            
        返回:
            (支路电流, 支路是否被阻塞, 激活的旁路二极管列表)
        """
        n_series = self.config.n_cells_series
        group_size = self.config.bypass_diode_group_size
        n_groups = int(np.ceil(n_series / group_size))
        
        # 获取该支路的电池失效状态
        start_idx = string_idx * n_series
        end_idx = start_idx + n_series
        string_failures = self.cell_failures[start_idx:end_idx]
        
        # 获取单片电池辐照度
        cell_irradiances = None
        if conditions.cell_irradiances is not None:
            if len(conditions.cell_irradiances) == self.config.total_cells:
                cell_irradiances = conditions.cell_irradiances[start_idx:end_idx]
        
        # 检查失效电池，分析旁路二极管状态
        bypass_activated = [False] * n_groups
        short_circuit_cells = []
        open_circuit_cells = []
        partial_cells = []
        
        for i, failure in enumerate(string_failures):
            if failure.failure_mode == CellFailureMode.SHORT_CIRCUIT:
                short_circuit_cells.append(i)
            elif failure.failure_mode == CellFailureMode.OPEN_CIRCUIT:
                open_circuit_cells.append(i)
            elif failure.failure_mode == CellFailureMode.PARTIAL:
                partial_cells.append(i)
        
        # 计算各组的有效电池数
        effective_cells_per_group = []
        total_effective_cells = 0
        
        for g in range(n_groups):
            group_start = g * group_size
            group_end = min(group_start + group_size, n_series)
            group_cells = list(range(group_start, group_end))
            
            n_short = sum(1 for c in group_cells if c in short_circuit_cells)
            n_open = sum(1 for c in group_cells if c in open_circuit_cells)
            n_active = len(group_cells) - n_short - n_open
            
            # 如果有开路电池，该组需要旁路
            if n_open > 0:
                bypass_activated[g] = True
                effective_cells_per_group.append(0)
            else:
                effective_cells_per_group.append(n_active)
                total_effective_cells += n_active
        
        # 检查是否整条支路失效
        if total_effective_cells == 0:
            return 0.0, True, bypass_activated
        
        # 计算有效串联电池数
        effective_series = sum(effective_cells_per_group)
        
        # 考虑旁路二极管压降（每个激活的旁路二极管贡献一个压降）
        n_bypass_active = sum(1 for b in bypass_activated if b)
        V_bypass_drop = n_bypass_active * self.config.bypass_diode_drop
        
        # 有效电压需要扣除旁路二极管压降
        # 电池总电压 = 支路电压 + 旁路二极管压降
        V_cells_total = string_voltage + V_bypass_drop
        
        # 每片电池的电压降
        V_per_cell = V_cells_total / max(1, effective_series)
        
        # 限制单片电池反向电压（防止热斑）
        if V_per_cell < -self.config.reverse_bias_voltage_limit:
            V_per_cell = -self.config.reverse_bias_voltage_limit
        
        # 计算各电池片的电流（取最小值）
        I_string = float('inf')
        
        for g in range(n_groups):
            if bypass_activated[g]:
                continue
                
            group_start = g * group_size
            group_end = min(group_start + group_size, n_series)
            
            for cell_in_group in range(group_start, group_end):
                # 跳过短路电池
                if cell_in_group in short_circuit_cells:
                    continue
                
                # 获取该电池的工作条件
                cell_irr = conditions.irradiance
                if cell_irradiances is not None:
                    cell_irr = cell_irradiances[cell_in_group]
                
                cell_remaining = remaining_factor
                if cell_in_group in partial_cells:
                    cell_remaining *= self.cell_failures[start_idx + cell_in_group].partial_degradation
                
                cell_conditions = OperatingConditions(
                    irradiance=cell_irr,
                    temperature=conditions.temperature,
                    remaining_factor=cell_remaining
                )
                
                I_cell = self.cell_model.calculate_current(
                    V_per_cell, cell_conditions, cell_remaining
                )
                
                I_string = min(I_string, I_cell)
        
        if I_string == float('inf'):
            I_string = 0.0
        
        # 热斑保护：检查反向偏压
        if self.config.hot_spot_protection:
            self._check_hot_spot_protection(
                string_idx, I_string, string_voltage, 
                string_failures, effective_cells_per_group, bypass_activated
            )
        
        return I_string, False, bypass_activated

    def _check_hot_spot_protection(self, string_idx: int, I_string: float, V_string: float,
                                   string_failures: List[CellFailureState],
                                   effective_cells_per_group: List[int],
                                   bypass_activated: List[bool]):
        """
        热斑保护：检测并处理反向偏压过高的情况
        """
        n_series = self.config.n_cells_series
        group_size = self.config.bypass_diode_group_size
        
        for g, n_effective in enumerate(effective_cells_per_group):
            if bypass_activated[g]:
                continue
                
            # 检查该组是否有被遮挡的电池
            group_start = g * group_size
            group_end = min(group_start + group_size, n_series)
            
            for cell_in_group in range(group_start, group_end):
                if (string_failures[cell_in_group].failure_mode == CellFailureMode.PARTIAL and
                    string_failures[cell_in_group].partial_degradation < 0.5):
                    # 部分失效严重，可能产生热斑
                    # 激活旁路二极管
                    bypass_activated[g] = True
                    break

    def analyze_reconfiguration(self,
                                 conditions: OperatingConditions,
                                 string_voltage: float,
                                 remaining_factor: float = 1.0) -> ArrayReconfigurationResult:
        """
        分析整个阵列的电路重配状态
        
        参数:
            conditions: 工作条件
            string_voltage: 每条支路的电压 (V)
            remaining_factor: 剩余因子
            
        返回:
            ArrayReconfigurationResult
        """
        n_strings = self.config.n_strings_parallel
        n_series = self.config.n_cells_series
        group_size = self.config.bypass_diode_group_size
        
        string_currents = np.zeros(n_strings)
        string_blocked = [False] * n_strings
        all_bypass = []
        total_effective_cells = 0
        
        total_effective_cells_list = []
        for s in range(n_strings):
            I, blocked, bypass = self._analyze_string_reconfiguration(
                s, string_voltage, conditions, remaining_factor
            )
            string_currents[s] = I
            string_blocked[s] = blocked
            all_bypass.extend(bypass)
            
            if not blocked:
                n_groups = int(np.ceil(n_series / group_size))
                string_effective = 0
                
                # 获取该支路的失效信息
                start_idx = s * n_series
                end_idx = start_idx + n_series
                string_failures = self.cell_failures[start_idx:end_idx]
                
                for g, bypass_active in enumerate(bypass):
                    if not bypass_active:
                        group_start = g * group_size
                        group_end = min(group_start + group_size, n_series)
                        group_cells = list(range(group_start, group_end))
                        
                        # 计算该组的有效电池数（扣除短路和开路）
                        n_short = sum(1 for c in group_cells 
                                     if string_failures[c].failure_mode == CellFailureMode.SHORT_CIRCUIT)
                        n_open = sum(1 for c in group_cells 
                                    if string_failures[c].failure_mode == CellFailureMode.OPEN_CIRCUIT)
                        n_active = len(group_cells) - n_short - n_open
                        string_effective += n_active
                        
                total_effective_cells_list.append(string_effective)
                total_effective_cells += string_effective
        
        # 计算各支路最小有效电池数（串联瓶颈）
        avg_series = (sum(total_effective_cells_list) / len(total_effective_cells_list) 
                      if total_effective_cells_list else 0)
        
        # 统计失效情况
        failure_summary = {
            'normal': sum(1 for f in self.cell_failures if f.failure_mode == CellFailureMode.NORMAL),
            'open_circuit': sum(1 for f in self.cell_failures if f.failure_mode == CellFailureMode.OPEN_CIRCUIT),
            'short_circuit': sum(1 for f in self.cell_failures if f.failure_mode == CellFailureMode.SHORT_CIRCUIT),
            'partial': sum(1 for f in self.cell_failures if f.failure_mode == CellFailureMode.PARTIAL)
        }
        
        reconfigured = (any(all_bypass) or any(string_blocked) or 
                       failure_summary['open_circuit'] > 0 or 
                       failure_summary['short_circuit'] > 0)
        
        return ArrayReconfigurationResult(
            effective_series_cells=int(round(avg_series)) if avg_series > 0 else 0,
            effective_parallel_strings=n_strings - sum(string_blocked),
            bypass_diodes_active=all_bypass,
            blocked_strings=string_blocked,
            string_currents=string_currents,
            string_voltages=np.array([string_voltage] * n_strings),
            reconfigured=reconfigured,
            failure_summary=failure_summary
        )

    def calculate_array_performance(self,
                                 conditions: OperatingConditions,
                                 remaining_factor: float = 1.0) -> Tuple[float, float, float, float]:
        """
        计算阵列性能参数（考虑电池失效和电路重配）
        
        参数:
            conditions: 工作条件
            remaining_factor: 剩余因子
            
        返回:
            (I_mpp_array, V_mpp_array, P_mpp_array, efficiency)
        """
        # 首先估计开路电压（使用全部电池）
        n_series = self.config.n_cells_series
        n_parallel = self.config.n_strings_parallel
        
        # 先分析重配状态，确定有效电池数
        # 先用一个估计的支路电压
        V_cell_ref = self.config.cell_params.V_mpp_ref
        V_string_est = V_cell_ref * n_series
        
        recon_result = self.analyze_reconfiguration(
            conditions, V_string_est, remaining_factor
        )
        
        # 扫描电压寻找MPP
        # 使用有效电池数估计电压范围
        if recon_result.effective_series_cells > 0:
            V_cell_ref = self.config.cell_params.V_oc_ref
            V_oc_est = V_cell_ref * recon_result.effective_series_cells
        else:
            V_oc_est = V_cell_ref * n_series
        
        V_oc_est = max(V_oc_est, 1.0)  # 确保至少1V
        
        n_points = 60
        voltages = np.linspace(0, V_oc_est * 1.05, n_points)
        powers = np.zeros(n_points)
        currents = np.zeros(n_points)
        
        for i, V in enumerate(voltages):
            I = self.calculate_operating_current(
                conditions, V, remaining_factor
            )
            currents[i] = I
            powers[i] = V * I
        
        max_idx = np.argmax(powers)
        P_mpp = float(powers[max_idx])
        V_mpp = float(voltages[max_idx])
        I_mpp = float(currents[max_idx])
        
        # 计算效率
        if conditions.cell_irradiances is not None:
            total_irr = np.sum(conditions.cell_irradiances) * self.config.cell_params.area
        else:
            total_irr = conditions.irradiance * self.config.total_area
            
        efficiency = P_mpp / total_irr if total_irr > 0 else 0
        
        return I_mpp, V_mpp, P_mpp, efficiency

    def calculate_operating_current(self,
                                    conditions: OperatingConditions,
                                    operating_voltage: float,
                                    remaining_factor: float = 1.0) -> float:
        """
        计算在给定工作电压下的阵列输出电流（考虑电路重配）
        
        参数:
            conditions: 工作条件
            operating_voltage: 工作电压 (V)
            remaining_factor: 剩余因子
            
        返回:
            输出电流 (A)
        """
        # 检查是否有电池失效
        has_failures = any(f.is_failed for f in self.cell_failures)
        
        if not has_failures and conditions.cell_irradiances is None:
            # 无失效，使用简化模型
            V_cell_eff = (operating_voltage + self.config.blocking_diode_drop) / self.config.n_cells_series
            
            I_cell = self.cell_model.calculate_current(
                V_cell_eff, conditions, remaining_factor
            )
            
            return self.config.calculate_array_current(I_cell)
        
        # 有失效，使用电路重配分析
        n_strings = self.config.n_strings_parallel
        
        # 每条支路的电压（并联电路，每条支路电压相同，加上阻塞二极管压降）
        string_voltage = operating_voltage + self.config.string_blocking_diode_drop
        
        recon_result = self.analyze_reconfiguration(conditions, string_voltage, remaining_factor)
        
        # 计算总电流（只有未阻塞的支路有电流）
        total_current = 0.0
        for s in range(n_strings):
            if not recon_result.blocked_strings[s]:
                total_current += recon_result.string_currents[s]
        
        # 应用布线损耗因子
        total_current *= self.config.degradation_factor
        
        return max(0.0, total_current)

    def calculate_short_circuit_current(self,
                                      conditions: OperatingConditions,
                                      remaining_factor: float = 1.0) -> float:
        """计算阵列短路电流（考虑电路重配）"""
        has_failures = any(f.is_failed for f in self.cell_failures)
        
        if not has_failures and conditions.cell_irradiances is None:
            I_sc_cell = self.cell_model.calculate_isc(conditions, remaining_factor)
            return self.config.calculate_array_current(I_sc_cell)
        
        # 有失效，使用电路重配分析
        return self.calculate_operating_current(conditions, 0.0, remaining_factor)

    def calculate_open_circuit_voltage(self,
                                     conditions: OperatingConditions,
                                     remaining_factor: float = 1.0) -> float:
        """计算阵列开路电压（考虑电路重配）"""
        has_failures = any(f.is_failed for f in self.cell_failures)
        
        if not has_failures and conditions.cell_irradiances is None:
            V_oc_cell = self.cell_model.calculate_voc(conditions, remaining_factor)
            return self.config.calculate_array_voltage(V_oc_cell)
        
        # 有失效，使用迭代法求开路电压
        # 首先使用二分法寻找电流为零的电压
        V_low = 0.0
        V_high = self.config.n_cells_series * self.config.cell_params.V_oc_ref * 1.5
        
        for _ in range(50):
            V_mid = (V_low + V_high) / 2
            I_mid = self.calculate_operating_current(conditions, V_mid, remaining_factor)
            if I_mid > 0:
                V_low = V_mid
            else:
                V_high = V_mid
            if abs(V_high - V_low) < 1e-4:
                break
        
        return (V_low + V_high) / 2

    def calculate_string_iv_curve(self,
                                   string_idx: int,
                                   conditions: OperatingConditions,
                                   remaining_factor: float = 1.0,
                                   num_points: int = 100) -> IVCurve:
        """
        计算单条支路的I-V曲线
        
        参数:
            string_idx: 支路索引
            conditions: 工作条件
            remaining_factor: 剩余因子
            num_points: 曲线点数
            
        返回:
            IVCurve对象
        """
        # 先分析重配状态，确定有效电池数
        V_ref = self.config.cell_params.V_mpp_ref * self.config.n_cells_series
        recon = self.analyze_reconfiguration(conditions, V_ref, remaining_factor)
        
        # 获取该支路的有效电池数
        n_series = self.config.n_cells_series
        group_size = self.config.bypass_diode_group_size
        n_groups = int(np.ceil(n_series / group_size))
        
        # 获取该支路的旁路二极管状态
        string_start = string_idx * n_groups
        string_end = string_start + n_groups
        bypass_for_string = recon.bypass_diodes_active[string_start:string_end]
        
        # 计算有效电池数
        effective_cells = 0
        for g in range(n_groups):
            if not bypass_for_string[g]:
                group_start = g * group_size
                group_end = min(group_start + group_size, n_series)
                effective_cells += (group_end - group_start)
        
        # 估计开路电压
        if effective_cells > 0:
            V_oc_est = effective_cells * self.config.cell_params.V_oc_ref
        else:
            V_oc_est = self.config.n_cells_series * self.config.cell_params.V_oc_ref
        
        V_oc_est = max(V_oc_est, 1.0)
        
        voltages = np.linspace(0, V_oc_est * 1.05, num_points)
        currents = np.zeros(num_points)
        
        for i, V in enumerate(voltages):
            I, _, _ = self._analyze_string_reconfiguration(
                string_idx, V, conditions, remaining_factor
            )
            currents[i] = I
        
        powers = voltages * currents
        
        I_sc = currents[0]
        max_idx = np.argmax(powers)
        P_mpp = powers[max_idx]
        V_mpp = voltages[max_idx]
        I_mpp = currents[max_idx]
        
        # 计算实际开路电压
        V_oc = 0.0
        for i in range(num_points - 1):
            if currents[i] > 0 and currents[i + 1] <= 0:
                # 线性插值
                if abs(currents[i] - currents[i + 1]) > 1e-10:
                    V_oc = voltages[i] + currents[i] * (voltages[i + 1] - voltages[i]) / (currents[i] - currents[i + 1])
                break
        
        if V_oc == 0.0 and currents[-1] > 0:
            V_oc = voltages[-1]
        
        fill_factor = (I_mpp * V_mpp / (I_sc * V_oc)) if (I_sc * V_oc) > 0 else 0
        efficiency = P_mpp / (conditions.irradiance * self.config.total_area / self.config.n_strings_parallel) if conditions.irradiance > 0 else 0
        
        return IVCurve(
            voltage=voltages,
            current=currents,
            power=powers,
            I_sc=I_sc,
            V_oc=V_oc,
            I_mpp=I_mpp,
            V_mpp=V_mpp,
            P_mpp=P_mpp,
            fill_factor=fill_factor,
            efficiency=efficiency
        )


@dataclass
class TransientState:
    """
    瞬态响应状态
    
    描述电池在阴影区和再入影过程中的电压/电流瞬态响应
    """
    voltage: float  # 当前电压 (V)
    current: float  # 当前电流 (A)
    steady_state_voltage: float  # 稳态电压 (V)
    steady_state_current: float  # 稳态电流 (A)
    time_since_transition: float  # 距状态切换的时间 (s)
    is_in_eclipse: bool  # 是否在阴影区
    settling_complete: bool  # 是否已达到稳态
    junction_charge: float  # 结电容电荷量 (C)


class TransientResponseModel:
    """
    太阳能电池瞬态响应模型
    
    功能：
    - 阴影区（地影）电池电压跌落的瞬态响应（指数衰减）
    - 再入影（出地影）电压恢复的瞬态响应（指数上升）
    - 考虑结电容、旁路电容、布线电感的影响
    - 与温度瞬态响应的耦合
    - 支持旁路二极管激活/关闭的瞬态过程
    """
    
    def __init__(self,
                 array_config: SolarArrayConfig,
                 junction_capacitance_per_cell: float = 1.0e-6,  # F/片
                 bypass_capacitance: float = 100.0e-6,  # F/组
                 wiring_inductance: float = 1.0e-6,  # H
                 voltage_settling_time: float = 0.5,  # 电压稳定时间常数 (s)
                 current_settling_time: float = 0.1,  # 电流稳定时间常数 (s)
                 diode_recovery_time: float = 10.0e-6):  # 二极管反向恢复时间 (s)
        """
        初始化瞬态响应模型
        
        参数:
            array_config: 太阳能阵列配置
            junction_capacitance_per_cell: 单片电池结电容 (F)
            bypass_capacitance: 每组旁路电容 (F)
            wiring_inductance: 布线电感 (H)
            voltage_settling_time: 电压稳定时间常数 (s)
            current_settling_time: 电流稳定时间常数 (s)
            diode_recovery_time: 二极管反向恢复时间 (s)
        """
        self.config = array_config
        self.Cj = junction_capacitance_per_cell
        self.Cb = bypass_capacitance
        self.L = wiring_inductance
        self.tau_v = voltage_settling_time
        self.tau_i = current_settling_time
        self.t_r = diode_recovery_time
        
        # 总结电容（串联电池的等效电容）
        n_series = array_config.n_cells_series
        self.Cj_total = self.Cj / n_series * array_config.n_strings_parallel
        
        # 总旁路电容
        n_groups = int(np.ceil(n_series / array_config.bypass_diode_group_size))
        self.Cb_total = self.Cb * n_groups / array_config.n_strings_parallel
        
        # 等效RC时间常数
        self.R_load_typical = 1.0  # 典型负载电阻 (Ω)
        self.tau_rc = (self.Cj_total + self.Cb_total) * self.R_load_typical
    
    def calculate_eclipse_voltage_decay(self,
                                         initial_voltage: float,
                                         initial_current: float,
                                         time_in_eclipse: float,
                                         load_resistance: float = 1.0,
                                         is_mpc: bool = True) -> Tuple[float, float, bool]:
        """
        计算阴影区（地影）的电压跌落
        
        参数:
            initial_voltage: 进入阴影时的初始电压 (V)
            initial_current: 进入阴影时的初始电流 (A)
            time_in_eclipse: 在阴影区的时间 (s)
            load_resistance: 负载电阻 (Ω)
            is_mpc: 是否为最大功率点控制模式
            
        返回:
            (voltage, current, is_settled): 当前电压(V), 电流(A), 是否已稳定
        """
        if time_in_eclipse <= 0:
            return initial_voltage, initial_current, False
        
        # 开路电压衰减（由于结电容放电）
        # 阴影区辐照度为0，光生电流为0
        # 等效电路：电容通过负载电阻放电
        
        # 稳态电压（阴影区）
        if is_mpc:
            # MPPT模式下，阴影区尝试维持电压，但电流为0
            V_steady = 0.0
            I_steady = 0.0
        else:
            # 恒压模式或直接连接负载
            V_steady = 0.0
            I_steady = 0.0
        
        # 瞬态响应：指数衰减
        tau = self._calculate_effective_time_constant(load_resistance, is_eclipse=True)
        
        # 电压跌落（考虑初始电荷）
        V_prev = initial_voltage
        Q0 = (self.Cj_total + self.Cb_total) * V_prev
        
        # 放电过程
        decay_factor = np.exp(-time_in_eclipse / tau)
        
        voltage = V_steady + (initial_voltage - V_steady) * decay_factor
        current = initial_current * decay_factor
        
        # 考虑二极管反向恢复效应（短时间尺度）
        if time_in_eclipse < self.t_r * 10:
            # 快速瞬态：二极管恢复期间有额外电流
            recovery_factor = np.exp(-time_in_eclipse / self.t_r)
            current += initial_current * 0.1 * recovery_factor
        
        # 判断是否已稳定
        is_settled = abs(voltage - V_steady) < 0.01 * max(abs(initial_voltage), 0.1)
        
        return voltage, current, is_settled
    
    def calculate_illumination_recovery(self,
                                         initial_voltage: float,
                                         initial_current: float,
                                         steady_state_voltage: float,
                                         steady_state_current: float,
                                         time_since_illumination: float,
                                         load_resistance: float = 1.0,
                                         irradiance_level: float = 1.0) -> Tuple[float, float, bool]:
        """
        计算再入影（出地影）的电压/电流恢复
        
        参数:
            initial_voltage: 出阴影时的初始电压 (V)
            initial_current: 出阴影时的初始电流 (A)
            steady_state_voltage: 稳态电压 (V)
            steady_state_current: 稳态电流 (A)
            time_since_illumination: 出阴影后的时间 (s)
            load_resistance: 负载电阻 (Ω)
            irradiance_level: 相对辐照度水平 (0-1)
            
        返回:
            (voltage, current, is_settled): 当前电压(V), 电流(A), 是否已稳定
        """
        if time_since_illumination <= 0:
            return initial_voltage, initial_current, False
        
        # 瞬态响应：指数上升
        tau_v = self._calculate_effective_time_constant(load_resistance, is_eclipse=False)
        tau_i = self.tau_i
        
        # 电压恢复（考虑电容充电）
        v_factor = 1.0 - np.exp(-time_since_illumination / tau_v)
        voltage = initial_voltage + (steady_state_voltage - initial_voltage) * v_factor
        
        # 电流恢复（更快的时间常数）
        i_factor = 1.0 - np.exp(-time_since_illumination / tau_i)
        current = initial_current + (steady_state_current - initial_current) * i_factor
        
        # 考虑过冲效应（由于布线电感）
        if self.L > 0 and time_since_illumination < 3 * tau_i:
            # RLC振荡的简化模型
            omega = 1.0 / np.sqrt(max(self.L * (self.Cj_total + self.Cb_total), 1e-12))
            alpha = load_resistance / (2 * self.L) if self.L > 0 else 0
            
            if omega > alpha:  # 欠阻尼
                omega_d = np.sqrt(omega ** 2 - alpha ** 2)
                overshoot = np.exp(-alpha * time_since_illumination) * np.cos(omega_d * time_since_illumination)
                current += (steady_state_current - initial_current) * 0.1 * overshoot
        
        # 辐照度渐变效应（如果辐照度是逐渐增加的）
        if irradiance_level < 1.0:
            voltage *= irradiance_level
            current *= irradiance_level
        
        # 判断是否已稳定
        v_settled = abs(voltage - steady_state_voltage) < 0.01 * max(abs(steady_state_voltage), 0.1)
        i_settled = abs(current - steady_state_current) < 0.01 * max(abs(steady_state_current), 0.01)
        is_settled = v_settled and i_settled
        
        return voltage, current, is_settled
    
    def _calculate_effective_time_constant(self, 
                                            load_resistance: float,
                                            is_eclipse: bool) -> float:
        """
        计算有效的时间常数
        
        参数:
            load_resistance: 负载电阻 (Ω)
            is_eclipse: 是否在阴影区
            
        返回:
            时间常数 (s)
        """
        # 阴影区：电容通过负载和并联电阻放电
        if is_eclipse:
            R_parallel = self.config.cell_params.R_sh / self.config.n_cells_series
            R_eq = 1.0 / (1.0 / load_resistance + 1.0 / R_parallel)
        else:
            # 光照区：主要由负载和二极管电阻决定
            R_diode = self.config.cell_params.R_s * self.config.n_cells_series
            R_eq = load_resistance + R_diode
        
        C_eq = self.Cj_total + self.Cb_total
        tau = R_eq * C_eq
        
        # 与配置的时间常数取最大值
        return max(tau, self.tau_v * 0.1)
    
    def update_transient_state(self,
                                 current_state: TransientState,
                                 new_steady_voltage: float,
                                 new_steady_current: float,
                                 new_is_in_eclipse: bool,
                                 time_step: float,
                                 load_resistance: float = 1.0) -> TransientState:
        """
        更新瞬态状态
        
        参数:
            current_state: 当前瞬态状态
            new_steady_voltage: 新的稳态电压 (V)
            new_steady_current: 新的稳态电流 (A)
            new_is_in_eclipse: 新的阴影状态
            time_step: 时间步长 (s)
            load_resistance: 负载电阻 (Ω)
            
        返回:
            更新后的TransientState
        """
        # 检测状态切换（进入/离开阴影）
        state_changed = (current_state.is_in_eclipse != new_is_in_eclipse)
        
        if state_changed:
            # 状态切换，从当前时间步长开始计算
            time_since_transition = time_step
            initial_v = current_state.voltage
            initial_i = current_state.current
        else:
            time_since_transition = current_state.time_since_transition + time_step
            initial_v = current_state.steady_state_voltage
            initial_i = current_state.steady_state_current
        
        # 计算瞬态响应
        if new_is_in_eclipse:
            voltage, current, settled = self.calculate_eclipse_voltage_decay(
                current_state.voltage if state_changed else current_state.voltage,
                current_state.current if state_changed else current_state.current,
                time_since_transition,
                load_resistance
            )
        else:
            voltage, current, settled = self.calculate_illumination_recovery(
                current_state.voltage if state_changed else current_state.voltage,
                current_state.current if state_changed else current_state.current,
                new_steady_voltage,
                new_steady_current,
                time_since_transition,
                load_resistance
            )
        
        # 更新结电容电荷
        junction_charge = (self.Cj_total + self.Cb_total) * voltage
        
        return TransientState(
            voltage=voltage,
            current=current,
            steady_state_voltage=new_steady_voltage,
            steady_state_current=new_steady_current,
            time_since_transition=time_since_transition,
            is_in_eclipse=new_is_in_eclipse,
            settling_complete=settled,
            junction_charge=junction_charge
        )
    
    def simulate_eclipse_transit(self,
                                   pre_eclipse_voltage: float,
                                   pre_eclipse_current: float,
                                   eclipse_duration: float,
                                   post_eclipse_steady_voltage: float,
                                   post_eclipse_steady_current: float,
                                   num_points: int = 100,
                                   load_resistance: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        模拟完整的阴影-再入影过渡过程
        
        参数:
            pre_eclipse_voltage: 阴影前稳态电压 (V)
            pre_eclipse_current: 阴影前稳态电流 (A)
            eclipse_duration: 阴影持续时间 (s)
            post_eclipse_steady_voltage: 出阴影后稳态电压 (V)
            post_eclipse_steady_current: 出阴影后稳态电流 (A)
            num_points: 模拟点数
            load_resistance: 负载电阻 (Ω)
            
        返回:
            (time_array, voltage_array, current_array): 时间、电压、电流数组
        """
        # 总时间：阴影过程 + 3倍恢复时间常数
        total_time = eclipse_duration + 3 * self.tau_v
        times = np.linspace(-eclipse_duration * 0.1, total_time, num_points)
        
        voltages = np.zeros(num_points)
        currents = np.zeros(num_points)
        
        for i, t in enumerate(times):
            if t < 0:
                # 阴影前
                voltages[i] = pre_eclipse_voltage
                currents[i] = pre_eclipse_current
            elif t < eclipse_duration:
                # 阴影中
                v, c, _ = self.calculate_eclipse_voltage_decay(
                    pre_eclipse_voltage, pre_eclipse_current, t, load_resistance
                )
                voltages[i] = v
                currents[i] = c
            else:
                # 出阴影后
                time_in_light = t - eclipse_duration
                
                # 先找到阴影结束时的电压电流
                v_eclipse_end, c_eclipse_end, _ = self.calculate_eclipse_voltage_decay(
                    pre_eclipse_voltage, pre_eclipse_current, eclipse_duration, load_resistance
                )
                
                v, c, _ = self.calculate_illumination_recovery(
                    v_eclipse_end, c_eclipse_end,
                    post_eclipse_steady_voltage, post_eclipse_steady_current,
                    time_in_light, load_resistance
                )
                voltages[i] = v
                currents[i] = c
        
        return times, voltages, currents
    
    def get_transient_performance_metrics(self,
                                           time_array: np.ndarray,
                                           voltage_array: np.ndarray,
                                           current_array: np.ndarray) -> Dict[str, float]:
        """
        计算瞬态响应的性能指标
        
        参数:
            time_array: 时间数组 (s)
            voltage_array: 电压数组 (V)
            current_array: 电流数组 (A)
            
        返回:
            包含性能指标的字典
        """
        power_array = voltage_array * current_array
        
        # 找到阴影开始和结束的索引
        eclipse_start_idx = np.argmax(np.abs(np.diff(voltage_array)) > 0.1)
        eclipse_end_idx = len(voltage_array) - eclipse_start_idx
        
        # 恢复时间（从阴影结束到达到95%稳态的时间）
        steady_v = voltage_array[-1]
        steady_i = current_array[-1]
        
        recovery_idx = eclipse_end_idx
        while recovery_idx < len(voltage_array):
            if (abs(voltage_array[recovery_idx] - steady_v) < 0.05 * abs(steady_v) and
                abs(current_array[recovery_idx] - steady_i) < 0.05 * abs(steady_i)):
                break
            recovery_idx += 1
        
        recovery_time = time_array[recovery_idx] - time_array[eclipse_end_idx] if recovery_idx < len(time_array) else -1
        
        # 电压跌落深度
        voltage_drop = np.max(voltage_array[:eclipse_start_idx]) - np.min(voltage_array[eclipse_start_idx:eclipse_end_idx])
        voltage_drop_ratio = voltage_drop / np.max(voltage_array[:eclipse_start_idx])
        
        # 恢复过冲
        overshoot = np.max(voltage_array[eclipse_end_idx:]) - steady_v
        overshoot_ratio = overshoot / abs(steady_v) if steady_v != 0 else 0
        
        # 能量损失
        pre_eclipse_power = np.mean(power_array[:eclipse_start_idx])
        post_eclipse_power = np.mean(power_array[eclipse_end_idx:])
        transient_energy_loss = np.trapz(
            pre_eclipse_power - power_array[eclipse_end_idx:recovery_idx],
            time_array[eclipse_end_idx:recovery_idx]
        ) if recovery_idx > eclipse_end_idx else 0
        
        return {
            'recovery_time_s': recovery_time,
            'voltage_drop_V': voltage_drop,
            'voltage_drop_ratio': voltage_drop_ratio,
            'overshoot_V': overshoot,
            'overshoot_ratio': overshoot_ratio,
            'transient_energy_loss_J': transient_energy_loss,
            'pre_eclipse_power_W': pre_eclipse_power,
            'post_eclipse_power_W': post_eclipse_power
        }
