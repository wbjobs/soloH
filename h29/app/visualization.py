import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.colors import Normalize
from typing import List, Optional, Tuple
from .models import VelocityModel, Shot, Receiver, TravelTimeData


def create_figure(figsize: Tuple[int, int] = (8, 6)) -> Figure:
    return Figure(figsize=figsize, dpi=100)


def plot_velocity_model(ax: plt.Axes, model: VelocityModel,
                        title: str = 'Velocity Model',
                        cmap: str = 'jet',
                        show_colorbar: bool = True) -> plt.Axes:
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    im = ax.imshow(model.velocity, extent=extent, cmap=cmap,
                   aspect='auto', origin='upper')
    
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title(title)
    
    if show_colorbar:
        plt.colorbar(im, ax=ax, label='Velocity (m/s)')
    
    return ax


def plot_ray_density(ax: plt.Axes, model: VelocityModel,
                     title: str = 'Ray Coverage Density',
                     cmap: str = 'hot',
                     show_colorbar: bool = True) -> plt.Axes:
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    density = model.ray_density.copy()
    if density.max() > 0:
        density = np.log10(density + 1)
    
    im = ax.imshow(density, extent=extent, cmap=cmap,
                   aspect='auto', origin='upper')
    
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title(title)
    
    if show_colorbar:
        plt.colorbar(im, ax=ax, label='Log Ray Density')
    
    return ax


def plot_residual_histogram(ax: plt.Axes, data: List[TravelTimeData],
                            title: str = 'Travel Time Residuals',
                            bins: int = 30) -> plt.Axes:
    residuals = np.array([d.residual for d in data if np.isfinite(d.residual)])
    
    ax.hist(residuals * 1000, bins=bins, edgecolor='black', alpha=0.7)
    ax.axvline(0, color='red', linestyle='--', linewidth=2)
    
    mean_res = np.mean(residuals) * 1000
    std_res = np.std(residuals) * 1000
    rms = np.sqrt(np.mean(residuals ** 2)) * 1000
    
    ax.set_xlabel('Residual (ms)')
    ax.set_ylabel('Frequency')
    ax.set_title(f'{title}\nMean={mean_res:.2f} ms, Std={std_res:.2f} ms, RMS={rms:.2f} ms')
    ax.grid(True, alpha=0.3)
    
    return ax


def plot_geometry(ax: plt.Axes, shots: List[Shot], receivers: List[Receiver],
                  title: str = 'Survey Geometry') -> plt.Axes:
    sx = [s.x for s in shots]
    sz = [s.z for s in shots]
    rx = [r.x for r in receivers]
    rz = [r.z for r in receivers]
    
    ax.scatter(sx, sz, c='red', marker='*', s=100, label='Shots', zorder=5)
    ax.scatter(rx, rz, c='blue', marker='v', s=60, label='Receivers', zorder=5)
    
    for shot in shots:
        for rec in receivers:
            ax.plot([shot.x, rec.x], [shot.z, rec.z], 'k-', alpha=0.1, linewidth=0.5)
    
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title(title)
    ax.legend()
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    
    return ax


def plot_inversion_result(ax: plt.Axes, true_model: Optional[VelocityModel],
                          initial_model: VelocityModel,
                          inverted_model: VelocityModel,
                          title: str = 'Inversion Result') -> plt.Axes:
    if true_model is not None:
        im = ax.imshow(inverted_model.velocity - true_model.velocity,
                       cmap='RdBu_r', aspect='auto', origin='upper',
                       extent=[inverted_model.x_coords()[0], inverted_model.x_coords()[-1],
                               inverted_model.z_coords()[-1], inverted_model.z_coords()[0]])
        plt.colorbar(im, ax=ax, label='Velocity Error (m/s)')
        ax.set_title(f'{title}\nDifference from True Model')
    else:
        im = ax.imshow(inverted_model.velocity - initial_model.velocity,
                       cmap='RdBu_r', aspect='auto', origin='upper',
                       extent=[inverted_model.x_coords()[0], inverted_model.x_coords()[-1],
                               inverted_model.z_coords()[-1], inverted_model.z_coords()[0]])
        plt.colorbar(im, ax=ax, label='Velocity Update (m/s)')
        ax.set_title(f'{title}\nUpdate from Initial Model')
    
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    
    return ax


def plot_convergence(ax: plt.Axes, history: List[dict],
                     title: str = 'Convergence History') -> plt.Axes:
    iterations = [h['iteration'] for h in history]
    rms_before = [h['rms_before'] * 1000 for h in history]
    rms_after = [h['rms_after'] * 1000 for h in history]
    
    ax.plot(iterations, rms_before, 'o-', label='RMS before update', linewidth=2)
    ax.plot(iterations, rms_after, 's-', label='RMS after update', linewidth=2)
    
    ax.set_xlabel('Iteration')
    ax.set_ylabel('RMS Residual (ms)')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(iterations)
    
    return ax


def plot_all_results(canvas: FigureCanvas,
                     initial_model: VelocityModel,
                     inverted_model: VelocityModel,
                     true_model: Optional[VelocityModel],
                     data: List[TravelTimeData],
                     history: List[dict],
                     shots: List[Shot],
                     receivers: List[Receiver]):
    fig = canvas.figure
    fig.clear()
    
    gs = fig.add_gridspec(3, 2, hspace=0.4, wspace=0.3)
    
    ax1 = fig.add_subplot(gs[0, 0])
    plot_velocity_model(ax1, initial_model, 'Initial Velocity Model')
    
    ax2 = fig.add_subplot(gs[0, 1])
    plot_velocity_model(ax2, inverted_model, 'Inverted Velocity Model')
    
    ax3 = fig.add_subplot(gs[1, 0])
    plot_inversion_result(ax3, true_model, initial_model, inverted_model, 'Velocity Update')
    
    ax4 = fig.add_subplot(gs[1, 1])
    plot_ray_density(ax4, inverted_model, 'Ray Coverage Density')
    
    ax5 = fig.add_subplot(gs[2, 0])
    plot_residual_histogram(ax5, data, 'Final Travel Time Residuals')
    
    ax6 = fig.add_subplot(gs[2, 1])
    plot_convergence(ax6, history, 'Convergence History')
    
    canvas.draw()


def plot_geometry_only(canvas: FigureCanvas,
                       shots: List[Shot],
                       receivers: List[Receiver],
                       model: VelocityModel):
    fig = canvas.figure
    fig.clear()
    
    ax = fig.add_subplot(111)
    plot_velocity_model(ax, model, 'Velocity Model with Survey Geometry',
                        show_colorbar=True)
    
    sx = [s.x for s in shots]
    sz = [s.z for s in shots]
    rx = [r.x for r in receivers]
    rz = [r.z for r in receivers]
    
    ax.scatter(sx, sz, c='red', marker='*', s=150, edgecolor='white',
               linewidth=1, label='Shots', zorder=10)
    ax.scatter(rx, rz, c='blue', marker='v', s=100, edgecolor='white',
               linewidth=1, label='Receivers', zorder=10)
    
    ax.legend()
    canvas.draw()


def plot_anisotropic_params(canvas: FigureCanvas, model: VelocityModel):
    fig = canvas.figure
    fig.clear()
    
    if not model.is_anisotropic or model.anisotropy is None:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, '模型非各向异性', ha='center', va='center', fontsize=16)
        ax.set_axis_off()
        canvas.draw()
        return
    
    gs = fig.add_gridspec(1, 3, wspace=0.3)
    
    ax1 = fig.add_subplot(gs[0, 0])
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    im1 = ax1.imshow(model.anisotropy.epsilon, extent=extent, cmap='RdBu_r',
                    aspect='auto', origin='upper')
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Z (m)')
    ax1.set_title('Anisotropy ε')
    plt.colorbar(im1, ax=ax1)
    
    ax2 = fig.add_subplot(gs[0, 1])
    im2 = ax2.imshow(model.anisotropy.delta, extent=extent, cmap='RdBu_r',
                    aspect='auto', origin='upper')
    ax2.set_xlabel('X (m)')
    ax2.set_title('Anisotropy δ')
    plt.colorbar(im2, ax=ax2)
    
    ax3 = fig.add_subplot(gs[0, 2])
    im3 = ax3.imshow(model.anisotropy.gamma, extent=extent, cmap='RdBu_r',
                    aspect='auto', origin='upper')
    ax3.set_xlabel('X (m)')
    ax3.set_title('Anisotropy γ')
    plt.colorbar(im3, ax=ax3)
    
    canvas.draw()


def plot_uncertainty(canvas: FigureCanvas, result):
    fig = canvas.figure
    fig.clear()
    
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    
    x_coords = result.velocity_mean.shape[1]
    z_coords = result.velocity_mean.shape[0]
    extent = [0, x_coords, z_coords, 0]
    
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(result.velocity_mean, cmap='jet', aspect='auto', origin='upper')
    ax1.set_title('Mean Velocity')
    plt.colorbar(im1, ax=ax1)
    
    ax2 = fig.add_subplot(gs[0, 1])
    im2 = ax2.imshow(result.velocity_std, cmap='hot_r', aspect='auto', origin='upper')
    ax2.set_title('Velocity Std (m/s)')
    plt.colorbar(im2, ax=ax2)
    
    ax3 = fig.add_subplot(gs[0, 2])
    coefficient_of_variation = result.velocity_std / (result.velocity_mean + 1e-10) * 100
    im3 = ax3.imshow(coefficient_of_variation, cmap='hot_r', aspect='auto', origin='upper')
    ax3.set_title('Coefficient of Variation (%)')
    plt.colorbar(im3, ax=ax3)
    
    ax4 = fig.add_subplot(gs[1, 0])
    im4 = ax4.imshow(result.velocity_percentile_5, cmap='jet', aspect='auto', origin='upper')
    ax4.set_title('5th Percentile')
    plt.colorbar(im4, ax=ax4)
    
    ax5 = fig.add_subplot(gs[1, 1])
    im5 = ax5.imshow(result.velocity_percentile_95, cmap='jet', aspect='auto', origin='upper')
    ax5.set_title('95th Percentile')
    plt.colorbar(im5, ax=ax5)
    
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.hist(result.rms_distribution * 1000, bins=20, edgecolor='black', alpha=0.7)
    ax6.axvline(result.rms_mean * 1000, color='red', linestyle='--', 
                label=f'Mean={result.rms_mean*1000:.2f} ms')
    ax6.set_xlabel('RMS Residual (ms)')
    ax6.set_ylabel('Frequency')
    ax6.set_title(f'RMS Distribution (n={result.n_samples})')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    canvas.draw()


def plot_fwi_gradient(canvas: FigureCanvas, gradient: np.ndarray,
                      model: VelocityModel, objective_history: List[float] = None):
    fig = canvas.figure
    fig.clear()
    
    gs = fig.add_gridspec(1, 2, wspace=0.3)
    
    ax1 = fig.add_subplot(gs[0, 0])
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    max_grad = np.abs(gradient).max()
    im1 = ax1.imshow(gradient, extent=extent, cmap='RdBu_r',
                    aspect='auto', origin='upper',
                    vmin=-max_grad, vmax=max_grad)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Z (m)')
    ax1.set_title('FWI Gradient')
    plt.colorbar(im1, ax=ax1, label='∂J/∂v')
    
    if objective_history and len(objective_history) > 1:
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(range(1, len(objective_history) + 1), objective_history, 'o-', linewidth=2)
        ax2.set_xlabel('Iteration')
        ax2.set_ylabel('Objective Function')
        ax2.set_title('FWI Convergence')
        ax2.grid(True, alpha=0.3)
        ax2.set_yscale('log' if min(objective_history) > 0 else 'linear')
    
    canvas.draw()


def plot_wavefield_snapshot(canvas: FigureCanvas, wavefield: np.ndarray,
                             model: VelocityModel, shot: Shot = None,
                             receivers: List[Receiver] = None):
    fig = canvas.figure
    fig.clear()
    
    ax = fig.add_subplot(111)
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    max_amp = np.abs(wavefield).max()
    im = ax.imshow(wavefield, extent=extent, cmap='seismic',
                   aspect='auto', origin='upper',
                   vmin=-max_amp, vmax=max_amp)
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title('Wavefield Snapshot')
    plt.colorbar(im, ax=ax, label='Pressure')
    
    if shot is not None:
        ax.scatter(shot.x, shot.z, c='red', marker='*', s=200, 
                   edgecolor='white', linewidth=2, label='Source', zorder=10)
    
    if receivers is not None:
        rx = [r.x for r in receivers]
        rz = [r.z for r in receivers]
        ax.scatter(rx, rz, c='blue', marker='v', s=100,
                   edgecolor='white', linewidth=1, label='Receivers', zorder=10)
    
    if shot is not None or receivers is not None:
        ax.legend()
    
    canvas.draw()


def plot_seismograms(canvas: FigureCanvas, seismograms: np.ndarray,
                     receivers: List[Receiver] = None, dt: float = 0.001):
    fig = canvas.figure
    fig.clear()
    
    ax = fig.add_subplot(111)
    n_rec = seismograms.shape[1]
    n_time = seismograms.shape[0]
    times = np.arange(n_time) * dt
    
    spacing = np.max(np.abs(seismograms)) * 2
    
    for i in range(n_rec):
        trace = seismograms[:, i] + i * spacing
        ax.plot(trace, times, 'k-', linewidth=0.5)
        ax.fill_betweenx(times, i * spacing, trace,
                        where=trace > i * spacing, color='black', alpha=0.5)
    
    ax.set_ylabel('Time (s)')
    ax.set_xlabel('Receiver Number')
    ax.set_title('Seismogram Gather')
    ax.invert_yaxis()
    
    if receivers is not None:
        ax.set_xticks(np.arange(n_rec) * spacing)
        ax.set_xticklabels([f'{r.id}' for r in receivers])
    
    canvas.draw()


def plot_vti_velocity(canvas: FigureCanvas, model: VelocityModel, angles: List[float] = None):
    if not model.is_anisotropic or model.anisotropy is None:
        fig = canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, '模型非各向异性', ha='center', va='center', fontsize=16)
        ax.set_axis_off()
        canvas.draw()
        return
    
    if angles is None:
        angles = [0, 30, 45, 60, 90]
    
    fig = canvas.figure
    fig.clear()
    
    n_plots = len(angles)
    n_cols = min(3, n_plots)
    n_rows = (n_plots + n_cols - 1) // n_cols
    
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.3, wspace=0.3)
    
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    vmin = model.velocity.min()
    vmax = model.velocity.max() * 1.5
    
    for i, angle_deg in enumerate(angles):
        ax = fig.add_subplot(gs[i // n_cols, i % n_cols])
        
        angle_rad = np.deg2rad(angle_deg)
        v = np.zeros_like(model.velocity)
        
        for iz in range(model.nz):
            for ix in range(model.nx):
                v0 = model.velocity[iz, ix]
                eps = model.anisotropy.epsilon[iz, ix]
                delta = model.anisotropy.delta[iz, ix]
                from .anisotropic import vti_phase_velocity
                v[iz, ix] = vti_phase_velocity(angle_rad, v0, eps, delta)
        
        im = ax.imshow(v, extent=extent, cmap='jet', aspect='auto',
                       origin='upper', vmin=vmin, vmax=vmax)
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Z (m)')
        ax.set_title(f'Phase Velocity at {angle_deg}°')
        plt.colorbar(im, ax=ax, label='Velocity (m/s)')
    
    canvas.draw()

