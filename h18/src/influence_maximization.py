import time
import heapq
import numpy as np
import networkx as nx
from typing import List, Set, Tuple, Dict, Callable
from collections import defaultdict


class InfluenceMaximization:
    def __init__(self, G: nx.Graph, random_seed: int = 42):
        self.G = G
        self.adj = self._build_adjacency()
        self.random_seed = random_seed
        np.random.seed(random_seed)

        n = G.number_of_nodes()
        self._pagerank_nstart = {node: 1.0 / n for node in G.nodes()}

    def _check_convergence(self, spreads: List[int], threshold: float = 0.01,
                           min_samples: int = 50) -> bool:
        if len(spreads) < min_samples:
            return False

        current_mean = np.mean(spreads)
        if current_mean == 0:
            return True

        half = len(spreads) // 2
        first_half_mean = np.mean(spreads[:half])
        second_half_mean = np.mean(spreads[half:])

        relative_diff = abs(first_half_mean - second_half_mean) / current_mean

        return relative_diff < threshold

    def _build_adjacency(self) -> Dict[int, List[Tuple[int, float]]]:
        adj = {}
        for node in self.G.nodes():
            neighbors = []
            for neighbor in self.G.neighbors(node):
                prob = self.G[node][neighbor].get('propagation_prob', 0.1)
                neighbors.append((neighbor, prob))
            adj[node] = neighbors
        return adj

    def _icm_spread(self, seeds: Set[int], vaccinated: Set[int] = None,
                    simulations: int = 20, use_adaptive: bool = False,
                    max_simulations: int = 200, convergence_threshold: float = 0.02) -> float:
        if vaccinated is None:
            vaccinated = set()

        spreads = []
        min_simulations = simulations

        if use_adaptive:
            batch_size = 20
            while len(spreads) < max_simulations:
                for _ in range(batch_size):
                    infected = set(seeds) - vaccinated
                    active = set(infected)

                    while active:
                        new_active = set()
                        for node in active:
                            for neighbor, prob in self.adj.get(node, []):
                                if neighbor in infected or neighbor in vaccinated:
                                    continue
                                if np.random.random() < prob:
                                    new_active.add(neighbor)
                        active = new_active
                        infected.update(new_active)

                    spreads.append(len(infected))

                if len(spreads) >= min_simulations and self._check_convergence(
                        spreads, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(simulations):
                infected = set(seeds) - vaccinated
                active = set(infected)

                while active:
                    new_active = set()
                    for node in active:
                        for neighbor, prob in self.adj.get(node, []):
                            if neighbor in infected or neighbor in vaccinated:
                                continue
                            if np.random.random() < prob:
                                new_active.add(neighbor)
                    active = new_active
                    infected.update(new_active)

                spreads.append(len(infected))

        return float(np.mean(spreads))

    def greedy(self, k: int, seeds: Set[int], exclude_nodes: Set[int] = None) -> Tuple[List[int], float]:
        if exclude_nodes is None:
            exclude_nodes = set()

        start_time = time.time()
        selected = []
        candidate_nodes = [n for n in self.G.nodes() if n not in exclude_nodes]

        current_spread = self._icm_spread(seeds, set())

        for _ in range(min(k, len(candidate_nodes))):
            best_node = None
            best_reduction = -1

            for node in candidate_nodes:
                if node in selected or node in exclude_nodes:
                    continue

                test_vaccinated = set(selected + [node])
                new_spread = self._icm_spread(seeds, test_vaccinated)
                reduction = current_spread - new_spread

                if reduction > best_reduction:
                    best_reduction = reduction
                    best_node = node

            if best_node is None:
                break

            selected.append(best_node)
            current_spread -= best_reduction

        runtime = time.time() - start_time
        return selected, runtime

    def celf(self, k: int, seeds: Set[int], exclude_nodes: Set[int] = None) -> Tuple[List[int], float]:
        if exclude_nodes is None:
            exclude_nodes = set()

        start_time = time.time()
        selected = []
        candidate_nodes = [n for n in self.G.nodes() if n not in exclude_nodes]

        base_spread = self._icm_spread(seeds, set())

        heap = []
        for node in candidate_nodes:
            if node in exclude_nodes:
                continue
            spread_with = self._icm_spread(seeds, {node})
            marginal_gain = base_spread - spread_with
            heapq.heappush(heap, (-marginal_gain, node, 0))

        while len(selected) < k and heap:
            neg_gain, node, iteration = heapq.heappop(heap)

            if iteration == len(selected):
                selected.append(node)
                continue

            test_vaccinated = set(selected + [node])
            current_spread = self._icm_spread(seeds, set(selected))
            new_spread = self._icm_spread(seeds, test_vaccinated)
            marginal_gain = current_spread - new_spread

            heapq.heappush(heap, (-marginal_gain, node, len(selected)))

        runtime = time.time() - start_time
        return selected, runtime

    def pagerank(self, k: int, exclude_nodes: Set[int] = None) -> Tuple[List[int], float]:
        if exclude_nodes is None:
            exclude_nodes = set()

        start_time = time.time()

        pr = nx.pagerank(
            self.G, alpha=0.85, weight='weight',
            nstart=self._pagerank_nstart, max_iter=500
        )

        sorted_nodes = sorted(
            pr.items(),
            key=lambda x: (-round(x[1], 10), x[0])
        )

        selected = []
        for node, _ in sorted_nodes:
            if node not in exclude_nodes:
                selected.append(node)
                if len(selected) >= k:
                    break

        runtime = time.time() - start_time
        return selected, runtime

    def degree_centrality(self, k: int, exclude_nodes: Set[int] = None) -> Tuple[List[int], float]:
        if exclude_nodes is None:
            exclude_nodes = set()

        start_time = time.time()

        degree_cent = nx.degree_centrality(self.G)

        sorted_nodes = sorted(
            degree_cent.items(),
            key=lambda x: (-round(x[1], 10), x[0])
        )

        selected = []
        for node, _ in sorted_nodes:
            if node not in exclude_nodes:
                selected.append(node)
                if len(selected) >= k:
                    break

        runtime = time.time() - start_time
        return selected, runtime

    def k_core(self, k: int, exclude_nodes: Set[int] = None) -> Tuple[List[int], float]:
        if exclude_nodes is None:
            exclude_nodes = set()

        start_time = time.time()

        core_numbers = nx.core_number(self.G)

        sorted_nodes = sorted(
            core_numbers.items(),
            key=lambda x: (-x[1], x[0])
        )

        selected = []
        for node, _ in sorted_nodes:
            if node not in exclude_nodes:
                selected.append(node)
                if len(selected) >= k:
                    break

        runtime = time.time() - start_time
        return selected, runtime

    def run_all_algorithms(self, k: int, seeds: Set[int], exclude_nodes: Set[int] = None) -> Dict:
        if exclude_nodes is None:
            exclude_nodes = set(seeds)
        else:
            exclude_nodes = exclude_nodes | set(seeds)

        results = {}

        print("Running PageRank...")
        pr_selected, pr_time = self.pagerank(k, exclude_nodes)
        results['pagerank'] = {'nodes': pr_selected, 'time': pr_time}

        print("Running Degree Centrality...")
        deg_selected, deg_time = self.degree_centrality(k, exclude_nodes)
        results['degree_centrality'] = {'nodes': deg_selected, 'time': deg_time}

        print("Running K-core...")
        kcore_selected, kcore_time = self.k_core(k, exclude_nodes)
        results['k_core'] = {'nodes': kcore_selected, 'time': kcore_time}

        print("Running Greedy...")
        greedy_selected, greedy_time = self.greedy(k, seeds, exclude_nodes)
        results['greedy'] = {'nodes': greedy_selected, 'time': greedy_time}

        print("Running CELF...")
        celf_selected, celf_time = self.celf(k, seeds, exclude_nodes)
        results['celf'] = {'nodes': celf_selected, 'time': celf_time}

        return results

    def evaluate_strategies(self, results: Dict, seeds: Set[int], simulations: int = 50) -> Dict:
        base_spread = self._icm_spread(seeds, simulations=simulations)

        evaluation = {}
        for algo_name, algo_data in results.items():
            vaccinated = set(algo_data['nodes'])
            protected_spread = self._icm_spread(seeds, vaccinated, simulations=simulations)
            reduction = base_spread - protected_spread
            reduction_ratio = reduction / base_spread if base_spread > 0 else 0

            evaluation[algo_name] = {
                'base_spread': base_spread,
                'protected_spread': protected_spread,
                'reduction': reduction,
                'reduction_ratio': reduction_ratio
            }

        return evaluation

    def get_spread_distribution(self, seeds: Set[int], vaccinated: Set[int] = None,
                                simulations: int = 200, use_adaptive: bool = True,
                                max_simulations: int = 500, convergence_threshold: float = 0.015) -> List[int]:
        if vaccinated is None:
            vaccinated = set()

        spreads = []
        min_simulations = min(simulations, max_simulations)

        if use_adaptive:
            batch_size = 20
            while len(spreads) < max_simulations:
                for _ in range(batch_size):
                    infected = set(seeds) - vaccinated
                    active = set(infected)

                    while active:
                        new_active = set()
                        for node in active:
                            for neighbor, prob in self.adj.get(node, []):
                                if neighbor in infected or neighbor in vaccinated:
                                    continue
                                if np.random.random() < prob:
                                    new_active.add(neighbor)
                        active = new_active
                        infected.update(new_active)

                    spreads.append(len(infected))

                if len(spreads) >= min_simulations and self._check_convergence(
                        spreads, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(simulations):
                infected = set(seeds) - vaccinated
                active = set(infected)

                while active:
                    new_active = set()
                    for node in active:
                        for neighbor, prob in self.adj.get(node, []):
                            if neighbor in infected or neighbor in vaccinated:
                                continue
                            if np.random.random() < prob:
                                new_active.add(neighbor)
                    active = new_active
                    infected.update(new_active)

                spreads.append(len(infected))

        return spreads
