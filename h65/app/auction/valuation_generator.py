import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from itertools import combinations
import random


class ValuationGenerator:
    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.RandomState(seed)

    def generate_valuations(
        self,
        num_items: int,
        num_bidders: int,
        valuation_model: str = "random",
        **params: Any
    ) -> List[Dict]:
        params = params or {}
        base_value_range = params.get("base_value_range", (50.0, 500.0))
        complementary_range = params.get("complementary_range", (0.1, 0.5))
        complementary_density = params.get("complementary_density", 0.3)
        substitute_range = params.get("substitute_range", (0.1, 0.3))
        substitute_density = params.get("substitute_density", 0.2)

        if valuation_model == "random":
            return self._random_valuations(
                num_items, num_bidders, base_value_range,
                complementary_range, complementary_density,
                substitute_range, substitute_density
            )
        elif valuation_model == "hierarchical":
            return self._hierarchical_valuations(
                num_items, num_bidders, **params
            )
        elif valuation_model == "regional":
                return self._regional_valuations(
                num_items, num_bidders, **params
            )
        elif valuation_model == "uniform":
            return self._uniform_valuations(
                num_items, num_bidders, base_value_range,
                complementary_range, complementary_density,
                substitute_range, substitute_density
            )
        else:
            raise ValueError(f"Unknown valuation model: {valuation_model}")

    def _random_valuations(
        self,
        num_items: int,
        num_bidders: int,
        base_value_range: Tuple[float, float],
        complementary_range: Tuple[float, float],
        complementary_density: float,
        substitute_range: Tuple[float, float] = (0.1, 0.3),
        substitute_density: float = 0.2
    ) -> List[Dict]:
        valuations = []
        for bidder_idx in range(num_bidders):
            bidder_val = {
                "base_values": {},
                "complementary_values": {},
                "substitute_values": {}
            }
            for item_idx in range(num_items):
                base_value = self.rng.uniform(*base_value_range)
                bidder_val["base_values"][item_idx] = round(base_value, 2)

            for i in range(num_items):
                for j in range(i + 1, num_items):
                    key = f"{i}_{j}"
                    v_i = bidder_val["base_values"][i]
                    v_j = bidder_val["base_values"][j]

                    if self.rng.random() < complementary_density:
                        alpha = self.rng.uniform(*complementary_range)
                        comp_value = alpha * min(v_i, v_j)
                        bidder_val["complementary_values"][key] = round(comp_value, 2)

                    if self.rng.random() < substitute_density:
                        beta = self.rng.uniform(*substitute_range)
                        sub_value = beta * min(v_i, v_j)
                        bidder_val["substitute_values"][key] = round(sub_value, 2)

            valuations.append(bidder_val)

        return valuations

    def _hierarchical_valuations(
        self,
        num_items: int,
        num_bidders: int,
        **params
    ) -> List[Dict]:
        high_value_range = params.get("high_value_range", (300.0, 600.0))
        medium_value_range = params.get("medium_value_range", (150.0, 300.0))
        low_value_range = params.get("low_value_range", (50.0, 150.0))
        complementary_strength = params.get("complementary_strength", 0.3)

        tiers = []
        for i in range(num_items):
            tier = self.rng.choice(["high", "medium", "low"], p=[0.2, 0.5, 0.3])
            tiers.append(tier)

        valuations = []
        for bidder_idx in range(num_bidders):
            bidder_val = {
                "base_values": {},
                "complementary_values": {}
            }

            preference = self.rng.choice(["high_pref", "balanced", "low_pref"])

            for item_idx in range(num_items):
                tier = tiers[item_idx]
                if tier == "high":
                    if preference == "high_pref":
                        base = self.rng.uniform(*high_value_range) * 1.2
                    elif preference == "balanced":
                        base = self.rng.uniform(*high_value_range)
                    else:
                        base = self.rng.uniform(*high_value_range) * 0.8
                elif tier == "medium":
                    base = self.rng.uniform(*medium_value_range)
                else:
                    if preference == "low_pref":
                        base = self.rng.uniform(*low_value_range) * 1.2
                    elif preference == "balanced":
                        base = self.rng.uniform(*low_value_range)
                    else:
                        base = self.rng.uniform(*low_value_range) * 0.8

                bidder_val["base_values"][item_idx] = round(base, 2)

            for i in range(num_items):
                for j in range(i + 1, num_items):
                    if tiers[i] == tiers[j] and tiers[i] == "high":
                        if self.rng.random() < 0.6:
                            v_i = bidder_val["base_values"][i]
                            v_j = bidder_val["base_values"][j]
                            comp_value = complementary_strength * min(v_i, v_j)
                            key = f"{i}_{j}"
                            bidder_val["complementary_values"][key] = round(comp_value, 2)

            valuations.append(bidder_val)

        return valuations

    def _regional_valuations(
        self,
        num_items: int,
        num_bidders: int,
        **params
    ) -> List[Dict]:
        regions = params.get("regions", None)
        if regions is None:
            num_regions = params.get("num_regions", 3)
            regions = {i: i % num_regions for i in range(num_items)}

        base_value_range = params.get("base_value_range", (100.0, 400.0))
        regional_comp = params.get("regional_complementary", 0.4)
        cross_region_penalty = params.get("cross_region_penalty", 0.2)

        valuations = []
        for bidder_idx in range(num_bidders):
            bidder_val = {
                "base_values": {},
                "complementary_values": {}
            }

            preferred_region = self.rng.randint(0, len(set(regions.values())))

            for item_idx in range(num_items):
                item_region = regions[item_idx]
                base = self.rng.uniform(*base_value_range)
                if item_region == preferred_region:
                    base *= 1.5
                else:
                    base *= (1 - cross_region_penalty)
                bidder_val["base_values"][item_idx] = round(base, 2)

            for i in range(num_items):
                for j in range(i + 1, num_items):
                    if regions[i] == regions[j]:
                        if self.rng.random() < 0.7:
                            v_i = bidder_val["base_values"][i]
                            v_j = bidder_val["base_values"][j]
                            comp_value = regional_comp * min(v_i, v_j)
                            key = f"{i}_{j}"
                            bidder_val["complementary_values"][key] = round(comp_value, 2)

            valuations.append(bidder_val)

        return valuations

    def _uniform_valuations(
        self,
        num_items: int,
        num_bidders: int,
        base_value_range: Tuple[float, float],
        complementary_range: Tuple[float, float],
        complementary_density: float,
        substitute_range: Tuple[float, float] = (0.1, 0.3),
        substitute_density: float = 0.2
    ) -> List[Dict]:
        valuations = []
        for bidder_idx in range(num_bidders):
            bidder_val = {
                "base_values": {},
                "complementary_values": {},
                "substitute_values": {}
            }

            base_mean = self.rng.uniform(*base_value_range)

            for item_idx in range(num_items):
                variance = self.rng.uniform(0.8, 1.2)
                base_value = base_mean * variance
                bidder_val["base_values"][item_idx] = round(base_value, 2)

            pairs = list(combinations(range(num_items), 2))
            num_comp = int(len(pairs) * complementary_density)
            num_sub = int(len(pairs) * substitute_density)
            selected_comp_pairs = self.rng.choice(len(pairs), size=num_comp, replace=False)
            available_sub = [i for i in range(len(pairs)) if i not in selected_comp_pairs]
            num_sub_actual = min(num_sub, len(available_sub))
            selected_sub_pairs = self.rng.choice(available_sub, size=num_sub_actual, replace=False) if available_sub else []

            for idx in selected_comp_pairs:
                i, j = pairs[idx]
                alpha = self.rng.uniform(*complementary_range)
                v_i = bidder_val["base_values"][i]
                v_j = bidder_val["base_values"][j]
                comp_value = alpha * min(v_i, v_j)
                key = f"{i}_{j}"
                bidder_val["complementary_values"][key] = round(comp_value, 2)

            for idx in selected_sub_pairs:
                i, j = pairs[idx]
                beta = self.rng.uniform(*substitute_range)
                v_i = bidder_val["base_values"][i]
                v_j = bidder_val["base_values"][j]
                sub_value = beta * min(v_i, v_j)
                key = f"{i}_{j}"
                bidder_val["substitute_values"][key] = round(sub_value, 2)

            valuations.append(bidder_val)

        return valuations

    def compute_bundle_value(
        self,
        bundle: List[int],
        base_values: Dict[int, float],
        complementary_values: Dict[str, float],
        substitute_values: Optional[Dict[str, float]] = None
    ) -> float:
        if not bundle:
            return 0.0

        substitute_values = substitute_values or {}
        total = sum(base_values.get(item_idx, 0.0) for item_idx in bundle)

        for i in range(len(bundle)):
            for j in range(i + 1, len(bundle)):
                key1 = f"{bundle[i]}_{bundle[j]}"
                key2 = f"{bundle[j]}_{bundle[i]}"
                total += complementary_values.get(key1, 0.0)
                total += complementary_values.get(key2, 0.0)
                total -= substitute_values.get(key1, 0.0)
                total -= substitute_values.get(key2, 0.0)

        return round(total, 2)

    def compute_marginal_value(
        self,
        item: int,
        current_bundle: List[int],
        base_values: Dict[int, float],
        complementary_values: Dict[str, float],
        substitute_values: Optional[Dict[str, float]] = None
    ) -> float:
        substitute_values = substitute_values or {}
        current_value = self.compute_bundle_value(current_bundle, base_values, complementary_values, substitute_values)
        new_bundle = current_bundle + [item]
        new_value = self.compute_bundle_value(new_bundle, base_values, complementary_values, substitute_values)
        return new_value - current_value


def create_items(num_items: int, seed: Optional[int] = None) -> List[Dict]:
    rng = random.Random(seed)
    items = []
    for i in range(num_items):
        bandwidth_options = [5, 10, 15, 20]
        freq_bands = [700, 800, 900, 1800, 2100, 2600, 3500]
        base_value = round(rng.uniform(50.0, 500.0), 2)
        reserve_price = round(base_value * rng.uniform(0.1, 0.3), 2)
        item = {
            "name": f"Block_{i+1}",
            "description": f"Spectrum block {i+1}",
            "bandwidth": rng.choice(bandwidth_options),
            "frequency_range": f"{rng.choice(freq_bands)} MHz",
            "base_value": base_value,
            "reserve_price": reserve_price
        }
        items.append(item)
    return items
