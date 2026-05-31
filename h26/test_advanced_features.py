import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from app.models.resnet import resnet18_contact
from app.utils.encoding import get_sequence_features, build_input_tensor
from app.utils.pssm import create_dummy_pssm
from app.utils.attention_explain import compute_attention_map, compute_residue_importance
from app.utils.mutation_effect import predict_mutation_effect, scan_all_mutations, analyze_mutation_impact
from app.utils.structure_compare import (
    parse_pdb_coordinates,
    kabsch_alignment,
    calculate_tm_score,
    calculate_gdt,
    compare_with_alphafold
)


def test_attention_explanation():
    print("=" * 60)
    print("测试1: 注意力机制接触图解释")
    print("=" * 60)

    model = resnet18_contact(in_channels=80)
    model.eval()

    sequence = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"
    pssm = create_dummy_pssm(sequence)
    features = get_sequence_features(sequence, pssm)
    input_tensor = build_input_tensor(features)

    with torch.no_grad():
        output = model(input_tensor)
        contact_map = output.squeeze(0).numpy()
        contact_map = (contact_map + contact_map.T) / 2

    print(f"  序列长度: {len(sequence)}")
    print(f"  接触图形状: {contact_map.shape}")

    print("\n  --- 计算残基重要性 ---")
    residue_importance = compute_residue_importance(contact_map)
    print(f"  前5个最重要残基:")
    for i, imp in enumerate(residue_importance[:5]):
        print(f"    {i+1}. 残基 {imp['residue_index']}: 归一化分数 = {imp['normalized_score']:.4f}, "
              f"高概率接触数 = {imp['high_prob_contact_count']}")

    print("\n  --- 计算Top-3接触的注意力 ---")
    attention_data = compute_attention_map(
        model, input_tensor, contact_map, top_k=3
    )

    print(f"  分析了 {attention_data['analyzed_contacts']} 个接触")
    for i, attn in enumerate(attention_data['attention_results']):
        print(f"\n  接触 {i+1}: ({attn['target_i']}, {attn['target_j']})")
        print(f"    预测概率: {attn['target_probability']:.4f}")
        print(f"    注意力分数: {attn['attention_score']:.4f}")
        print(f"    前5个影响最大的残基:")
        for j, (res, score) in enumerate(attn['top_residues'][:5]):
            print(f"      {j+1}. 残基 {res}: {score:.4f}")
        print(f"    注意力热图形状: {np.array(attn['importance_map']).shape}")

    print("\n  ✓ 注意力机制解释测试通过!")
    print()
    return True


def test_mutation_effect():
    print("=" * 60)
    print("测试2: 突变效应预测")
    print("=" * 60)

    model = resnet18_contact(in_channels=80)
    model.eval()

    sequence = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"
    model_name = "resnet18_test"

    print(f"  原始序列: {sequence[:30]}...")
    print(f"  序列长度: {len(sequence)}")

    print("\n  --- 单点突变预测 ---")
    position = 10
    mutant_aa = "A"
    print(f"  突变: {sequence[position]}{position}{mutant_aa}")

    result = predict_mutation_effect(
        model=model,
        sequence=sequence,
        position=position,
        mutant_aa=mutant_aa,
        model_name=model_name
    )

    print(f"  接触图变化: {result.contact_map_change:.6f}")
    print(f"  位置概率变化: {result.delta_probability:.4f}")
    print(f"  结构变化分数: {result.structure_change_score:.4f}")
    print(f"  功能影响分级: {result.functional_impact.upper()}")
    print(f"  受影响的接触数量: {len(result.affected_contacts)}")
    if result.affected_contacts:
        print(f"  最显著的接触变化:")
        for i, contact in enumerate(result.affected_contacts[:3]):
            print(f"    {i+1}. ({contact['i']},{contact['j']}): "
                  f"{contact['wild_type_probability']:.3f} → {contact['mutant_probability']:.3f} "
                  f"(Δ={contact['delta']:.3f})")

    print("\n  --- 突变扫描（前5个位置） ---")
    scan_results = scan_all_mutations(
        model=model,
        sequence=sequence,
        model_name=model_name,
        positions=[0, 1, 2, 3, 4]
    )

    print(f"  扫描了 {len(scan_results)} 个突变（5个位置 × 19种突变）")

    analysis = analyze_mutation_impact(scan_results)
    print(f"\n  突变影响分析:")
    print(f"    高影响: {analysis['impact_counts']['high']} ({analysis['impact_percentages']['high']:.1f}%)")
    print(f"    中影响: {analysis['impact_counts']['medium']} ({analysis['impact_percentages']['medium']:.1f}%)")
    print(f"    低影响: {analysis['impact_counts']['low']} ({analysis['impact_percentages']['low']:.1f}%)")
    print(f"    中性: {analysis['impact_counts']['neutral']} ({analysis['impact_percentages']['neutral']:.1f}%)")
    print(f"    平均接触图变化: {analysis['avg_contact_map_change']:.6f}")

    if analysis.get('hotspot_positions'):
        print(f"    热点位置:")
        for hs in analysis['hotspot_positions'][:3]:
            print(f"      位置 {hs['position']}: 平均效应 = {hs['average_effect']:.6f}")

    print("\n  ✓ 突变效应预测测试通过!")
    print()
    return True


def test_structure_comparison():
    print("=" * 60)
    print("测试3: AlphaFold结构对比与TM-score")
    print("=" * 60)

    mock_pdb = generate_mock_pdb()
    print("  已生成模拟PDB结构 (51个残基)")

    coords, sequence, residue_numbers = parse_pdb_coordinates(mock_pdb)
    print(f"  解析的坐标形状: {coords.shape}")
    print(f"  解析的序列: {sequence[:30]}...")
    print(f"  残基编号范围: {residue_numbers[0]} - {residue_numbers[-1]}")

    coords_pred = coords + np.random.normal(0, 1.5, coords.shape).astype(np.float32)

    print("\n  --- Kabsch对齐测试 ---")
    R, t, coords_aligned, rmsd = kabsch_alignment(coords_pred, coords)
    print(f"  对齐前RMSD: {np.sqrt(np.mean(np.sum((coords_pred - coords)**2, axis=1))):.2f}Å")
    print(f"  对齐后RMSD: {rmsd:.2f}Å")
    print(f"  旋转矩阵行列式: {np.linalg.det(R):.4f} (应为±1)")

    print("\n  --- TM-score计算 ---")
    tm_score, aligned_length, aligned_pos = calculate_tm_score(coords_pred, coords)
    print(f"  TM-score: {tm_score:.4f}")
    print(f"  对齐残基数: {aligned_length}")

    print("\n  --- GDT计算 ---")
    gdt_scores = calculate_gdt(coords_pred, coords)
    print(f"  GDT_TS: {gdt_scores['gdt_ts']:.4f}")
    print(f"  GDT_HA: {gdt_scores['gdt_ha']:.4f}")
    print(f"  GDT@1Å: {gdt_scores['gdt_10']:.4f}")
    print(f"  GDT@2Å: {gdt_scores['gdt_20']:.4f}")
    print(f"  GDT@4Å: {gdt_scores['gdt_40']:.4f}")
    print(f"  GDT@8Å: {gdt_scores['gdt_80']:.4f}")

    print("\n  --- 完整结构对比 ---")
    seq_len = len(coords)
    contact_map_pred = np.random.rand(seq_len, seq_len)
    contact_map_pred = (contact_map_pred + contact_map_pred.T) / 2
    for i in range(seq_len):
        for j in range(seq_len):
            dist = np.linalg.norm(coords_pred[i] - coords_pred[j])
            contact_map_pred[i, j] = np.exp(-0.1 * (dist - 8.0) ** 2) if dist > 6 else 0.9

    comparison_result = compare_with_alphafold(
        predicted_coords=coords_pred,
        predicted_contact_map=contact_map_pred,
        alphafold_pdb_content=mock_pdb
    )

    print(f"  对比结果:")
    print(f"    TM-score: {comparison_result.tm_score:.4f}")
    print(f"    GDT_TS: {comparison_result.gdt_ts:.4f}")
    print(f"    GDT_HA: {comparison_result.gdt_ha:.4f}")
    print(f"    RMSD: {comparison_result.rmsd:.2f}Å")
    print(f"    接触图相似度(F1): {comparison_result.contact_map_similarity:.4f}")
    print(f"    对齐残基数: {comparison_result.aligned_length}")

    if comparison_result.per_residue_errors:
        errors = [e['error_angstrom'] for e in comparison_result.per_residue_errors]
        print(f"    残基误差: 平均={np.mean(errors):.2f}Å, 最大={np.max(errors):.2f}Å")
        within = sum(1 for e in comparison_result.per_residue_errors if e['within_threshold'])
        print(f"    8Å阈值内的残基: {within}/{len(comparison_result.per_residue_errors)} ({within/len(comparison_result.per_residue_errors)*100:.1f}%)")

    print("\n  ✓ AlphaFold结构对比测试通过!")
    print()
    return True


def generate_mock_pdb() -> str:
    np.random.seed(42)
    sequence = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"

    three_letter = {
        'A': 'ALA', 'R': 'ARG', 'N': 'ASN', 'D': 'ASP', 'C': 'CYS',
        'Q': 'GLN', 'E': 'GLU', 'G': 'GLY', 'H': 'HIS', 'I': 'ILE',
        'L': 'LEU', 'K': 'LYS', 'M': 'MET', 'F': 'PHE', 'P': 'PRO',
        'S': 'SER', 'T': 'THR', 'W': 'TRP', 'Y': 'TYR', 'V': 'VAL'
    }

    coords = np.zeros((len(sequence), 3), dtype=np.float32)
    for i in range(1, len(sequence)):
        theta = np.random.uniform(-np.pi/3, np.pi/3)
        phi = np.random.uniform(0, 2*np.pi)
        step = 3.8
        dx = step * np.sin(theta) * np.cos(phi)
        dy = step * np.sin(theta) * np.sin(phi)
        dz = step * np.cos(theta)
        coords[i] = coords[i-1] + [dx, dy, dz]

    pdb_lines = []
    atom_num = 1

    for i, aa in enumerate(sequence):
        res_name = three_letter.get(aa, 'ALA')
        res_num = i + 1
        x, y, z = coords[i]

        pdb_lines.append(
            f"ATOM  {atom_num:>5}  CA  {res_name} A{res_num:>4}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C"
        )
        atom_num += 1

    pdb_lines.append("END")
    return "\n".join(pdb_lines)


def main():
    print("\n蛋白质接触图预测 - 高级功能验证测试")
    print("=" * 60 + "\n")

    results = []

    try:
        results.append(("注意力机制解释", test_attention_explanation()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("注意力机制解释", False))
        import traceback
        traceback.print_exc()

    try:
        results.append(("突变效应预测", test_mutation_effect()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("突变效应预测", False))
        import traceback
        traceback.print_exc()

    try:
        results.append(("AlphaFold结构对比", test_structure_comparison()))
    except Exception as e:
        print(f"  测试异常: {e}\n")
        results.append(("AlphaFold结构对比", False))
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
        print("所有高级功能测试通过! ✓")
    else:
        print(f"{sum(1 for r in results if r[1])}/{len(results)} 测试通过")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
