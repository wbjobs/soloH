from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np
from collections import defaultdict
from itertools import combinations


@dataclass
class CollusionRisk:
    bidder_pair: Tuple[int, int]
    risk_score: float
    risk_level: str
    evidence: List[str]


@dataclass
class MarketPowerAnalysis:
    hhi_index: float
    concentration_level: str
    collusion_risks: List[CollusionRisk]
    market_power_scores: Dict[int, float]
    winning_bidder_shares: Dict[int, float]
    suspicious_patterns: List[str]
    overall_risk_level: str


class MarketPowerAnalyzer:
    def __init__(self, auction_state: Any):
        self.state = auction_state
        self.num_rounds = len(auction_state.round_history)
        self.num_bidders = len(auction_state.bidders)
        self.num_items = len(auction_state.items)

    def analyze(self) -> MarketPowerAnalysis:
        hhi = self._compute_hhi()
        concentration = self._get_concentration_level(hhi)
        collusion_risks = self._detect_collusion()
        market_power = self._compute_market_power_scores()
        winning_shares = self._compute_winning_shares()
        patterns = self._detect_suspicious_patterns()
        overall_risk = self._assess_overall_risk(hhi, collusion_risks, patterns)

        return MarketPowerAnalysis(
            hhi_index=round(hhi, 2),
            concentration_level=concentration,
            collusion_risks=collusion_risks,
            market_power_scores={k: round(v, 4) for k, v in market_power.items()},
            winning_bidder_shares={k: round(v, 4) for k, v in winning_shares.items()},
            suspicious_patterns=patterns,
            overall_risk_level=overall_risk
        )

    def _compute_hhi(self) -> float:
        if self.num_items == 0:
            return 0.0

        winning_shares = self._compute_winning_shares()
        hhi = sum(share ** 2 for share in winning_shares.values()) * 10000
        return hhi

    def _compute_winning_shares(self) -> Dict[int, float]:
        if not self.state.round_history:
            return {b.bidder_id: 0.0 for b in self.state.bidders}

        last_round = self.state.round_history[-1]
        allocation = last_round.provisional_allocation

        shares = {}
        for bidder in self.state.bidders:
            won_items = len(allocation.get(bidder.bidder_id, []))
            shares[bidder.bidder_id] = won_items / max(1, self.num_items)

        return shares

    def _get_concentration_level(self, hhi: float) -> str:
        if hhi < 1500:
            return "unconcentrated"
        elif hhi < 2500:
            return "moderately_concentrated"
        else:
            return "highly_concentrated"

    def _detect_collusion(self) -> List[CollusionRisk]:
        risks = []
        bidder_ids = [b.bidder_id for b in self.state.bidders]

        for i, j in combinations(bidder_ids, 2):
            evidence = []
            score = 0.0

            corr = self._bid_correlation(i, j)
            if corr > 0.8:
                score += 0.3
                evidence.append(f"出价高度相关 (corr={corr:.2f})")
            elif corr > 0.6:
                score += 0.15
                evidence.append(f"出价中度相关 (corr={corr:.2f})")

            rotation_score = self._rotation_analysis(i, j)
            if rotation_score > 0.7:
                score += 0.3
                evidence.append(f"轮换出价模式明显 (score={rotation_score:.2f})")
            elif rotation_score > 0.5:
                score += 0.15
                evidence.append(f"疑似轮换出价 (score={rotation_score:.2f})")

            parallel_score = self._parallel_bidding_analysis(i, j)
            if parallel_score > 0.8:
                score += 0.25
                evidence.append(f"平行出价行为 (score={parallel_score:.2f})")

            suppress_score = self._bid_suppression_analysis(i, j)
            if suppress_score > 0.7:
                score += 0.25
                evidence.append(f"出价抑制迹象 (score={suppress_score:.2f})")

            if evidence:
                if score >= 0.7:
                    level = "high"
                elif score >= 0.4:
                    level = "medium"
                else:
                    level = "low"

                risks.append(CollusionRisk(
                    bidder_pair=(i, j),
                    risk_score=round(score, 4),
                    risk_level=level,
                    evidence=evidence
                ))

        risks.sort(key=lambda x: x.risk_score, reverse=True)
        return risks

    def _bid_correlation(self, bidder1: int, bidder2: int) -> float:
        if self.num_rounds < 3:
            return 0.0

        bids1 = []
        bids2 = []

        for round_info in self.state.round_history:
            b1_bid = 0.0
            b2_bid = 0.0
            for bid in round_info.bids:
                if bid["bidder_id"] == bidder1:
                    b1_bid = max(b1_bid, bid.get("price", 0.0))
                if bid["bidder_id"] == bidder2:
                    b2_bid = max(b2_bid, bid.get("price", 0.0))
            bids1.append(b1_bid)
            bids2.append(b2_bid)

        if len(bids1) < 2 or np.std(bids1) == 0 or np.std(bids2) == 0:
            return 0.0

        correlation = np.corrcoef(bids1, bids2)[0, 1]
        return max(0.0, correlation) if not np.isnan(correlation) else 0.0

    def _rotation_analysis(self, bidder1: int, bidder2: int) -> float:
        if self.num_rounds < 4:
            return 0.0

        winner_sequence = []
        for round_info in self.state.round_history:
            high_bidder = None
            high_bid = 0.0
            for bid in round_info.bids:
                if bid["bidder_id"] in [bidder1, bidder2]:
                    if bid.get("price", 0.0) > high_bid:
                        high_bid = bid.get("price", 0.0)
                        high_bidder = bid["bidder_id"]
            winner_sequence.append(high_bidder)

        if not winner_sequence:
            return 0.0

        rotations = 0
        for k in range(1, len(winner_sequence)):
            if (winner_sequence[k-1] == bidder1 and winner_sequence[k] == bidder2) or \
               (winner_sequence[k-1] == bidder2 and winner_sequence[k] == bidder1):
                rotations += 1

        expected_rotations = (len(winner_sequence) - 1) * 0.5
        rotation_ratio = min(rotations / max(expected_rotations, 1), 1.0)

        return rotation_ratio

    def _parallel_bidding_analysis(self, bidder1: int, bidder2: int) -> float:
        if self.num_rounds < 3:
            return 0.0

        parallel_rounds = 0
        total_rounds = 0

        for round_info in self.state.round_history:
            b1_bids = [b for b in round_info.bids if b["bidder_id"] == bidder1]
            b2_bids = [b for b in round_info.bids if b["bidder_id"] == bidder2]

            if b1_bids and b2_bids:
                total_rounds += 1
                b1_items = set()
                for b in b1_bids:
                    if b.get("item_id"):
                        b1_items.add(b["item_id"])
                    elif b.get("bundle"):
                        b1_items.update([int(k) for k in b["bundle"].keys()])

                b2_items = set()
                for b in b2_bids:
                    if b.get("item_id"):
                        b2_items.add(b["item_id"])
                    elif b.get("bundle"):
                        b2_items.update([int(k) for k in b["bundle"].keys()])

                if b1_items and b2_items and b1_items.isdisjoint(b2_items):
                    parallel_rounds += 1

        return parallel_rounds / max(total_rounds, 1)

    def _bid_suppression_analysis(self, bidder1: int, bidder2: int) -> float:
        if self.num_rounds < 5:
            return 0.0

        suppressed_rounds = 0
        check_rounds = 0

        for round_idx in range(2, self.num_rounds):
            round_info = self.state.round_history[round_idx]
            prev_info = self.state.round_history[round_idx - 1]

            b1_high_prev = max([b.get("price", 0) for b in prev_info.bids
                             if b["bidder_id"] == bidder1], default=0)
            b2_high_prev = max([b.get("price", 0) for b in prev_info.bids
                             if b["bidder_id"] == bidder2], default=0)

            prev_winner = bidder1 if b1_high_prev > b2_high_prev else bidder2

            b1_high_curr = max([b.get("price", 0) for b in round_info.bids
                             if b["bidder_id"] == bidder1], default=0)
            b2_high_curr = max([b.get("price", 0) for b in round_info.bids
                             if b["bidder_id"] == bidder2], default=0)

            if prev_winner == bidder1 and b2_high_curr <= b2_high_prev * 1.05:
                check_rounds += 1
                if b2_high_curr <= b2_high_prev:
                    suppressed_rounds += 1
            elif prev_winner == bidder2 and b1_high_curr <= b1_high_prev * 1.05:
                check_rounds += 1
                if b1_high_curr <= b1_high_prev:
                    suppressed_rounds += 1

        return suppressed_rounds / max(check_rounds, 1)

    def _compute_market_power_scores(self) -> Dict[int, float]:
        scores = {}
        winning_shares = self._compute_winning_shares()

        for bidder in self.state.bidders:
            share = winning_shares.get(bidder.bidder_id, 0.0)

            budget_score = min(bidder.budget / 1e9, 1.0) if bidder.budget > 0 else 0.5

            activity_score = 0.0
            if self.num_rounds > 0:
                active_rounds = sum(1 for r in self.state.round_history
                                  if any(b["bidder_id"] == bidder.bidder_id for b in r.bids))
                activity_score = active_rounds / self.num_rounds

            valuation_score = 0.0
            if bidder.base_values:
                max_val = max(bidder.base_values.values())
                avg_val = np.mean(list(bidder.base_values.values()))
                valuation_score = min(avg_val / max(max_val, 1), 1.0)

            score = (share * 0.4 + budget_score * 0.2 +
                    activity_score * 0.2 + valuation_score * 0.2)
            scores[bidder.bidder_id] = score

        return scores

    def _detect_suspicious_patterns(self) -> List[str]:
        patterns = []

        if self.num_rounds >= 5:
            price_stability = self._check_price_stability()
            if price_stability > 0.8:
                patterns.append(f"价格异常稳定 (稳定性={price_stability:.2f})")

            jump_analysis = self._check_price_jumps()
            if jump_analysis > 0.7:
                patterns.append(f"异常价格跳升模式 (score={jump_analysis:.2f})")

            bid_withdrawal = self._check_bid_withdrawal()
            if bid_withdrawal > 0.6:
                patterns.append(f"频繁出价撤回 (score={bid_withdrawal:.2f})")

            low_competition = self._check_low_competition()
            if low_competition:
                patterns.append("多物品竞争不足，疑似市场分割")

        return patterns

    def _check_price_stability(self) -> float:
        if self.num_rounds < 3:
            return 0.0

        stable_rounds = 0
        for item in self.state.items:
            item_prices = []
            for round_info in self.state.round_history:
                price = round_info.prices.get(item.item_id, 0.0)
                if price > 0:
                    item_prices.append(price)

            if len(item_prices) >= 3:
                changes = np.diff(item_prices)
                mean_change = np.mean(np.abs(changes))
                if mean_change < self.state.bid_increment * 0.5:
                    stable_rounds += 1

        return stable_rounds / max(self.num_items, 1)

    def _check_price_jumps(self) -> float:
        if self.num_rounds < 4:
            return 0.0

        jump_count = 0
        check_rounds = 0

        for item in self.state.items:
            item_prices = []
            for round_info in self.state.round_history:
                price = round_info.prices.get(item.item_id, 0.0)
                if price > 0:
                    item_prices.append(price)

            if len(item_prices) >= 4:
                for k in range(2, len(item_prices)):
                    check_rounds += 1
                    prev_change = item_prices[k-1] - item_prices[k-2]
                    curr_change = item_prices[k] - item_prices[k-1]

                    if prev_change > 0 and curr_change > prev_change * 3:
                        jump_count += 1

        return jump_count / max(check_rounds, 1)

    def _check_bid_withdrawal(self) -> float:
        if self.num_rounds < 3:
            return 0.0

        withdrawal_count = 0
        total_bidder_rounds = 0

        for bidder in self.state.bidders:
            prev_bundle = set()
            for round_idx, round_info in enumerate(self.state.round_history):
                total_bidder_rounds += 1
                curr_bundle = set()
                for bid in round_info.bids:
                    if bid["bidder_id"] == bidder.bidder_id:
                        if bid.get("item_id"):
                            curr_bundle.add(bid["item_id"])
                        elif bid.get("bundle"):
                            curr_bundle.update([int(k) for k in bid["bundle"].keys()])

                if round_idx > 0 and prev_bundle and not curr_bundle:
                    withdrawal_count += 1
                prev_bundle = curr_bundle

        return withdrawal_count / max(total_bidder_rounds, 1)

    def _check_low_competition(self) -> bool:
        if self.num_items < 3 or self.num_bidders < 3:
            return False

        last_round = self.state.round_history[-1] if self.state.round_history else None
        if not last_round:
            return False

        items_per_bidder = defaultdict(int)
        for bid in last_round.bids:
            items_per_bidder[bid["bidder_id"]] += 1

        if max(items_per_bidder.values(), default=0) > self.num_items * 0.6:
            return True

        bidders_with_bids = len([b for b in items_per_bidder.values() if b > 0])
        if bidders_with_bids < self.num_bidders * 0.5:
            return True

        return False

    def _assess_overall_risk(self, hhi: float, risks: List[CollusionRisk],
                            patterns: List[str]) -> str:
        risk_points = 0

        if hhi >= 2500:
            risk_points += 2
        elif hhi >= 1500:
            risk_points += 1

        high_risks = sum(1 for r in risks if r.risk_level == "high")
        medium_risks = sum(1 for r in risks if r.risk_level == "medium")
        risk_points += high_risks * 2 + medium_risks

        risk_points += len(patterns)

        if risk_points >= 5:
            return "high"
        elif risk_points >= 2:
            return "medium"
        else:
            return "low"
