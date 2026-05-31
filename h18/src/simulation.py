import io
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import platform
from typing import List, Set, Dict, Tuple
from collections import Counter


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


def _check_convergence(spreads: List[int], threshold: float = 0.01, min_samples: int = 50) -> bool:
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


class ICMModel:
    def __init__(self, adj: Dict[int, List[Tuple[int, float]]], random_seed: int = 42):
        self.adj = adj
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def simulate(self, seeds: Set[int], vaccinated: Set[int] = None) -> int:
        if vaccinated is None:
            vaccinated = set()

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

        return len(infected)

    def simulate_detailed(self, seeds: Set[int], vaccinated: Set[int] = None) -> Tuple[List[int], List[int]]:
        if vaccinated is None:
            vaccinated = set()

        infected = set(seeds) - vaccinated
        active = set(infected)

        infection_counts = [len(infected)]
        new_infections = [len(active)]

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
            infection_counts.append(len(infected))
            new_infections.append(len(new_active))

        return infection_counts, new_infections

    def run_multiple_simulations(self, seeds: Set[int], vaccinated: Set[int] = None,
                                 num_simulations: int = 200, use_adaptive: bool = True,
                                 max_simulations: int = 500, convergence_threshold: float = 0.015) -> List[int]:
        results = []
        min_simulations = min(num_simulations, max_simulations)

        if use_adaptive:
            batch_size = 20
            while len(results) < max_simulations:
                for _ in range(batch_size):
                    results.append(self.simulate(seeds, vaccinated))

                if len(results) >= min_simulations and _check_convergence(
                        results, threshold=convergence_threshold, min_samples=min_simulations):
                    break
        else:
            for _ in range(num_simulations):
                results.append(self.simulate(seeds, vaccinated))

        return results


class CDFPlotter:
    @staticmethod
    def compute_cdf(data: List[int]) -> Tuple[List[int], List[float]]:
        if not data:
            return [], []

        sorted_data = sorted(data)
        n = len(sorted_data)
        cdf = []
        cumulative = 0

        unique_values = sorted(set(sorted_data))
        counter = Counter(sorted_data)

        for val in unique_values:
            cumulative += counter[val]
            cdf.append(cumulative / n)

        return unique_values, cdf

    @staticmethod
    def generate_cdf_plot(distributions: Dict[str, List[int]], title: str = "传播范围CDF对比") -> str:
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        markers = ['o', 's', '^', 'D', 'v', '*']

        for i, (label, data) in enumerate(distributions.items()):
            if len(data) == 0:
                continue
            x, y = CDFPlotter.compute_cdf(data)
            color = colors[i % len(colors)]
            marker = markers[i % len(markers)]
            ax.step(x, y, where='post', label=label, color=color, linewidth=2, marker=marker, markevery=5, markersize=4)

        ax.set_xlabel('最终感染节点数', fontsize=12)
        ax.set_ylabel('累积分布概率 (CDF)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(fontsize=10, loc='lower right')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_ylim([0, 1.05])

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return img_base64

    @staticmethod
    def generate_reduction_bar_chart(evaluations: Dict) -> str:
        fig, ax = plt.subplots(figsize=(10, 6))

        algorithms = list(evaluations.keys())
        reduction_ratios = [evaluations[algo]['reduction_ratio'] * 100 for algo in algorithms]

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        bars = ax.bar(algorithms, reduction_ratios, color=colors, edgecolor='black', linewidth=0.5)

        for bar, ratio in zip(bars, reduction_ratios):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                    f'{ratio:.1f}%',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_xlabel('算法', fontsize=12)
        ax.set_ylabel('感染节点减少比例 (%)', fontsize=12)
        ax.set_title('各算法免疫效果对比', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax.set_ylim([0, max(reduction_ratios) * 1.2 if reduction_ratios else 100])

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.xticks(rotation=15)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return img_base64


def compute_statistics(data: List[int]) -> Dict:
    if not data:
        return {}

    arr = np.array(data)
    return {
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std': float(np.std(arr)),
        'min': int(np.min(arr)),
        'max': int(np.max(arr)),
        'percentile_25': float(np.percentile(arr, 25)),
        'percentile_75': float(np.percentile(arr, 75))
    }
