# 频谱拍卖模拟平台 (Spectrum Auction Simulation Platform)

基于 FastAPI + PostgreSQL 的频谱拍卖模拟平台，支持多种拍卖格式、竞标者模型、自定义策略和可视化。

## 功能特性

### 拍卖格式
- **SMR (Simultaneous Multi-Round Ascending)** - 同时多轮增价拍卖
- **CCA (Combinatorial Clock Auction)** - 组合时钟拍卖

### 竞标者模型
- 估值随机生成（支持4种模型）
- 互补估值（物品间协同效应）
- 预算约束和风险偏好
- 活动规则（Activity Rule）

### 竞标策略
- 内置策略：
  - `truthful` - 真实出价策略
  - `aggressive` - 激进策略
  - `conservative` - 保守策略
  - `bundle` - 组合策略
  - `adaptive` - 自适应策略（基于竞争对手历史）
  - `bundle_bid` - 组合出价策略（CCA专用）
- 支持用户自定义策略上传

### 分析指标
- 成交价分析
- 拍卖效率（社会福利）
- 卖方收益
- 竞标者效用/利润
- 收敛速度
- 分配率

### 可视化
- 价格上升路径
- 超额需求曲线
- 分配结果饼图
- 收益-效率对比
- 竞标者效用柱状图
- 每轮出价数量
- 价格收敛速度

### 策略对战
- 上传自定义策略算法
- 多轮比赛
- 排名统计
- 胜率和平均收益追踪

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

默认使用 SQLite（无需配置）。如需使用 PostgreSQL，修改 `app/core/config.py`：

```python
USE_SQLITE = False
DATABASE_URL = "postgresql://username:password@localhost:5432/spectrum_auction"
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 使用示例

### 示例1: 创建并运行 SMR 拍卖

```bash
# 创建拍卖（5个物品，4个竞标者）
curl -X POST "http://localhost:8000/api/v1/auctions?seed=42" \
-H "Content-Type: application/json" \
-d '{
  "name": "SMR Auction Test",
  "auction_type": "smr",
  "description": "Test SMR auction with 5 items and 4 bidders",
  "min_price": 10.0,
  "max_price": 1000.0,
  "bid_increment": 5.0,
  "max_rounds": 100,
  "activity_rule": true,
  "num_items": 5,
  "num_bidders": 4
}'

# 运行拍卖
curl -X POST "http://localhost:8000/api/v1/auctions/1/run?verbose=true"

# 查看结果
curl "http://localhost:8000/api/v1/auctions/1/result"
```

### 示例2: 创建并运行 CCA 拍卖

```bash
curl -X POST "http://localhost:8000/api/v1/auctions?seed=42" \
-H "Content-Type: application/json" \
-d '{
  "name": "CCA Auction Test",
  "auction_type": "cca",
  "description": "Test CCA auction with complementary items",
  "min_price": 10.0,
  "max_price": 1000.0,
  "bid_increment": 5.0,
  "max_rounds": 100,
  "activity_rule": true,
  "config": {
    "supplementary_rounds": 3,
    "core_selecting": true
  },
  "num_items": 6,
  "num_bidders": 4
}'

curl -X POST "http://localhost:8000/api/v1/auctions/2/run?verbose=true"
```

### 示例3: 单步执行拍卖

```bash
# 第一步
curl -X POST "http://localhost:8000/api/v1/auctions/1/step"

# 查看当前状态
curl "http://localhost:8000/api/v1/auctions/1/state"

# 继续执行...
curl -X POST "http://localhost:8000/api/v1/auctions/1/step"
```

### 示例4: 上传自定义策略

```bash
# 获取策略模板
curl "http://localhost:8000/api/v1/strategies/example"

# 上传策略文件
curl -X POST "http://localhost:8000/api/v1/strategies" \
-F "name=my_strategy" \
-F "description=My custom bidding strategy" \
-F "author=Alice" \
-F "file=@my_strategy.py"
```

### 示例5: 策略对战

```bash
# 创建比赛
curl -X POST "http://localhost:8000/api/v1/competitions" \
-H "Content-Type: application/json" \
-d '{
  "name": "Strategy Battle",
  "auction_type": "smr",
  "description": "Battle between different strategies",
  "strategy_ids": [1, 2, 3],
  "config": {
    "num_items": 5,
    "base_value_range": [50.0, 300.0]
  },
  "num_rounds": 5
}'

# 运行比赛
curl -X POST "http://localhost:8000/api/v1/competitions/1/run?num_rounds=5&verbose=true"
```

### 示例6: 查看可视化

```bash
# 获取所有图表
curl "http://localhost:8000/api/v1/visualization/auctions/1"

# 查看价格路径数据
curl "http://localhost:8000/api/v1/visualization/auctions/1/price-path"

# 直接访问图表
# http://localhost:8000/static/price_path.png
# http://localhost:8000/static/allocation.png
```

## 自定义策略开发

### 策略模板

```python
from typing import List, Dict, Any
from app.strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "My custom strategy"

    def decide_bid(
        self,
        bidder,        # BidderState 对象
        auction_state,  # AuctionState 对象
        round_number    # 当前轮次
    ) -> List[Dict[str, Any]]:
        """
        返回出价列表，每个出价是一个字典：
        {
            "item_id": int,           # 单品出价
            "bundle": Dict[int, int], # 组合出价 {item_id: quantity}
            "price": float,           # 出价
            "quantity": int           # 数量（可选）
        }
        """
        prices = auction_state.get_current_prices()
        bids = []

        # 获取需求集
        demand = bidder.get_demand_set(prices)

        for item_id in demand:
            value = bidder.get_individual_value(item_id)
            price = prices.get(item_id, 0)

            if value > price * 1.1:  # 价值超过价格10%才出价
                bids.append({
                    "item_id": item_id,
                    "price": price + auction_state.bid_increment,
                    "quantity": 1
                })

        return bids

    def observe_history(
        self,
        bidder,
        auction_state,
        round_number
    ):
        """可选：观察历史，用于学习竞争对手行为"""
        if round_number > 0 and auction_state.round_history:
            last_round = auction_state.round_history[-1]
            for bid in last_round.bids:
                if bid.get("bidder_id") != bidder.bidder_id:
                    # 分析竞争对手
                    pass
```

### 可用数据

**BidderState 属性:**
- `base_values: Dict[int, float]` - 各物品基础估值
- `complementary_values: Dict[str, float]` - 互补值 {"i_j": value}
- `budget: float` - 预算
- `risk_aversion: float` - 风险厌恶系数 [0,1]
- `activity_score: float` - 活动得分
- `history_bids: List[Dict]` - 历史出价
- `history_allocation: List[List[int]]` - 历史分配

**BidderState 方法:**
- `get_value(bundle: List[int]) -> float` - 计算组合价值
- `get_marginal_value(item: int, current_bundle: List[int]) -> float` - 计算边际价值
- `get_individual_value(item: int) -> float` - 获取单品价值
- `get_demand_set(prices: Dict[int, float], max_items: Optional[int]) -> List[int]` - 获取需求集
- `can_afford(cost: float) -> bool` - 检查预算
- `get_utility() -> float` - 获取当前效用

**AuctionState 方法:**
- `get_current_prices() -> Dict[int, float]` - 获取当前价格
- `get_excess_demand(demanded_bundles: Dict[int, List[int]]) -> Dict[int, float]` - 计算超额需求
- `get_item(item_id: int) -> Optional[AuctionItem]` - 获取物品
- `get_bidder(bidder_id: int) -> Optional[BidderState]` - 获取竞标者
- `get_all_item_ids() -> List[int]` - 获取所有物品ID

**AuctionState 属性:**
- `current_round: int` - 当前轮次
- `phase: str` - 阶段 ("clock", "supplementary", "assignment")
- `items: List[AuctionItem]` - 物品列表
- `bidders: List[BidderState]` - 竞标者列表
- `round_history: List[RoundInfo]` - 历史记录
- `min_price`, `max_price`, `bid_increment` - 拍卖参数

## 项目结构

```
spectrum_auction/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── auction/
│   │   ├── __init__.py
│   │   ├── bidder.py              # 竞标者和拍卖状态类
│   │   ├── valuation_generator.py # 估值生成器
│   │   ├── smr_auction.py         # SMR 拍卖算法
│   │   ├── cca_auction.py         # CCA 拍卖算法
│   │   ├── auction_service.py     # 拍卖服务层
│   │   ├── competition_service.py # 策略对战服务
│   │   └── result_analyzer.py     # 结果分析器
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py              # SQLAlchemy 模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic 模型
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base_strategy.py       # 策略基类和内置策略
│   │   └── strategy_manager.py    # 策略管理器
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auction_routes.py      # 拍卖API路由
│   │   ├── strategy_routes.py     # 策略API路由
│   │   └── visualization_routes.py # 可视化API路由
│   ├── visualization/
│   │   ├── __init__.py
│   │   └── plots.py               # 可视化模块
│   └── core/
│       ├── __init__.py
│       ├── config.py              # 配置
│       └── database.py            # 数据库连接
├── uploaded_strategies/           # 用户上传策略
├── static/                        # 静态文件（图表）
├── requirements.txt
└── README.md
```

## 拍卖算法说明

### SMR (Simultaneous Multi-Round Ascending)

1. **时钟阶段**: 所有物品同时拍卖，每轮竞标者对想要的物品出价
2. **价格更新**: 根据超额需求调整价格（需求>供给则涨价）
3. **活动规则**: 竞标者需保持活跃度，否则失去后续轮次的竞价权
4. **结束条件**: 连续多轮无超额需求，或达到最大轮次
5. **分配**: 最高出价者获得物品

### CCA (Combinatorial Clock Auction)

1. **时钟阶段**: 类似SMR，但竞标者对组合出价
2. **补充报价阶段**: 竞标者可提交额外的组合出价
3. **赢家确定**: 使用 VCG 或 Core-Selecting 机制确定最优分配
4. **定价**: 基于VCG或核定价计算最终支付

## 效率计算

拍卖效率 = 实际社会福利 / 最优社会福利

- **社会福利**: 所有竞标者对所获物品的估值之和
- **最优社会福利**: 通过穷举搜索找到的理论最高社会福利

## 开发说明

### 运行测试

```bash
# 启动服务后访问
# http://localhost:8000/docs
```

### 代码规范

- 遵循 PEP 8
- 使用类型注解
- 文档字符串使用 Google 风格

## License

MIT License
