import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import LinearSegmentedColormap
from scipy.interpolate import griddata


class Visualizer:
    def __init__(self):
        self.colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        self.state_colors = LinearSegmentedColormap.from_list(
            'microstates', self.colors, N=4)
        self.fig = None
        self.canvas = None

    def _create_canvas(self):
        self.fig = plt.figure(figsize=(12, 10))
        self.canvas = FigureCanvas(self.fig)
        return self.canvas

    def plot_topomap(self, data, pos, ax=None, title='', vmin=None, vmax=None,
                     cmap='RdBu_r', contours=True, show_names=False,
                     head_radius=0.5):
        if ax is None:
            fig, ax = plt.subplots()

        if vmin is None:
            vmin = -np.max(np.abs(data))
        if vmax is None:
            vmax = np.max(np.abs(data))

        x = pos[:, 0]
        y = pos[:, 1]

        xi = np.linspace(-head_radius, head_radius, 100)
        yi = np.linspace(-head_radius, head_radius, 100)
        xi, yi = np.meshgrid(xi, yi)

        zi = griddata((x, y), data, (xi, yi), method='cubic')

        dist_from_center = np.sqrt(xi ** 2 + yi ** 2)
        mask = dist_from_center > head_radius
        zi[mask] = np.nan

        im = ax.imshow(zi, vmin=vmin, vmax=vmax, origin='lower',
                       extent=[-head_radius, head_radius, -head_radius, head_radius],
                       cmap=cmap, aspect='equal')

        if contours:
            zi_masked = np.ma.masked_where(mask, zi)
            ax.contour(xi, yi, zi_masked, levels=10, colors='k', linewidths=0.5, alpha=0.5)

        circle = plt.Circle((0, 0), head_radius, color='k', fill=False, linewidth=2)
        ax.add_artist(circle)

        if show_names:
            for ch_x, ch_y in zip(x, y):
                if np.sqrt(ch_x**2 + ch_y**2) <= head_radius:
                    ax.plot(ch_x, ch_y, 'ko', markersize=4, markerfacecolor='w')

        ax.set_xlim(-head_radius * 1.1, head_radius * 1.1)
        ax.set_ylim(-head_radius * 1.1, head_radius * 1.1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=12, fontweight='bold')

        return im

    def plot_microstate_topomaps(self, templates, pos, titles=None, fig=None):
        n_clusters = templates.shape[1]
        
        if fig is None:
            fig, axes = plt.subplots(1, n_clusters, figsize=(4 * n_clusters, 4))
        else:
            fig.clear()
            axes = [fig.add_subplot(1, n_clusters, i + 1) for i in range(n_clusters)]

        if titles is None:
            titles = [f'微状态 {i + 1}' for i in range(n_clusters)]

        vmax = np.max(np.abs(templates))
        vmin = -vmax

        for i in range(n_clusters):
            im = self.plot_topomap(templates[:, i], pos, ax=axes[i],
                                   title=titles[i], vmin=vmin, vmax=vmax)

        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        fig.colorbar(im, cax=cbar_ax)
        fig.tight_layout(rect=[0, 0, 0.9, 1])

        return fig

    def plot_microstate_sequence(self, microstate_sequence, times, sfreq,
                                 ax=None, show_gfp=True, gfp=None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 3))

        n_samples = len(microstate_sequence)
        color_sequence = [self.colors[int(s)] for s in microstate_sequence]

        for i in range(n_samples):
            ax.axvspan(times[i], times[i] + 1 / sfreq,
                       color=color_sequence[i], alpha=0.8, linewidth=0)

        if show_gfp and gfp is not None:
            ax2 = ax.twinx()
            ax2.plot(times, gfp, 'k-', linewidth=1, alpha=0.7, label='GFP')
            ax2.set_ylabel('GFP (μV)', fontsize=10)
            ax2.legend(loc='upper right')

        ax.set_xlabel('时间 (s)', fontsize=10)
        ax.set_yticks([])
        ax.set_title('微状态时间序列', fontsize=12, fontweight='bold')
        ax.set_xlim(times[0], times[-1])

        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=self.colors[i], 
                                 label=f'微状态 {i + 1}') 
                           for i in range(4)]
        ax.legend(handles=legend_elements, loc='upper left', ncol=4)

        return ax

    def plot_gfp_with_peaks(self, gfp, peak_indices, times, ax=None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 4))

        ax.plot(times, gfp, 'b-', linewidth=1, label='GFP')
        ax.plot(times[peak_indices], gfp[peak_indices], 'ro', 
                markersize=4, label='峰值')
        ax.set_xlabel('时间 (s)', fontsize=10)
        ax.set_ylabel('GFP (μV)', fontsize=10)
        ax.set_title('全局场强 (GFP) 及峰值提取', fontsize=12, fontweight='bold')
        ax.legend()
        ax.set_xlim(times[0], times[-1])

        return ax

    def plot_statistics(self, stats, ax=None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        mean_durations = stats['mean_durations']
        frequencies = stats['frequencies']
        std_durations = stats['std_durations']

        x = np.arange(4)
        width = 0.35

        ax.bar(x - width / 2, mean_durations, width, yerr=std_durations,
               label='平均持续时间 (ms)', color=self.colors, alpha=0.7,
               capsize=5)
        ax.set_ylabel('平均持续时间 (ms)', fontsize=10)
        ax.set_xlabel('微状态', fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels([f'微状态 {i + 1}' for i in range(4)])

        ax2 = ax.twinx()
        ax2.bar(x + width / 2, frequencies * 100, width,
                label='出现频率 (%)', color='gray', alpha=0.5)
        ax2.set_ylabel('出现频率 (%)', fontsize=10)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        ax.set_title('微状态统计特征', fontsize=12, fontweight='bold')

        return ax

    def plot_transition_matrix(self, transition_probs, ax=None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 5))

        im = ax.imshow(transition_probs, cmap='YlOrRd', vmin=0, vmax=1)

        for i in range(4):
            for j in range(4):
                ax.text(j, i, f'{transition_probs[i, j]:.2f}',
                        ha='center', va='center', fontsize=12,
                        color='white' if transition_probs[i, j] > 0.5 else 'black')

        ax.set_xticks(np.arange(4))
        ax.set_yticks(np.arange(4))
        ax.set_xticklabels([f'状态 {i + 1}' for i in range(4)])
        ax.set_yticklabels([f'状态 {i + 1}' for i in range(4)])
        ax.set_xlabel('下一个状态', fontsize=10)
        ax.set_ylabel('当前状态', fontsize=10)
        ax.set_title('微状态转换概率矩阵', fontsize=12, fontweight='bold')
        plt.colorbar(im, ax=ax, label='概率')

        return ax

    def plot_eeg_signal(self, data, times, ch_names, n_channels=5, ax=None):
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))

        step = max(1, data.shape[0] // n_channels)
        channels_to_show = np.arange(0, data.shape[0], step)[:n_channels]

        offset = 0
        for i, ch_idx in enumerate(channels_to_show):
            ax.plot(times, data[ch_idx] + offset, label=ch_names[ch_idx])
            offset -= 2 * np.std(data[ch_idx])

        ax.set_xlabel('时间 (s)', fontsize=10)
        ax.set_ylabel('幅值 (μV)', fontsize=10)
        ax.set_title('EEG信号示例', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right')
        ax.set_xlim(times[0], times[-1])
        ax.set_yticks([])

        return ax
