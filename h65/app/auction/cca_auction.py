from typing import List, Dict, Optional, Any, Tuple, Set, FrozenSet
import time
from collections import defaultdict
from itertools import combinations
import numpy as np

from app.auction.bidder import BidderState, AuctionItem, AuctionState
from app.strategies.strategy_manager import strategy_manager


class CCAAuction:
    def __init__(self, auction_state: AuctionState):
        self.state = auction_state
        self.bidder_strategies: Dict[int, Any] = {}
        self.clock_rounds_completed = False
        self.supplementary_rounds_completed = False
        self.current_supplementary_round = 0
        self.all_bids: List[Dict] = []
        self._initialize_strategies()

    def _initialize_strategies(self):
        for bidder in self.state.bidders:
            try:
                strategy = strategy_manager.get_strategy(
                    bidder.strategy_name,
                    bidder.strategy_params
                )
                self.bidder_strategies[bidder.bidder_id] = strategy
            except ValueError:
                from app.strategies.base_strategy import BundleBidStrategy
                self.bidder_strategies[bidder.bidder_id] = BundleBidStrategy()

    def run(self, verbose: bool = False) -> Dict[str, Any]:
        start_time = time.time()
        self.state.status = "running"

        if verbose:
            print(f"Starting CCA Auction with {len(self.state.items)} items and {len(self.state.bidders)} bidders")

        if verbose:
            print("Phase 1: Clock Phase")
        self._run_clock_phase(verbose)

        if verbose:
            print(f"Phase 2: Supplementary Bidding ({self._get_supplementary_rounds()} rounds)")
        self._run_supplementary_phase(verbose)

        if verbose:
            print("Phase 3: Winner Determination")
        result = self._run_winner_determination()

        self.state.status = "completed"
        self.state.is_completed = True

        duration = time.time() - start_time
        result["duration_seconds"] = round(duration, 2)

        return result

    def _get_supplementary_rounds(self) -> int:
        return self.state.config.get("supplementary_rounds", 3)

    def _run_clock_phase(self, verbose: bool = False):
        self.state.phase = "clock"

        while not self._is_clock_phase_complete():
            self.state.current_round += 1
            round_result = self._run_clock_round()

            if verbose and self.state.current_round % 5 == 0:
                print(f"Clock Round {self.state.current_round}: "
                      f"excess_demand={max(round_result['excess_demand'].values(), default=0):.1f}")

            self._update_clock_prices(round_result["excess_demand"])
            self._update_activity_scores(round_result["demanded_bundles"])

            self.state.record_round(
                prices=self.state.get_current_prices(),
                excess_demand=round_result["excess_demand"],
                provisional_allocation=round_result["provisional_allocation"],
                bids=round_result["bids"],
                bidder_activity=round_result["bidder_activity"]
            )

            if self.state.current_round >= self.state.max_rounds:
                break

        self.clock_rounds_completed = True

    def _run_clock_round(self) -> Dict[str, Any]:
        bids = []
        demanded_bundles: Dict[int, List[int]] = {}
        bidder_activity: Dict[int, float] = {}

        for bidder in self.state.bidders:
            if bidder.activity_score < 0.1 and self.state.activity_rule:
                demanded_bundles[bidder.bidder_id] = []
                bidder_activity[bidder.bidder_id] = bidder.activity_score
                continue

            strategy = self.bidder_strategies[bidder.bidder_id]
            try:
                round_bids = strategy.decide_bid(
                    bidder, self.state, self.state.current_round
                )
            except Exception as e:
                print(f"Error in bidder {bidder.bidder_id} strategy: {e}")
                round_bids = []

            valid_bids = []
            bid_items = []
            for bid in round_bids:
                bundle = bid.get("bundle")
                price = bid.get("price", 0.0)

                if bundle is None and bid.get("item_id") is not None:
                    item_id = bid.get("item_id")
                    bundle = {item_id: 1}

                if bundle is None:
                    continue

                item_ids = [int(k) for k in bundle.keys()]
                cost = sum(
                    self.state.get_current_prices().get(item_id, 0) * qty
                    for item_id, qty in bundle.items()
                )

                if price < cost * 0.9:
                    continue

                if not bidder.can_afford(price):
                    continue

                valid_bids.append({
                    "bidder_id": bidder.bidder_id,
                    "bundle": bundle,
                    "price": round(price, 2),
                    "round_number": self.state.current_round,
                    "phase": "clock"
                })
                bid_items.extend(item_ids)

            bids.extend(valid_bids)
            self.all_bids.extend(valid_bids)

            demanded_bundles[bidder.bidder_id] = list(set(bid_items))
            bidder_activity[bidder.bidder_id] = bidder.activity_score

            bidder.record_bid(self.state.current_round, valid_bids)

        excess_demand = self.state.get_excess_demand(demanded_bundles)
        provisional_allocation = self._compute_provisional_allocation_clock(bids)

        return {
            "bids": bids,
            "demanded_bundles": demanded_bundles,
            "excess_demand": excess_demand,
            "provisional_allocation": provisional_allocation,
            "bidder_activity": bidder_activity
        }

    def _compute_provisional_allocation_clock(self, bids: List[Dict]) -> Dict[int, List[int]]:
        item_bids: Dict[int, List[Tuple[int, float]]] = defaultdict(list)

        for bid in bids:
            bidder_id = bid["bidder_id"]
            price = bid["price"]
            bundle = bid.get("bundle", {})

            for item_id_str, qty in bundle.items():
                item_id = int(item_id_str)
                per_item_price = price / max(1, len(bundle))
                item_bids[item_id].append((bidder_id, per_item_price))

        allocation: Dict[int, List[int]] = defaultdict(list)
        for item_id, bid_list in item_bids.items():
            if bid_list:
                bid_list.sort(key=lambda x: x[1], reverse=True)
                winner_id = bid_list[0][0]
                allocation[winner_id].append(item_id)
                item = self.state.get_item(item_id)
                if item:
                    item.provisional_winner = winner_id

        return dict(allocation)

    def _update_clock_prices(self, excess_demand: Dict[int, float]):
        clock_increment = self.state.config.get("clock_increment", 5.0)
        for item_id, excess in excess_demand.items():
            if excess > 0:
                item = self.state.get_item(item_id)
                if item:
                    price_adjustment = clock_increment * (1 + excess / len(self.state.bidders))
                    item.current_price = min(
                        self.state.max_price,
                        item.current_price + price_adjustment
                    )

    def _update_activity_scores(self, demanded_bundles: Dict[int, List[int]]):
        if not self.state.activity_rule:
            return

        activity_weight = self.state.config.get("activity_weight", 0.8)
        for bidder in self.state.bidders:
            bundle = demanded_bundles.get(bidder.bidder_id, [])
            bidder.update_activity(bundle, activity_weight)

    def _is_clock_phase_complete(self) -> bool:
        if self.state.current_round == 0:
            return False

        if self.state.current_round >= self.state.max_rounds:
            return True

        if self.state.round_history:
            last_round = self.state.round_history[-1]
            max_excess = max(last_round.excess_demand.values(), default=0)
            if max_excess <= 0:
                consecutive_zero = sum(
                    1 for r in self.state.round_history[-2:]
                    if max(r.excess_demand.values(), default=0) <= 0
                )
                if consecutive_zero >= 2:
                    return True

        return False

    def _run_supplementary_phase(self, verbose: bool = False):
        self.state.phase = "supplementary"
        num_rounds = self._get_supplementary_rounds()

        for supp_round in range(1, num_rounds + 1):
            self.current_supplementary_round = supp_round
            self.state.current_round += 1
            round_result = self._run_supplementary_round(supp_round)

            if verbose:
                print(f"Supplementary Round {supp_round}: {len(round_result['bids'])} bids submitted")

            self.state.record_round(
                prices=self.state.get_current_prices(),
                excess_demand={},
                provisional_allocation=round_result["provisional_allocation"],
                bids=round_result["bids"],
                bidder_activity=round_result["bidder_activity"]
            )

        self.supplementary_rounds_completed = True

    def _run_supplementary_round(self, supp_round: int) -> Dict[str, Any]:
        bids = []
        bidder_activity: Dict[int, float] = {}

        for bidder in self.state.bidders:
            strategy = self.bidder_strategies[bidder.bidder_id]

            try:
                extra_bids = self._generate_supplementary_bids(bidder, supp_round)
            except Exception as e:
                print(f"Error generating supplementary bids for bidder {bidder.bidder_id}: {e}")
                extra_bids = []

            for bid in extra_bids:
                bundle = bid.get("bundle", {})
                price = bid.get("price", 0.0)

                if not bundle:
                    continue

                if not bidder.can_afford(price):
                    continue

                valid_bid = {
                    "bidder_id": bidder.bidder_id,
                    "bundle": bundle,
                    "price": round(price, 2),
                    "round_number": self.state.current_round,
                    "phase": "supplementary"
                }
                bids.append(valid_bid)
                self.all_bids.append(valid_bid)

            bidder_activity[bidder.bidder_id] = bidder.activity_score

        provisional_allocation = self._compute_provisional_allocation_clock(bids)

        return {
            "bids": bids,
            "provisional_allocation": provisional_allocation,
            "bidder_activity": bidder_activity
        }

    def _generate_supplementary_bids(self, bidder: BidderState, supp_round: int) -> List[Dict]:
        bids = []
        items = self.state.get_all_item_ids()
        final_clock_prices = self.state.get_current_prices()

        existing_bundles: Set[FrozenSet[int]] = set()
        for bid in self.all_bids:
            if bid["bidder_id"] == bidder.bidder_id:
                bundle = bid.get("bundle", {})
                bundle_items = frozenset([int(k) for k in bundle.keys()])
                existing_bundles.add(bundle_items)

        max_bundle_size = min(4, len(items))
        num_bundles = 5 + supp_round * 2

        for r in range(1, max_bundle_size + 1):
            for bundle in combinations(items, r):
                if len(bids) >= num_bundles:
                    break

                bundle_set = frozenset(bundle)
                if bundle_set in existing_bundles:
                    continue

                bundle_list = list(bundle)
                value = bidder.get_value(bundle_list)
                cost = sum(final_clock_prices.get(item, 0) for item in bundle_list)

                if value > cost * 0.8:
                    bid_price = min(value, cost * 1.1)
                    bids.append({
                        "bundle": {item_id: 1 for item_id in bundle_list},
                        "price": bid_price
                    })

                existing_bundles.add(bundle_set)

            if len(bids) >= num_bundles:
                break

        return bids

    def _run_winner_determination(self) -> Dict[str, Any]:
        self.state.phase = "assignment"

        pricing_rule = self.state.config.get("pricing_rule", "core_selecting")

        if pricing_rule == "core_selecting":
            allocation, payments = self._core_selecting_auction()
        elif pricing_rule == "second_price":
            allocation, payments = self._second_price_winner_determination()
        elif pricing_rule == "first_price":
            allocation, payments = self._first_price_winner_determination()
        elif pricing_rule == "vcg":
            allocation, payments = self._vcg_mechanism()
        else:
            allocation, payments = self._core_selecting_auction()

        self._apply_allocation(allocation, payments)

        return {
            "auction_id": self.state.auction_id,
            "auction_type": "cca",
            "final_round": self.state.current_round,
            "final_prices": {item.item_id: round(item.current_price, 2) for item in self.state.items},
            "final_allocation": allocation,
            "bidder_results": self._get_bidder_results(payments),
            "total_revenue": sum(payments.values()),
            "pricing_rule": pricing_rule
        }

    def _first_price_winner_determination(self) -> Tuple[Dict[int, List[int]], Dict[int, float]]:
        best_allocation = {}
        best_payments = {}
        best_surplus = 0.0

        items = self.state.get_all_item_ids()
        n_items = len(items)

        bidder_bids: Dict[int, List[Dict]] = defaultdict(list)
        for bid in self.all_bids:
            bidder_bids[bid["bidder_id"]].append(bid)

        from itertools import product
        max_bids_per_bidder = min(10, max(len(b) for b in bidder_bids.values()) if bidder_bids else 1)
        bid_options = []
        for bidder_id in self.state.get_all_bidder_ids():
            bid_list = bidder_bids.get(bidder_id, [])
            bid_list.sort(key=lambda x: x["price"], reverse=True)
            options = [None] + bid_list[:max_bids_per_bidder]
            bid_options.append(options)

        for selection in product(*bid_options):
            item_assignment: Dict[int, int] = {}
            valid = True
            total_price = 0.0
            allocation: Dict[int, List[int]] = defaultdict(list)
            payments: Dict[int, float] = defaultdict(float)

            for bidder_idx, bid in enumerate(selection):
                if bid is None:
                    continue

                bidder_id = self.state.get_all_bidder_ids()[bidder_idx]
                bundle = bid.get("bundle", {})

                for item_id_str in bundle.keys():
                    item_id = int(item_id_str)
                    if item_id in item_assignment:
                        valid = False
                        break
                    item_assignment[item_id] = bidder_id

                if not valid:
                    break

                for item_id_str in bundle.keys():
                    item_id = int(item_id_str)
                    allocation[bidder_id].append(item_id)
                payments[bidder_id] += bid["price"]
                total_price += bid["price"]

            if valid and total_price > best_surplus:
                best_surplus = total_price
                best_allocation = dict(allocation)
                best_payments = dict(payments)

        return best_allocation, best_payments

    def _second_price_winner_determination(self) -> Tuple[Dict[int, List[int]], Dict[int, float]]:
        best_allocation, _ = self._first_price_winner_determination()

        item_bids: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
        bundle_bids: Dict[Tuple[int, ...], List[Tuple[int, float]]] = defaultdict(list)

        for bid in self.all_bids:
            bidder_id = bid["bidder_id"]
            price = bid.get("price", 0.0)
            bundle = bid.get("bundle", {})
            item_ids = sorted([int(k) for k in bundle.keys()])

            if len(item_ids) == 1:
                item_bids[item_ids[0]].append((bidder_id, price))
            else:
                bundle_key = tuple(item_ids)
                bundle_bids[bundle_key].append((bidder_id, price))

        for item_id in item_bids:
            item_bids[item_id].sort(key=lambda x: x[1], reverse=True)
        for bundle_key in bundle_bids:
            bundle_bids[bundle_key].sort(key=lambda x: x[1], reverse=True)

        payments: Dict[int, float] = defaultdict(float)

        for bidder_id, items in best_allocation.items():
            if not items:
                continue

            items_sorted = sorted(items)
            bundle_key = tuple(items_sorted)

            second_price = 0.0

            if len(items_sorted) == 1:
                item_id = items_sorted[0]
                bids = item_bids.get(item_id, [])
                other_bids = [b for b in bids if b[0] != bidder_id]
                if other_bids:
                    second_price = other_bids[0][1]
                elif bids:
                    second_price = bids[-1][1] * 0.9
            else:
                bids = bundle_bids.get(bundle_key, [])
                other_bids = [b for b in bids if b[0] != bidder_id]
                if other_bids:
                    second_price = other_bids[0][1]
                else:
                    individual_second = 0.0
                    for item_id in items_sorted:
                        item_bid_list = item_bids.get(item_id, [])
                        other_item_bids = [b for b in item_bid_list if b[0] != bidder_id]
                        if other_item_bids:
                            individual_second += other_item_bids[0][1]
                    second_price = individual_second

            reserve_total = 0.0
            for item_id in items:
                item = self.state.get_item(item_id)
                if item and item.reserve_price > 0:
                    reserve_total += item.reserve_price

            payments[bidder_id] = max(second_price, reserve_total)

        return best_allocation, payments

    def _core_selecting_auction(self) -> Tuple[Dict[int, List[int]], Dict[int, float]]:
        efficient_allocation, vcg_payments = self._vcg_mechanism()

        if not efficient_allocation:
            return {}, {}

        total_revenue = sum(vcg_payments.values())

        bidder_ids = list(efficient_allocation.keys())
        n_winners = len(bidder_ids)

        if n_winners <= 1:
            return efficient_allocation, vcg_payments

        core_payments = vcg_payments.copy()
        max_iterations = 100
        alpha = 0.1

        for _ in range(max_iterations):
            blocking_coalitions = self._find_blocking_coalitions(
                efficient_allocation, core_payments
            )

            if not blocking_coalitions:
                break

            for coalition, min_revenue in blocking_coalitions:
                current_revenue = sum(core_payments.get(b, 0) for b in coalition)
                if current_revenue < min_revenue:
                    gap = min_revenue - current_revenue
                    per_bidder = gap / len(coalition)
                    for bidder_id in coalition:
                        core_payments[bidder_id] = core_payments.get(bidder_id, 0) + per_bidder * alpha

        for bidder_id in core_payments:
            bidder = self.state.get_bidder(bidder_id)
            if bidder:
                bundle = efficient_allocation.get(bidder_id, [])
                value = bidder.get_value(bundle)
                core_payments[bidder_id] = min(core_payments[bidder_id], value)

        return efficient_allocation, core_payments

    def _vcg_mechanism(self) -> Tuple[Dict[int, List[int]], Dict[int, float]]:
        items = self.state.get_all_item_ids()
        n_items = len(items)

        total_value, efficient_allocation = self._compute_efficient_allocation()

        vcg_payments = {}

        for bidder_id in efficient_allocation.keys():
            vcg_payments[bidder_id] = self._compute_vcg_payment(
                bidder_id, efficient_allocation, total_value
            )

        return efficient_allocation, vcg_payments

    def _compute_efficient_allocation(self) -> Tuple[float, Dict[int, List[int]]]:
        best_value = 0.0
        best_allocation: Dict[int, List[int]] = {}

        items = self.state.get_all_item_ids()
        bidder_ids = self.state.get_all_bidder_ids()

        from itertools import combinations

        def search(current_item_idx, allocation, current_value):
            nonlocal best_value, best_allocation

            if current_item_idx >= len(items):
                if current_value > best_value:
                    best_value = current_value
                    best_allocation = {k: v.copy() for k, v in allocation.items()}
                return

            item_id = items[current_item_idx]

            search(current_item_idx + 1, allocation, current_value)

            for bidder_id in bidder_ids:
                current_bundle = allocation.get(bidder_id, [])
                marginal_value = self.state.get_bidder(bidder_id).get_marginal_value(
                    item_id, current_bundle
                )

                if marginal_value > 0:
                    if bidder_id not in allocation:
                        allocation[bidder_id] = []
                    allocation[bidder_id].append(item_id)
                    search(current_item_idx + 1, allocation, current_value + marginal_value)
                    allocation[bidder_id].pop()
                    if not allocation[bidder_id]:
                        del allocation[bidder_id]

        search(0, {}, 0.0)

        return best_value, best_allocation

    def _compute_vcg_payment(
        self,
        excluded_bidder: int,
        efficient_allocation: Dict[int, List[int]],
        total_efficient_value: float
    ) -> float:
        other_bidders_value = 0.0
        for bidder_id, bundle in efficient_allocation.items():
            if bidder_id != excluded_bidder:
                bidder = self.state.get_bidder(bidder_id)
                if bidder:
                    other_bidders_value += bidder.get_value(bundle)

        best_value_without = 0.0

        items = self.state.get_all_item_ids()
        other_bidder_ids = [
            b for b in self.state.get_all_bidder_ids() if b != excluded_bidder
        ]

        def search(current_item_idx, allocation, current_value):
            nonlocal best_value_without

            if current_item_idx >= len(items):
                if current_value > best_value_without:
                    best_value_without = current_value
                return

            item_id = items[current_item_idx]

            search(current_item_idx + 1, allocation, current_value)

            for bidder_id in other_bidder_ids:
                current_bundle = allocation.get(bidder_id, [])
                bidder = self.state.get_bidder(bidder_id)
                if bidder:
                    marginal_value = bidder.get_marginal_value(item_id, current_bundle)

                    if marginal_value > 0:
                        if bidder_id not in allocation:
                            allocation[bidder_id] = []
                        allocation[bidder_id].append(item_id)
                        search(current_item_idx + 1, allocation, current_value + marginal_value)
                        allocation[bidder_id].pop()
                        if not allocation[bidder_id]:
                            del allocation[bidder_id]

        search(0, {}, 0.0)

        vcg_payment = best_value_without - other_bidders_value
        return max(0.0, vcg_payment)

    def _find_blocking_coalitions(
        self,
        allocation: Dict[int, List[int]],
        payments: Dict[int, float]
    ) -> List[Tuple[List[int], float]]:
        blocking_coalitions = []
        bidder_ids = list(allocation.keys())

        for r in range(2, len(bidder_ids) + 1):
            for coalition in combinations(bidder_ids, r):
                coalition_list = list(coalition)

                current_payments = sum(payments.get(b, 0) for b in coalition_list)

                coalition_value = self._compute_coalition_value(coalition_list)

                min_revenue = self._compute_min_coalition_revenue(
                    coalition_list, allocation, payments
                )

                if current_payments < min_revenue - 1e-6:
                    blocking_coalitions.append((coalition_list, min_revenue))

        return blocking_coalitions

    def _compute_coalition_value(self, bidder_ids: List[int]) -> float:
        items = self.state.get_all_item_ids()
        best_value = 0.0

        def search(current_item_idx, allocation, current_value):
            nonlocal best_value

            if current_item_idx >= len(items):
                if current_value > best_value:
                    best_value = current_value
                return

            item_id = items[current_item_idx]

            search(current_item_idx + 1, allocation, current_value)

            for bidder_id in bidder_ids:
                current_bundle = allocation.get(bidder_id, [])
                bidder = self.state.get_bidder(bidder_id)
                if bidder:
                    marginal_value = bidder.get_marginal_value(item_id, current_bundle)

                    if marginal_value > 0:
                        if bidder_id not in allocation:
                            allocation[bidder_id] = []
                        allocation[bidder_id].append(item_id)
                        search(current_item_idx + 1, allocation, current_value + marginal_value)
                        allocation[bidder_id].pop()
                        if not allocation[bidder_id]:
                            del allocation[bidder_id]

        search(0, {}, 0.0)
        return best_value

    def _compute_min_coalition_revenue(
        self,
        coalition: List[int],
        allocation: Dict[int, List[int]],
        payments: Dict[int, float]
    ) -> float:
        bidder_ids = [
            b for b in self.state.get_all_bidder_ids() if b not in coalition
        ]

        best_value = 0.0

        items = self.state.get_all_item_ids()

        def search(current_item_idx, current_allocation, current_value):
            nonlocal best_value

            if current_item_idx >= len(items):
                if current_value > best_value:
                    best_value = current_value
                return

            item_id = items[current_item_idx]

            search(current_item_idx + 1, current_allocation, current_value)

            for bidder_id in bidder_ids:
                bidder = self.state.get_bidder(bidder_id)
                if bidder:
                    current_bundle = current_allocation.get(bidder_id, [])
                    marginal_value = bidder.get_marginal_value(item_id, current_bundle)

                    if marginal_value > 0:
                        if bidder_id not in current_allocation:
                            current_allocation[bidder_id] = []
                        current_allocation[bidder_id].append(item_id)
                        search(current_item_idx + 1, current_allocation, current_value + marginal_value)
                        current_allocation[bidder_id].pop()
                        if not current_allocation[bidder_id]:
                            del current_allocation[bidder_id]

        search(0, {}, 0.0)

        coalition_value = sum(
            self.state.get_bidder(b).get_value(allocation.get(b, []))
            for b in coalition
            if self.state.get_bidder(b)
        )

        return coalition_value + best_value - best_value

    def _apply_allocation(self, allocation: Dict[int, List[int]], payments: Dict[int, float]):
        for item in self.state.items:
            item.final_winner = None
            item.final_price = None

        for bidder_id, items_list in allocation.items():
            for item_id in items_list:
                item = self.state.get_item(item_id)
                if item:
                    item.final_winner = bidder_id
                    item.final_price = payments.get(bidder_id, 0.0) / max(1, len(items_list))

            bidder = self.state.get_bidder(bidder_id)
            if bidder:
                bidder.total_payment = payments.get(bidder_id, 0.0)
                bidder.total_value = bidder.get_value(items_list)
                bidder.current_bundle = items_list

    def _get_bidder_results(self, payments: Dict[int, float]) -> Dict[int, Dict[str, Any]]:
        results = {}
        for bidder in self.state.bidders:
            won_items = [
                item.item_id for item in self.state.items
                if item.final_winner == bidder.bidder_id
            ]
            bundle_value = bidder.get_value(won_items)
            payment = payments.get(bidder.bidder_id, 0.0)

            results[bidder.bidder_id] = {
                "bidder_name": bidder.name,
                "strategy": bidder.strategy_name,
                "won_items": won_items,
                "total_payment": round(payment, 2),
                "total_value": round(bundle_value, 2),
                "utility": round(bundle_value - payment, 2),
                "profit": round(bundle_value - payment, 2),
                "activity_score": round(bidder.activity_score, 3)
            }
        return results

    def step(self) -> Dict[str, Any]:
        if self.state.is_completed:
            return {"status": "completed"}

        if not self.clock_rounds_completed:
            self.state.phase = "clock"
            self.state.current_round += 1
            round_result = self._run_clock_round()
            self._update_clock_prices(round_result["excess_demand"])
            self._update_activity_scores(round_result["demanded_bundles"])

            self.state.record_round(
                prices=self.state.get_current_prices(),
                excess_demand=round_result["excess_demand"],
                provisional_allocation=round_result["provisional_allocation"],
                bids=round_result["bids"],
                bidder_activity=round_result["bidder_activity"]
            )

            clock_complete = self._is_clock_phase_complete()
            if clock_complete:
                self.clock_rounds_completed = True

            return {
                "round": self.state.current_round,
                "phase": "clock",
                "is_complete": False,
                "round_completed": True,
                "prices": {k: round(v, 2) for k, v in self.state.get_current_prices().items()},
                "excess_demand": round_result["excess_demand"],
                "bids_count": len(round_result["bids"]),
                "provisional_allocation": round_result["provisional_allocation"],
                "clock_phase_complete": clock_complete
            }

        elif not self.supplementary_rounds_completed:
            self.state.phase = "supplementary"
            self.current_supplementary_round += 1
            self.state.current_round += 1

            round_result = self._run_supplementary_round(self.current_supplementary_round)
            self.state.record_round(
                prices=self.state.get_current_prices(),
                excess_demand={},
                provisional_allocation=round_result["provisional_allocation"],
                bids=round_result["bids"],
                bidder_activity=round_result["bidder_activity"]
            )

            if self.current_supplementary_round >= self._get_supplementary_rounds():
                self.supplementary_rounds_completed = True

            return {
                "round": self.state.current_round,
                "phase": "supplementary",
                "supplementary_round": self.current_supplementary_round,
                "is_complete": False,
                "round_completed": True,
                "bids_count": len(round_result["bids"]),
                "supplementary_phase_complete": self.supplementary_rounds_completed
            }

        else:
            result = self._run_winner_determination()
            self.state.status = "completed"
            self.state.is_completed = True
            return {
                "round": self.state.current_round,
                "phase": "assignment",
                "is_complete": True,
                "result": result
            }
