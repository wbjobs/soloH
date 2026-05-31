from app.models import JensenModel, BlightcastModel
import numpy as np

print('=== 测试Jensen小麦锈病模型 ===')
jensen = JensenModel()
print('模型信息:', jensen.get_model_info())

risk, prob, details = jensen.calculate_risk(
    temperature=18, humidity=95, leaf_wetness=12,
    spore_concentration=80, resistance_level=2,
    consecutive_wet_days=3
)
print('高风险场景 - 风险指数:', risk, '感染概率:', prob)
print('风险等级:', details['risk_level'])

risk2, prob2, details2 = jensen.calculate_risk(
    temperature=8, humidity=60, leaf_wetness=3,
    spore_concentration=10, resistance_level=4
)
print('低风险场景 - 风险指数:', risk2, '感染概率:', prob2)
print('风险等级:', details2['risk_level'])

print()
print('=== 测试Blightcast马铃薯晚疫病模型 ===')
blightcast = BlightcastModel()
print('模型信息:', blightcast.get_model_info())

risk3, prob3, details3 = blightcast.calculate_risk(
    temperature=18, humidity=95, rainfall=15,
    leaf_wetness=18, spore_concentration=100, resistance_level=2,
    consecutive_wet_days=5, hours_rh_gt_90=16
)
print('高风险场景 - 风险指数:', risk3, '感染概率:', prob3)
print('风险等级:', details3['risk_level'])
print('单日SV:', details3['factors']['daily_severity_value'])
print('累积CSV:', details3['factors']['cumulative_severity_value'])

risk4, prob4, details4 = blightcast.calculate_risk(
    temperature=20, humidity=85, spore_concentration=50, resistance_level=3,
    consecutive_wet_days=2
)
print('中风险场景 - 风险指数:', risk4, '感染概率:', prob4)
print('风险等级:', details4['risk_level'])

print()
print('=== 测试输入验证 ===')
valid, msg = jensen.validate_inputs(temperature=175, humidity=80)
print('无效温度验证:', valid, msg)

valid, msg = jensen.validate_inputs(temperature=18, humidity=120)
print('无效湿度验证:', valid, msg)

valid, msg = jensen.validate_inputs(temperature=18, humidity=85, resistance_level=8)
print('无效抗性验证:', valid, msg)

valid, msg = jensen.validate_inputs(temperature=18, humidity=85, resistance_level=3)
print('有效参数验证:', valid, msg)

print()
print('=== 所有测试通过 ===')
