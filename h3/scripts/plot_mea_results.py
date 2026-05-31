import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
import csv
import os
import argparse
from collections import defaultdict


class MEADataLoader:
    def __init__(self, mea_spike_file: str = "mea_spikes.csv",
                 mea_lfp_file: str = "mea_lfp.csv"):
        self.mea_spike_file = mea_spike_file
        self.mea_lfp_file = mea_lfp_file
        self.electrode_positions = {}
        self.electrode_spikes = defaultdict(list)
        self.lfp_data = {}
        self.lfp_time = []

    def load(self):
        self.load_mea_spikes()
        self.load_lfp_data()

    def load_mea_spikes(self):
        if not os.path.exists(self.mea_spike_file):
            print(f"Warning: {self.mea_spike_file} not found.")
            return

        with open(self.mea_spike_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = int(row['electrode_id'])
                x = float(row['x_um'])
                y = float(row['y_um'])
                t = float(row['time_ms'])
                nid = int(row['neuron_id'])

                self.electrode_positions[eid] = (x, y)
                self.electrode_spikes[eid].append((t, nid))

        print(f"Loaded MEA spikes: {len(self.electrode_spikes)} electrodes, "
              f"{sum(len(v) for v in self.electrode_spikes.values())} events")

    def load_lfp_data(self):
        if not os.path.exists(self.mea_lfp_file):
            print(f"Warning: {self.mea_lfp_file} not found.")
            return

        with open(self.mea_lfp_file, 'r') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            ch_names = [h for h in headers if h.startswith('ch')]

            for name in ch_names:
                self.lfp_data[name] = []

            for row in reader:
                self.lfp_time.append(float(row['time_ms']))
                for name in ch_names:
                    self.lfp_data[name].append(float(row[name]))

        self.lfp_time = np.array(self.lfp_time)
        for name in self.lfp_data:
            self.lfp_data[name] = np.array(self.lfp_data[name])

        print(f"Loaded LFP: {len(self.lfp_data)} channels, "
              f"{len(self.lfp_time)} time points")


class MEAResultsPlotter:
    def __init__(self, mea_spike_file: str = "mea_spikes.csv",
                 mea_lfp_file: str = "mea_lfp.csv"):
        self.loader = MEADataLoader(mea_spike_file, mea_lfp_file)
        self.loader.load()

    def plot_all(self):
        fig = plt.figure(figsize=(20, 16))
        fig.suptitle('Multi-Electrode Array (MEA) Recording Results',
                     fontsize=14, fontweight='bold')

        gs = GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.3)

        ax_layout = fig.add_subplot(gs[0, 0])
        ax_raster = fig.add_subplot(gs[0, 1:])
        ax_lfp_example = fig.add_subplot(gs[1, 0])
        ax_lfp_grid = fig.add_subplot(gs[1, 1:])
        ax_rate = fig.add_subplot(gs[2, 0])
        ax_spatial = fig.add_subplot(gs[2, 1])
        ax_psth = fig.add_subplot(gs[2, 2])

        self.plot_electrode_layout(ax_layout)
        self.plot_mea_raster(ax_raster)
        self.plot_lfp_example(ax_lfp_example)
        self.plot_lfp_grid(ax_lfp_grid)
        self.plot_electrode_firing_rate(ax_rate)
        self.plot_spatial_firing_map(ax_spatial)
        self.plot_psth(ax_psth)

        plt.savefig('mea_results.png', dpi=150, bbox_inches='tight')
        print("MEA plot saved to mea_results.png")
        plt.show()

    def plot_electrode_layout(self, ax):
        for eid, (x, y) in self.loader.electrode_positions.items():
            ax.plot(x, y, 's', color='#3498db', markersize=10, markeredgecolor='black',
                    markeredgewidth=0.5)

        ax.set_title('Electrode Array Layout')
        ax.set_xlabel('X (um)')
        ax.set_ylabel('Y (um)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    def plot_mea_raster(self, ax):
        for eid in sorted(self.loader.electrode_spikes.keys()):
            times = [t for t, _ in self.loader.electrode_spikes[eid]]
            if times:
                ax.scatter(times, [eid] * len(times), c='#2ecc71', s=2, alpha=0.7)

        ax.set_title('MEA Spike Raster')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('Electrode ID')
        ax.grid(True, alpha=0.3)

    def plot_lfp_example(self, ax):
        if not self.loader.lfp_data:
            ax.text(0.5, 0.5, 'No LFP data', ha='center', va='center')
            return

        ch = list(self.loader.lfp_data.keys())[0]
        t = self.loader.lfp_time
        lfp = self.loader.lfp_data[ch]

        ax.plot(t, lfp, color='#3498db', linewidth=0.5)
        ax.set_title(f'LFP Example - {ch}')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('LFP (mV)')
        ax.grid(True, alpha=0.3)

    def plot_lfp_grid(self, ax):
        if not self.loader.lfp_data:
            ax.text(0.5, 0.5, 'No LFP data', ha='center', va='center')
            return

        ch_names = sorted(self.loader.lfp_data.keys(),
                         key=lambda x: int(x[2:]))
        n_channels = min(len(ch_names), 64)
        ch_names = ch_names[:n_channels]

        t = self.loader.lfp_time

        grid_size = int(np.ceil(np.sqrt(n_channels)))

        for idx, ch in enumerate(ch_names):
            sub_ax = ax.inset_axes([
                (idx % grid_size) / grid_size,
                1.0 - (idx // grid_size + 1) / grid_size,
                1.0 / grid_size - 0.01,
                1.0 / grid_size - 0.01
            ])

            lfp = self.loader.lfp_data[ch]
            sub_ax.plot(t, lfp, linewidth=0.3, color='#3498db')
            sub_ax.set_xticks([])
            sub_ax.set_yticks([])
            sub_ax.set_title(ch, fontsize=4, pad=0)

        ax.set_title('LFP Grid View')
        ax.set_xticks([])
        ax.set_yticks([])

    def plot_electrode_firing_rate(self, ax):
        rates = {}
        for eid, spikes in self.loader.electrode_spikes.items():
            if spikes:
                times = [t for t, _ in spikes]
                duration = max(times) - min(times) if len(times) > 1 else 1.0
                rates[eid] = len(times) / duration * 1000.0
            else:
                rates[eid] = 0.0

        if rates:
            eids = sorted(rates.keys())
            rate_vals = [rates[e] for e in eids]
            ax.bar(eids, rate_vals, color='#e74c3c', alpha=0.7)

        ax.set_title('Electrode Firing Rate')
        ax.set_xlabel('Electrode ID')
        ax.set_ylabel('Rate (Hz)')
        ax.grid(True, alpha=0.3, axis='y')

    def plot_spatial_firing_map(self, ax):
        for eid, (x, y) in self.loader.electrode_positions.items():
            n_spikes = len(self.loader.electrode_spikes.get(eid, []))
            color = plt.cm.YlOrRd(min(n_spikes / 100.0, 1.0))
            ax.plot(x, y, 'o', color=color, markersize=15, markeredgecolor='black',
                    markeredgewidth=0.5)

        ax.set_title('Spatial Firing Rate Map')
        ax.set_xlabel('X (um)')
        ax.set_ylabel('Y (um)')
        ax.set_aspect('equal')

        sm = plt.cm.ScalarMappable(cmap='YlOrRd',
                                    norm=plt.Normalize(0, 100))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.6)
        cbar.set_label('Spike Count')

    def plot_psth(self, ax):
        if not self.loader.electrode_spikes:
            ax.text(0.5, 0.5, 'No spike data', ha='center', va='center')
            return

        all_times = []
        for spikes in self.loader.electrode_spikes.values():
            all_times.extend([t for t, _ in spikes])

        if all_times:
            bins = 50
            ax.hist(all_times, bins=bins, color='#9b59b6', alpha=0.7,
                    edgecolor='white', linewidth=0.5)

        ax.set_title('Peri-Stimulus Time Histogram (PSTH)')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('Spike Count')
        ax.grid(True, alpha=0.3, axis='y')


class MEARealTimePlotter:
    def __init__(self, mea_spike_file: str = "mea_spikes.csv",
                 mea_lfp_file: str = "mea_lfp.csv",
                 update_interval: int = 500):
        self.loader = MEADataLoader(mea_spike_file, mea_lfp_file)
        self.update_interval = update_interval

        self.fig = plt.figure(figsize=(16, 10))
        self.fig.suptitle('MEA Real-Time Monitoring', fontsize=14, fontweight='bold')

        gs = GridSpec(2, 2, figure=fig, hspace=0.3)

        self.ax_raster = self.fig.add_subplot(gs[0, :])
        self.ax_lfp = self.fig.add_subplot(gs[1, 0])
        self.ax_layout = self.fig.add_subplot(gs[1, 1])

        self.scatter = None
        self.lfp_lines = []

    def animate(self, frame):
        self.loader.load()

        self.ax_raster.clear()
        for eid in sorted(self.loader.electrode_spikes.keys()):
            times = [t for t, _ in self.loader.electrode_spikes[eid]]
            if times:
                self.ax_raster.scatter(times, [eid] * len(times),
                                       c='#2ecc71', s=2, alpha=0.7)
        self.ax_raster.set_title('MEA Spike Raster (Real-time)')
        self.ax_raster.set_xlabel('Time (ms)')
        self.ax_raster.set_ylabel('Electrode ID')
        self.ax_raster.grid(True, alpha=0.3)

        self.ax_lfp.clear()
        if self.loader.lfp_data:
            ch = list(self.loader.lfp_data.keys())[0]
            self.ax_lfp.plot(self.loader.lfp_time, self.loader.lfp_data[ch],
                            color='#3498db', linewidth=0.5)
            self.ax_lfp.set_title(f'LFP - {ch}')
            self.ax_lfp.set_xlabel('Time (ms)')
            self.ax_lfp.grid(True, alpha=0.3)

        self.ax_layout.clear()
        for eid, (x, y) in self.loader.electrode_positions.items():
            n_spikes = len(self.loader.electrode_spikes.get(eid, []))
            color = plt.cm.YlOrRd(min(n_spikes / 50.0, 1.0))
            self.ax_layout.plot(x, y, 'o', color=color, markersize=10)
        self.ax_layout.set_title('Electrode Activity')
        self.ax_layout.set_aspect('equal')
        self.ax_layout.grid(True, alpha=0.3)

        return []

    def run(self):
        print("Starting MEA real-time visualization...")
        anim = animation.FuncAnimation(
            self.fig, self.animate, frames=100,
            interval=self.update_interval, blit=False
        )
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='MEA Recording Visualization Tool')
    parser.add_argument('--mea-spike-file', type=str, default='mea_spikes.csv',
                       help='Path to MEA spike data CSV file')
    parser.add_argument('--mea-lfp-file', type=str, default='mea_lfp.csv',
                       help='Path to MEA LFP data CSV file')
    parser.add_argument('--realtime', action='store_true',
                       help='Enable real-time visualization mode')
    parser.add_argument('--post', action='store_true',
                       help='Enable post-simulation plotting (default)')
    parser.add_argument('--interval', type=int, default=500,
                       help='Update interval in ms (real-time mode)')

    args = parser.parse_args()

    if args.realtime:
        plotter = MEARealTimePlotter(
            mea_spike_file=args.mea_spike_file,
            mea_lfp_file=args.mea_lfp_file,
            update_interval=args.interval
        )
        plotter.run()
    else:
        plotter = MEAResultsPlotter(
            mea_spike_file=args.mea_spike_file,
            mea_lfp_file=args.mea_lfp_file
        )
        plotter.plot_all()


if __name__ == '__main__':
    main()
