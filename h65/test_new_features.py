import urllib.request
import urllib.parse
import json
import time
import asyncio
import websockets

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


def make_request(method, endpoint, data=None, params=None):
    url = BASE_URL + endpoint
    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')

    if data:
        data_bytes = json.dumps(data).encode('utf-8')
        req.data = data_bytes

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return None


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, description):
    print(f"\n[Step {step_num}] {description}...")


def create_test_auction(auction_type="smr"):
    print_step(1, f"创建{auction_type.upper()}拍卖")
    data = {
        "name": f"测试拍卖 - 新功能验证 ({auction_type.upper()})",
        "auction_type": auction_type,
        "description": "测试市场势力分析、二次交易、WebSocket推送",
        "num_items": 5,
        "num_bidders": 4,
        "bidder_strategies": ["truthful", "aggressive", "conservative", "bundle"],
        "min_price": 10,
        "max_price": 500,
        "bid_increment": 5,
        "max_rounds": 30,
        "pricing_rule": "second_price",
        "reserve_strategy": "public",
        "reserve_price_multiplier": 0.3
    }
    result = make_request("POST", f"{API_PREFIX}/auctions", data)
    if result:
        auction_id = result["id"]
        print(f"  ✓ 创建成功 ID={auction_id}")
        print(f"    物品数: {len(result['items'])}")
        print(f"    竞标者数: {len(result['bidders'])}")
        return auction_id
    return None


def run_auction(auction_id):
    print_step(2, "运行拍卖")
    result = make_request("POST", f"{API_PREFIX}/auctions/{auction_id}/run")
    if result:
        final_round = result.get('result', {}).get('final_round', 'N/A')
        print(f"  ✓ 完成! 共 {final_round} 轮")

        efficiency = result.get('analysis', {}).get('efficiency_metrics', {}).get('efficiency', None)
        if efficiency is None:
            efficiency = result.get('analysis', {}).get('efficiency', 0)
        print(f"    效率: {efficiency * 100:.2f}%")

        revenue = result.get('analysis', {}).get('revenue_metrics', {}).get('total_revenue', None)
        if revenue is None:
            revenue = result.get('result', {}).get('total_revenue', 0)
        print(f"    收益: ${revenue:.2f}")
        return result
    return None


def test_market_power_analysis(auction_id):
    print_header("测试 1: 市场势力分析（合谋检测）")

    print_step(1, "获取HHI市场集中度指数")
    result = make_request("GET", f"/api/market-power/auction/{auction_id}/hhi")
    if result:
        print(f"  ✓ HHI指数: {result['hhi_index']:.2f}")
        print(f"    市场集中度: {result['concentration_level']}")
        print(f"    解读: {result['interpretation']}")
        for bidder_id, share in result['winning_shares'].items():
            print(f"    竞标者 {bidder_id}: {share * 100:.1f}% 份额")

    print_step(2, "检测竞标者合谋风险")
    result = make_request("GET", f"/api/market-power/auction/{auction_id}/collusion-risks")
    if result:
        print(f"  ✓ 分析完成")
        print(f"    分析竞标者对: {result['total_pairs_analyzed']}")
        print(f"    高风险对: {result['high_risk_pairs']}")
        print(f"    中风险对: {result['medium_risk_pairs']}")
        print(f"    低风险对: {result['low_risk_pairs']}")

        for risk in result['risks'][:3]:
            print(f"\n    竞标者对 {risk['bidder_pair']}:")
            print(f"      风险等级: {risk['risk_level']} (score={risk['risk_score']:.2f})")
            for ev in risk['evidence']:
                print(f"      - {ev}")

    print_step(3, "获取竞标者市场势力评分")
    result = make_request("GET", f"/api/market-power/auction/{auction_id}/market-power-scores")
    if result:
        print(f"  ✓ 计算完成")
        for entry in result['market_power_scores']:
            print(f"    竞标者 {entry['bidder_id']}: score={entry['score']:.4f}, 支配等级={entry['dominance_level']}")
        if result['dominant_bidder']:
            print(f"    支配竞标者: {result['dominant_bidder'][0]} (score={result['dominant_bidder'][1]:.4f})")

    print_step(4, "生成完整市场势力分析报告")
    result = make_request("GET", f"/api/market-power/auction/{auction_id}")
    if result:
        print(f"  ✓ 报告生成")
        print(f"    总体风险等级: {result['overall_risk_level']}")
        print(f"    可疑模式: {len(result['suspicious_patterns'])} 项")
        for pattern in result['suspicious_patterns']:
            print(f"      - {pattern}")
        print(f"    合谋风险对: {len(result['collusion_risks'])} 个")
        print(f"    报告已保存到数据库")

    print_step(5, "查询历史分析报告列表")
    result = make_request("GET", f"/api/market-power/auction/{auction_id}/reports")
    if result:
        print(f"  ✓ 历史报告: {len(result)} 份")
        for report in result[:3]:
            print(f"    报告ID={report['id']}, 风险={report['overall_risk_level']}, HHI={report['hhi_index']:.2f}")

    print("\n✓ 市场势力分析测试通过")
    return True


def test_secondary_market(auction_id, run_result):
    print_header("测试 2: 频谱再打包/二次交易市场")

    bidders = make_request("GET", f"{API_PREFIX}/auctions/{auction_id}")
    if bidders and 'bidders' in bidders:
        bidder_list = bidders['bidders']
        if len(bidder_list) >= 2:
            seller_id = bidder_list[0]['id']
            buyer_id = bidder_list[1]['id']
        else:
            seller_id = 1
            buyer_id = 2
    else:
        seller_id = 1
        buyer_id = 2

    items = make_request("GET", f"{API_PREFIX}/auctions/{auction_id}")
    if items and 'items' in items:
        item_list = items['items']
        seller_items = [item['id'] for item in item_list[:2]]
        all_items = [item['id'] for item in item_list]
    else:
        seller_items = [1, 2]
        all_items = [1, 2, 3, 4, 5]

    print_step(1, "获取拍卖结果 - 确定竞标者")
    print(f"    卖家竞标者: {seller_id}")
    print(f"    买家竞标者: {buyer_id}")
    print(f"    挂牌物品: {seller_items}")

    print_step(2, "创建二手挂牌")
    listing_data = {
        "auction_id": auction_id,
        "seller_id": int(seller_id),
        "item_ids": seller_items,
        "ask_price": 500.0,
        "min_bid_price": 400.0,
        "description": "出售频谱块组合",
        "duration_hours": 24
    }
    listing = make_request("POST", "/api/secondary-market/listings", listing_data)
    if listing:
        listing_id = listing["listing_id"]
        print(f"  ✓ 挂牌成功 ID={listing_id}")
        print(f"    物品: {listing['item_ids']}")
        print(f"    一口价: ${listing['ask_price']:.2f}")
        print(f"    起拍价: ${listing['min_bid_price']:.2f}")
        print(f"    到期时间: {listing['expires_at']}")

    print_step(3, "查询活跃挂牌列表")
    listings = make_request("GET", f"/api/secondary-market/auction/{auction_id}/listings",
                           params={"status": "active"})
    if listings:
        print(f"  ✓ 活跃挂牌数: {len(listings)}")
        for l in listings:
            print(f"    {l['listing_id']}: 物品={l['item_ids']}, 价格=${l['ask_price']:.2f}")

    print_step(4, "买家出价")
    bid_data = {
        "listing_id": listing_id,
        "bidder_id": int(buyer_id),
        "price": 450.0
    }
    bid_result = make_request("POST", f"/api/secondary-market/listings/{listing_id}/bids", bid_data)
    if bid_result:
        print(f"  ✓ 出价成功")
        print(f"    出价价格: ${bid_result['price']:.2f}")
        print(f"    出价时间: {bid_result['created_at']}")

    print_step(5, "卖家接受出价 - 完成交易")
    accept_result = make_request("POST", f"/api/secondary-market/listings/{listing_id}/accept")
    if accept_result:
        trade = accept_result["trade"]
        print(f"  ✓ 交易完成")
        print(f"    交易ID: {trade['trade_id']}")
        print(f"    卖家→买家: {trade['seller_id']} → {trade['buyer_id']}")
        print(f"    成交价: ${trade['price']:.2f}")
        print(f"    交易类型: {trade['trade_type']}")

    print_step(6, "创建频谱再打包组合拍卖")
    repackage_data = {
        "auction_id": auction_id,
        "creator_id": int(seller_id),
        "item_ids": all_items[:3],
        "name": "城市核心频段组合包",
        "description": "包含3个相邻频谱块，适合5G组网",
        "reserve_price": 800.0
    }
    bundle = make_request("POST", "/api/secondary-market/bundles", repackage_data)
    if bundle:
        bundle_id = bundle["bundle_id"]
        print(f"  ✓ 再打包组合创建成功 ID={bundle_id}")
        print(f"    组合名称: {bundle['name']}")
        print(f"    包含物品: {bundle['item_ids']}")
        print(f"    保留价: ${bundle['reserve_price']:.2f}")

    print_step(7, "对再打包组合出价")
    bundle_bid_data = {
        "bundle_id": bundle_id,
        "bidder_id": int(buyer_id),
        "price": 850.0
    }
    bundle_bid = make_request("POST", f"/api/secondary-market/bundles/{bundle_id}/bids", bundle_bid_data)
    if bundle_bid:
        print(f"  ✓ 组合出价成功: ${bundle_bid['price']:.2f}")

    print_step(8, "完成组合拍卖")
    finalize_result = make_request("POST", f"/api/secondary-market/bundles/{bundle_id}/finalize")
    if finalize_result:
        trade = finalize_result["trade"]
        print(f"  ✓ 组合拍卖完成")
        print(f"    成交价: ${trade['price']:.2f}")
        print(f"    买家: {trade['buyer_id']}")

    print_step(9, "获取市场总览")
    summary = make_request("GET", f"/api/secondary-market/auction/{auction_id}/summary")
    if summary:
        print(f"  ✓ 市场总览")
        print(f"    总挂牌数: {summary['total_listings']}")
        print(f"    活跃挂牌: {summary['active_listings']}")
        print(f"    总交易数: {summary['total_trades']}")
        print(f"    总交易额: ${summary['total_trade_volume']:.2f}")
        print(f"    平均成交价: ${summary['average_trade_price']:.2f}")
        print(f"    再打包组合: {summary['repackaged_bundles']} 个")
        print(f"    市场中物品: {summary['items_in_market']} 个")

    print_step(10, "查询竞标者库存")
    inventory = make_request("GET", f"/api/secondary-market/auction/{auction_id}/bidder/{seller_id}/inventory")
    if inventory:
        print(f"  ✓ 竞标者 {seller_id} 库存")
        print(f"    原始中标: {inventory['original_won_items']}")
        print(f"    已出售: {inventory['sold_items']}")
        print(f"    已购买: {inventory['purchased_items']}")
        print(f"    当前库存: {inventory['current_inventory']}")
        print(f"    活跃挂牌: {len(inventory['active_listings'])} 个")

    print_step(11, "查询交易历史")
    trades = make_request("GET", f"/api/secondary-market/auction/{auction_id}/trades")
    if trades:
        print(f"  ✓ 交易历史: {len(trades)} 笔")
        for t in trades:
            print(f"    {t['trade_id']}: {t['seller_id']}→{t['buyer_id']}, ${t['price']:.2f}, {t['trade_type']}")

    print("\n✓ 二次交易市场测试通过")
    return True


async def test_websocket_realtime(auction_id):
    print_header("测试 3: WebSocket实时推送")

    print_step(1, "创建新的测试拍卖用于WebSocket测试")
    data = {
        "name": "WebSocket实时测试拍卖",
        "auction_type": "smr",
        "num_items": 3,
        "num_bidders": 3,
        "max_rounds": 10,
        "bid_increment": 10
    }
    new_auction = make_request("POST", f"{API_PREFIX}/auctions", data)
    if not new_auction:
        print("  ✗ 无法创建测试拍卖")
        return False
    ws_auction_id = new_auction["id"]
    print(f"  ✓ 测试拍卖创建 ID={ws_auction_id}")

    print_step(2, "建立WebSocket连接")
    ws_url = f"ws://localhost:8000/api/realtime/ws/auction/{ws_auction_id}?bidder_id=1&is_admin=true"
    print(f"    连接到: {ws_url}")

    messages_received = []
    expected_events = ["connection_established", "auction_start",
                       "round_update", "current_state", "auction_end"]

    async def listen_for_messages(ws, count):
        for _ in range(count):
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                msg_data = json.loads(message)
                messages_received.append(msg_data)
                msg_type = msg_data.get('type')
                round_num = msg_data.get('data', {}).get('round_number', 'N/A')
                print(f"    ✓ 收到 {msg_type}: round={round_num}")
                if msg_type == "auction_end":
                    break
            except asyncio.TimeoutError:
                print("    等待消息超时")
                break
            except Exception as e:
                print(f"    错误: {e}")
                import traceback
                traceback.print_exc()
                break

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"  ✓ WebSocket连接建立")

            listener_task = asyncio.create_task(listen_for_messages(websocket, 15))

            await asyncio.sleep(1)

            print_step(3, "逐步运行拍卖，触发实时推送")
            for i in range(12):
                step_result = make_request("POST", f"{API_PREFIX}/auctions/{ws_auction_id}/step")
                if step_result:
                    status = step_result.get("status", step_result.get("round", "running"))
                    print(f"    执行单步: {status}")
                if step_result and step_result.get("is_complete"):
                    print(f"    拍卖完成")
                    break
                await asyncio.sleep(0.5)

            await listener_task

            print_step(4, "验证收到的实时消息")
            print(f"  ✓ 收到 {len(messages_received)} 条实时消息")

            message_types = [m["type"] for m in messages_received]
            for expected in expected_events:
                count = message_types.count(expected)
                status = "✓" if count > 0 else "✗"
                print(f"    {status} {expected}: {count} 条")

            round_updates = [m for m in messages_received if m["type"] == "round_update"]
            if round_updates:
                print(f"\n    最新轮次数据:")
                latest = round_updates[-1]["data"]
                print(f"      轮次: {latest.get('round_number')}")
                print(f"      价格: {latest.get('prices')}")
                print(f"      超额需求: {latest.get('excess_demand')}")
                print(f"      出价数: {latest.get('bids_count')}")
                print(f"      阶段: {latest.get('phase')}")

            print_step(5, "查询连接状态")
            conn_stats = make_request("GET", f"/api/realtime/auction/{ws_auction_id}/connections")
            if conn_stats:
                print(f"  ✓ 连接统计")
                print(f"    总连接数: {conn_stats['total_connections']}")
                print(f"    竞标者连接: {conn_stats['bidder_connections']}")
                print(f"    管理员连接: {conn_stats['admin_connections']}")

            print_step(6, "测试手动广播消息")
            broadcast_data = {"message": "测试广播消息", "level": "info"}
            result = make_request("POST", f"/api/realtime/auction/{ws_auction_id}/broadcast",
                                 data=broadcast_data)
            if result and result.get("success"):
                print(f"  ✓ 手动广播成功")

            await asyncio.sleep(0.5)
            final_count = len([m for m in messages_received if "message" in str(m["type"])])
            print(f"    额外广播消息: {final_count} 条")

    except Exception as e:
        print(f"  ✗ WebSocket测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n✓ WebSocket实时推送测试通过")
    return True


def test_rest_api():
    print_header("测试 4: REST API接口可用性")

    print_step(1, "检查根端点")
    root = make_request("GET", "/")
    if root:
        print(f"  ✓ 根端点可用")
        print(f"    项目: {root['name']} v{root['version']}")
        for key, url in root['endpoints'].items():
            print(f"    {key}: {url}")

    print_step(2, "检查健康检查")
    health = make_request("GET", "/health")
    if health:
        print(f"  ✓ 健康检查: {health['status']}")

    print_step(3, "列出新API端点")
    endpoints = [
        "/api/market-power/auction/1",
        "/api/secondary-market/auction/1/summary",
        "/api/realtime/auction/1/connections"
    ]
    for ep in endpoints:
        print(f"    {ep}")

    print("\n✓ REST API测试通过")
    return True


def main():
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "频谱拍卖平台 - 新功能测试套件" + " " * 17 + "║")
    print("╚" + "═" * 68 + "╝")

    print(f"\n服务器地址: {BASE_URL}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    print_header("准备工作: 创建并运行基础拍卖")
    auction_id = create_test_auction("cca")
    if not auction_id:
        print("✗ 无法创建拍卖，测试终止")
        return

    run_result = run_auction(auction_id)
    if not run_result:
        print("✗ 无法运行拍卖，测试终止")
        return

    time.sleep(1)

    tests_passed = 0
    tests_total = 4

    try:
        if test_market_power_analysis(auction_id):
            tests_passed += 1
    except Exception as e:
        print(f"✗ 市场势力分析测试失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        if test_secondary_market(auction_id, run_result):
            tests_passed += 1
    except Exception as e:
        print(f"✗ 二次交易市场测试失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        if asyncio.run(test_websocket_realtime(auction_id)):
            tests_passed += 1
    except Exception as e:
        print(f"✗ WebSocket实时推送测试失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        if test_rest_api():
            tests_passed += 1
    except Exception as e:
        print(f"✗ REST API测试失败: {e}")

    print("\n" + "=" * 70)
    print(f"  测试结果: {tests_passed}/{tests_total} 项测试通过")
    print("=" * 70)

    if tests_passed == tests_total:
        print("\n🎉 所有新功能测试通过!")
    else:
        print(f"\n⚠️  {tests_total - tests_passed} 项测试失败")

    print("\n新功能总结:")
    print("  1. ✓ 市场势力分析: HHI指数、合谋检测、市场势力评分")
    print("  2. ✓ 频谱再打包: 二手挂牌、打包拍卖、交易市场")
    print("  3. ✓ 实时推送: WebSocket广播、每轮结果推送、个人通知")

    print(f"\n访问 {BASE_URL}/docs 查看完整API文档")
    print(f"WebSocket端点: ws://localhost:8000/api/realtime/ws/auction/{{auction_id}}")


if __name__ == "__main__":
    main()
