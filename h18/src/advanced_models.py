import io
import base64
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import platform
from typing import List, Set, Dict, Tuple, Optional, Callable
from collections import defaultdict, Counter
from copy import deepcopy


def _setup_chinese_font():
    system = platform.system()
    font_names = []

    if system == 'Windows':
        font_names = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong']
    elif system == 'Darwin':
        font_names = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
    else:
        font_names = ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 'SimHei']

    for font_name in font_names:
        try:
            font_path = font_manager.findfont(font_name, fallback_to_default=False)
            if font_path:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                return
        except Exception:
            continue

    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


_setup_chinese_font()


def _check_convergence(spreads: List[int], threshold: float = 0.015, min_samples: int = 100) -> bool:
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


class TimeSensitiveICM:
    def __init__(self, adj: Dict[int, List[Tuple[int, float]]],
                 decay_rate: float = 0.1,
                 recovery_rate: float = 0.05,
                 memory_decay: float = 0.02,
                 random_seed: int = 42):
        self.adj = adj
        self.decay_rate = decay_rate
        self.recovery_rate = recovery_rate
        self.memory_decay = memory_decay
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def _memory_factor(self, time_infected: int) -> float:
        return np.exp(-self.memory_decay * time_infected)

    def simulate(self, seeds: Set[int], vaccinated: Set[int] = None,
                 max_time_steps: int = 50) -> Dict:
        if vaccinated is None:
            vaccinated = set()

        all_nodes = set(self.adj.keys())
        infected = {node: 0 for node in (seeds - vaccinated)}
        recovered = set()
        active = set(infected.keys())

        infection_history = [len(infected)]
        recovered_history = [0]
        new_infections = [len(active)]
        infected_nodes_detail = {node: 0 for node in infected}

        for t in range(1, max_time_steps + 1):
            new_active = set()

            for node in active:
                if node in recovered or node in vaccinated:
                    continue

                for neighbor, base_prob in self.adj.get(node, []):
                    if neighbor in infected or neighbor in recovered or neighbor in vaccinated:
                        continue

                    memory_factor = self._memory_factor(infected[node])
                    time_decay = np.exp(-self.decay_rate * t)
                    effective_prob = base_prob * memory_factor * time_decay

                    if np.random.random() < effective_prob:
                        new_active.add(neighbor)
                        infected_nodes_detail[neighbor] = t

            for node in list(infected.keys()):
                if np.random.random() < self.recovery_rate:
                    recovered.add(node)
                    if node in active:
                        active.remove(node)

            for node in new_active:
                infected[node] = t

            active = new_active - recovered
            infection_history.append(len(infected) - len(recovered))
            recovered_history.append(len(recovered))
            new_infections.append(len(new_active))

            if not active and not new_active:
                break

        total_infected = len(infected)
        return {
            'total_infected': total_infected,
            'final_active': len(infected) - len(recovered),
            'total_recovered': len(recovered),
            'infection_history': infection_history,
            'recovered_history': recovered_history,
            'new_infections': new_infections,
            'infection_times': infected_nodes_detail,
            'time_steps': len(infection_history) - 1
        }

    def run_multiple_simulations(self, seeds: Set[int], vaccinated: Set[int] = None,
                                 num_simulations: int = 100, use_adaptive: bool = True,
                                 max_simulations: int = 500, max_time_steps: int = 50,
                                 convergence_threshold: float = 0.015) -> Dict:
        results = []
        min_simulations = min(num_simulations, max_simulations)

        if use_adaptive:
            batch_size = 20
            while len(results) < max_simulations:
                for _ in range(batch_size):
                    sim_result = self.simulate(seeds, vaccinated, max_time_steps)
                    results.append(sim_result)

                spreads = [r['total_infected'] for r in results]
                if len(results) >= min_simulations and _check_convergence(
                        spreads, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(num_simulations):
                sim_result = self.simulate(seeds, vaccinated, max_time_steps)
                results.append(sim_result)

        spreads = [r['total_infected'] for r in results]
        active_counts = [r['final_active'] for r in results]
        recovered_counts = [r['total_recovered'] for r in results]

        max_len = max(len(r['infection_history']) for r in results)
        avg_infection_curve = np.zeros(max_len)
        avg_recovered_curve = np.zeros(max_len)

        for r in results:
            hist = r['infection_history']
            rec = r['recovered_history']
            for i in range(len(hist)):
                avg_infection_curve[i] += hist[i]
            for i in range(len(rec)):
                avg_recovered_curve[i] += rec[i]

        avg_infection_curve /= len(results)
        avg_recovered_curve /= len(results)

        return {
            'results': results,
            'total_infected_distribution': spreads,
            'final_active_distribution': active_counts,
            'total_recovered_distribution': recovered_counts,
            'avg_infection_curve': avg_infection_curve.tolist(),
            'avg_recovered_curve': avg_recovered_curve.tolist(),
            'actual_simulations': len(results),
            'mean_total_infected': float(np.mean(spreads)),
            'std_total_infected': float(np.std(spreads))
        }


class MultiRumorModel:
    def __init__(self, adj: Dict[int, List[Tuple[int, float]]],
                 rumor_configs: Dict[str, Dict],
                 competition_matrix: Optional[Dict[Tuple[str, str], float]] = None,
                 enhancement_matrix: Optional[Dict[Tuple[str, str], float]] = None,
                 random_seed: int = 42):
        self.adj = adj
        self.rumor_configs = rumor_configs
        self.competition_matrix = competition_matrix or {}
        self.enhancement_matrix = enhancement_matrix or {}
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def simulate(self, seeds_by_rumor: Dict[str, Set[int]],
                 vaccinated: Set[int] = None,
                 max_time_steps: int = 50) -> Dict:
        if vaccinated is None:
            vaccinated = set()

        rumor_names = list(self.rumor_configs.keys())

        infected_by_rumor = {rumor: {} for rumor in rumor_names}
        recovered_by_rumor = {rumor: set() for rumor in rumor_names}
        active_by_rumor = {rumor: set() for rumor in rumor_names}

        for rumor in rumor_names:
            seeds = seeds_by_rumor.get(rumor, set()) - vaccinated
            for node in seeds:
                infected_by_rumor[rumor][node] = 0
                active_by_rumor[rumor].add(node)

        coinfected = defaultdict(set)

        infection_history = {rumor: [len(infected_by_rumor[rumor])] for rumor in rumor_names}
        recovered_history = {rumor: [0] for rumor in rumor_names}
        coinfection_history = [0]

        for t in range(1, max_time_steps + 1):
            new_active_by_rumor = {rumor: set() for rumor in rumor_names}
            new_coinfections = set()

            for rumor in rumor_names:
                config = self.rumor_configs[rumor]
                base_prob = config.get('base_prob', 0.5)
                recovery_rate = config.get('recovery_rate', 0.05)
                decay_rate = config.get('decay_rate', 0.0)
                memory_decay = config.get('memory_decay', 0.0)

                for node in active_by_rumor[rumor]:
                    if node in vaccinated:
                        continue

                    for neighbor, edge_weight in self.adj.get(node, []):
                        if neighbor in vaccinated:
                            continue

                        competition_factor = 1.0
                        for other_rumor in rumor_names:
                            if other_rumor == rumor:
                                continue
                            if neighbor in infected_by_rumor[other_rumor]:
                                key = (rumor, other_rumor)
                                competition_factor *= self.competition_matrix.get(key, 1.0)

                        enhancement_factor = 1.0
                        for other_rumor in rumor_names:
                            if other_rumor == rumor:
                                continue
                            if node in infected_by_rumor[other_rumor]:
                                key = (rumor, other_rumor)
                                enhancement_factor *= self.enhancement_matrix.get(key, 1.0)

                        time_infected = infected_by_rumor[rumor].get(node, 0)
                        memory_factor = np.exp(-memory_decay * time_infected)
                        time_decay = np.exp(-decay_rate * t)

                        effective_prob = base_prob * edge_weight * memory_factor * time_decay * competition_factor * enhancement_factor

                        already_infected = any(neighbor in infected_by_rumor[r] for r in rumor_names)

                        if np.random.random() < effective_prob:
                            if neighbor not in infected_by_rumor[rumor]:
                                new_active_by_rumor[rumor].add(neighbor)
                                infected_by_rumor[rumor][neighbor] = t

                                for other_rumor in rumor_names:
                                    if other_rumor != rumor and neighbor in infected_by_rumor[other_rumor]:
                                        new_coinfections.add(neighbor)
                                        coinfected[neighbor].add(rumor)
                                        coinfected[neighbor].add(other_rumor)

                for node in list(infected_by_rumor[rumor].keys()):
                    if np.random.random() < recovery_rate and node not in recovered_by_rumor[rumor]:
                        recovered_by_rumor[rumor].add(node)
                        if node in active_by_rumor[rumor]:
                            active_by_rumor[rumor].remove(node)

            for rumor in rumor_names:
                active_by_rumor[rumor] = new_active_by_rumor[rumor] - recovered_by_rumor[rumor]
                infection_history[rumor].append(
                    len(infected_by_rumor[rumor]) - len(recovered_by_rumor[rumor]))
                recovered_history[rumor].append(len(recovered_by_rumor[rumor]))

            coinfection_history.append(len(coinfected))

            all_active = set()
            for rumor in rumor_names:
                all_active.update(active_by_rumor[rumor])
            if not all_active:
                break

        result = {
            'infection_by_rumor': {r: len(infected_by_rumor[r]) for r in rumor_names},
            'recovered_by_rumor': {r: len(recovered_by_rumor[r]) for r in rumor_names},
            'coinfection_count': len(coinfected),
            'coinfection_pairs': {node: list(r) for node, r in coinfected.items() if len(r) >= 2},
            'infection_history': infection_history,
            'recovered_history': recovered_history,
            'coinfection_history': coinfection_history,
            'time_steps': len(coinfection_history) - 1
        }

        return result

    def run_multiple_simulations(self, seeds_by_rumor: Dict[str, Set[int]],
                                 vaccinated: Set[int] = None,
                                 num_simulations: int = 100, use_adaptive: bool = True,
                                 max_simulations: int = 500, max_time_steps: int = 50,
                                 convergence_threshold: float = 0.015) -> Dict:
        results = []
        rumor_names = list(self.rumor_configs.keys())
        min_simulations = min(num_simulations, max_simulations)

        if use_adaptive:
            batch_size = 20
            while len(results) < max_simulations:
                for _ in range(batch_size):
                    results.append(self.simulate(seeds_by_rumor, vaccinated, max_time_steps))

                total_spreads = [sum(r['infection_by_rumor'].values()) for r in results]
                if len(results) >= min_simulations and _check_convergence(
                        total_spreads, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(num_simulations):
                results.append(self.simulate(seeds_by_rumor, vaccinated, max_time_steps))

        summary = {
            'results': results,
            'actual_simulations': len(results),
            'infection_by_rumor_mean': {},
            'infection_by_rumor_std': {},
            'coinfection_mean': float(np.mean([r['coinfection_count'] for r in results])),
            'coinfection_std': float(np.std([r['coinfection_count'] for r in results]))
        }

        for rumor in rumor_names:
            vals = [r['infection_by_rumor'][rumor] for r in results]
            summary['infection_by_rumor_mean'][rumor] = float(np.mean(vals))
            summary['infection_by_rumor_std'][rumor] = float(np.std(vals))

        max_len = max(len(r['coinfection_history']) for r in results)
        avg_coinfection_curve = np.zeros(max_len)
        avg_infection_curves = {r: np.zeros(max_len) for r in rumor_names}

        for res in results:
            for i, v in enumerate(res['coinfection_history']):
                avg_coinfection_curve[i] += v
            for rumor in rumor_names:
                for i, v in enumerate(res['infection_history'][rumor]):
                    avg_infection_curves[rumor][i] += v

        avg_coinfection_curve /= len(results)
        for rumor in rumor_names:
            avg_infection_curves[rumor] /= len(results)
            summary[f'avg_infection_curve_{rumor}'] = avg_infection_curves[rumor].tolist()

        summary['avg_coinfection_curve'] = avg_coinfection_curve.tolist()

        return summary


class DynamicGraphICM:
    def __init__(self, static_adj: Dict[int, List[Tuple[int, float]]],
                 edge_changes: Optional[Dict[int, List[Tuple[str, int, int, float]]]] = None,
                 node_changes: Optional[Dict[int, List[Tuple[str, int]]]] = None,
                 random_seed: int = 42):
        self.static_adj = deepcopy(static_adj)
        self.edge_changes = edge_changes or {}
        self.node_changes = node_changes or {}
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def _get_adj_at_time(self, t: int) -> Dict[int, List[Tuple[int, float]]]:
        adj = deepcopy(self.static_adj)
        active_nodes = set(adj.keys())

        for time, changes in sorted(self.node_changes.items()):
            if time > t:
                break
            for change_type, node in changes:
                if change_type == 'add' and node not in adj:
                    adj[node] = []
                    active_nodes.add(node)
                elif change_type == 'remove' and node in adj:
                    del adj[node]
                    active_nodes.discard(node)
                    for n in adj:
                        adj[n] = [(nb, p) for nb, p in adj[n] if nb != node]

        for time, changes in sorted(self.edge_changes.items()):
            if time > t:
                break
            for change_type, u, v, prob in changes:
                if change_type == 'add':
                    if u in adj and v in adj:
                        if not any(nb == v for nb, _ in adj[u]):
                            adj[u].append((v, prob))
                        if not any(nb == u for nb, _ in adj[v]):
                            adj[v].append((u, prob))
                elif change_type == 'remove':
                    if u in adj:
                        adj[u] = [(nb, p) for nb, p in adj[u] if nb != v]
                    if v in adj:
                        adj[v] = [(nb, p) for nb, p in adj[v] if nb != u]

        return adj

    def simulate(self, seeds: Set[int], vaccinated: Set[int] = None,
                 max_time_steps: int = 50) -> Dict:
        if vaccinated is None:
            vaccinated = set()

        current_adj = self._get_adj_at_time(0)
        all_nodes = set(current_adj.keys())

        infected = {}
        for node in (seeds & all_nodes) - vaccinated:
            infected[node] = 0
        active = set(infected.keys())
        spread_finished = False

        infection_history = [len(infected)]
        new_infections = [len(active)]
        edge_count_history = [sum(len(v) for v in current_adj.values()) // 2]
        node_count_history = [len(current_adj)]

        for t in range(1, max_time_steps + 1):
            current_adj = self._get_adj_at_time(t)
            active_nodes = set(current_adj.keys())

            if not spread_finished:
                new_active = set()

                for node in active:
                    if node in vaccinated or node not in active_nodes:
                        continue

                    for neighbor, prob in current_adj.get(node, []):
                        if neighbor in infected or neighbor in vaccinated or neighbor not in active_nodes:
                            continue
                        if np.random.random() < prob:
                            new_active.add(neighbor)
                            infected[neighbor] = t

                active = new_active - vaccinated
                infected = {k: v for k, v in infected.items() if k in active_nodes}

                if not active:
                    spread_finished = True

                infection_history.append(len(infected))
                new_infections.append(len(new_active))
            else:
                infected = {k: v for k, v in infected.items() if k in active_nodes}
                infection_history.append(len(infected))
                new_infections.append(0)

            edge_count_history.append(sum(len(v) for v in current_adj.values()) // 2)
            node_count_history.append(len(current_adj))

        return {
            'total_infected': len(infected),
            'infection_history': infection_history,
            'new_infections': new_infections,
            'edge_count_history': edge_count_history,
            'node_count_history': node_count_history,
            'time_steps': max_time_steps
        }

    def run_multiple_simulations(self, seeds: Set[int], vaccinated: Set[int] = None,
                                 num_simulations: int = 100, use_adaptive: bool = True,
                                 max_simulations: int = 500, max_time_steps: int = 50,
                                 convergence_threshold: float = 0.015) -> Dict:
        results = []
        min_simulations = min(num_simulations, max_simulations)

        if use_adaptive:
            batch_size = 20
            while len(results) < max_simulations:
                for _ in range(batch_size):
                    results.append(self.simulate(seeds, vaccinated, max_time_steps))

                spreads = [r['total_infected'] for r in results]
                if len(results) >= min_simulations and _check_convergence(
                        spreads, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(num_simulations):
                results.append(self.simulate(seeds, vaccinated, max_time_steps))

        spreads = [r['total_infected'] for r in results]

        max_len = max(len(r['infection_history']) for r in results)
        avg_infection_curve = np.zeros(max_len)
        avg_edge_curve = np.zeros(max_len)
        avg_node_curve = np.zeros(max_len)

        for r in results:
            for i in range(len(r['infection_history'])):
                avg_infection_curve[i] += r['infection_history'][i]
            for i in range(len(r['edge_count_history'])):
                avg_edge_curve[i] += r['edge_count_history'][i]
            for i in range(len(r['node_count_history'])):
                avg_node_curve[i] += r['node_count_history'][i]

        avg_infection_curve /= len(results)
        avg_edge_curve /= len(results)
        avg_node_curve /= len(results)

        return {
            'results': results,
            'total_infected_distribution': spreads,
            'avg_infection_curve': avg_infection_curve.tolist(),
            'avg_edge_curve': avg_edge_curve.tolist(),
            'avg_node_curve': avg_node_curve.tolist(),
            'actual_simulations': len(results),
            'mean_total_infected': float(np.mean(spreads)),
            'std_total_infected': float(np.std(spreads))
        }


class AdvancedPlotter:
    @staticmethod
    def plot_time_sensitive_curves(result: Dict, title: str = "时间敏感传播动态") -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        infection_curve = result['avg_infection_curve']
        recovered_curve = result['avg_recovered_curve']
        time_steps = list(range(len(infection_curve)))

        ax1.plot(time_steps, infection_curve, label='活跃感染', color='#d62728', linewidth=2)
        ax1.plot(time_steps, recovered_curve, label='已康复', color='#2ca02c', linewidth=2)
        ax1.fill_between(time_steps, infection_curve, alpha=0.2, color='#d62728')
        ax1.fill_between(time_steps, recovered_curve, alpha=0.2, color='#2ca02c')
        ax1.set_xlabel('时间步', fontsize=12)
        ax1.set_ylabel('节点数', fontsize=12)
        ax1.set_title('感染与康复动态', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        spreads = result['total_infected_distribution']
        sorted_data = sorted(spreads)
        n = len(sorted_data)
        cdf = []
        cumulative = 0
        counter = Counter(sorted_data)
        for val in sorted(set(sorted_data)):
            cumulative += counter[val]
            cdf.append(cumulative / n)
        ax2.step(sorted(set(sorted_data)), cdf, where='post', color='#1f77b4', linewidth=2)
        ax2.set_xlabel('最终总感染节点数', fontsize=12)
        ax2.set_ylabel('累积分布概率 (CDF)', fontsize=12)
        ax2.set_title('总感染数分布', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    @staticmethod
    def plot_multi_rumor_curves(summary: Dict, rumor_names: List[str],
                                title: str = "多谣言传播对比") -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, rumor in enumerate(rumor_names):
            curve = summary[f'avg_infection_curve_{rumor}']
            time_steps = list(range(len(curve)))
            ax1.plot(time_steps, curve, label=f'谣言 {rumor}',
                     color=colors[i % len(colors)], linewidth=2)

        coinfection_curve = summary['avg_coinfection_curve']
        time_steps = list(range(len(coinfection_curve)))
        ax1.plot(time_steps, coinfection_curve, label='交叉感染',
                 color='black', linewidth=2, linestyle='--')

        ax1.set_xlabel('时间步', fontsize=12)
        ax1.set_ylabel('活跃感染节点数', fontsize=12)
        ax1.set_title('各谣言传播动态', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        means = [summary['infection_by_rumor_mean'][r] for r in rumor_names]
        stds = [summary['infection_by_rumor_std'][r] for r in rumor_names]
        x_pos = np.arange(len(rumor_names))

        bars = ax2.bar(x_pos, means, yerr=stds, capsize=5,
                       color=[colors[i % len(colors)] for i in range(len(rumor_names))],
                       edgecolor='black', linewidth=0.5)

        for bar, mean in zip(bars, means):
            ax2.text(bar.get_x() + bar.get_width() / 2., mean + max(stds) * 0.1,
                     f'{mean:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax2.set_xlabel('谣言', fontsize=12)
        ax2.set_ylabel('平均总感染节点数', fontsize=12)
        ax2.set_title('各谣言最终影响', fontsize=14, fontweight='bold')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(rumor_names)
        ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    @staticmethod
    def plot_dynamic_graph_curves(summary: Dict, title: str = "动态图传播模拟") -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        infection_curve = summary['avg_infection_curve']
        edge_curve = summary['avg_edge_curve']
        node_curve = summary['avg_node_curve']
        time_steps = list(range(len(infection_curve)))

        ax1.plot(time_steps, infection_curve, label='活跃感染', color='#d62728', linewidth=2)
        ax1.fill_between(time_steps, infection_curve, alpha=0.2, color='#d62728')
        ax1.set_xlabel('时间步', fontsize=12)
        ax1.set_ylabel('活跃感染节点数', fontsize=12)
        ax1.set_title('传播动态', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        ax2_twin = ax2.twinx()
        line1 = ax2.plot(time_steps, node_curve, label='节点数', color='#1f77b4', linewidth=2, marker='o', markevery=5)
        line2 = ax2_twin.plot(time_steps, edge_curve, label='边数', color='#ff7f0e', linewidth=2, marker='s', markevery=5)

        ax2.set_xlabel('时间步', fontsize=12)
        ax2.set_ylabel('节点数', fontsize=12, color='#1f77b4')
        ax2_twin.set_ylabel('边数', fontsize=12, color='#ff7f0e')
        ax2.set_title('网络结构变化', fontsize=14, fontweight='bold')

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax2.legend(lines, labels, fontsize=10, loc='upper left')

        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.spines['top'].set_visible(False)
        ax2_twin.spines['top'].set_visible(False)

        plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
