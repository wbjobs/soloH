"""
系统常量和物理参数
System Constants and Physical Parameters
"""

import numpy as np

# 物理常数
SPEED_OF_LIGHT = 299792458.0  # m/s
BOLTZMANN_CONSTANT = 1.380649e-23  # J/K
ELEMENTARY_CHARGE = 1.602176634e-19  # C

# 天文常数
AU = 149597870700.0  # 天文单位, m
EARTH_RADIUS = 6378.137  # 地球半径, km
EARTH_MU = 398600.4418  # 地球引力常数, km^3/s^2
SOLAR_CONSTANT = 1361.0  # 太阳常数, W/m^2 (AM0)

# 地球反照参数
EARTH_ALBEDO = 0.30  # 地球平均反照率
EARTH_EMISSIVITY = 0.95  # 地球红外发射率
EARTH_IR_FLUX = 237.0  # 地球红外辐射通量, W/m^2

# 太阳能电池标准测试条件 (STC)
STC_TEMPERATURE = 25.0 + 273.15  # K
STC_IRRADIANCE = 1000.0  # W/m^2 (AM1.5G)

# 温度系数 (典型值，可根据具体电池类型调整)
DEFAULT_TEMP_COEFF_VOC = -0.0022  # 1/K, 开路电压温度系数
DEFAULT_TEMP_COEFF_ISC = 0.0004  # 1/K, 短路电流温度系数
DEFAULT_TEMP_COEFF_PMAX = -0.0038  # 1/K, 最大功率温度系数

# 辐射降解参数 (位移损伤剂量)
DEFAULT_DDD_FACTOR = 1.5e-10  # 典型位移损伤剂量系数, (MeV/g)^-1
DEFAULT_REMAINING_FACTOR_INITIAL = 1.0  # 初始剩余因子

# 蒙特卡洛模拟参数
DEFAULT_MC_SAMPLES = 1000  # 默认蒙特卡洛样本数
DEFAULT_CONFIDENCE_LEVEL = 0.95  # 默认置信水平

# 坐标系转换
J2000_EPOCH = 2451545.0  # J2000儒略日
DEG2RAD = np.pi / 180.0
RAD2DEG = 180.0 / np.pi

# 时间转换
SEC_PER_DAY = 86400.0
SEC_PER_HOUR = 3600.0
SEC_PER_MINUTE = 60.0

# 帆板姿态参数
DEFAULT_SA_NORMAL = np.array([1.0, 0.0, 0.0])  # 帆板法向量默认方向(卫星本体坐标系)
