#!/usr/bin/env python
import urllib.request
import urllib.parse
import json
import time


BASE_URL = "http://localhost:8000/api/v1"


def make_request(method, endpoint, data=None):
    url = BASE_URL + endpoint
    headers = {"Content-Type": "application/json"}

    if method == "GET":
        if data:
            query = urllib.parse.urlencode(data)
            url = f"{url}?{query}"
        req = urllib.request.Request(url, method="GET", headers=headers)
    else:
        if data:
            body = json.dumps(data).encode()
        else:
            body = b"{}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        raise


def test_smr_auction():
    print("\n=== 测试 1: SMR 拍卖 ===")

    create_data = {
        "name": "SMR Test",
        "auction_type": "smr",
        "description": "Test SMR",
        "min_price": 10.0,
        "max_price": 500.0,
        "bid_increment": 5.0,
        "max_rounds": 50,
        "activity_rule": True,
        "num_items": 4,
        "num_bidders": 3,
        "bidder_strategies": ["truthful", "aggressive", "conservative"]
    }

    print("\n[Step 1] 创建拍卖...")
    auction = make_request("POST", "/auctions?seed=42", create_data)
    auction_id = auction["id"]
    print(f"  ✓ 创建成功 ID={auction_id}")
    print(f"  物品: {len(auction['items'])} 个")
    print(f"  竞标者: {len(auction['bidders'])} 个")

    print("\n[Step 2] 运行拍卖...")
    result = make_request("POST", f"/auctions/{auction_id}/run")
    final_round = result["result"]["final_round"]
    print(f"  ✓ 完成! 共 {final_round} 轮")

    print("\n[Step 3] 结果分析...")
    analysis = result["analysis"]
    summary = analysis["summary"]
    print(f"  效率: {summary['efficiency_percentage']:.2f}%")
    print(f"  收益: ${summary['total_revenue']:.2f}")
    print(f"  社会福利: ${summary['social_welfare']:.2f}")
    print(f"  分配率: {summary['allocation_rate']:.0%}")

    print("\n  分配结果:")
    final_prices = result["result"]["final_prices"]
    final_alloc = result["result"]["final_allocation"]
    for item in auction["items"]:
        price = final_prices.get(str(item["id"]), 0)
        winner = None
        for bidder_id, items in final_alloc.items():
            if item["id"] in items:
                winner = bidder_id
                break
        if winner:
            print(f"    {item['name']}: 竞标者 {winner} @ ${price:.2f}")
        else:
            print(f"    {item['name']}: 未售出")

    if "plots" in result:
        print(f"\n  ✓ 生成 {len(result['plots'])} 个可视化图表")

    return auction_id


def test_cca_auction():
    print("\n=== 测试 2: CCA 拍卖 ===")

    create_data = {
        "name": "CCA Test",
        "auction_type": "cca",
        "description": "Test CCA",
        "min_price": 10.0,
        "max_price": 1000.0,
        "bid_increment": 5.0,
        "max_rounds": 80,
        "activity_rule": True,
        "config": {
            "supplementary_rounds": 2,
            "core_selecting": True
        },
        "num_items": 6,
        "num_bidders": 4,
        "bidder_strategies": ["truthful", "bundle", "bundle_bid", "adaptive"],
        "valuation_model": "hierarchical"
    }

    print("\n[Step 1] 创建拍卖...")
    auction = make_request("POST", "/auctions?seed=123", create_data)
    auction_id = auction["id"]
    print(f"  ✓ 创建成功 ID={auction_id}")

    print("\n[Step 2] 运行拍卖...")
    result = make_request("POST", f"/auctions/{auction_id}/run")
    final_round = result["result"]["final_round"]
    print(f"  ✓ 完成! 共 {final_round} 轮")

    analysis = result["analysis"]
    summary = analysis["summary"]
    detailed = analysis["detailed_metrics"]
    print(f"\n[Step 3] 结果分析...")
    if "auction_summary" in detailed:
        print(f"  定价机制: {detailed['auction_summary'].get('pricing_mechanism', 'N/A')}")
    print(f"  效率: {summary['efficiency_percentage']:.2f}%")
    print(f"  收益: ${summary['total_revenue']:.2f}")
    print(f"  分配率: {summary['allocation_rate']:.0%}")

    if "plots" in result:
        print(f"  ✓ 生成 {len(result['plots'])} 个图表")

    return auction_id


def test_visualization(auction_id):
    print("\n=== 测试 3: 可视化 ===")

    print("\n[Step 1] 获取可视化...")
    viz = make_request("GET", f"/visualization/auctions/{auction_id}")
    print(f"  ✓ 图表 URL:")
    for name, url in viz["plots"].items():
        print(f"    - {name}: {url}")

    print("\n[Step 2] 获取价格路径数据...")
    price_data = make_request("GET", f"/visualization/auctions/{auction_id}/price-path")
    print(f"  ✓ {len(price_data['price_data'])} 轮价格数据")
    print(f"  物品: {[item['name'] for item in price_data['items']]}")
    if price_data["price_data"]:
        print(f"  最终价格: {price_data['price_data'][-1]['prices']}")


def test_strategies():
    print("\n=== 测试 4: 策略列表 ===")

    strategies = make_request("GET", "/strategies")
    built_in = [s for s in strategies if s.get("is_builtin")]
    print(f"\n  内置策略 ({len(built_in)} 个):")
    for s in built_in:
        print(f"    - {s['name']}: {s['description']}")

    example = make_request("GET", "/strategies/example")
    code = example["example_code"]
    print(f"\n  示例代码长度: {len(code)} 字符")
    print("  代码片段:")
    for line in code.split("\n")[:8]:
        print(f"    {line}")


def test_step_auction():
    print("\n=== 测试 5: 单步执行 ===")

    create_data = {
        "name": "Step Test",
        "auction_type": "smr",
        "description": "Test step execution",
        "min_price": 10.0,
        "max_price": 200.0,
        "bid_increment": 5.0,
        "max_rounds": 30,
        "activity_rule": True,
        "num_items": 3,
        "num_bidders": 2,
        "bidder_strategies": ["truthful", "conservative"]
    }

    print("\n[Step 1] 创建拍卖...")
    auction = make_request("POST", "/auctions?seed=999", create_data)
    auction_id = auction["id"]
    print(f"  ✓ 创建成功 ID={auction_id}")

    print("\n[Step 2] 逐步执行 (最多8步)...")
    for i in range(8):
        step_result = make_request("POST", f"/auctions/{auction_id}/step")
        excess = max(step_result['excess_demand'].values()) if step_result['excess_demand'] else 0
        print(f"  第 {step_result['round']} 轮: 出价数={step_result['bids_count']}, 超额需求={excess}")
        if step_result.get("is_complete"):
            print("  ✓ 拍卖已完成!")
            break

    print("\n[Step 3] 查看当前状态...")
    state = make_request("GET", f"/auctions/{auction_id}/state")
    print(f"  当前轮次: {state['current_round']}")
    print(f"  当前价格: {state['prices']}")
    print(f"  临时分配: {state['provisional_allocation']}")

    return auction_id


def main():
    print("=" * 50)
    print("频谱拍卖模拟平台 - 完整测试套件")
    print("=" * 50)

    start = time.time()
    try:
        test_strategies()
        smr_id = test_smr_auction()
        cca_id = test_cca_auction()
        step_id = test_step_auction()
        test_visualization(smr_id)

        elapsed = time.time() - start
        print(f"\n{'=' * 50}")
        print(f"✓ 所有测试通过! 总耗时: {elapsed:.2f}秒")
        print(f"{'=' * 50}")
        print(f"\n测试结果汇总:")
        print(f"  - 策略列表: ✓")
        print(f"  - SMR拍卖 ID={smr_id}: ✓")
        print(f"  - CCA拍卖 ID={cca_id}: ✓")
        print(f"  - 单步执行 ID={step_id}: ✓")
        print(f"  - 可视化: ✓")
        print(f"\n访问 http://localhost:8000/docs 查看完整API文档")
        print(f"访问 http://localhost:8000/static/price_path.png 查看价格路径图")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
