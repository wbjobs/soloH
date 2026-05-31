#!/usr/bin/env python
import urllib.request
import urllib.parse
import json
import base64
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
            body = b""
        req = urllib.request.Request(url, data=body, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        raise


def test_smr_auction():
    print("\n" + "=" * 60)
    print("测试 1: 创建并运行 SMR 拍卖")
    print("=" * 60)

    create_data = {
        "name": "SMR Test Auction",
        "auction_type": "smr",
        "description": "Test SMR with 4 items and 3 bidders",
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
    print(f"  ✓ 拍卖创建成功! ID={auction_id}")
    print(f"  物品: {len(auction['items'])} 个")
    print(f"  竞标者: {len(auction['bidders'])} 个")

    print("\n[Step 2] 运行拍卖...")
    result = make_request("POST", f"/auctions/{auction_id}/run?verbose=true")
    print(f"  ✓ 拍卖完成! 用时 {len(result['round_records'])} 轮")

    print("\n[Step 3] 查看结果...")
    final_result = result["result"]
    print(f"  拍卖效率: {final_result['efficiency_metrics']['efficiency_ratio']:.2%}")
    print(f"  总收益: ${final_result['revenue_metrics']['total_revenue']:.2f}")
    print(f"  最优社会福利: ${final_result['efficiency_metrics']['optimal_social_welfare']:.2f}")
    print(f"  实际社会福利: ${final_result['efficiency_metrics']['actual_social_welfare']:.2f}")

    print("\n  物品分配:")
    for item in auction["items"]:
        item_result = [a for a in final_result["allocation_metrics"]["final_allocations"]
                       if a["item_id"] == item["id"]][0]
        status = f"→ 竞标者 {item_result['winner']} @ ${item_result['price']:.2f}" if item_result["winner"] else "→ 未售出"
        print(f"    {item['name']}: {status}")

    return auction_id


def test_cca_auction():
    print("\n" + "=" * 60)
    print("测试 2: 创建并运行 CCA 拍卖")
    print("=" * 60)

    create_data = {
        "name": "CCA Test Auction",
        "auction_type": "cca",
        "description": "Test CCA with complementary items",
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
    print(f"  ✓ CCA拍卖创建成功! ID={auction_id}")

    print("\n[Step 2] 运行拍卖...")
    result = make_request("POST", f"/auctions/{auction_id}/run?verbose=true")
    print(f"  ✓ CCA拍卖完成! 用时 {len(result['round_records'])} 轮")

    final_result = result["result"]
    print(f"\n[Step 3] 结果分析:")
    print(f"  定价机制: {final_result['auction_summary']['pricing_mechanism']}")
    print(f"  拍卖效率: {final_result['efficiency_metrics']['efficiency_ratio']:.2%}")
    print(f"  总收益: ${final_result['revenue_metrics']['total_revenue']:.2f}")

    if "plots" in result:
        print(f"  ✓ 生成了 {len(result['plots'])} 个可视化图表")

    return auction_id


def test_step_auction():
    print("\n" + "=" * 60)
    print("测试 3: 单步执行拍卖")
    print("=" * 60)

    create_data = {
        "name": "Step-by-Step Auction",
        "auction_type": "smr",
        "description": "Test step-by-step execution",
        "min_price": 10.0,
        "max_price": 500.0,
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
    print(f"  ✓ 拍卖创建成功! ID={auction_id}")

    print("\n[Step 2] 逐步执行拍卖 (最多10步)...")
    for i in range(10):
        state = make_request("POST", f"/auctions/{auction_id}/step")
        print(f"  第 {state['current_round']} 轮: 阶段={state['phase']}, "
              f"超额需求={max(state['excess_demand'].values()) if state['excess_demand'] else 0}")
        if state.get("is_completed"):
            print("  ✓ 拍卖已完成!")
            break

    print("\n[Step 3] 查看当前状态...")
    state = make_request("GET", f"/auctions/{auction_id}/state")
    print(f"  当前轮次: {state['current_round']}")
    print(f"  当前价格: {state['current_prices']}")
    print(f"  临时分配: {state['provisional_allocation']}")

    return auction_id


def test_strategy_list():
    print("\n" + "=" * 60)
    print("测试 4: 查看可用策略")
    print("=" * 60)

    strategies = make_request("GET", "/strategies")
    built_in = [s for s in strategies if s.get("is_builtin")]
    uploaded = [s for s in strategies if not s.get("is_builtin")]
    print(f"\n  可用策略 ({len(built_in)} 个内置):")
    for s in built_in:
        print(f"    - {s['name']}: {s['description']}")

    print(f"\n  用户上传策略: {len(uploaded)} 个")

    print("\n[Step 1] 获取策略模板...")
    example = make_request("GET", "/strategies/example")
    print(f"  ✓ 获取到示例代码, 长度: {len(example)} 字符")
    print("  代码片段:")
    for line in example.split("\n")[:10]:
        print(f"    {line}")


def test_competition():
    print("\n" + "=" * 60)
    print("测试 5: 策略对战")
    print("=" * 60)

    print("\n[Step 1] 创建比赛 (真实策略 vs 激进策略 vs 保守策略)...")
    comp_data = {
        "name": "Strategy Battle Royale",
        "auction_type": "smr",
        "description": "Battle between built-in strategies",
        "strategy_names": ["truthful", "aggressive", "conservative", "adaptive"],
        "config": {
            "num_items": 5,
            "base_value_range": [50.0, 300.0]
        },
        "num_rounds": 3
    }

    competition = make_request("POST", "/competitions", comp_data)
    comp_id = competition["id"]
    print(f"  ✓ 比赛创建成功! ID={comp_id}")

    print("\n[Step 2] 运行比赛 (3轮)...")
    result = make_request("POST", f"/competitions/{comp_id}/run?num_rounds=3&verbose=true")
    print(f"  ✓ 比赛完成! 执行了 {result['rounds_played']} 轮")

    print("\n[Step 3] 查看排名...")
    rankings = result.get("rankings", [])
    for i, rank in enumerate(rankings[:5], 1):
        print(f"    #{i} {rank['strategy_name']}: "
              f"${rank['total_profit']:.2f} ({rank['win_rate']:.0%} win rate)")

    return comp_id


def test_visualization(auction_id):
    print("\n" + "=" * 60)
    print("测试 6: 可视化")
    print("=" * 60)

    print("\n[Step 1] 获取可视化数据...")
    viz = make_request("GET", f"/visualization/auctions/{auction_id}")
    print(f"  ✓ 生成了 {len(viz['plots'])} 个图表")
    print(f"  图表 URL:")
    for name, url in viz["plots"].items():
        print(f"    - {name}: {url}")

    print("\n[Step 2] 获取价格路径数据...")
    price_data = make_request("GET", f"/visualization/auctions/{auction_id}/price-path")
    print(f"  ✓ 价格数据包含 {len(price_data['price_data'])} 轮")
    print(f"  物品列表: {[item['name'] for item in price_data['items']]}")
    if price_data["price_data"]:
        last_round = price_data["price_data"][-1]
        print(f"  最后一轮价格: {last_round['prices']}")


def main():
    print("=" * 60)
    print("频谱拍卖模拟平台 - API 完整测试")
    print("=" * 60)

    start_time = time.time()

    try:
        test_strategy_list()
        smr_id = test_smr_auction()
        cca_id = test_cca_auction()
        step_id = test_step_auction()
        test_visualization(smr_id)
        comp_id = test_competition()

        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"✓ 所有测试通过! 总耗时: {elapsed:.2f}秒")
        print("=" * 60)
        print("\n测试结果汇总:")
        print(f"  - SMR拍卖: ID={smr_id} ✓")
        print(f"  - CCA拍卖: ID={cca_id} ✓")
        print(f"  - 单步执行: ID={step_id} ✓")
        print(f"  - 策略对战: ID={comp_id} ✓")
        print(f"  - 可视化: ✓")
        print("\n访问 http://localhost:8000/docs 查看完整API文档")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
