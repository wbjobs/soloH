import asyncio
import sys
import os
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.models import CropType


def print_section(title):
    """打印测试分区标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title):
    """打印测试子标题"""
    print(f"\n--- {title} ---")


async def test_attribution_service():
    """测试风险归因分析服务"""
    print_section("模块1：风险归因分析（SHAP值）")

    from app.services.attribution_service import AttributionService
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = AttributionService(db)

        test_lon, test_lat = 116.4, 39.9
        crop_type = CropType.wheat
        forecast_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # ===== Test 1: 单点归因计算 =====
        print_subsection("测试1：计算单点风险归因分析")
        result = await service.calculate_point_attribution(
            lon=test_lon,
            lat=test_lat,
            crop_type=crop_type,
            forecast_date=forecast_date,
            resistance_level=3,
        )

        print(f"坐标: ({test_lon}, {test_lat})")
        print(f"作物: {crop_type.value}")
        print(f"风险指数: {result['risk_index']:.2f}")
        print(f"风险等级: {result['risk_level']}")

        attr = result["attribution"]
        print(f"\nSHAP归因分析:")
        print(f"  方法: {attr['method']}")
        print(f"  基线值(base_value): {attr['base_value']:.2f}")
        print(f"  主导因素: {attr['dominant_factor']}")
        print(f"  主导因素贡献: {attr['dominant_factor_contribution']:.2f} ({attr['dominant_factor_contribution_percent']:.1f}%)")

        print(f"\n  各因素SHAP值:")
        for feat, info in attr["shap_values"].items():
            if isinstance(info, dict):
                print(f"    {info['name']:20s}: {info['value']:+.3f}  (影响: {info['impact']})")

        print(f"\n  特征重要性排序:")
        for i, imp in enumerate(attr["feature_importance"], 1):
            print(f"    {i}. {imp['name']:20s}: {imp['importance']:.3f}")

        assert "shap_values" in attr, "SHAP值缺失"
        assert "dominant_factor" in attr, "主导因素缺失"
        assert len(attr["shap_values"]) == 5, "特征数量不正确"
        print("✓ 测试1通过")

        # ===== Test 2: 保存归因结果 =====
        print_subsection("测试2：保存归因分析结果")
        saved = await service.save_attribution(
            grid_id=result["grid_id"],
            forecast_date=forecast_date,
            crop_type=crop_type,
            risk_index=result["risk_index"],
            attribution=attr,
        )

        print(f"归因记录ID: {saved.id}")
        print(f"网格ID: {saved.grid_id}")
        print(f"主导因素: {saved.dominant_factor}")
        print(f"风险指数: {saved.risk_index:.2f}")
        assert saved.id is not None, "保存失败"
        print("✓ 测试2通过")

        # ===== Test 3: 获取已保存的归因结果 =====
        print_subsection("测试3：获取已保存的归因结果")
        saved_result = await service.get_attribution_for_point(
            lon=test_lon,
            lat=test_lat,
            crop_type=crop_type,
            forecast_date=forecast_date,
        )

        assert saved_result is not None, "获取保存结果失败"
        print(f"获取到的风险指数: {saved_result['risk_index']:.2f}")
        print(f"获取到的主导因素: {saved_result['attribution']['dominant_factor']}")
        print("✓ 测试3通过")

        # ===== Test 4: 区域主导因素分析 =====
        print_subsection("测试4：区域主导因素统计")
        summary = await service.analyze_dominant_factors(
            crop_type=crop_type,
            forecast_date=forecast_date,
        )

        print(f"总网格数: {summary['total_grids']}")
        print(f"高风险网格数: {summary['high_risk_total']}")
        print(f"\n主导因素分布:")
        for factor, dist in summary["dominant_distribution"].items():
            print(f"  {factor:25s}: {dist['count']:4d}  ({dist['percentage']:5.1f}%)")

        print(f"\n各因素平均贡献度:")
        for factor, contrib in summary["average_contribution"].items():
            print(f"  {factor:25s}: {contrib:.3f}")

        print("\n高风险区域主导因素分布:")
        for factor, dist in summary["high_risk_dominant"].items():
            print(f"  {factor:25s}: {dist['count']:4d}  ({dist['percentage']:5.1f}%)")

        print("✓ 测试4通过")

        print_subsection("风险归因模块 - 全部测试通过 ✓")


async def test_drone_service():
    """测试无人机多光谱影像服务"""
    print_section("模块2：无人机多光谱影像病害检测")

    from app.services.drone_service import DroneService
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = DroneService(db)

        # ===== Test 1: 创建飞行记录 =====
        print_subsection("测试1：创建无人机飞行记录")
        flight_code = f"TEST_FLIGHT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        flight = await service.create_flight(
            flight_code=flight_code,
            drone_id="DJI-MATRICE-300-RTK",
            crop_type=CropType.wheat,
            flight_date=datetime.utcnow(),
            pilot_name="测试飞行员",
            area_covered_ha=50.0,
            altitude_m=100.0,
        )

        print(f"飞行记录ID: {flight.id}")
        print(f"飞行编号: {flight.flight_code}")
        print(f"无人机: {flight.drone_id}")
        print(f"作物类型: {flight.crop_type.value}")
        print(f"覆盖面积: {flight.area_covered_ha} 公顷")
        assert flight.id is not None, "创建飞行记录失败"
        print("✓ 测试1通过")

        # ===== Test 2: 添加影像 =====
        print_subsection("测试2：添加影像信息")
        image = await service.add_image(
            flight_id=flight.id,
            file_name="test_multispectral_001.tif",
            file_path="/data/drone/test_001.tif",
            image_type="Multispectral",
            center_lon=116.4,
            center_lat=39.9,
            capture_time=datetime.utcnow(),
        )

        print(f"影像ID: {image.id}")
        print(f"文件名: {image.file_name}")
        print(f"影像类型: {image.image_type}")
        assert image.id is not None, "添加影像失败"
        print("✓ 测试2通过")

        # ===== Test 3: 植被指数计算 =====
        print_subsection("测试3：植被指数计算")
        band_data = service.generate_mock_band_data(256, 256, stress_level=0.3)
        indices = DroneService.calculate_vegetation_indices(band_data)

        print("各波段数据统计:")
        for band, data in band_data.items():
            if hasattr(data, 'mean'):
                print(f"  {band:8s}: min={data.min():.3f}, max={data.max():.3f}, mean={data.mean():.3f}")

        print(f"\n计算的植被指数:")
        for idx_name, value in indices.items():
            idx_info = DroneService.VEGETATION_INDICES.get(idx_name, {})
            print(f"  {idx_name:6s}: {value:.4f} - {idx_info.get('name', '')}")
            formula = idx_info.get('formula', '')
            if formula:
                print(f"          公式: {formula}")

        assert "NDVI" in indices, "NDVI计算失败"
        assert -1 <= indices["NDVI"] <= 1, "NDVI范围不正确"
        print("✓ 测试3通过")

        # ===== Test 4: 基于植被指数的病害检测 =====
        print_subsection("测试4：基于植被指数的病害检测")
        detected, disease_name, confidence, severity = service.detect_disease_from_indices(
            indices, CropType.wheat
        )

        print(f"病害检测结果:")
        print(f"  是否检测到: {detected}")
        print(f"  病害名称: {disease_name}")
        print(f"  置信度: {confidence:.4f}")
        print(f"  严重度: {severity:.2f}%")

        if detected:
            assert severity > 0, "检测到病害但严重度为0"
            assert confidence > 0, "检测到病害但置信度为0"
        print("✓ 测试4通过")

        # ===== Test 5: 影像分析 =====
        print_subsection("测试5：完整影像分析流程")
        analysis_result = await service.analyze_image(
            band_data=band_data,
            crop_type=CropType.wheat,
            center_lon=116.4,
            center_lat=39.9,
        )

        print(f"影像分析结果:")
        print(f"  分析方法: {analysis_result['analysis_method']}")
        print(f"  总像素: {analysis_result['pixel_count']}")
        print(f"  受影响像素: {analysis_result['affected_pixels']}")
        print(f"  病害检测: {analysis_result['disease_detected']}")
        print(f"  病害名称: {analysis_result['disease_name']}")
        print(f"  置信度: {analysis_result['detection_confidence']:.4f}")
        print(f"  严重度: {analysis_result['severity']:.2f}%")
        print(f"  风险提升因子: {analysis_result['risk_boost_factor']:.2f}x")

        assert analysis_result["indices"], "植被指数缺失"
        print("✓ 测试5通过")

        # ===== Test 6: 保存病害检测 =====
        print_subsection("测试6：保存病害检测结果")
        detection = await service.save_detection(
            flight_id=flight.id,
            image_id=image.id,
            crop_type=CropType.wheat,
            disease_name=disease_name,
            detection_confidence=confidence,
            severity=severity,
            lon=116.4,
            lat=39.9,
            ndvi_value=indices.get("NDVI"),
            ndre_value=indices.get("NDRE"),
            gndvi_value=indices.get("GNDVI"),
            pri_value=indices.get("PRI"),
            fused_risk_boost=analysis_result["risk_boost_factor"],
            area_affected_m2=1000.0,
            notes="测试检测",
        )

        print(f"检测记录ID: {detection.id}")
        print(f"病害: {detection.disease_name}")
        print(f"严重度: {detection.severity:.2f}%")
        print(f"关联网格ID: {detection.grid_id}")
        print(f"风险提升: {detection.fused_risk_boost:.2f}x")
        assert detection.id is not None, "保存检测失败"
        print("✓ 测试6通过")

        # ===== Test 7: 数据融合测试 =====
        print_subsection("测试7：无人机检测与气象模型风险融合")
        await service._fuse_with_risk_model(
            grid_id=detection.grid_id,
            crop_type=CropType.wheat,
            severity=severity,
            risk_boost=analysis_result["risk_boost_factor"],
        )
        print("  数据融合完成（风险已乘以提升因子）")
        print("✓ 测试7通过")

        # ===== Test 8: 获取病害检测热图 =====
        print_subsection("测试8：生成病害检测热图（GeoJSON）")
        heatmap = await service.get_detection_heatmap(
            crop_type=CropType.wheat,
            flight_id=flight.id,
        )

        print(f"热图结果:")
        print(f"  总检测数: {heatmap['total_detections']}")
        print(f"  平均严重度: {heatmap['average_severity']:.2f}%")
        print(f"  高风险检测: {heatmap['high_risk_count']}")
        print(f"  中风险检测: {heatmap['medium_risk_count']}")
        print(f"  低风险检测: {heatmap['low_risk_count']}")
        print(f"  GeoJSON要素数: {len(heatmap['features'])}")

        if heatmap["features"]:
            feature = heatmap["features"][0]
            print(f"\n  首个检测点:")
            print(f"    位置: {feature['geometry']['coordinates']}")
            props = feature["properties"]
            print(f"    病害: {props['disease']}")
            print(f"    严重度: {props['severity']:.2f}%")
            print(f"    颜色: {props['color']}")

        print("✓ 测试8通过")

        print_subsection("无人机影像模块 - 全部测试通过 ✓")


async def test_pesticide_service():
    """测试农药喷洒建议服务"""
    print_section("模块3：农药喷洒建议（基于风险和经济阈值）")

    from app.services.pesticide_service import PesticideService
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = PesticideService(db)

        # ===== Test 1: 初始化默认农药产品 =====
        print_subsection("测试1：初始化默认农药产品")
        products = await service.init_default_products()

        print(f"初始化产品数量: {len(products)}")
        for i, p in enumerate(products, 1):
            print(f"  {i}. {p.product_name}")
            print(f"     有效成分: {p.active_ingredient}")
            print(f"     用量: {p.dosage_ha} {p.unit}/公顷")
            print(f"     效果评级: {p.efficacy_rating}/100")
            print(f"     单价: {p.price_per_unit} 元/{p.unit}")

        assert len(products) >= 6, "默认产品数量不足"
        print("✓ 测试1通过")

        # ===== Test 2: 经济阈值计算 =====
        print_subsection("测试2：经济阈值计算")
        et_result = service.calculate_economic_threshold(
            crop_type=CropType.wheat,
            yield_tons_ha=6.0,
            price_yuan_ton=2500.0,
            control_cost_yuan_ha=150.0,
            efficacy=0.85,
        )

        print(f"小麦经济阈值分析:")
        print(f"  经济阈值 (风险指数): {et_result['economic_threshold']:.2f}")
        print(f"  预期产量: {et_result['yield_tons_ha']} 吨/公顷")
        print(f"  产品价格: {et_result['price_yuan_ton']} 元/吨")
        print(f"  防治成本: {et_result['control_cost_yuan_ha']} 元/公顷")
        print(f"  防治效果: {et_result['efficacy'] * 100:.0f}%")
        print(f"  收支平衡严重度: {et_result['break_even_severity']:.2f}%")
        print(f"  预期损失产量: {et_result['expected_yield_loss_tons']:.4f} 吨/公顷")
        print(f"  预期损失金额: {et_result['expected_yield_loss_yuan']:.2f} 元/公顷")
        print(f"\n  计算公式: {et_result['formula']}")
        print(f"  参数说明:")
        for key, desc in et_result["formula_explanation"].items():
            print(f"    {key}: {desc}")

        assert et_result["economic_threshold"] > 0, "经济阈值计算错误"
        print("✓ 测试2通过")

        # ===== Test 3: 马铃薯经济阈值 =====
        print_subsection("测试3：马铃薯经济阈值（对比）")
        et_potato = service.calculate_economic_threshold(
            crop_type=CropType.potato,
            yield_tons_ha=25.0,
            price_yuan_ton=1200.0,
            control_cost_yuan_ha=300.0,
            efficacy=0.85,
        )

        print(f"马铃薯经济阈值分析:")
        print(f"  经济阈值 (风险指数): {et_potato['economic_threshold']:.2f}")
        print(f"  预期产量: {et_potato['yield_tons_ha']} 吨/公顷")
        print(f"  预期损失金额: {et_potato['expected_yield_loss_yuan']:.2f} 元/公顷")

        assert et_potato["economic_threshold"] != et_result["economic_threshold"], "不同作物阈值不应相同"
        print("✓ 测试3通过")

        # ===== Test 4: 紧急程度判断 =====
        print_subsection("测试4：施药紧急程度判断")
        test_cases = [
            (85, None, "rising", "immediate"),
            (55, 40, "stable", "high"),
            (25, 20, "falling", "medium"),
            (10, None, "stable", "low"),
        ]

        for risk, severity, trend, expected in test_cases:
            urgency, _ = service.determine_urgency(risk, severity, trend)
            severity_str = f", 无人机严重度={severity}%" if severity else ""
            print(f"  风险={risk}{severity_str}, 趋势={trend:8s} → 紧急度={urgency['level']} ({urgency['name']}), 时间窗口={urgency['time_window']}")
            assert urgency["level"] == expected, f"紧急度判断错误: 期望{expected}, 实际{urgency['level']}"

        print("✓ 测试4通过")

        # ===== Test 5: 成本收益分析 =====
        print_subsection("测试5：成本收益分析")
        cb = service.calculate_cost_benefit(
            risk_index=55.0,
            economic_threshold=et_result["economic_threshold"],
            crop_type=CropType.wheat,
            product=products[0],
            area_ha=10.0,
            yield_tons_ha=6.0,
            price_yuan_ton=2500.0,
        )

        print(f"成本收益分析:")
        print(f"  风险指数: {cb['risk_index']:.2f}")
        print(f"  有效风险: {cb['effective_risk']:.2f}")
        print(f"  产量损失率: {cb['yield_loss_ratio'] * 100:.2f}%")
        print(f"  预期损失: {cb['expected_loss_tons_ha']:.4f} 吨/公顷")
        print(f"  挽回损失: {cb['prevented_loss_tons_ha']:.4f} 吨/公顷")
        print(f"  挽回收益: {cb['revenue_gain_yuan_ha']:.2f} 元/公顷")
        print(f"  防治成本: {cb['cost_yuan_ha']:.2f} 元/公顷")
        print(f"  净收益: {cb['net_benefit_yuan_ha']:.2f} 元/公顷")
        print(f"\n  总面积: {cb['area_ha']} 公顷")
        print(f"  总成本: {cb['total_cost_yuan']:.2f} 元")
        print(f"  总挽回收益: {cb['total_revenue_gain_yuan']:.2f} 元")
        print(f"  总净收益: {cb['total_net_benefit_yuan']:.2f} 元")
        print(f"  投入产出比: {cb['benefit_cost_ratio']:.2f} : 1")
        print(f"  经济性建议: {cb['recommendation']}")

        assert cb["benefit_cost_ratio"] > 0, "投入产出比计算错误"
        print("✓ 测试5通过")

        # ===== Test 6: 完整喷洒建议生成 =====
        print_subsection("测试6：生成完整的农药喷洒建议")
        recommendation = await service.generate_spray_recommendation(
            lon=116.4,
            lat=39.9,
            crop_type=CropType.wheat,
            forecast_date=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            area_ha=10.0,
            yield_tons_ha=6.0,
            price_yuan_ton=2500.0,
            max_cost_yuan_ha=200.0,
            last_used_ingredient="三唑酮",
            forecast_risk_trend="rising",
        )

        print(f"喷洒建议结果:")
        print(f"  建议ID: {recommendation.get('recommendation_id')}")
        print(f"  风险指数: {recommendation['risk_index']:.2f}")
        print(f"  风险等级: {recommendation['risk_level']}")
        print(f"  经济阈值: {recommendation['economic_threshold']['economic_threshold']:.2f}")
        print(f"  是否需要施药: {recommendation['spray_needed']}")
        print(f"  紧急程度: {recommendation['urgency']['name']} ({recommendation['urgency']['level']})")
        print(f"  无人机检测数量: {recommendation['drone_detections_count']}")
        if recommendation['drone_detected_severity']:
            print(f"  无人机检测严重度: {recommendation['drone_detected_severity']:.2f}%")

        if recommendation["recommended_product"]:
            prod = recommendation["recommended_product"]
            print(f"\n  推荐产品: {prod['product_name']}")
            print(f"    有效成分: {prod['active_ingredient']}")
            print(f"    用量: {prod['dosage_ha']} {prod['unit']}/公顷")
            print(f"    总用量: {prod['total_dosage']:.2f} {prod['unit']}")
            print(f"    预估成本: {prod['estimated_cost']:.2f} 元")
            print(f"    效果评级: {prod['efficacy_rating']}/100")
            print(f"    抗性风险: {prod['resistance_risk']}")

        if recommendation["alternative_product"]:
            alt = recommendation["alternative_product"]
            print(f"\n  备选产品: {alt['product_name']}")
            print(f"    有效成分: {alt['active_ingredient']}")
            print(f"    预估成本: {alt['estimated_cost']:.2f} 元")

        if recommendation["cost_benefit_analysis"]:
            cb = recommendation["cost_benefit_analysis"]
            print(f"\n  成本收益:")
            print(f"    投入产出比: {cb['benefit_cost_ratio']:.2f} : 1")
            print(f"    净收益: {cb['total_net_benefit_yuan']:.2f} 元")
            print(f"    经济性: {cb['recommendation']}")

        timing = recommendation["application_timing"]
        print(f"\n  施药时间:")
        print(f"    最佳时间: {timing.get('best_time', '')}")
        print(f"    避开条件: {', '.join(timing.get('avoid_conditions', []))}")
        if timing.get("next_window"):
            print(f"    下一个窗口: {timing['next_window']}")

        print(f"\n  施药方法: {recommendation['application_method']}")

        print(f"\n  安全注意事项:")
        for i, note in enumerate(recommendation["safety_precautions"][:3], 1):
            print(f"    {i}. {note}")

        print(f"\n  抗性管理建议:")
        for i, note in enumerate(recommendation["resistance_management"][:3], 1):
            print(f"    {i}. {note}")

        print(f"\n  环境保护建议:")
        for i, note in enumerate(recommendation["environmental_impact"][:3], 1):
            print(f"    {i}. {note}")

        print(f"\n  生成时间: {recommendation.get('generated_at')}")
        print(f"  过期时间: {recommendation.get('expires_at')}")

        print("✓ 测试6通过")

        # ===== Test 7: 标记已施药 =====
        print_subsection("测试7：标记喷洒建议为已施药")
        rec_id = recommendation.get("recommendation_id")
        if rec_id:
            updated = await service.mark_recommendation_applied(
                recommendation_id=rec_id,
                applied_at=datetime.utcnow(),
                actual_dosage=recommendation["recommended_product"]["total_dosage"] if recommendation["recommended_product"] else None,
                notes="测试施药完成",
            )

            print(f"建议ID: {updated.id}")
            print(f"已施药: {updated.is_applied}")
            print(f"施药时间: {updated.applied_at}")
            print(f"实际用量: {updated.actual_dosage}")
            assert updated.is_applied is True, "标记失败"
            print("✓ 测试7通过")
        else:
            print("  跳过（无建议ID）")

        print_subsection("农药喷洒模块 - 全部测试通过 ✓")


async def main():
    """运行所有测试"""
    print("\n" + "#" * 80)
    print("#" + " " * 78 + "#")
    print("#" + " " * 20 + "农业病害预警系统 - 新功能测试" + " " * 28 + "#")
    print("#" + " " * 78 + "#")
    print("#" * 80)
    print("\n测试三个新增功能模块:")
    print("  1. 基于机器学习的风险归因分析（SHAP值解释）")
    print("  2. 无人机多光谱影像的实时病害检测与数据融合")
    print("  3. 农药喷洒建议（基于风险和经济阈值）")
    print()

    try:
        await test_attribution_service()
        await test_drone_service()
        await test_pesticide_service()

        print_section("✅ 所有测试通过！")
        print("\n新增功能模块总结:")
        print("\n📊 风险归因分析（SHAP值）:")
        print("   - Kernel SHAP算法解释各因素贡献度")
        print("   - 支持SHAP不可用时的特征排列重要性降级")
        print("   - 自动识别主导风险因素")
        print("   - 区域主导因素统计分析")

        print("\n🚁 无人机多光谱影像分析:")
        print("   - NDVI、NDRE、GNDVI、PRI四种植被指数")
        print("   - 基于光谱特征的病害检测（小麦锈病、马铃薯晚疫病）")
        print("   - 病害严重度评估")
        print("   - 与气象模型风险数据融合（风险提升因子）")
        print("   - GeoJSON格式病害热图输出")

        print("\n💊 农药喷洒建议:")
        print("   - 经济阈值计算（ET = C×100/(Y×P×E)）")
        print("   - 成本收益分析（投入产出比、净收益）")
        print("   - 紧急程度分级（立即/尽快/准备/观察）")
        print("   - 多维度农药产品选择（效果、成本、抗性管理）")
        print("   - 完整施药指南（时间、方法、安全、环保）")

        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
