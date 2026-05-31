import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from typing import Dict, List, Optional, Any
from io import BytesIO
import base64
import os

from app.auction.bidder import AuctionState
from app.auction.result_analyzer import ResultAnalyzer


class AuctionVisualizer:
    def __init__(self, auction_state: AuctionState, output_dir: str = "static"):
        self.state = auction_state
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.colors = plt.cm.Set3(np.linspace(0, 1, max(10, len(auction_state.items))))

    def generate_all_plots(self, save_to_disk: bool = True) -> Dict[str, str]:
        plots = {}

        plots["price_path"] = self.plot_price_path(save_to_disk)
        plots["excess_demand"] = self.plot_excess_demand(save_to_disk)
        plots["allocation"] = self.plot_final_allocation(save_to_disk)
        plots["revenue_efficiency"] = self.plot_revenue_efficiency(save_to_disk)
        plots["bidder_utility"] = self.plot_bidder_utility(save_to_disk)
        plots["bids_per_round"] = self.plot_bids_per_round(save_to_disk)
        plots["price_convergence"] = self.plot_price_convergence(save_to_disk)

        return plots

    def plot_price_path(self, save_to_disk: bool = True) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        item_ids = self.state.get_all_item_ids()
        rounds = list(range(1, len(self.state.round_history) + 1))

        for idx, item_id in enumerate(item_ids):
            prices = []
            for round_record in self.state.round_history:
                price = round_record.prices.get(item_id, 0)
                prices.append(price)

            item = self.state.get_item(item_id)
            label = item.name if item else f"Item {item_id}"
            ax.plot(rounds, prices, marker='o', linewidth=2, markersize=4,
                    label=label, color=self.colors[idx % len(self.colors)])

        ax.set_xlabel('Round')
        ax.set_ylabel('Price')
        ax.set_title(f'Price Evolution - {self.state.auction_type.upper()} Auction')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)

        if self.state.round_history:
            for round_record in self.state.round_history:
                if round_record.phase == "supplementary":
                    ax.axvline(x=round_record.round_number, color='r', linestyle='--', alpha=0.3)
                    break

        plt.tight_layout()
        return self._save_plot(fig, "price_path.png", save_to_disk)

    def plot_excess_demand(self, save_to_disk: bool = True) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        item_ids = self.state.get_all_item_ids()
        rounds = list(range(1, len(self.state.round_history) + 1))

        for idx, item_id in enumerate(item_ids):
            demands = []
            for round_record in self.state.round_history:
                demand = round_record.excess_demand.get(item_id, 0)
                demands.append(demand)

            item = self.state.get_item(item_id)
            label = item.name if item else f"Item {item_id}"
            ax.plot(rounds, demands, marker='s', linewidth=2, markersize=4,
                    label=label, color=self.colors[idx % len(self.colors)])

        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_xlabel('Round')
        ax.set_ylabel('Excess Demand')
        ax.set_title('Excess Demand Over Time')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return self._save_plot(fig, "excess_demand.png", save_to_disk)

    def plot_final_allocation(self, save_to_disk: bool = True) -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        analyzer = ResultAnalyzer(self.state)
        metrics = analyzer.compute_all_metrics()

        allocation = metrics["allocation_metrics"]["final_allocation"]

        bidder_names = []
        item_counts = []
        for bidder_id, items in allocation.items():
            bidder = self.state.get_bidder(bidder_id)
            name = bidder.name if bidder else f"Bidder {bidder_id}"
            bidder_names.append(name)
            item_counts.append(len(items))

        unallocated = metrics["allocation_metrics"]["num_unallocated_items"]
        if unallocated > 0:
            bidder_names.append("Unallocated")
            item_counts.append(unallocated)

        colors = plt.cm.Pastel1(np.linspace(0, 1, len(bidder_names)))
        ax1.pie(item_counts, labels=bidder_names, autopct='%1.1f%%',
                colors=colors, startangle=90)
        ax1.set_title('Item Allocation Distribution')

        final_prices = metrics["price_metrics"]["final_prices"]
        item_ids = self.state.get_all_item_ids()
        price_values = [final_prices.get(item_id, 0) for item_id in item_ids]

        item_names = []
        for item_id in item_ids:
            item = self.state.get_item(item_id)
            item_names.append(item.name if item else f"Item {item_id}")

        bars = ax2.bar(item_names, price_values, color=self.colors[:len(item_names)])
        ax2.set_xlabel('Items')
        ax2.set_ylabel('Final Price')
        ax2.set_title('Final Prices by Item')
        ax2.tick_params(axis='x', rotation=45)

        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                     f'{height:.1f}', ha='center', va='bottom')

        plt.tight_layout()
        return self._save_plot(fig, "allocation.png", save_to_disk)

    def plot_revenue_efficiency(self, save_to_disk: bool = True) -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        analyzer = ResultAnalyzer(self.state)
        metrics = analyzer.compute_all_metrics()

        revenue_metrics = metrics["revenue_metrics"]
        total_revenue = revenue_metrics["total_revenue"]
        total_reserve = revenue_metrics["total_reserve"]

        labels = ['Reserve Price', 'Final Revenue']
        values = [total_reserve, total_revenue]
        colors = ['#FF9999', '#66B2FF']

        bars = ax1.bar(labels, values, color=colors)
        ax1.set_ylabel('Amount')
        ax1.set_title('Revenue vs Reserve Price')

        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                     f'{height:.1f}', ha='center', va='bottom')

        efficiency_metrics = metrics["efficiency_metrics"]
        optimal = efficiency_metrics["optimal_social_welfare"]
        actual = efficiency_metrics["actual_social_welfare"]
        efficiency = efficiency_metrics["efficiency_percentage"]

        labels = ['Optimal Welfare', 'Actual Welfare']
        values = [optimal, actual]
        colors = ['#99FF99', '#FFCC99']

        bars = ax2.bar(labels, values, color=colors)
        ax2.set_ylabel('Social Welfare')
        ax2.set_title(f'Efficiency: {efficiency:.1f}%')

        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                     f'{height:.1f}', ha='center', va='bottom')

        plt.tight_layout()
        return self._save_plot(fig, "revenue_efficiency.png", save_to_disk)

    def plot_bidder_utility(self, save_to_disk: bool = True) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        analyzer = ResultAnalyzer(self.state)
        metrics = analyzer.compute_all_metrics()
        bidder_metrics = metrics["bidder_metrics"]["bidder_details"]

        names = []
        utilities = []
        values = []
        payments = []

        for bidder_id, data in bidder_metrics.items():
            names.append(data["bidder_name"])
            utilities.append(data["utility"])
            values.append(data["total_value"])
            payments.append(data["total_payment"])

        x = np.arange(len(names))
        width = 0.25

        ax.bar(x - width, values, width, label='Total Value', color='#66B2FF')
        ax.bar(x, payments, width, label='Payment', color='#FF9999')
        ax.bar(x + width, utilities, width, label='Utility/Profit', color='#99FF99')

        ax.set_xlabel('Bidders')
        ax.set_ylabel('Amount')
        ax.set_title('Bidder Value, Payment, and Utility')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        plt.tight_layout()
        return self._save_plot(fig, "bidder_utility.png", save_to_disk)

    def plot_bids_per_round(self, save_to_disk: bool = True) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        rounds = list(range(1, len(self.state.round_history) + 1))
        bids_count = [record.bids_count for record in self.state.round_history]

        ax.bar(rounds, bids_count, color='#66B2FF', alpha=0.7)

        if self.state.round_history:
            for round_record in self.state.round_history:
                if round_record.phase == "supplementary":
                    ax.axvline(x=round_record.round_number, color='r', linestyle='--',
                               alpha=0.5, label='Supplementary Phase')
                    break

        ax.set_xlabel('Round')
        ax.set_ylabel('Number of Bids')
        ax.set_title('Bids Submitted Per Round')
        ax.grid(True, alpha=0.3, axis='y')

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend([handles[-1]], [labels[-1]])

        plt.tight_layout()
        return self._save_plot(fig, "bids_per_round.png", save_to_disk)

    def plot_price_convergence(self, save_to_disk: bool = True) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        item_ids = self.state.get_all_item_ids()
        rounds = list(range(1, len(self.state.round_history) + 1))

        price_changes = []
        if len(self.state.round_history) > 1:
            for i in range(1, len(self.state.round_history)):
                curr_prices = self.state.round_history[i].prices
                prev_prices = self.state.round_history[i-1].prices
                total_change = sum(
                    abs(curr_prices.get(item_id, 0) - prev_prices.get(item_id, 0))
                    for item_id in item_ids
                )
                price_changes.append(total_change)

        if price_changes:
            ax.plot(rounds[1:], price_changes, marker='o', linewidth=2,
                    color='#FF6B6B', markersize=6)

        ax.set_xlabel('Round')
        ax.set_ylabel('Total Price Change')
        ax.set_title('Price Convergence (Total Change Per Round)')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return self._save_plot(fig, "price_convergence.png", save_to_disk)

    def _save_plot(self, fig: plt.Figure, filename: str, save_to_disk: bool) -> str:
        if save_to_disk:
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=100, bbox_inches='tight')

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return img_str

    def generate_interactive_data(self) -> Dict[str, Any]:
        price_data = []
        for round_record in self.state.round_history:
            price_data.append({
                "round": round_record.round_number,
                "phase": round_record.phase,
                "prices": {str(k): v for k, v in round_record.prices.items()},
                "excess_demand": {str(k): v for k, v in round_record.excess_demand.items()},
                "bids_count": round_record.bids_count
            })

        item_info = []
        for item in self.state.items:
            item_info.append({
                "id": item.item_id,
                "name": item.name,
                "final_price": item.final_price,
                "winner": item.final_winner
            })

        bidder_info = []
        for bidder in self.state.bidders:
            won_items = [
                item.item_id for item in self.state.items
                if item.final_winner == bidder.bidder_id
            ]
            bidder_info.append({
                "id": bidder.bidder_id,
                "name": bidder.name,
                "strategy": bidder.strategy_name,
                "won_items": won_items,
                "utility": round(bidder.get_value(won_items) - bidder.total_payment, 2)
            })

        return {
            "price_data": price_data,
            "items": item_info,
            "bidders": bidder_info,
            "auction_type": self.state.auction_type,
            "total_rounds": len(self.state.round_history)
        }
