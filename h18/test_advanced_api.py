import os
import sys
import json
import time
import requests
import base64
from io import BytesIO


def save_base64_image(base64_str, output_path):
    try:
        img_data = base64.b64decode(base64_str)
        with open(output_path, 'wb') as f:
            f.write(img_data)
        print(f"  图片已保存到: {output_path}")
        return True
    except Exception as e:
        print(f"  保存图片失败: {e}")
        return False


def wait_for_server(base_url, max_wait=30):
    print("等待服务器就绪...")
    for i in range(max_wait):
        try:
            requests.get(f"{base_url}/api/health", timeout=2)
            print("服务器已就绪!")
            return True
        except Exception:
            time.sleep(1)
            print(f"  重试 {i+1}/{max_wait}...")
    print("服务器启动超时!")
    return False


def test_time_sensitive_api(base_url, output_dir):
    print("\n" + "=" * 60)
    print("API测试1: 时间敏感传播模型")
    print("=" * 60)

    payload = {
        'network': 'sample_network.txt',
        'seeds': [1, 5, 10, 15, 20, 25, 30, 35, 40, 45],
        'vaccinated': [],
        'simulations': 100,
        'max_time_steps': 50,
        'decay_rate': 0.1,
        'recovery_rate': 0.05,
        'memory_decay': 0.02,
        'use_adaptive': True
    }

    print("请求参数:")
    print(f"  初始传播源: {payload['seeds']}")
    print(f"  时间衰减率: {payload['decay_rate']}")
    print(f"  康复率: {payload['recovery_rate']}")
    print(f"  记忆衰减率: {payload['memory_decay']}")
    print(f"  最大时间步: {payload['max_time_steps']}")
    print(f"  模拟次数: {payload['simulations']}\n")

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/time_sensitive",
            json=payload,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}")
        print(f"总耗时: {elapsed:.2f}s\n")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print("结果摘要:")
        print(f"  实际模拟次数: {data['actual_simulations']}")
        print(f"  平均总感染: {data['mean_total_infected']:.2f} ± {data['std_total_infected']:.2f}")
        print(f"  平均最终活跃: {data['mean_final_active']:.2f}")
        print(f"  平均总康复: {data['mean_total_recovered']:.2f}")
        print(f"  感染曲线长度: {len(data['avg_infection_curve'])}")
        print(f"  康复曲线长度: {len(data['avg_recovered_curve'])}")
        print(f"  传播范围分布长度: {len(data['total_infected_distribution'])}")
        print(f"  Plot base64长度: {len(data['plot_base64'])}")

        print("\n参数对比（与经典ICM比较）:")
        payload_no_decay = payload.copy()
        payload_no_decay['decay_rate'] = 0.0
        payload_no_decay['recovery_rate'] = 0.0
        payload_no_decay['memory_decay'] = 0.0
        response2 = requests.post(
            f"{base_url}/api/simulate/time_sensitive",
            json=payload_no_decay,
            timeout=120
        )
        data2 = response2.json()
        print(f"  经典ICM(无衰减): 平均感染={data2['mean_total_infected']:.2f}")
        print(f"  时间敏感模型: 平均感染={data['mean_total_infected']:.2f}")
        print(f"  衰减效应减少: {(data2['mean_total_infected'] - data['mean_total_infected']):.2f} 个节点")

        print("\n保存可视化结果...")
        img_path = os.path.join(output_dir, 'time_sensitive_curves.png')
        save_base64_image(data['plot_base64'], img_path)

        print("\n✓ 时间敏感传播模型API测试通过!")
        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_rumor_api(base_url, output_dir):
    print("\n" + "=" * 60)
    print("API测试2: 多谣言传播模型（竞争+交叉增强）")
    print("=" * 60)

    payload = {
        'network': 'sample_network.txt',
        'seeds_by_rumor': {
            'rumor_A': [1, 5, 10, 15, 20],
            'rumor_B': [25, 30, 35, 40, 45]
        },
        'vaccinated': [],
        'rumor_configs': {
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
        },
        'simulations': 100,
        'max_time_steps': 50,
        'use_adaptive': True
    }

    print("--- 测试1: 无相互作用 ---")
    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/multi_rumor",
            json=payload,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  实际模拟次数: {data['actual_simulations']}")
        print(f"  谣言A平均感染: {data['infection_by_rumor_mean']['rumor_A']:.2f} ± {data['infection_by_rumor_std']['rumor_A']:.2f}")
        print(f"  谣言B平均感染: {data['infection_by_rumor_mean']['rumor_B']:.2f} ± {data['infection_by_rumor_std']['rumor_B']:.2f}")
        print(f"  平均交叉感染: {data['coinfection_mean']:.2f} ± {data['coinfection_std']:.2f}")
        base_coinfection = data['coinfection_mean']

        img_path = os.path.join(output_dir, 'multi_rumor_no_interaction.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n--- 测试2: 竞争关系 ---")
    payload_competition = payload.copy()
    payload_competition['competition_matrix'] = {
        'rumor_A,rumor_B': 0.3,
        'rumor_B,rumor_A': 0.5
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/multi_rumor",
            json=payload_competition,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  谣言A平均感染: {data['infection_by_rumor_mean']['rumor_A']:.2f}")
        print(f"  谣言B平均感染: {data['infection_by_rumor_mean']['rumor_B']:.2f}")
        print(f"  平均交叉感染: {data['coinfection_mean']:.2f} (无竞争时: {base_coinfection:.2f})")
        print(f"  竞争效应: 交叉感染减少 {(base_coinfection - data['coinfection_mean']):.2f}")

        img_path = os.path.join(output_dir, 'multi_rumor_competition.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n--- 测试3: 交叉增强 ---")
    payload_enhancement = payload.copy()
    payload_enhancement['enhancement_matrix'] = {
        'rumor_A,rumor_B': 1.8,
        'rumor_B,rumor_A': 2.0
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/multi_rumor",
            json=payload_enhancement,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  谣言A平均感染: {data['infection_by_rumor_mean']['rumor_A']:.2f}")
        print(f"  谣言B平均感染: {data['infection_by_rumor_mean']['rumor_B']:.2f}")
        print(f"  平均交叉感染: {data['coinfection_mean']:.2f} (无增强时: {base_coinfection:.2f})")
        print(f"  增强效应: 交叉感染增加 {(data['coinfection_mean'] - base_coinfection):.2f}")

        img_path = os.path.join(output_dir, 'multi_rumor_enhancement.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n✓ 多谣言传播模型API测试通过!")
    return True


def test_dynamic_graph_api(base_url, output_dir):
    print("\n" + "=" * 60)
    print("API测试3: 动态图传播模型（节点/边随时间变化）")
    print("=" * 60)

    print("--- 测试1: 静态图（基线） ---")
    payload_static = {
        'network': 'sample_network.txt',
        'seeds': [1, 5, 10, 15, 20, 25, 30, 35, 40, 45],
        'vaccinated': [],
        'simulations': 100,
        'max_time_steps': 50,
        'use_adaptive': True
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/dynamic_graph",
            json=payload_static,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  实际模拟次数: {data['actual_simulations']}")
        print(f"  平均总感染: {data['mean_total_infected']:.2f} ± {data['std_total_infected']:.2f}")
        print(f"  初始节点数: {data['avg_node_curve'][0]}")
        print(f"  初始边数: {data['avg_edge_curve'][0]}")
        print(f"  最终节点数: {data['avg_node_curve'][-1]}")
        print(f"  最终边数: {data['avg_edge_curve'][-1]}")
        base_infected = data['mean_total_infected']

        img_path = os.path.join(output_dir, 'dynamic_graph_static.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n--- 测试2: 动态移除边 ---")
    payload_edge_remove = payload_static.copy()
    payload_edge_remove['edge_changes'] = {
        '10': [['remove', 1, 2, 0.5], ['remove', 1, 3, 0.5], ['remove', 1, 4, 0.5]],
        '20': [['remove', 3, 6, 0.5], ['remove', 6, 7, 0.5]],
        '30': [['remove', 9, 10, 0.5], ['remove', 10, 13, 0.5]]
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/dynamic_graph",
            json=payload_edge_remove,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  平均总感染: {data['mean_total_infected']:.2f} (静态: {base_infected:.2f})")
        print(f"  t=0边数: {data['avg_edge_curve'][0]}")
        print(f"  t=10边数: {data['avg_edge_curve'][10]} (移除3条)")
        print(f"  t=20边数: {data['avg_edge_curve'][20]} (再移除2条)")
        print(f"  t=30边数: {data['avg_edge_curve'][30]} (再移除2条)")

        img_path = os.path.join(output_dir, 'dynamic_graph_edge_remove.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n--- 测试3: 动态移除节点 ---")
    payload_node_remove = payload_static.copy()
    payload_node_remove['node_changes'] = {
        '10': [['remove', 1], ['remove', 3]],
        '20': [['remove', 6], ['remove', 9]],
        '30': [['remove', 10], ['remove', 15]]
    }
    payload_node_remove['edge_changes'] = {}

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/dynamic_graph",
            json=payload_node_remove,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  平均总感染: {data['mean_total_infected']:.2f} (静态: {base_infected:.2f})")
        print(f"  t=0节点数: {data['avg_node_curve'][0]}")
        print(f"  t=10节点数: {data['avg_node_curve'][10]} (移除2个)")
        print(f"  t=20节点数: {data['avg_node_curve'][20]} (再移除2个)")
        print(f"  t=30节点数: {data['avg_node_curve'][30]} (再移除2个)")

        img_path = os.path.join(output_dir, 'dynamic_graph_node_remove.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n--- 测试4: 综合动态变化 ---")
    payload_complex = payload_static.copy()
    payload_complex['edge_changes'] = {
        '10': [['remove', 1, 2, 0.5], ['add', 1, 50, 0.7]],
        '20': [['remove', 10, 13, 0.5], ['add', 20, 40, 0.6]],
        '30': [['remove', 30, 2, 0.5], ['add', 30, 50, 0.8]]
    }
    payload_complex['node_changes'] = {
        '15': [['remove', 5]],
        '25': [['add', 100]],
        '35': [['remove', 15]]
    }
    payload_complex['edge_changes']['25'] = [['add', 100, 1, 0.7], ['add', 100, 50, 0.6]]

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/simulate/dynamic_graph",
            json=payload_complex,
            timeout=120
        )
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}, 总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print(f"  平均总感染: {data['mean_total_infected']:.2f} (静态: {base_infected:.2f})")
        print(f"  t=0节点数: {data['avg_node_curve'][0]}")
        print(f"  t=15节点数: {data['avg_node_curve'][15]} (移除5)")
        print(f"  t=25节点数: {data['avg_node_curve'][25]} (添加100)")
        print(f"  t=35节点数: {data['avg_node_curve'][35]} (移除15)")

        img_path = os.path.join(output_dir, 'dynamic_graph_complex.png')
        save_base64_image(data['plot_base64'], img_path)

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n✓ 动态图传播模型API测试通过!")
    return True


def main():
    base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    output_dir = os.path.join(os.path.dirname(__file__), 'test_output', 'advanced')

    print("\n" + "#" * 60)
    print("#  高级模型API集成测试")
    print(f"#  目标服务器: {base_url}")
    print("#" * 60)

    os.makedirs(output_dir, exist_ok=True)

    if not wait_for_server(base_url):
        return False

    results = []

    results.append(('时间敏感传播API', test_time_sensitive_api(base_url, output_dir)))
    results.append(('多谣言传播API', test_multi_rumor_api(base_url, output_dir)))
    results.append(('动态图传播API', test_dynamic_graph_api(base_url, output_dir)))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:20s} {status}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 所有高级模型API测试通过!")
    else:
        print("\n⚠️  部分测试失败")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
