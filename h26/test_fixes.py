import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from app.utils.postprocessing import (
    calculate_top_l_precision,
    contact_map_to_distances,
    enforce_triangle_inequality,
    reconstruct_3d_coords,
    postprocess_predictions
)
from app.models.resnet import resnet18_contact
from app.utils.encoding import get_sequence_features, build_input_tensor


def test_symmetry_fix():
    print("=" * 60)
    print("测试1: 接触图对称性修复验证")
    print("=" * 60)

    model = resnet18_contact(in_channels=40)
    model.eval()

    sequence = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"
    features = get_sequence_features(sequence)
    input_tensor = build_input_tensor(features)

    with torch.no_grad():
        output = model(input_tensor)

    contact_map = output.squeeze(0).numpy()

    max_diff = np.max(np.abs(contact_map - contact_map.T))
    is_symmetric = np.allclose(contact_map, contact_map.T, atol=1e-6)

    print(f"  序列长度: {len(sequence)}")
    print(f"  接触图形状: {contact_map.shape}")
    print(f"  最大不对称误差: {max_diff:.2e}")
    print(f"  是否对称 (atol=1e-6): {is_symmetric}")

    if max_diff < 1e-6 and is_symmetric:
        print("  ✓ 模型输出对称性修复验证通过!")
    else:
        print("  ✗ 模型输出对称性修复验证失败!")

    print("\n  --- 测试后处理对称性保证 ---")
    contact_map_asym = contact_map.copy()
    for i in range(contact_map_asym.shape[0]):
        for j in range(i + 1, contact_map_asym.shape[1]):
            if np.random.rand() > 0.5:
                contact_map_asym[i, j] += np.random.uniform(0, 0.3)

    max_diff_before = np.max(np.abs(contact_map_asym - contact_map_asym.T))
    print(f"  人为引入不对称后的最大误差: {max_diff_before:.2e}")

    postprocessed = postprocess_predictions(contact_map_asym)
    sym_check = postprocessed["symmetry_check"]
    print(f"  后处理后对称性: {sym_check['is_symmetric']}")
    print(f"  后处理后最大不对称误差: {sym_check['max_asymmetry_before']:.2e}")

    if sym_check['is_symmetric']:
        print("  ✓ 后处理对称性保证验证通过!")
    else:
        print("  ✗ 后处理对称性保证验证失败!")

    print()

    return max_diff < 1e-6 and sym_check['is_symmetric']


def test_top_l_precision_fix():
    print("=" * 60)
    print("测试2: Top-L精度计算修复验证")
    print("=" * 60)

    test_cases = [
        (20, "小蛋白 (L=20)"),
        (50, "中小蛋白 (L=50)"),
        (100, "中等蛋白 (L=100)"),
        (200, "大蛋白 (L=200)"),
    ]

    all_passed = True

    for seq_len, description in test_cases:
        print(f"\n  {description}:")

        contact_map = np.random.rand(seq_len, seq_len)
        contact_map = (contact_map + contact_map.T) / 2

        true_contacts = np.zeros((seq_len, seq_len))
        triu = np.triu_indices(seq_len, k=6)
        n_true = min(seq_len, len(triu[0]))
        true_idx = np.random.choice(len(triu[0]), n_true, replace=False)
        true_contacts[triu[0][true_idx], triu[1][true_idx]] = 1

        metrics_old = calculate_top_l_precision(contact_map, true_contacts=true_contacts, casp_mode=False)
        metrics_new = calculate_top_l_precision(contact_map, true_contacts=true_contacts, casp_mode=True)

        effective_L = metrics_new["effective_L"]
        print(f"    序列长度 L = {seq_len}")
        print(f"    CASP有效长度 effective_L = {effective_L}")
        print(f"    旧方法 Top-1L: {metrics_old['top_1L_total']} 个, 新方法 Top-1L: {metrics_new['top_1L_total']} 个")
        print(f"    旧方法 Top-1L 精度: {metrics_old['top_1L_precision']:.4f}")
        print(f"    新方法 Top-1L 精度: {metrics_new['top_1L_precision']:.4f}")

        if seq_len < 100 and effective_L == 100:
            print(f"    ✓ 小蛋白 effective_L 正确修正为 100")
        elif seq_len >= 100 and effective_L == seq_len:
            print(f"    ✓ 大蛋白 effective_L 正确使用序列长度")
        else:
            print(f"    ✗ effective_L 计算错误")
            all_passed = False

        if metrics_new["top_1L_total"] <= len(triu[0]):
            print(f"    ✓ Top-L 数量不超过候选对总数")
        else:
            print(f"    ✗ Top-L 数量超过候选对总数")
            all_passed = False

    print()
    return all_passed


def test_mds_distance_fix():
    print("=" * 60)
    print("测试3: MDS距离约束修复验证")
    print("=" * 60)

    seq_len = 30

    contact_map = np.zeros((seq_len, seq_len))
    for i in range(seq_len):
        for j in range(i + 6, seq_len):
            if np.random.rand() > 0.7:
                contact_map[i, j] = np.random.uniform(0.6, 1.0)
                contact_map[j, i] = contact_map[i, j]

    distances_old = contact_map_to_distances(contact_map, max_distance=100.0)
    distances_new = contact_map_to_distances(contact_map, max_distance=30.0, bonded_distance=3.8)

    print(f"  序列长度: {seq_len}")
    print(f"  旧方法最大距离: {np.max(distances_old):.1f}Å")
    print(f"  新方法最大距离: {np.max(distances_new):.1f}Å")
    print(f"  相邻残基距离 (i,i+1): {distances_new[0, 1]:.1f}Å")

    if distances_new[0, 1] == 3.8:
        print("  ✓ 相邻残基距离约束正确应用")
    else:
        print("  ✗ 相邻残基距离约束缺失")

    if np.max(distances_new) <= 30.0:
        print("  ✓ 最大距离限制正确应用")
    else:
        print("  ✗ 最大距离限制缺失")

    distances_violating = distances_new.copy()
    distances_violating[0, 10] = 100.0
    distances_violating[10, 0] = 100.0

    distances_enforced = enforce_triangle_inequality(distances_violating)
    max_violation = 0.0
    for k in range(seq_len):
        for i in range(seq_len):
            for j in range(seq_len):
                if distances_enforced[i, j] > distances_enforced[i, k] + distances_enforced[k, j] + 1e-5:
                    max_violation = max(max_violation, distances_enforced[i, j] - (distances_enforced[i, k] + distances_enforced[k, j]))

    print(f"  三角不等式最大违反量: {max_violation:.2e}")

    coords = reconstruct_3d_coords(contact_map)
    print(f"  重建坐标形状: {coords.shape}")
    print(f"  坐标中心: {np.mean(coords, axis=0)}")

    dist_reconstructed = np.zeros((seq_len, seq_len))
    for i in range(seq_len):
        for j in range(seq_len):
            dist_reconstructed[i, j] = np.linalg.norm(coords[i] - coords[j])

    dist_error = np.mean(np.abs(dist_reconstructed - distances_enforced))
    print(f"  重建距离平均误差: {dist_error:.2f}Å")

    if max_violation < 1e-5:
        print("  ✓ 三角不等式约束验证通过!")
    else:
        print("  ✗ 三角不等式约束验证失败!")

    if coords.shape == (seq_len, 3):
        print("  ✓ 3D坐标重建成功!")
    else:
        print("  ✗ 3D坐标重建失败!")

    print()
    return max_violation < 1e-5 and coords.shape == (seq_len, 3)


def test_full_pipeline():
    print("=" * 60)
    print("测试4: 完整后处理流程验证")
    print("=" * 60)

    seq_len = 50
    contact_map = np.random.rand(seq_len, seq_len)
    contact_map = 0.5 * (contact_map + contact_map.T)

    result = postprocess_predictions(contact_map, casp_mode=True)

    print(f"  序列长度: {result['sequence_length']}")
    print(f"  接触数量: {result['num_contacts']}")
    print(f"  对称性检查: {result['symmetry_check']}")
    print(f"  精度指标: {result['precision_metrics']}")
    print(f"  3D坐标形状: ({len(result['coordinates_3d'])}, {len(result['coordinates_3d'][0])})")

    all_passed = True

    if result["symmetry_check"]["is_symmetric"]:
        print("  ✓ 输出接触图对称")
    else:
        print("  ✗ 输出接触图不对称")
        all_passed = False

    if result["precision_metrics"]["effective_L"] == 100:
        print("  ✓ 小蛋白 effective_L 正确")
    else:
        print("  ✗ 小蛋白 effective_L 错误")
        all_passed = False

    if len(result["coordinates_3d"]) == seq_len:
        print("  ✓ 3D坐标长度正确")
    else:
        print("  ✗ 3D坐标长度错误")
        all_passed = False

    print()
    return all_passed


def main():
    print("\n蛋白质接触图预测 - Bug修复验证测试")
    print("=" * 60 + "\n")

    results = []

    try:
        results.append(("对称性修复", test_symmetry_fix()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("对称性修复", False))
        import traceback
        traceback.print_exc()

    try:
        results.append(("Top-L精度修复", test_top_l_precision_fix()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("Top-L精度修复", False))
        import traceback
        traceback.print_exc()

    try:
        results.append(("MDS距离约束修复", test_mds_distance_fix()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("MDS距离约束修复", False))
        import traceback
        traceback.print_exc()

    try:
        results.append(("完整流程验证", test_full_pipeline()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("完整流程验证", False))
        import traceback
        traceback.print_exc()

    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")

    print()
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("所有测试通过! ✓")
    else:
        print(f"{sum(1 for r in results if r[1])}/{len(results)} 测试通过")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
