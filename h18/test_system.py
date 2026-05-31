import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from network_processor import NetworkProcessor
from influence_maximization import InfluenceMaximization
from simulation import ICMModel, CDFPlotter, compute_statistics


def test_network_processor():
    print("=" * 60)
    print("测试1: 网络数据处理器")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')

    edges = processor.load_edge_list(file_path)
    print(f"加载边数: {len(edges)}")
    print(f"前5条边: {edges[:5]}")

    G = processor.build_graph(edges)
    print(f"节点数: {G.number_of_nodes()}")
    print(f"边数: {G.number_of_edges()}")

    adj = processor.get_adjacency_with_probs(G)
    print(f"节点1的邻居数: {len(adj.get(1, []))}")
    if 1 in adj and adj[1]:
        print(f"节点1的第一个邻居及传播概率: {adj[1][0]}")

    print("✓ 网络数据处理器测试通过\n")
    return G, adj


def test_influence_maximization(G):
    print("=" * 60)
    print("测试2: 影响力最大化算法")
    print("=" * 60)

    im = InfluenceMaximization(G)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}
    k = 5
    exclude_nodes = set(seeds)

    print(f"初始传播源: {sorted(seeds)}")
    print(f"选择免疫节点数 k={k}\n")

    print("--- PageRank ---")
    pr_nodes, pr_time = im.pagerank(k, exclude_nodes)
    print(f"推荐节点: {pr_nodes}")
    print(f"运行时间: {pr_time:.4f}s\n")

    print("--- 度中心性 ---")
    deg_nodes, deg_time = im.degree_centrality(k, exclude_nodes)
    print(f"推荐节点: {deg_nodes}")
    print(f"运行时间: {deg_time:.4f}s\n")

    print("--- K-core ---")
    kcore_nodes, kcore_time = im.k_core(k, exclude_nodes)
    print(f"推荐节点: {kcore_nodes}")
    print(f"运行时间: {kcore_time:.4f}s\n")

    print("--- 贪心算法 (蒙特卡洛模拟次数减少以加快测试) ---")
    greedy_nodes, greedy_time = im.greedy(k, seeds, exclude_nodes)
    print(f"推荐节点: {greedy_nodes}")
    print(f"运行时间: {greedy_time:.4f}s\n")

    print("--- CELF优化 ---")
    celf_nodes, celf_time = im.celf(k, seeds, exclude_nodes)
    print(f"推荐节点: {celf_nodes}")
    print(f"运行时间: {celf_time:.4f}s\n")

    print("✓ 影响力最大化算法测试通过\n")
    return im, seeds


def test_icm_simulation(adj, seeds):
    print("=" * 60)
    print("测试3: 独立级联模型(ICM)传播模拟")
    print("=" * 60)

    icm = ICMModel(adj)

    print(f"初始传播源: {sorted(seeds)}")

    base_result = icm.simulate(seeds)
    print(f"单次模拟 - 无免疫感染节点数: {base_result}")

    vaccinated = {3, 8, 12}
    protected_result = icm.simulate(seeds, vaccinated)
    print(f"单次模拟 - 免疫{vaccinated}后感染节点数: {protected_result}")

    print("\n运行200次蒙特卡洛模拟...")
    base_spreads = icm.run_multiple_simulations(seeds, num_simulations=200)
    protected_spreads = icm.run_multiple_simulations(seeds, vaccinated, num_simulations=200)

    base_mean = np.mean(base_spreads)
    protected_mean = np.mean(protected_spreads)

    print(f"无免疫 - 平均感染: {base_mean:.2f}")
    print(f"免疫后 - 平均感染: {protected_mean:.2f}")
    print(f"减少比例: {(base_mean - protected_mean) / base_mean * 100:.2f}%")

    base_stats = compute_statistics(base_spreads)
    print(f"\n无免疫统计:")
    print(f"  均值: {base_stats['mean']:.2f}, 中位数: {base_stats['median']:.2f}")
    print(f"  标准差: {base_stats['std']:.2f}, 范围: [{base_stats['min']}, {base_stats['max']}]")

    print("✓ ICM传播模拟测试通过\n")
    return base_spreads, protected_spreads


def test_cdf_plotting(base_spreads, protected_spreads):
    print("=" * 60)
    print("测试4: CDF曲线绘制和base64编码")
    print("=" * 60)

    distributions = {
        '无免疫': base_spreads,
        '免疫后': protected_spreads
    }

    print("生成CDF对比图...")
    cdf_base64 = CDFPlotter.generate_cdf_plot(distributions)
    print(f"CDF图片base64长度: {len(cdf_base64)}")
    print(f"base64前缀: {cdf_base64[:50]}...")

    evaluations = {
        'pagerank': {'reduction_ratio': 0.35},
        'degree_centrality': {'reduction_ratio': 0.28},
        'k_core': {'reduction_ratio': 0.31}
    }

    print("生成减少比例柱状图...")
    bar_base64 = CDFPlotter.generate_reduction_bar_chart(evaluations)
    print(f"柱状图base64长度: {len(bar_base64)}")

    print("✓ CDF曲线绘制测试通过\n")
    return cdf_base64, bar_base64


def test_full_pipeline():
    print("\n" + "=" * 60)
    print("测试5: 完整流程测试")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}
    k = 5

    im = InfluenceMaximization(G)

    print("运行所有算法(模拟次数减少)...")
    results = im.run_all_algorithms(k, seeds)

    print("\n各算法结果:")
    for algo_name, algo_data in results.items():
        print(f"  {algo_name:20s} - 节点: {algo_data['nodes']}, 时间: {algo_data['time']:.4f}s")

    print("\n评估各算法效果...")
    evaluations = im.evaluate_strategies(results, seeds, simulations=100)

    print("\n各算法效果评估:")
    for algo_name, eval_data in evaluations.items():
        reduction_pct = eval_data['reduction_ratio'] * 100
        print(f"  {algo_name:20s} - 减少比例: {reduction_pct:.2f}%, "
              f"基础传播: {eval_data['base_spread']:.2f}, "
              f"免疫后: {eval_data['protected_spread']:.2f}")

    adj = processor.get_adjacency_with_probs(G)
    icm = ICMModel(adj)

    distributions = {'无免疫 (Baseline)': icm.run_multiple_simulations(seeds, num_simulations=100)}
    for algo_name, algo_data in results.items():
        vaccinated = set(algo_data['nodes'])
        spreads = icm.run_multiple_simulations(seeds, vaccinated, num_simulations=100)
        distributions[f'{algo_name} (免疫)'] = spreads

    print("\n生成CDF对比图...")
    cdf_base64 = CDFPlotter.generate_cdf_plot(distributions)
    print(f"CDF图片生成成功, base64长度: {len(cdf_base64)}")

    print("\n✓ 完整流程测试通过\n")


def main():
    print("\n" + "#" * 60)
    print("#  社交网络谣言传播与免疫策略分析系统 - 单元测试")
    print("#" * 60 + "\n")

    try:
        G, adj = test_network_processor()
        im, seeds = test_influence_maximization(G)
        base_spreads, protected_spreads = test_icm_simulation(adj, seeds)
        test_cdf_plotting(base_spreads, protected_spreads)
        test_full_pipeline()

        print("=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
        return True

    except Exception as e:
        import traceback
        print(f"\n✗ 测试失败: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
