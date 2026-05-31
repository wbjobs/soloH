import os
import sys
import json
import time
import requests
import base64
from io import BytesIO
from PIL import Image


def save_base64_image(base64_str, output_path):
    try:
        img_data = base64.b64decode(base64_str)
        img = Image.open(BytesIO(img_data))
        img.save(output_path)
        print(f"图片已保存到: {output_path}")
        return True
    except Exception as e:
        print(f"保存图片失败: {e}")
        return False


def test_health_check(base_url):
    print("\n" + "=" * 60)
    print("测试1: 健康检查")
    print("=" * 60)

    try:
        response = requests.get(f"{base_url}/api/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        print("✓ 健康检查通过")
        return True
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
        return False


def test_list_networks(base_url):
    print("\n" + "=" * 60)
    print("测试2: 获取可用网络列表")
    print("=" * 60)

    try:
        response = requests.get(f"{base_url}/api/networks")
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        assert response.status_code == 200
        assert 'networks' in data
        print(f"✓ 获取到 {len(data['networks'])} 个网络文件")
        return True
    except Exception as e:
        print(f"✗ 获取网络列表失败: {e}")
        return False


def test_network_info(base_url):
    print("\n" + "=" * 60)
    print("测试3: 获取网络信息")
    print("=" * 60)

    try:
        response = requests.get(f"{base_url}/api/network/info?network=sample_network.txt")
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        assert response.status_code == 200
        assert data['nodes'] == 50
        print("✓ 网络信息获取成功")
        return True
    except Exception as e:
        print(f"✗ 获取网络信息失败: {e}")
        return False


def test_immunize(base_url, output_dir):
    print("\n" + "=" * 60)
    print("测试4: 免疫节点推荐 (核心API)")
    print("=" * 60)

    seeds = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45]
    payload = {
        'network': 'sample_network.txt',
        'seeds': seeds,
        'k': 5,
        'simulations': 100,
        'algorithms': ['pagerank', 'degree_centrality', 'k_core', 'greedy', 'celf']
    }

    try:
        print(f"请求参数:")
        print(f"  初始传播源 (10个): {seeds}")
        print(f"  选择免疫节点数 k=5")
        print(f"  蒙特卡洛模拟次数: 100")
        print("\n正在处理（贪心算法和CELF可能需要一些时间）...\n")

        start_time = time.time()
        response = requests.post(f"{base_url}/api/immunize", json=payload, timeout=120)
        elapsed = time.time() - start_time

        print(f"状态码: {response.status_code}")
        print(f"总耗时: {elapsed:.2f}s")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()

        print("\n" + "-" * 60)
        print("各算法推荐免疫节点:")
        print("-" * 60)

        for algo_name, algo_data in data['algorithms'].items():
            reduction_pct = algo_data['reduction_ratio'] * 100
            print(f"\n【{algo_name}】")
            print(f"  推荐节点: {algo_data['recommended_nodes']}")
            print(f"  算法运行时间: {algo_data['algorithm_runtime']:.4f}s")
            print(f"  无免疫平均感染: {algo_data['base_spread_mean']:.2f}")
            print(f"  免疫后平均感染: {algo_data['protected_spread_mean']:.2f}")
            print(f"  感染减少数: {algo_data['infected_reduction']:.2f}")
            print(f"  减少比例: {reduction_pct:.2f}%")

        print("\n" + "-" * 60)
        print("保存生成的图表:")
        print("-" * 60)

        os.makedirs(output_dir, exist_ok=True)

        cdf_path = os.path.join(output_dir, 'cdf_comparison.png')
        if save_base64_image(data['cdf_plot_base64'], cdf_path):
            print(f"  CDF对比图已保存")

        bar_path = os.path.join(output_dir, 'reduction_comparison.png')
        if save_base64_image(data['reduction_plot_base64'], bar_path):
            print(f"  减少比例对比图已保存")

        print("\n✓ 免疫节点推荐测试通过")
        return True

    except Exception as e:
        print(f"✗ 免疫节点推荐测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simulate(base_url):
    print("\n" + "=" * 60)
    print("测试5: 自定义传播模拟")
    print("=" * 60)

    payload = {
        'network': 'sample_network.txt',
        'seeds': [1, 5, 10, 15, 20, 25, 30, 35, 40, 45],
        'vaccinated': [3, 9, 33, 50, 36],
        'simulations': 100
    }

    try:
        print(f"初始传播源: {payload['seeds']}")
        print(f"免疫节点: {payload['vaccinated']}")
        print(f"模拟次数: {payload['simulations']}\n")

        response = requests.post(f"{base_url}/api/simulate", json=payload, timeout=60)
        print(f"状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")
            return False

        data = response.json()
        reduction_pct = data['reduction_ratio'] * 100

        print(f"无免疫平均感染: {data['base_spread']['mean']:.2f}")
        print(f"免疫后平均感染: {data['protected_spread']['mean']:.2f}")
        print(f"减少数: {data['reduction']:.2f}")
        print(f"减少比例: {reduction_pct:.2f}%")
        print(f"CDF图base64长度: {len(data['cdf_plot_base64'])}")

        print("✓ 自定义传播模拟测试通过")
        return True

    except Exception as e:
        print(f"✗ 自定义传播模拟测试失败: {e}")
        return False


def main():
    base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
    output_dir = os.path.join(os.path.dirname(__file__), 'test_output')

    print("\n" + "#" * 60)
    print("#  Flask API 集成测试")
    print(f"#  目标服务器: {base_url}")
    print("#" * 60)

    print("\n请确保Flask服务器已启动: python app.py")
    print("按 Enter 继续，或 Ctrl+C 取消...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n测试取消")
        return

    results = []
    results.append(('健康检查', test_health_check(base_url)))
    results.append(('网络列表', test_list_networks(base_url)))
    results.append(('网络信息', test_network_info(base_url)))
    results.append(('免疫推荐', test_immunize(base_url, output_dir)))
    results.append(('传播模拟', test_simulate(base_url)))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:20s} {status}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n✓ 所有API测试通过!")
    else:
        print("\n✗ 部分测试失败")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
