import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button, CheckButtons
import csv
import os
import time
from collections import defaultdict
from typing import Dict, List, Tuple


class SpikeDataLoader:
    def __init__(self, spike_file: str = "spike_data.csv",
                 voltage_file: str = "voltage_traces.csv"):
        self.spike_file = spike_file
        self.voltage_file = voltage_file
        self.spike_data = defaultdict(list)
        self.neuron_types = {}
        self.voltage_data = {}
        self.time_array = []

    def load_spike_data(self) -> Dict[int, List[float]]:
        if not os.path.exists(self.spike_file):
            print(f"Warning: {self.spike_file} not found.")
            return self.spike_data

        self.spike_data.clear()
        self.neuron_types.clear()

        with open(self.spike_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                neuron_id = int(row['neuron_id'])
                spike_time = float(row['time'])
                neuron_type = row['type']

                self.spike_data[neuron_id].append(spike_time)
                self.neuron_types[neuron_id] = neuron_type

        return self.spike_data

    def load_voltage_data(self) -> Tuple[np.ndarray, Dict[int, np.ndarray]]:
        if not os.path.exists(self.voltage_file):
            print(f"Warning: {self.voltage_file} not found.")
            return np.array([]), self.voltage_data

        self.voltage_data.clear()
        data = np.genfromtxt(self.voltage_file, delimiter=',', names=True)

        self.time_array = data['time']

        for name in data.dtype.names:
            if name.startswith('v'):
                neuron_id = int(name[1:])
                self.voltage_data[neuron_id] = data[name]

        return self.time_array, self.voltage_data


class RealTimePlotter:
    def __init__(self, spike_file: str = "spike_data.csv",
                 voltage_file: str = "voltage_traces.csv",
                 max_display_neurons: int = 100,
                 update_interval: int = 500):
        self.loader = SpikeDataLoader(spike_file, voltage_file)
        self.max_display_neurons = max_display_neurons
        self.update_interval = update_interval
        self.selected_neuron = 0
        self.display_count = min(max_display_neurons, 50)
        self.show_excitatory = True
        self.show_inhibitory = True
        self.last_update_time = 0
        self.update_threshold = 0.1

        self.fig = plt.figure(figsize=(14, 10))
        self.fig.suptitle('Izhikevich Network Simulation - Real-time Visualization',
                         fontsize=14, fontweight='bold')

        gs = self.fig.add_gridspec(3, 2, height_ratios=[3, 2, 0.5], hspace=0.3)

        self.ax_raster = self.fig.add_subplot(gs[0, :])
        self.ax_voltage = self.fig.add_subplot(gs[1, 0])
        self.ax_rate = self.fig.add_subplot(gs[1, 1])

        self.ax_controls = self.fig.add_subplot(gs[2, :])
        self.ax_controls.set_visible(False)

        self._setup_raster_plot()
        self._setup_voltage_plot()
        self._setup_rate_plot()
        self._setup_controls()

    def _setup_raster_plot(self):
        self.ax_raster.set_title('Spike Raster Plot', fontsize=12)
        self.ax_raster.set_xlabel('Time (ms)')
        self.ax_raster.set_ylabel('Neuron ID')
        self.ax_raster.set_xlim(0, 1000)
        self.ax_raster.set_ylim(-1, self.display_count)

        self.exc_scatter = self.ax_raster.scatter([], [], c='#3498db', s=5,
                                                   label='Excitatory', alpha=0.7)
        self.inh_scatter = self.ax_raster.scatter([], [], c='#e74c3c', s=5,
                                                   label='Inhibitory', alpha=0.7)

        self.time_line = self.ax_raster.axvline(x=0, color='green',
                                                 linestyle='--', alpha=0.5,
                                                 linewidth=2)

        self.ax_raster.legend(loc='upper right')
        self.ax_raster.grid(True, alpha=0.3)

    def _setup_voltage_plot(self):
        self.ax_voltage.set_title(f'Membrane Potential - Neuron {self.selected_neuron}',
                                   fontsize=12)
        self.ax_voltage.set_xlabel('Time (ms)')
        self.ax_voltage.set_ylabel('V (mV)')
        self.ax_voltage.set_xlim(0, 1000)
        self.ax_voltage.set_ylim(-80, 40)

        self.voltage_line, = self.ax_voltage.plot([], [], color='#e74c3c',
                                                   linewidth=1.5, label='V(t)')
        self.spike_markers, = self.ax_voltage.plot([], [], 'k|', markersize=15,
                                                    label='Spike')

        self.ax_voltage.legend(loc='upper right')
        self.ax_voltage.grid(True, alpha=0.3)

    def _setup_rate_plot(self):
        self.ax_rate.set_title('Population Firing Rate', fontsize=12)
        self.ax_rate.set_xlabel('Time (ms)')
        self.ax_rate.set_ylabel('Rate (Hz)')

        self.exc_rate_line, = self.ax_rate.plot([], [], color='#3498db',
                                                 linewidth=2, label='Excitatory')
        self.inh_rate_line, = self.ax_rate.plot([], [], color='#e74c3c',
                                                 linewidth=2, label='Inhibitory')
        self.total_rate_line, = self.ax_rate.plot([], [], color='#2ecc71',
                                                   linewidth=2, label='Total')

        self.ax_rate.legend(loc='upper right')
        self.ax_rate.grid(True, alpha=0.3)

    def _setup_controls(self):
        self.ax_slider = plt.axes([0.15, 0.02, 0.5, 0.03])
        self.neuron_slider = Slider(
            ax=self.ax_slider,
            label='Neuron',
            valmin=0,
            valmax=1000,
            valinit=self.selected_neuron,
            valstep=1
        )

        self.ax_count = plt.axes([0.15, 0.06, 0.3, 0.03])
        self.count_slider = Slider(
            ax=self.ax_count,
            label='Raster Count',
            valmin=10,
            valmax=self.max_display_neurons,
            valinit=self.display_count,
            valstep=10
        )

        self.ax_btn_refresh = plt.axes([0.7, 0.02, 0.1, 0.04])
        self.btn_refresh = Button(self.ax_btn_refresh, 'Refresh')

        self.ax_btn_pause = plt.axes([0.82, 0.02, 0.1, 0.04])
        self.btn_pause = Button(self.ax_btn_pause, 'Pause')

        self.ax_chk = plt.axes([0.7, 0.06, 0.22, 0.1])
        self.chk_buttons = CheckButtons(
            ax=self.ax_chk,
            labels=['Excitatory', 'Inhibitory'],
            actives=[True, True]
        )

        self.paused = False

        self.neuron_slider.on_changed(self._on_neuron_changed)
        self.count_slider.on_changed(self._on_count_changed)
        self.btn_refresh.on_clicked(self._on_refresh)
        self.btn_pause.on_clicked(self._on_pause)
        self.chk_buttons.on_clicked(self._on_check)

    def _on_neuron_changed(self, val):
        self.selected_neuron = int(val)
        self.ax_voltage.set_title(
            f'Membrane Potential - Neuron {self.selected_neuron}')

    def _on_count_changed(self, val):
        self.display_count = int(val)
        self.ax_raster.set_ylim(-1, self.display_count)

    def _on_refresh(self, event):
        self._update_data()

    def _on_pause(self, event):
        self.paused = not self.paused
        self.btn_pause.label.set_text('Resume' if self.paused else 'Pause')

    def _on_check(self, label):
        if label == 'Excitatory':
            self.show_excitatory = not self.show_excitatory
        elif label == 'Inhibitory':
            self.show_inhibitory = not self.show_inhibitory

    def _update_raster(self):
        if not self.loader.spike_data:
            return

        exc_times = []
        exc_ids = []
        inh_times = []
        inh_ids = []

        for neuron_id in range(min(self.display_count, len(self.loader.spike_data))):
            if neuron_id not in self.loader.spike_data:
                continue

            neuron_type = self.loader.neuron_types.get(neuron_id, 'excitatory')
            times = self.loader.spike_data[neuron_id]

            if neuron_type == 'excitatory' and self.show_excitatory:
                exc_times.extend(times)
                exc_ids.extend([neuron_id] * len(times))
            elif neuron_type == 'inhibitory' and self.show_inhibitory:
                inh_times.extend(times)
                inh_ids.extend([neuron_id] * len(times))

        if exc_times:
            self.exc_scatter.set_offsets(np.c_[exc_times, exc_ids])
        else:
            self.exc_scatter.set_offsets(np.empty((0, 2)))

        if inh_times:
            self.inh_scatter.set_offsets(np.c_[inh_times, inh_ids])
        else:
            self.inh_scatter.set_offsets(np.empty((0, 2)))

        if self.loader.time_array:
            max_time = max(self.loader.time_array) if self.loader.time_array else 1000
            self.ax_raster.set_xlim(0, max_time)
            self.time_line.set_xdata([max_time, max_time])

    def _update_voltage(self):
        if self.selected_neuron not in self.loader.voltage_data:
            return

        times = self.loader.time_array
        voltages = self.loader.voltage_data[self.selected_neuron]

        if len(times) > 0 and len(voltages) > 0:
            self.voltage_line.set_data(times, voltages)

            spikes = self.loader.spike_data.get(self.selected_neuron, [])
            if spikes:
                spike_voltages = [30] * len(spikes)
                self.spike_markers.set_data(spikes, spike_voltages)
            else:
                self.spike_markers.set_data([], [])

            self.ax_voltage.set_xlim(0, max(times))

    def _update_rate(self):
        if not self.loader.time_array or not self.loader.spike_data:
            return

        times = self.loader.time_array
        if len(times) < 2:
            return

        window_size = 10.0
        dt = times[1] - times[0]
        window_steps = int(window_size / dt)

        if window_steps < 2:
            return

        exc_counts = np.zeros(len(times))
        inh_counts = np.zeros(len(times))

        num_exc = 0
        num_inh = 0

        for neuron_id, spikes in self.loader.spike_data.items():
            neuron_type = self.loader.neuron_types.get(neuron_id, 'excitatory')

            if neuron_type == 'excitatory':
                num_exc += 1
            else:
                num_inh += 1

            for spike_time in spikes:
                idx = np.searchsorted(times, spike_time)
                if 0 <= idx < len(times):
                    if neuron_type == 'excitatory':
                        exc_counts[idx] += 1
                    else:
                        inh_counts[idx] += 1

        kernel = np.ones(window_steps) / window_steps

        if num_exc > 0:
            exc_rate = np.convolve(exc_counts, kernel, mode='same') * 1000 / num_exc
        else:
            exc_rate = np.zeros(len(times))

        if num_inh > 0:
            inh_rate = np.convolve(inh_counts, kernel, mode='same') * 1000 / num_inh
        else:
            inh_rate = np.zeros(len(times))

        total_rate = exc_rate + inh_rate

        self.exc_rate_line.set_data(times, exc_rate)
        self.inh_rate_line.set_data(times, inh_rate)
        self.total_rate_line.set_data(times, total_rate)

        self.ax_rate.set_xlim(0, max(times))
        self.ax_rate.relim()
        self.ax_rate.autoscale_view(scalex=False, scaley=True)

    def _update_data(self):
        current_time = time.time()
        if current_time - self.last_update_time < self.update_threshold:
            return
        self.last_update_time = current_time

        self.loader.load_spike_data()
        self.loader.load_voltage_data()

        self._update_raster()
        self._update_voltage()
        self._update_rate()

        self.fig.canvas.draw_idle()

    def animate(self, frame):
        if not self.paused:
            self._update_data()
        return []

    def run(self):
        print("Starting real-time visualization...")
        print("Controls:")
        print("  - Slider: Select neuron for voltage plot")
        print("  - Raster Count: Adjust number of neurons in raster plot")
        print("  - Refresh: Reload data from files")
        print("  - Pause/Resume: Control animation")
        print("  - Checkboxes: Show/hide excitatory/inhibitory neurons")
        print("\nWaiting for simulation data...")

        self.anim = animation.FuncAnimation(
            self.fig,
            self.animate,
            frames=100,
            interval=self.update_interval,
            blit=False
        )

        plt.tight_layout(rect=[0, 0.1, 1, 1])
        plt.show()


class PostSimulationPlotter:
    def __init__(self, spike_file: str = "spike_data.csv",
                 voltage_file: str = "voltage_traces.csv"):
        self.loader = SpikeDataLoader(spike_file, voltage_file)

    def plot_all(self):
        print("Loading data...")
        self.loader.load_spike_data()
        self.loader.load_voltage_data()

        if not self.loader.spike_data:
            print("No data to plot.")
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Izhikevich Network Simulation Results',
                     fontsize=14, fontweight='bold')

        self._plot_raster(axes[0, 0])
        self._plot_voltage_examples(axes[0, 1])
        self._plot_firing_rate(axes[1, 0])
        self._plot_interspike_interval(axes[1, 1])

        plt.tight_layout()
        plt.savefig('simulation_results.png', dpi=150, bbox_inches='tight')
        print("Plot saved to simulation_results.png")
        plt.show()

    def _plot_raster(self, ax):
        exc_times = []
        exc_ids = []
        inh_times = []
        inh_ids = []

        for neuron_id, times in self.loader.spike_data.items():
            neuron_type = self.loader.neuron_types.get(neuron_id, 'excitatory')

            if neuron_type == 'excitatory':
                exc_times.extend(times)
                exc_ids.extend([neuron_id] * len(times))
            else:
                inh_times.extend(times)
                inh_ids.extend([neuron_id] * len(times))

        if exc_times:
            ax.scatter(exc_times, exc_ids, c='#3498db', s=1, label='Excitatory',
                       alpha=0.5)
        if inh_times:
            ax.scatter(inh_times, inh_ids, c='#e74c3c', s=1, label='Inhibitory',
                       alpha=0.5)

        ax.set_title('Spike Raster Plot')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('Neuron ID')
        ax.legend(loc='upper right', markerscale=10)
        ax.grid(True, alpha=0.3)

    def _plot_voltage_examples(self, ax):
        exc_neurons = [n for n, t in self.loader.neuron_types.items()
                      if t == 'excitatory' and n in self.loader.voltage_data]
        inh_neurons = [n for n, t in self.loader.neuron_types.items()
                      if t == 'inhibitory' and n in self.loader.voltage_data]

        if exc_neurons:
            n = exc_neurons[0]
            ax.plot(self.loader.time_array, self.loader.voltage_data[n],
                    color='#3498db', linewidth=0.5, label=f'Neuron {n} (Exc)')

        if inh_neurons:
            n = inh_neurons[0]
            ax.plot(self.loader.time_array, self.loader.voltage_data[n],
                    color='#e74c3c', linewidth=0.5, label=f'Neuron {n} (Inh)')

        ax.set_title('Membrane Potential Examples')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('V (mV)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

    def _plot_firing_rate(self, ax):
        if not self.loader.time_array:
            return

        times = self.loader.time_array
        window_size = 20.0
        dt = times[1] - times[0]
        window_steps = int(window_size / dt)

        exc_counts = np.zeros(len(times))
        inh_counts = np.zeros(len(times))
        num_exc = 0
        num_inh = 0

        for neuron_id, spikes in self.loader.spike_data.items():
            neuron_type = self.loader.neuron_types.get(neuron_id, 'excitatory')
            if neuron_type == 'excitatory':
                num_exc += 1
            else:
                num_inh += 1

            for spike_time in spikes:
                idx = np.searchsorted(times, spike_time)
                if 0 <= idx < len(times):
                    if neuron_type == 'excitatory':
                        exc_counts[idx] += 1
                    else:
                        inh_counts[idx] += 1

        if window_steps >= 2:
            kernel = np.ones(window_steps) / window_steps
            if num_exc > 0:
                exc_rate = np.convolve(exc_counts, kernel, mode='same') * 1000 / num_exc
            else:
                exc_rate = np.zeros(len(times))
            if num_inh > 0:
                inh_rate = np.convolve(inh_counts, kernel, mode='same') * 1000 / num_inh
            else:
                inh_rate = np.zeros(len(times))

            ax.plot(times, exc_rate, color='#3498db', linewidth=1, label='Excitatory')
            ax.plot(times, inh_rate, color='#e74c3c', linewidth=1, label='Inhibitory')

        ax.set_title('Population Firing Rate')
        ax.set_xlabel('Time (ms)')
        ax.set_ylabel('Rate (Hz)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

    def _plot_interspike_interval(self, ax):
        all_isis = []
        exc_isis = []
        inh_isis = []

        for neuron_id, times in self.loader.spike_data.items():
            if len(times) < 2:
                continue

            isis = np.diff(sorted(times))
            all_isis.extend(isis)

            neuron_type = self.loader.neuron_types.get(neuron_id, 'excitatory')
            if neuron_type == 'excitatory':
                exc_isis.extend(isis)
            else:
                inh_isis.extend(isis)

        if all_isis:
            ax.hist(all_isis, bins=50, density=True, alpha=0.7, color='#95a5a6',
                    label='All')
            if exc_isis:
                ax.hist(exc_isis, bins=50, density=True, alpha=0.5, color='#3498db',
                        label='Excitatory')
            if inh_isis:
                ax.hist(inh_isis, bins=50, density=True, alpha=0.5, color='#e74c3c',
                        label='Inhibitory')

        ax.set_title('Interspike Interval Distribution')
        ax.set_xlabel('ISI (ms)')
        ax.set_ylabel('Density')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Izhikevich Network Visualization Tool')
    parser.add_argument('--spike-file', type=str, default='spike_data.csv',
                       help='Path to spike data CSV file')
    parser.add_argument('--voltage-file', type=str, default='voltage_traces.csv',
                       help='Path to voltage traces CSV file')
    parser.add_argument('--realtime', action='store_true',
                       help='Enable real-time visualization mode')
    parser.add_argument('--post', action='store_true',
                       help='Enable post-simulation plotting (default)')
    parser.add_argument('--interval', type=int, default=500,
                       help='Update interval in ms (real-time mode)')
    parser.add_argument('--max-neurons', type=int, default=100,
                       help='Maximum neurons to display (real-time mode)')

    args = parser.parse_args()

    if args.realtime:
        plotter = RealTimePlotter(
            spike_file=args.spike_file,
            voltage_file=args.voltage_file,
            max_display_neurons=args.max_neurons,
            update_interval=args.interval
        )
        plotter.run()
    else:
        plotter = PostSimulationPlotter(
            spike_file=args.spike_file,
            voltage_file=args.voltage_file
        )
        plotter.plot_all()


if __name__ == '__main__':
    main()
