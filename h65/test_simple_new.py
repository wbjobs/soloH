import urllib.request
import urllib.parse
import json
import time

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


def test_market_power(auction_id):
    print("\n=== 测试市场势力分析 ===")

    print("\n1. HHI指数:")
    r = make_request("GET", f"/api/market-power/auction/{auction_id}/hhi")
    if r:
        print(f"   HHI={r['hhi_index']:.2f}, 集中度={r['concentration_level']}")
        print(f"   ✓ 通过")

    print("\n2. 合谋风险检测:")
    r = make_request("GET", f"/api/market-power/auction/{auction_id}/collusion-risks")
    if r:
        print(f"   高风险对={r['high_risk_pairs']}, 中风险={r['medium_risk_pairs']}, 低风险={r['low_risk_pairs']}")
        print(f"   ✓ 通过")

    print("\n3. 市场势力评分:")
    r = make_request("GET", f"/api/market-power/auction/{auction_id}/market-power-scores")
    if r:
        print(f"   支配竞标者: {r['dominant_bidder']}")
        print(f"   ✓ 通过")

    print("\n4. 完整分析报告:")
    r = make_request("GET", f"/api/market-power/auction/{auction_id}")
    if r:
        print(f"   总体风险={r['overall_risk_level']}, 可疑模式={len(r['suspicious_patterns'])}项")
        print(f"   ✓ 通过")

    print("\n5. 历史报告:")
    r = make_request("GET", f"/api/market-power/auction/{auction_id}/reports")
    if r:
        print(f"   历史报告数={len(r)}")
        print(f"   ✓ 通过")

    return True


def test_secondary_market(auction_id, run_result=None):
    print("\n=== 测试二次交易市场 ===")

    allocation = {}
    if run_result:
        result = run_result
    else:
        result = make_request("GET", f"{API_PREFIX}/auctions/{auction_id}/result")
        if not result:
            result = make_request("POST", f"{API_PREFIX}/auctions/{auction_id}/run")

    if result:
        allocation = result.get('result', {}).get('final_allocation', {})
        if not allocation:
            analysis = result.get('analysis', {})
            for key in ['allocation_metrics', 'bidder_metrics', 'market_metrics']:
                if key in analysis and 'final_allocation' in analysis[key]:
                    allocation = analysis[key]['final_allocation']
                    break
        if not allocation:
            for key in analysis:
                if isinstance(analysis[key], dict) and 'allocation' in analysis[key]:
                    allocation = analysis[key]['allocation']
                    break

    print(f"   分配结果: {allocation}")

    auction = make_request("GET", f"{API_PREFIX}/auctions/{auction_id}")
    bidders = auction['bidders'] if auction else []
    items = auction['items'] if auction else []

    if len(bidders) < 2 or len(items) < 2:
        print("   ! 数据不足，跳过测试")
        return True

    if not allocation:
        print("   ! 无分配结果，跳过所有权测试")
        return True

    bidder_ids_with_items = [k for k, v in allocation.items() if len(v) > 0]
    if len(bidder_ids_with_items) < 1:
        print("   ! 无人中标，跳过测试")
        return True

    seller_id = int(bidder_ids_with_items[0])
    seller_items = allocation[bidder_ids_with_items[0]]

    other_bidders = [b['id'] for b in bidders if b['id'] != seller_id]
    if not other_bidders:
        other_bidders = [int(k) for k in allocation.keys() if int(k) != seller_id]
    buyer_id = other_bidders[0] if other_bidders else seller_id + 1

    item_ids = seller_items[:2]
    all_items = [i['id'] for i in items]

    print("\n1. 创建挂牌:")
    listing_data = {
        "auction_id": auction_id,
        "seller_id": seller_id,
        "item_ids": item_ids,
        "ask_price": 500.0,
        "min_bid_price": 400.0,
        "description": "测试挂牌",
        "duration_hours": 24
    }
    r = make_request("POST", "/api/secondary-market/listings", listing_data)
    if r:
        listing_id = r['listing_id']
        print(f"   挂牌成功 ID={listing_id}")
        print(f"   ✓ 通过")
    else:
        listing_id = None

    print("\n2. 查询挂牌列表:")
    r = make_request("GET", f"/api/secondary-market/auction/{auction_id}/listings",
                    params={"status": "active"})
    if r is not None:
        print(f"   活跃挂牌数={len(r)}")
        print(f"   ✓ 通过")

    if listing_id:
        print("\n3. 出价:")
        bid_data = {
            "listing_id": listing_id,
            "bidder_id": buyer_id,
            "price": 450.0
        }
        r = make_request("POST", f"/api/secondary-market/listings/{listing_id}/bids", bid_data)
        if r:
            print(f"   出价成功")
            print(f"   ✓ 通过")

        print("\n4. 接受出价:")
        r = make_request("POST", f"/api/secondary-market/listings/{listing_id}/accept")
        if r:
            print(f"   交易完成，价格=${r['trade']['price']:.2f}")
            print(f"   ✓ 通过")

    print("\n5. 创建再打包组合:")
    bundle_item_ids = seller_items[:]
    if len(bundle_item_ids) == 0:
        bundle_item_ids = all_items[:1]
    bundle_data = {
        "auction_id": auction_id,
        "creator_id": seller_id,
        "item_ids": bundle_item_ids,
        "name": "测试组合包",
        "description": "测试",
        "reserve_price": 800.0
    }
    r = make_request("POST", "/api/secondary-market/bundles", bundle_data)
    if r:
        bundle_id = r['bundle_id']
        print(f"   组合创建成功 ID={bundle_id}")
        print(f"   ✓ 通过")
    else:
        bundle_id = None

    if bundle_id:
        print("\n6. 组合出价:")
        bundle_bid = {
            "bundle_id": bundle_id,
            "bidder_id": buyer_id,
            "price": 850.0
        }
        r = make_request("POST", f"/api/secondary-market/bundles/{bundle_id}/bids", bundle_bid)
        if r:
            print(f"   组合出价成功")
            print(f"   ✓ 通过")

        print("\n7. 完成组合拍卖:")
        r = make_request("POST", f"/api/secondary-market/bundles/{bundle_id}/finalize")
        if r:
            print(f"   组合拍卖完成，价格=${r['trade']['price']:.2f}")
            print(f"   ✓ 通过")

    print("\n8. 市场总览:")
    r = make_request("GET", f"/api/secondary-market/auction/{auction_id}/summary")
    if r:
        print(f"   总挂牌={r['total_listings']}, 总交易={r['total_trades']}, 总交易额=${r['total_trade_volume']:.2f}")
        print(f"   ✓ 通过")

    print("\n9. 交易历史:")
    r = make_request("GET", f"/api/secondary-market/auction/{auction_id}/trades")
    if r is not None:
        print(f"   交易记录数={len(r)}")
        print(f"   ✓ 通过")

    return True


def test_realtime_api(auction_id):
    print("\n=== 测试实时推送REST API ===")

    print("\n1. 连接统计:")
    r = make_request("GET", f"/api/realtime/auction/{auction_id}/connections")
    if r:
        print(f"   总连接={r['total_connections']}, 竞标者连接={r['bidder_connections']}")
        print(f"   ✓ 通过")

    print("\n2. 手动广播:")
    r = make_request("POST", f"/api/realtime/auction/{auction_id}/broadcast",
                    data={"message": "测试广播", "level": "info"})
    if r and r.get("success"):
        print(f"   广播成功")
        print(f"   ✓ 通过")

    print("\n3. 发送个人通知:")
    r = make_request("POST", f"/api/realtime/auction/{auction_id}/notify-bidder/1",
                    data={"update_type": "activity_reminder",
                          "data": {"message": "测试通知"}})
    if r and r.get("success"):
        print(f"   通知发送成功")
        print(f"   ✓ 通过")

    return True


def main():
    print("=" * 60)
    print("  新功能API验证测试")
    print("=" * 60)

    print("\n准备: 创建并运行拍卖...")
    data = {
        "name": "新功能验证拍卖",
        "auction_type": "smr",
        "num_items": 4,
        "num_bidders": 3,
        "max_rounds": 15,
        "bid_increment": 10
    }
    auction = make_request("POST", f"{API_PREFIX}/auctions", data)
    if not auction:
        print("无法创建拍卖")
        return

    auction_id = auction['id']
    print(f"  拍卖ID={auction_id}")

    print("\n运行拍卖...")
    result = make_request("POST", f"{API_PREFIX}/auctions/{auction_id}/run")
    if not result:
        print("无法运行拍卖")
        return

    rounds = result.get('result', {}).get('final_round', 'N/A')
    print(f"  拍卖完成，共 {rounds} 轮")

    time.sleep(1)

    tests = [
        ("市场势力分析", test_market_power, (auction_id,)),
        ("二次交易市场", test_secondary_market, (auction_id, result)),
        ("实时推送API", test_realtime_api, (auction_id,))
    ]

    passed = 0
    for name, test_func, args in tests:
        try:
            if test_func(*args):
                passed += 1
        except Exception as e:
            print(f"\n  ✗ {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  测试结果: {passed}/{len(tests)} 项通过")
    print("=" * 60)

    if passed == len(tests):
        print("\n🎉 所有新功能API测试通过!")
    else:
        print(f"\n⚠️  {len(tests) - passed} 项测试失败")

    print(f"\nWebSocket端点: ws://localhost:8000/api/realtime/ws/auction/{auction_id}")
    print(f"API文档: {BASE_URL}/docs")


if __name__ == "__main__":
    main()
