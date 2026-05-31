"""
可视化模块
包含: 2D图像显示、相位剖面线、3D相位表面、残差点可视化
"""

import numpy as np
from typing import Tuple, Optional, List, Dict, Any
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends import backend_qt5
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.patches import Rectangle, Circle, Polygon
from mpl_toolkits.mplot3d import Axes3D
import warnings

warnings.filterwarnings('ignore')


class PhaseColormap:
    """
    相位专用色图
    """

    @staticmethod
    def get_phase_colormap():
        """获取循环相位色图"""
        from matplotlib.colors import LinearSegmentedColormap

        colors = [
            '#000080',
            '#0000FF',
            '#0080FF',
            '#00FFFF',
            '#00FF80',
            '#80FF00',
            '#FFFF00',
            '#FF8000',
            '#FF0000',
            '#FF0080',
            '#8000FF',
            '#000080',
        ]

        n_colors = len(colors)
        cmap = LinearSegmentedColormap.from_list(
            'phase_cyclic', colors, N=256
        )

        return cmap

    @staticmethod
    def get_wrapped_phase_norm():
        """获取包裹相位的归一化器 [-π, π]"""
        from matplotlib.colors import Normalize
        return Normalize(vmin=-np.pi, vmax=np.pi)


class ImageCanvas(FigureCanvas):
    """
    2D图像显示画布
    """

    def __init__(self, parent=None, width: int = 8, height: int = 6, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.im = None
        self.cbar = None
        self.current_data = None
        self.mask_overlay = None
        self.residue_overlay = None
        self.profile_line = None
        self.profile_points = []
        self.drawing_profile = False

        self.fig.tight_layout()

        self.cid_press = self.mpl_connect('button_press_event', self._on_press)
        self.cid_move = self.mpl_connect('motion_notify_event', self._on_move)
        self.cid_release = self.mpl_connect('button_release_event', self._on_release)

        self.data_changed_callback = None

    def _on_press(self, event):
        """鼠标按下事件"""
        if event.inaxes != self.ax:
            return

        if self.drawing_profile:
            self.profile_points = [(event.xdata, event.ydata)]
            if self.profile_line is not None:
                self.profile_line.remove()
            self.profile_line, = self.ax.plot([], [], 'r-', linewidth=2)
            self.draw()

    def _on_move(self, event):
        """鼠标移动事件"""
        if event.inaxes != self.ax or not self.drawing_profile:
            return

        if len(self.profile_points) > 0:
            x = [self.profile_points[0][0], event.xdata]
            y = [self.profile_points[0][1], event.ydata]
            self.profile_line.set_data(x, y)
            self.draw()

    def _on_release(self, event):
        """鼠标释放事件"""
        if event.inaxes != self.ax or not self.drawing_profile:
            return

        if len(self.profile_points) > 0:
            self.profile_points.append((event.xdata, event.ydata))
            self.drawing_profile = False
            if self.data_changed_callback is not None:
                self.data_changed_callback('profile_done', self.profile_points)

    def enable_profile_drawing(self):
        """启用剖面线绘制"""
        self.drawing_profile = True
        self.setCursor(matplotlib.backend_qt5.Qt.CrossCursor)

    def disable_profile_drawing(self):
        """禁用剖面线绘制"""
        self.drawing_profile = False
        self.unsetCursor()

    def clear_profile(self):
        """清除剖面线"""
        if self.profile_line is not None:
            self.profile_line.remove()
            self.profile_line = None
        self.profile_points = []
        self.draw()

    def display_image(self, data: np.ndarray, title: str = '',
                      cmap: str = 'viridis',
                      vmin: Optional[float] = None,
                      vmax: Optional[float] = None,
                      is_wrapped_phase: bool = False) -> None:
        """
        显示图像

        Args:
            data: 图像数据
            title: 图像标题
            cmap: 色图名称
            vmin: 最小值
            vmax: 最大值
            is_wrapped_phase: 是否为包裹相位
        """
        self.ax.clear()
        self.current_data = data.copy()

        if is_wrapped_phase:
            cmap = PhaseColormap.get_phase_colormap()
            vmin, vmax = -np.pi, np.pi

        if vmin is None:
            vmin = np.nanmin(data)
        if vmax is None:
            vmax = np.nanmax(data)

        self.im = self.ax.imshow(
            data,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            origin='upper',
            interpolation='nearest'
        )

        self.ax.set_title(title)
        self.ax.set_xlabel('列')
        self.ax.set_ylabel('行')

        if self.cbar is not None:
            self.cbar.remove()
        self.cbar = self.fig.colorbar(self.im, ax=self.ax, fraction=0.046, pad=0.04)

        self.fig.tight_layout()
        self.draw()

    def overlay_mask(self, mask: np.ndarray, color: str = 'red',
                     alpha: float = 0.3) -> None:
        """
        叠加显示掩膜

        Args:
            mask: 掩膜数据 (1表示掩膜区域)
            color: 掩膜颜色
            alpha: 透明度
        """
        if self.mask_overlay is not None:
            self.mask_overlay.remove()

        mask_rgba = np.zeros((*mask.shape, 4), dtype=np.float32)
        color_rgb = matplotlib.colors.to_rgb(color)
        mask_rgba[mask.astype(bool)] = [*color_rgb, alpha]

        self.mask_overlay = self.ax.imshow(
            mask_rgba,
            origin='upper',
            interpolation='nearest'
        )

        self.draw()

    def overlay_residues(self, pos_residues: np.ndarray,
                         neg_residues: np.ndarray,
                         marker_size: int = 20) -> None:
        """
        叠加显示残差点

        Args:
            pos_residues: 正残差点位置 (N, 2) - [行, 列]
            neg_residues: 负残差点位置 (N, 2) - [行, 列]
            marker_size: 标记大小
        """
        if self.residue_overlay is not None:
            for overlay in self.residue_overlay:
                overlay.remove()

        overlays = []

        if len(pos_residues) > 0:
            pos_plot = self.ax.scatter(
                pos_residues[:, 1], pos_residues[:, 0],
                c='red', s=marker_size, marker='+',
                label='正残差', linewidths=1.5
            )
            overlays.append(pos_plot)

        if len(neg_residues) > 0:
            neg_plot = self.ax.scatter(
                neg_residues[:, 1], neg_residues[:, 0],
                c='blue', s=marker_size, marker='_',
                label='负残差', linewidths=1.5
            )
            overlays.append(neg_plot)

        if len(overlays) > 0:
            self.ax.legend(loc='upper right', fontsize=8)
            self.residue_overlay = overlays
            self.draw()

    def clear_overlays(self) -> None:
        """清除所有叠加层"""
        if self.mask_overlay is not None:
            self.mask_overlay.remove()
            self.mask_overlay = None

        if self.residue_overlay is not None:
            for overlay in self.residue_overlay:
                overlay.remove()
            self.residue_overlay = None
            if self.ax.get_legend() is not None:
                self.ax.get_legend().remove()

        self.draw()

    def get_profile_data(self, start_point: Tuple[float, float],
                         end_point: Tuple[float, float],
                         num_points: int = 500) -> Tuple[np.ndarray, np.ndarray]:
        """
        获取剖面对应的数据值

        Args:
            start_point: 起点 (列, 行)
            end_point: 终点 (列, 行)
            num_points: 采样点数

        Returns:
            (距离数组, 数值数组)
        """
        if self.current_data is None:
            return np.array([]), np.array([])

        x0, y0 = start_point
        x1, y1 = end_point

        t = np.linspace(0, 1, num_points)
        x = x0 + t * (x1 - x0)
        y = y0 + t * (y1 - y0)

        rows, cols = self.current_data.shape
        x_idx = np.clip(x.astype(int), 0, cols - 1)
        y_idx = np.clip(y.astype(int), 0, rows - 1)

        values = self.current_data[y_idx, x_idx]

        dx = x[1:] - x[:-1]
        dy = y[1:] - y[:-1]
        dist = np.cumsum(np.sqrt(dx ** 2 + dy ** 2))
        dist = np.insert(dist, 0, 0)

        return dist, values


class ProfilePlotCanvas(FigureCanvas):
    """
    相位剖面线绘图画布
    """

    def __init__(self, parent=None, width: int = 8, height: int = 4, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.fig.tight_layout()

        self.datasets = []
        self.labels = []

    def plot_profile(self, distance: np.ndarray, values: np.ndarray,
                     label: str = '相位剖面',
                     color: str = 'blue',
                     is_wrapped: bool = False) -> None:
        """
        绘制剖面线

        Args:
            distance: 距离数组
            values: 数值数组
            label: 标签
            color: 颜色
            is_wrapped: 是否为包裹相位
        """
        self.ax.clear()

        valid_mask = ~np.isnan(values)
        if is_wrapped:
            self.ax.plot(
                distance[valid_mask], values[valid_mask],
                color=color, label=label, linewidth=1.5
            )
            self.ax.set_ylim(-np.pi - 0.5, np.pi + 0.5)
            self.ax.set_ylabel('相位 (弧度)')
            self.ax.axhline(y=np.pi, color='gray', linestyle='--', alpha=0.5)
            self.ax.axhline(y=-np.pi, color='gray', linestyle='--', alpha=0.5)
        else:
            self.ax.plot(
                distance[valid_mask], values[valid_mask],
                color=color, label=label, linewidth=1.5
            )
            self.ax.set_ylabel('相位 (弧度)')

        self.ax.set_xlabel('距离 (像素)')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        self.fig.tight_layout()
        self.draw()

    def plot_comparison(self, distance: np.ndarray,
                        wrapped_values: np.ndarray,
                        unwrapped_values: np.ndarray) -> None:
        """
        比较绘制包裹和解缠相位剖面

        Args:
            distance: 距离数组
            wrapped_values: 包裹相位值
            unwrapped_values: 解缠相位值
        """
        self.ax.clear()

        valid_wrapped = ~np.isnan(wrapped_values)
        valid_unwrapped = ~np.isnan(unwrapped_values)

        self.ax.plot(
            distance[valid_wrapped], wrapped_values[valid_wrapped],
            color='red', label='包裹相位', linewidth=1.5, alpha=0.7
        )

        self.ax.plot(
            distance[valid_unwrapped], unwrapped_values[valid_unwrapped],
            color='blue', label='解缠相位', linewidth=2
        )

        self.ax.set_xlabel('距离 (像素)')
        self.ax.set_ylabel('相位 (弧度)')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        self.fig.tight_layout()
        self.draw()

    def clear(self) -> None:
        """清除绘图"""
        self.ax.clear()
        self.fig.tight_layout()
        self.draw()


class Surface3DCanvas(FigureCanvas):
    """
    3D相位表面绘图画布
    """

    def __init__(self, parent=None, width: int = 8, height: int = 6, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111, projection='3d')
        self.fig.tight_layout()

        self.surface = None

    def plot_surface(self, data: np.ndarray,
                     title: str = '3D相位表面',
                     downsample: int = 2,
                     cmap: str = 'viridis') -> None:
        """
        绘制3D表面

        Args:
            data: 2D数据数组
            title: 标题
            downsample: 下采样因子 (用于大数据集)
            cmap: 色图
        """
        self.ax.clear()

        data_display = data.copy()
        if downsample > 1:
            data_display = data_display[::downsample, ::downsample]

        rows, cols = data_display.shape
        X, Y = np.meshgrid(np.arange(cols), np.arange(rows))

        Z = np.ma.masked_invalid(data_display)

        if self.surface is not None:
            self.surface.remove()

        self.surface = self.ax.plot_surface(
            X, Y, Z,
            cmap=cmap,
            linewidth=0,
            antialiased=False,
            alpha=0.9,
            rstride=1,
            cstride=1
        )

        self.ax.set_xlabel('列')
        self.ax.set_ylabel('行')
        self.ax.set_zlabel('相位 (弧度)')
        self.ax.set_title(title)

        if self.fig.axes[-1].get_ylabel() != '':
            pass

        self.fig.colorbar(self.surface, ax=self.ax, fraction=0.046, pad=0.1)
        self.fig.tight_layout()
        self.draw()

    def plot_wireframe(self, data: np.ndarray,
                       title: str = '3D相位网格',
                       downsample: int = 4) -> None:
        """
        绘制3D网格图

        Args:
            data: 2D数据数组
            title: 标题
            downsample: 下采样因子
        """
        self.ax.clear()

        data_display = data.copy()
        if downsample > 1:
            data_display = data_display[::downsample, ::downsample]

        rows, cols = data_display.shape
        X, Y = np.meshgrid(np.arange(cols), np.arange(rows))

        Z = np.ma.masked_invalid(data_display)

        self.ax.plot_wireframe(
            X, Y, Z,
            color='blue',
            linewidth=0.5,
            alpha=0.7,
            rstride=1,
            cstride=1
        )

        self.ax.set_xlabel('列')
        self.ax.set_ylabel('行')
        self.ax.set_zlabel('相位 (弧度)')
        self.ax.set_title(title)
        self.fig.tight_layout()
        self.draw()

    def clear(self) -> None:
        """清除绘图"""
        self.ax.clear()
        self.surface = None
        self.fig.tight_layout()
        self.draw()


class ResiduePlotCanvas(FigureCanvas):
    """
    残差点统计绘图画布
    """

    def __init__(self, parent=None, width: int = 8, height: int = 4, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.fig.tight_layout()

    def plot_residue_histogram(self, charge_map: np.ndarray) -> None:
        """
        绘制残差电荷直方图

        Args:
            charge_map: 残差电荷图
        """
        self.ax.clear()

        charges = charge_map[charge_map != 0]

        if len(charges) == 0:
            self.ax.text(0.5, 0.5, '未检测到残差点',
                        ha='center', va='center',
                        transform=self.ax.transAxes,
                        fontsize=12)
        else:
            unique_charges, counts = np.unique(charges, return_counts=True)

            colors = ['blue' if c < 0 else 'red' for c in unique_charges]
            bars = self.ax.bar(unique_charges.astype(str), counts, color=colors, alpha=0.7)

            for bar, count in zip(bars, counts):
                height = bar.get_height()
                self.ax.text(bar.get_x() + bar.get_width() / 2, height,
                            str(count), ha='center', va='bottom')

            self.ax.set_xlabel('残差电荷')
            self.ax.set_ylabel('数量')
            self.ax.set_title('残差点统计')
            self.ax.grid(axis='y', alpha=0.3)

        self.fig.tight_layout()
        self.draw()

    def plot_error_distribution(self, error_map: np.ndarray) -> None:
        """
        绘制解缠误差分布图

        Args:
            error_map: 误差估计图
        """
        self.ax.clear()

        valid_errors = error_map[~np.isnan(error_map)]

        if len(valid_errors) == 0:
            self.ax.text(0.5, 0.5, '无有效误差数据',
                        ha='center', va='center',
                        transform=self.ax.transAxes,
                        fontsize=12)
        else:
            self.ax.hist(valid_errors, bins=50, alpha=0.7, color='green',
                        edgecolor='black')

            mean_err = np.mean(valid_errors)
            max_err = np.max(valid_errors)
            self.ax.axvline(mean_err, color='red', linestyle='--',
                           label=f'均值: {mean_err:.4f}')

            self.ax.set_xlabel('误差 (弧度)')
            self.ax.set_ylabel('频数')
            self.ax.set_title(f'解缠误差分布 (最大值: {max_err:.4f})')
            self.ax.legend()
            self.ax.grid(alpha=0.3)

        self.fig.tight_layout()
        self.draw()

    def clear(self) -> None:
        """清除绘图"""
        self.ax.clear()
        self.fig.tight_layout()
        self.draw()


def create_navigation_toolbar(canvas: FigureCanvas, parent=None) -> NavigationToolbar:
    """
    创建matplotlib导航工具栏

    Args:
        canvas: 画布
        parent: 父窗口

    Returns:
        导航工具栏
    """
    return NavigationToolbar(canvas, parent)
