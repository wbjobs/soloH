import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from network_processor import NetworkProcessor
from influence_maximization import InfluenceMaximization
from simulation import ICMModel, _check_convergence


def test_k_core_stability():
    print("\n" + "=" * 60)
    print("测试1: K-core排序稳定性 (修复孤立节点层数错乱)")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)

    im = InfluenceMaximization(G, random_seed=42)

    print("运行10次K-core算法，检查结果一致性...")
    results = []
    for i in range(10):
        nodes, _ = im.k_core(k=10)
        results.append(nodes)
        print(f"  第{i+1}次: {nodes}")

    all_same = all(r == results[0] for r in results)
    print(f"\n所有结果是否一致: {all_same}")

    import networkx as nx
    core_numbers = nx.core_number(G)
    print(f"\nCore number分布:")
    core_counts = {}
    for node, core in core_numbers.items():
        core_counts[core] = core_counts.get(core, 0) + 1
    for core in sorted(core_counts.keys()):
        print(f"  Core {core}: {core_counts[core]}个节点")

    zero_core_nodes = [n for n, c in core_numbers.items() if c == 0]
    if zero_core_nodes:
        print(f"\n孤立节点(core=0): {zero_core_nodes}")
        print("修复前: 这些节点排序随机")
        print("修复后: 按node升序稳定排序")

    assert all_same, "K-core排序不稳定!"
    print("\n✓ K-core排序稳定性测试通过!")
    return True


def test_pagerank_stability():
    print("\n" + "=" * 60)
    print("测试2: PageRank排序稳定性 (修复值相近时排序不稳定)")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)

    print("运行10次PageRank算法，使用不同随机种子，检查结果一致性...")

    results = []
    for seed in [42, 123, 456, 789, 1000, 2000, 3000, 4000, 5000, 6000]:
        im = InfluenceMaximization(G, random_seed=seed)
        nodes, _ = im.pagerank(k=10)
        results.append((seed, nodes))
        print(f"  Seed={seed:4d}: {nodes}")

    all_same = all(r[1] == results[0][1] for r in results)
    print(f"\n所有结果是否一致: {all_same}")

    import networkx as nx
    pr = nx.pagerank(G, alpha=0.85, weight='weight')
    sorted_pr = sorted(pr.items(), key=lambda x: (-round(x[1], 10), x[0]))
    print(f"\n前10个节点的PageRank值(保留10位小数):")
    for i, (node, val) in enumerate(sorted_pr[:10]):
        print(f"  {i+1}. Node {node:2d}: {val:.10f}")

    assert all_same, "PageRank排序不稳定!"
    print("\n✓ PageRank排序稳定性测试通过!")
    return True


def test_icm_convergence():
    print("\n" + "=" * 60)
    print("测试3: ICM模拟收敛性 (修复方差过大问题)")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)
    adj = processor.get_adjacency_with_probs(G)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}

    print("对比固定次数 vs 自适应收敛:")
    print("-" * 60)

    icm1 = ICMModel(adj, random_seed=42)
    results_fixed = []
    for i in range(5):
        spreads = icm1.run_multiple_simulations(seeds, num_simulations=50, use_adaptive=False)
        mean = np.mean(spreads)
        results_fixed.append(mean)
        print(f"  固定50次 - 第{i+1}次: 均值={mean:.2f}, 样本数={len(spreads)}")

    print()
    icm2 = ICMModel(adj, random_seed=42)
    results_adaptive = []
    for i in range(5):
        spreads = icm2.run_multiple_simulations(
            seeds, num_simulations=100, use_adaptive=True,
            max_simulations=500, convergence_threshold=0.015
        )
        mean = np.mean(spreads)
        results_adaptive.append(mean)
        converged = _check_convergence(spreads, threshold=0.015, min_samples=100)
        print(f"  自适应收敛 - 第{i+1}次: 均值={mean:.2f}, 样本数={len(spreads)}, 已收敛={converged}")

    print("\n统计对比:")
    fixed_std = np.std(results_fixed)
    adaptive_std = np.std(results_adaptive)
    print(f"  固定次数的结果标准差: {fixed_std:.4f}")
    print(f"  自适应收敛的结果标准差: {adaptive_std:.4f}")
    print(f"  方差降低比例: {(fixed_std - adaptive_std) / fixed_std * 100:.1f}%" if fixed_std > 0 else "  方差为0")

    print("\n收敛检查函数测试:")
    test_data1 = list(range(100)) + list(range(100, 200))
    test_data2 = [40] * 100 + [40] * 100
    print(f"  递增序列是否收敛: {_check_convergence(test_data1, threshold=0.01, min_samples=50)} (期望: False)")
    print(f"  恒定序列是否收敛: {_check_convergence(test_data2, threshold=0.01, min_samples=50)} (期望: True)")

    assert adaptive_std <= fixed_std, "自适应收敛的方差应该小于等于固定次数!"
    print("\n✓ ICM收敛性测试通过!")
    return True


def test_api_consistency():
    print("\n" + "=" * 60)
    print("测试4: API返回一致性 (重复调用返回相同结果)")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}

    results = []
    for i in range(3):
        print(f"\n第{i+1}次完整运行...")
        im = InfluenceMaximization(G, random_seed=42)
        algo_results = im.run_all_algorithms(k=5, seeds=seeds)
        results.append(algo_results)

        for algo_name, data in algo_results.items():
            print(f"  {algo_name:20s}: {data['nodes']}")

    print("\n检查各算法结果一致性:")
    all_consistent = True
    for algo_name in results[0].keys():
        nodes_list = [r[algo_name]['nodes'] for r in results]
        consistent = all(n == nodes_list[0] for n in nodes_list)
        status = "✓ 一致" if consistent else "✗ 不一致"
        print(f"  {algo_name:20s}: {status}")
        if not consistent:
            all_consistent = False
            for j, n in enumerate(nodes_list):
                print(f"    第{j+1}次: {n}")

    assert all_consistent, "API返回结果不一致!"
    print("\n✓ API返回一致性测试通过!")
    return True


def main():
    print("\n" + "#" * 60)
    print("#  三项Bug修复验证测试")
    print("#" * 60)

    results = []

    try:
        results.append(('K-core稳定性', test_k_core_stability()))
    except Exception as e:
        print(f"\n✗ K-core稳定性测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('K-core稳定性', False))

    try:
        results.append(('PageRank稳定性', test_pagerank_stability()))
    except Exception as e:
        print(f"\n✗ PageRank稳定性测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('PageRank稳定性', False))

    try:
        results.append(('ICM收敛性', test_icm_convergence()))
    except Exception as e:
        print(f"\n✗ ICM收敛性测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('ICM收敛性', False))

    try:
        results.append(('API一致性', test_api_consistency()))
    except Exception as e:
        print(f"\n✗ API一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('API一致性', False))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:20s} {status}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 所有修复验证测试通过!")
    else:
        print("\n⚠️  部分测试失败")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
