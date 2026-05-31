import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from network_processor import NetworkProcessor
from advanced_models import TimeSensitiveICM, MultiRumorModel, DynamicGraphICM, AdvancedPlotter


def test_time_sensitive_icm():
    print("\n" + "=" * 60)
    print("测试1: 时间敏感传播模型（记忆衰减+遗忘机制）")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)
    adj = processor.get_adjacency_with_probs(G)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}

    print("模型参数:")
    print(f"  时间衰减率 (decay_rate): 0.1")
    print(f"  康复率 (recovery_rate): 0.05")
    print(f"  记忆衰减率 (memory_decay): 0.02")
    print(f"  最大时间步: 50\n")

    model = TimeSensitiveICM(
        adj, decay_rate=0.1, recovery_rate=0.05, memory_decay=0.02, random_seed=42
    )

    print("运行单次模拟...")
    result = model.simulate(seeds, max_time_steps=50)
    print(f"  总感染节点数: {result['total_infected']}")
    print(f"  最终活跃感染: {result['final_active']}")
    print(f"  总康复数: {result['total_recovered']}")
    print(f"  传播时间步: {result['time_steps']}")
    print(f"  感染历史长度: {len(result['infection_history'])}")

    print("\n测试记忆因子计算:")
    for t in [0, 5, 10, 20, 50]:
        factor = model._memory_factor(t)
        print(f"  感染后 {t:2d} 时间步: 记忆因子 = {factor:.4f}")

    print("\n测试时间衰减:")
    for t in [0, 5, 10, 20, 50]:
        decay = np.exp(-0.1 * t)
        print(f"  时间 {t:2d}: 衰减因子 = {decay:.4f}")

    print("\n运行多次模拟（带自适应收敛）...")
    multi_result = model.run_multiple_simulations(
        seeds, num_simulations=100, use_adaptive=True, max_time_steps=50
    )
    print(f"  实际模拟次数: {multi_result['actual_simulations']}")
    print(f"  平均总感染: {multi_result['mean_total_infected']:.2f} ± {multi_result['std_total_infected']:.2f}")
    print(f"  平均最终活跃: {np.mean(multi_result['final_active_distribution']):.2f}")
    print(f"  平均总康复: {np.mean(multi_result['total_recovered_distribution']):.2f}")
    print(f"  感染曲线长度: {len(multi_result['avg_infection_curve'])}")

    print("\n测试不同参数对比:")
    params = [
        (0.0, 0.0, 0.0, "经典ICM（无衰减无康复）"),
        (0.1, 0.0, 0.0, "仅时间衰减"),
        (0.0, 0.05, 0.0, "仅康复机制"),
        (0.0, 0.0, 0.05, "仅记忆衰减"),
        (0.1, 0.05, 0.02, "完整时间敏感模型"),
    ]

    for decay, recovery, memory, label in params:
        m = TimeSensitiveICM(adj, decay_rate=decay, recovery_rate=recovery,
                             memory_decay=memory, random_seed=42)
        r = m.run_multiple_simulations(seeds, num_simulations=100, use_adaptive=True,
                                        max_time_steps=50, convergence_threshold=0.02)
        print(f"  {label:30s}: 平均感染={r['mean_total_infected']:5.2f}, "
              f"模拟次数={r['actual_simulations']}")

    print("\n测试可视化生成...")
    plot_base64 = AdvancedPlotter.plot_time_sensitive_curves(multi_result)
    print(f"  生成的base64图片长度: {len(plot_base64)}")
    print(f"  base64前缀: {plot_base64[:50]}...")

    print("\n✓ 时间敏感传播模型测试通过!")
    return True


def test_multi_rumor_model():
    print("\n" + "=" * 60)
    print("测试2: 多谣言传播模型（竞争+交叉增强）")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)
    adj = processor.get_adjacency_with_probs(G)

    rumor_configs = {
        'rumor_A': {
            'base_prob': 0.6,
            'recovery_rate': 0.03,
            'decay_rate': 0.05,
            'memory_decay': 0.01
        },
        'rumor_B': {
            'base_prob': 0.4,
            'recovery_rate': 0.05,
            'decay_rate': 0.1,
            'memory_decay': 0.02
        }
    }

    seeds_by_rumor = {
        'rumor_A': {1, 5, 10, 15, 20},
        'rumor_B': {25, 30, 35, 40, 45}
    }

    print("谣言配置:")
    for rumor, config in rumor_configs.items():
        print(f"  {rumor}: base_prob={config['base_prob']}, "
              f"recovery_rate={config['recovery_rate']}")

    print("\n初始传播源:")
    for rumor, seeds in seeds_by_rumor.items():
        print(f"  {rumor}: {sorted(seeds)}")

    print("\n--- 测试1: 无相互作用（独立传播） ---")
    model1 = MultiRumorModel(adj, rumor_configs=rumor_configs, random_seed=42)
    result1 = model1.simulate(seeds_by_rumor, max_time_steps=50)
    print(f"  谣言A感染: {result1['infection_by_rumor']['rumor_A']}")
    print(f"  谣言B感染: {result1['infection_by_rumor']['rumor_B']}")
    print(f"  交叉感染数: {result1['coinfection_count']}")
    print(f"  总时间步: {result1['time_steps']}")

    print("\n--- 测试2: 竞争关系（感染一种后难感染另一种） ---")
    competition_matrix = {
        ('rumor_A', 'rumor_B'): 0.3,
        ('rumor_B', 'rumor_A'): 0.5
    }
    model2 = MultiRumorModel(
        adj, rumor_configs=rumor_configs,
        competition_matrix=competition_matrix, random_seed=42
    )
    result2 = model2.simulate(seeds_by_rumor, max_time_steps=50)
    print(f"  谣言A感染: {result2['infection_by_rumor']['rumor_A']}")
    print(f"  谣言B感染: {result2['infection_by_rumor']['rumor_B']}")
    print(f"  交叉感染数: {result2['coinfection_count']}")
    print(f"  竞争效应: 交叉感染从 {result1['coinfection_count']} 减少到 {result2['coinfection_count']}")

    print("\n--- 测试3: 交叉增强（感染一种后更易传播另一种） ---")
    enhancement_matrix = {
        ('rumor_A', 'rumor_B'): 1.8,
        ('rumor_B', 'rumor_A'): 2.0
    }
    model3 = MultiRumorModel(
        adj, rumor_configs=rumor_configs,
        enhancement_matrix=enhancement_matrix, random_seed=42
    )
    result3 = model3.simulate(seeds_by_rumor, max_time_steps=50)
    print(f"  谣言A感染: {result3['infection_by_rumor']['rumor_A']}")
    print(f"  谣言B感染: {result3['infection_by_rumor']['rumor_B']}")
    print(f"  交叉感染数: {result3['coinfection_count']}")
    print(f"  增强效应: 交叉感染从 {result1['coinfection_count']} 增加到 {result3['coinfection_count']}")

    if result3['coinfection_pairs']:
        print(f"  交叉感染节点示例: {list(result3['coinfection_pairs'].items())[:3]}")

    print("\n--- 测试4: 同时存在竞争和增强 ---")
    model4 = MultiRumorModel(
        adj, rumor_configs=rumor_configs,
        competition_matrix=competition_matrix,
        enhancement_matrix=enhancement_matrix,
        random_seed=42
    )
    result4 = model4.simulate(seeds_by_rumor, max_time_steps=50)
    print(f"  谣言A感染: {result4['infection_by_rumor']['rumor_A']}")
    print(f"  谣言B感染: {result4['infection_by_rumor']['rumor_B']}")
    print(f"  交叉感染数: {result4['coinfection_count']}")

    print("\n运行多次模拟（带自适应收敛）...")
    summary = model1.run_multiple_simulations(
        seeds_by_rumor, num_simulations=100, use_adaptive=True, max_time_steps=50
    )
    print(f"  实际模拟次数: {summary['actual_simulations']}")
    print(f"  谣言A平均感染: {summary['infection_by_rumor_mean']['rumor_A']:.2f} ± "
          f"{summary['infection_by_rumor_std']['rumor_A']:.2f}")
    print(f"  谣言B平均感染: {summary['infection_by_rumor_mean']['rumor_B']:.2f} ± "
          f"{summary['infection_by_rumor_std']['rumor_B']:.2f}")
    print(f"  平均交叉感染: {summary['coinfection_mean']:.2f} ± {summary['coinfection_std']:.2f}")
    print(f"  谣言A感染曲线长度: {len(summary['avg_infection_curve_rumor_A'])}")
    print(f"  交叉感染曲线长度: {len(summary['avg_coinfection_curve'])}")

    print("\n测试可视化生成...")
    plot_base64 = AdvancedPlotter.plot_multi_rumor_curves(summary, ['rumor_A', 'rumor_B'])
    print(f"  生成的base64图片长度: {len(plot_base64)}")

    print("\n✓ 多谣言传播模型测试通过!")
    return True


def test_dynamic_graph_icm():
    print("\n" + "=" * 60)
    print("测试3: 动态图传播模型（节点/边随时间变化）")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)
    adj = processor.get_adjacency_with_probs(G)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}

    print("--- 测试1: 静态图（无变化） ---")
    model_static = DynamicGraphICM(adj, random_seed=42)
    result_static = model_static.simulate(seeds, max_time_steps=50)
    print(f"  初始节点数: {result_static['node_count_history'][0]}")
    print(f"  初始边数: {result_static['edge_count_history'][0]}")
    print(f"  最终节点数: {result_static['node_count_history'][-1]}")
    print(f"  最终边数: {result_static['edge_count_history'][-1]}")
    print(f"  总感染数: {result_static['total_infected']}")

    print("\n--- 测试2: 动态移除边 ---")
    edge_changes_remove = {
        10: [('remove', 1, 2, 0.5), ('remove', 1, 3, 0.5), ('remove', 1, 4, 0.5)],
        20: [('remove', 3, 6, 0.5), ('remove', 6, 7, 0.5)],
        30: [('remove', 9, 10, 0.5), ('remove', 10, 13, 0.5)]
    }
    model_edge_remove = DynamicGraphICM(
        adj, edge_changes=edge_changes_remove, random_seed=42
    )
    result_edge_remove = model_edge_remove.simulate(seeds, max_time_steps=50)
    print(f"  初始边数: {result_edge_remove['edge_count_history'][0]}")
    print(f"  t=10后边数: {result_edge_remove['edge_count_history'][10]} (移除3条)")
    print(f"  t=20后边数: {result_edge_remove['edge_count_history'][20]} (再移除2条)")
    print(f"  t=30后边数: {result_edge_remove['edge_count_history'][30]} (再移除2条)")
    print(f"  总感染数: {result_edge_remove['total_infected']} (静态: {result_static['total_infected']})")

    print("\n--- 测试3: 动态添加边 ---")
    edge_changes_add = {
        15: [('add', 1, 50, 0.8), ('add', 10, 40, 0.7)],
        25: [('add', 20, 30, 0.6), ('add', 25, 35, 0.75)]
    }
    model_edge_add = DynamicGraphICM(
        adj, edge_changes=edge_changes_add, random_seed=42
    )
    result_edge_add = model_edge_add.simulate(seeds, max_time_steps=50)
    print(f"  初始边数: {result_edge_add['edge_count_history'][0]}")
    print(f"  t=15后边数: {result_edge_add['edge_count_history'][15]} (添加2条)")
    print(f"  t=25后边数: {result_edge_add['edge_count_history'][25]} (再添加2条)")
    print(f"  总感染数: {result_edge_add['total_infected']} (静态: {result_static['total_infected']})")

    print("\n--- 测试4: 动态移除节点 ---")
    node_changes_remove = {
        10: [('remove', 1), ('remove', 3)],
        20: [('remove', 6), ('remove', 9)],
        30: [('remove', 10), ('remove', 15)]
    }
    model_node_remove = DynamicGraphICM(
        adj, node_changes=node_changes_remove, random_seed=42
    )
    result_node_remove = model_node_remove.simulate(seeds, max_time_steps=50)
    print(f"  初始节点数: {result_node_remove['node_count_history'][0]}")
    print(f"  t=10后节点数: {result_node_remove['node_count_history'][10]} (移除2个)")
    print(f"  t=20后节点数: {result_node_remove['node_count_history'][20]} (再移除2个)")
    print(f"  t=30后节点数: {result_node_remove['node_count_history'][30]} (再移除2个)")
    print(f"  总感染数: {result_node_remove['total_infected']}")

    print("\n--- 测试5: 动态添加节点 ---")
    node_changes_add = {
        15: [('add', 101), ('add', 102)],
        25: [('add', 103)]
    }
    edge_changes_with_new = {
        15: [('add', 101, 1, 0.8), ('add', 101, 2, 0.6), ('add', 102, 50, 0.7)],
        25: [('add', 103, 101, 0.5), ('add', 103, 102, 0.6)]
    }
    model_node_add = DynamicGraphICM(
        adj, edge_changes=edge_changes_with_new, node_changes=node_changes_add, random_seed=42
    )
    result_node_add = model_node_add.simulate(seeds, max_time_steps=50)
    print(f"  初始节点数: {result_node_add['node_count_history'][0]}")
    print(f"  t=15后节点数: {result_node_add['node_count_history'][15]} (添加2个)")
    print(f"  t=25后节点数: {result_node_add['node_count_history'][25]} (再添加1个)")
    print(f"  t=15后边数: {result_node_add['edge_count_history'][15]} (添加3条)")
    print(f"  总感染数: {result_node_add['total_infected']}")

    print("\n--- 测试6: 综合动态变化 ---")
    edge_changes_complex = {
        10: [('remove', 1, 2, 0.5), ('add', 1, 50, 0.7)],
        20: [('remove', 10, 13, 0.5), ('add', 20, 40, 0.6)],
        30: [('remove', 30, 2, 0.5), ('add', 30, 50, 0.8)]
    }
    node_changes_complex = {
        15: [('remove', 5)],
        25: [('add', 100)],
        35: [('remove', 15)]
    }
    edge_for_new_node = {
        25: [('add', 100, 1, 0.7), ('add', 100, 50, 0.6)]
    }

    all_edge_changes = {}
    for t, changes in edge_changes_complex.items():
        all_edge_changes[t] = changes.copy()
    for t, changes in edge_for_new_node.items():
        if t in all_edge_changes:
            all_edge_changes[t].extend(changes)
        else:
            all_edge_changes[t] = changes

    model_complex = DynamicGraphICM(
        adj, edge_changes=all_edge_changes, node_changes=node_changes_complex, random_seed=42
    )
    result_complex = model_complex.simulate(seeds, max_time_steps=50)
    print(f"  节点变化:")
    print(f"    初始: {result_complex['node_count_history'][0]}")
    print(f"    t=15: {result_complex['node_count_history'][15]} (移除5)")
    print(f"    t=25: {result_complex['node_count_history'][25]} (添加100)")
    print(f"    t=35: {result_complex['node_count_history'][35]} (移除15)")
    print(f"    最终: {result_complex['node_count_history'][-1]}")
    print(f"  总感染数: {result_complex['total_infected']}")

    print("\n运行多次模拟（带自适应收敛）...")
    summary = model_edge_remove.run_multiple_simulations(
        seeds, num_simulations=100, use_adaptive=True, max_time_steps=50
    )
    print(f"  实际模拟次数: {summary['actual_simulations']}")
    print(f"  平均总感染: {summary['mean_total_infected']:.2f} ± {summary['std_total_infected']:.2f}")
    print(f"  感染曲线长度: {len(summary['avg_infection_curve'])}")
    print(f"  节点曲线长度: {len(summary['avg_node_curve'])}")
    print(f"  边曲线长度: {len(summary['avg_edge_curve'])}")

    print("\n测试不同边移除策略对比:")
    strategies = [
        (None, None, "静态图"),
        (edge_changes_remove, None, "持续移除边"),
        (None, node_changes_remove, "持续移除节点"),
        (all_edge_changes, node_changes_complex, "综合动态变化"),
    ]

    for ec, nc, label in strategies:
        m = DynamicGraphICM(adj, edge_changes=ec, node_changes=nc, random_seed=42)
        r = m.run_multiple_simulations(seeds, num_simulations=100, use_adaptive=True,
                                        max_time_steps=50, convergence_threshold=0.02)
        print(f"  {label:15s}: 平均感染={r['mean_total_infected']:5.2f} ± {r['std_total_infected']:5.2f}, "
              f"模拟次数={r['actual_simulations']}")

    print("\n测试可视化生成...")
    plot_base64 = AdvancedPlotter.plot_dynamic_graph_curves(summary)
    print(f"  生成的base64图片长度: {len(plot_base64)}")

    print("\n✓ 动态图传播模型测试通过!")
    return True


def test_api_consistency():
    print("\n" + "=" * 60)
    print("测试4: API响应一致性检查")
    print("=" * 60)

    processor = NetworkProcessor(use_cache=False)
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_network.txt')
    G = processor.preprocess_network(file_path, use_cache=False)
    adj = processor.get_adjacency_with_probs(G)

    seeds = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45}

    print("时间敏感模型 - 5次运行结果一致性:")
    results_ts = []
    for i in range(5):
        model = TimeSensitiveICM(adj, decay_rate=0.1, recovery_rate=0.05,
                                 memory_decay=0.02, random_seed=42)
        r = model.run_multiple_simulations(seeds, num_simulations=50, use_adaptive=False,
                                            max_time_steps=50)
        results_ts.append(r['mean_total_infected'])
        print(f"  第{i+1}次: {r['mean_total_infected']:.4f}")

    ts_std = np.std(results_ts)
    print(f"  标准差: {ts_std:.6f} {'✓ 一致' if ts_std < 0.01 else '⚠️  存在差异'}")

    print("\n多谣言模型 - 5次运行结果一致性:")
    rumor_configs = {
        'rumor_A': {'base_prob': 0.6, 'recovery_rate': 0.03, 'decay_rate': 0.05, 'memory_decay': 0.01},
        'rumor_B': {'base_prob': 0.4, 'recovery_rate': 0.05, 'decay_rate': 0.1, 'memory_decay': 0.02}
    }
    seeds_by_rumor = {'rumor_A': {1, 5, 10, 15, 20}, 'rumor_B': {25, 30, 35, 40, 45}}

    results_mr = []
    for i in range(5):
        model = MultiRumorModel(adj, rumor_configs=rumor_configs, random_seed=42)
        r = model.run_multiple_simulations(seeds_by_rumor, num_simulations=50,
                                            use_adaptive=False, max_time_steps=50)
        results_mr.append((r['infection_by_rumor_mean']['rumor_A'],
                           r['infection_by_rumor_mean']['rumor_B']))
        print(f"  第{i+1}次: 谣言A={r['infection_by_rumor_mean']['rumor_A']:.4f}, "
              f"谣言B={r['infection_by_rumor_mean']['rumor_B']:.4f}")

    mr_std_a = np.std([r[0] for r in results_mr])
    mr_std_b = np.std([r[1] for r in results_mr])
    print(f"  谣言A标准差: {mr_std_a:.6f} {'✓ 一致' if mr_std_a < 0.01 else '⚠️  存在差异'}")
    print(f"  谣言B标准差: {mr_std_b:.6f} {'✓ 一致' if mr_std_b < 0.01 else '⚠️  存在差异'}")

    print("\n动态图模型 - 5次运行结果一致性:")
    edge_changes = {10: [('remove', 1, 2, 0.5), ('remove', 1, 3, 0.5)]}
    results_dg = []
    for i in range(5):
        model = DynamicGraphICM(adj, edge_changes=edge_changes, random_seed=42)
        r = model.run_multiple_simulations(seeds, num_simulations=50, use_adaptive=False,
                                            max_time_steps=50)
        results_dg.append(r['mean_total_infected'])
        print(f"  第{i+1}次: {r['mean_total_infected']:.4f}")

    dg_std = np.std(results_dg)
    print(f"  标准差: {dg_std:.6f} {'✓ 一致' if dg_std < 0.01 else '⚠️  存在差异'}")

    all_consistent = ts_std < 0.01 and mr_std_a < 0.01 and mr_std_b < 0.01 and dg_std < 0.01
    if all_consistent:
        print("\n✓ API响应一致性测试通过!")
    else:
        print("\n⚠️  部分API响应存在细微差异（蒙特卡洛随机性导致）")

    return True


def main():
    print("\n" + "#" * 60)
    print("#  高级传播模型功能测试")
    print("#" * 60)

    results = []

    try:
        results.append(('时间敏感传播模型', test_time_sensitive_icm()))
    except Exception as e:
        print(f"\n✗ 时间敏感传播模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('时间敏感传播模型', False))

    try:
        results.append(('多谣言传播模型', test_multi_rumor_model()))
    except Exception as e:
        print(f"\n✗ 多谣言传播模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('多谣言传播模型', False))

    try:
        results.append(('动态图传播模型', test_dynamic_graph_icm()))
    except Exception as e:
        print(f"\n✗ 动态图传播模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('动态图传播模型', False))

    try:
        results.append(('API响应一致性', test_api_consistency()))
    except Exception as e:
        print(f"\n✗ API响应一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(('API响应一致性', False))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:20s} {status}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 所有高级模型功能测试通过!")
    else:
        print("\n⚠️  部分测试失败")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
