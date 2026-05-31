import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import Normalize, LinearSegmentedColormap
from typing import Optional, List, Tuple, Union
import os

plt.style.use('seaborn-v0_8-whitegrid')


seismic_cmap = LinearSegmentedColormap.from_list(
    'seismic',
    [(0.0, 0.0, 0.3), (0.0, 0.0, 0.7), (0.8, 0.9, 1.0),
     (1.0, 0.9, 0.8), (0.7, 0.0, 0.0), (0.3, 0.0, 0.0)]
)


def plot_wiggle(data: np.ndarray, time_axis: Optional[np.ndarray] = None,
                offset_axis: Optional[np.ndarray] = None,
                ax: Optional[plt.Axes] = None,
                scale: float = 0.8,
                color: str = 'black',
                fill_positive: bool = True,
                fill_negative: bool = True,
                positive_color: str = 'red',
                negative_color: str = 'blue',
                title: Optional[str] = None,
                xlabel: Optional[str] = None,
                ylabel: Optional[str] = None,
                linewidth: float = 0.5,
                invert_y: bool = True) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 8))
    
    nrec, nt = data.shape
    
    if time_axis is None:
        time_axis = np.arange(nt)
    
    if offset_axis is None:
        offset_axis = np.arange(nrec)
    
    dx = np.mean(np.diff(offset_axis))
    
    max_amp = np.max(np.abs(data))
    if max_amp == 0:
        max_amp = 1.0
    
    trace_scale = scale * dx / max_amp
    
    for i in range(nrec):
        trace = data[i] * trace_scale + offset_axis[i]
        
        ax.plot(trace, time_axis, color=color, linewidth=linewidth)
        
        if fill_positive:
            mask = trace > offset_axis[i]
            ax.fill_betweenx(time_axis, trace, offset_axis[i],
                            where=mask, color=positive_color, alpha=0.3)
        
        if fill_negative:
            mask = trace < offset_axis[i]
            ax.fill_betweenx(time_axis, trace, offset_axis[i],
                            where=mask, color=negative_color, alpha=0.3)
    
    if invert_y:
        ax.invert_yaxis()
    
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold')
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    
    ax.tick_params(axis='both', labelsize=9)
    
    return ax


def plot_seismogram(data: np.ndarray, time_axis: Optional[np.ndarray] = None,
                    ax: Optional[plt.Axes] = None,
                    components: Optional[List[str]] = None,
                    title: Optional[str] = None,
                    xlabel: str = 'Time (s)',
                    ylabel: str = 'Amplitude',
                    normalize: bool = True) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
    
    if time_axis is None:
        time_axis = np.arange(len(data))
    
    if components is None:
        components = ['']
    
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    
    if data.ndim == 1:
        data = data.reshape(1, -1)
    
    for i, (trace, comp) in enumerate(zip(data, components)):
        if normalize and np.max(np.abs(trace)) > 0:
            trace = trace / np.max(np.abs(trace))
        
        ax.plot(time_axis, trace, label=comp, color=colors[i % len(colors)], linewidth=1)
    
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    if title:
        ax.set_title(title, fontsize=13, fontweight='bold')
    if len(components) > 1:
        ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', labelsize=10)
    
    return ax


def plot_snapshot(field: np.ndarray, x_axis: Optional[np.ndarray] = None,
                  z_axis: Optional[np.ndarray] = None,
                  ax: Optional[plt.Axes] = None,
                  cmap: str = 'seismic',
                  vmin: Optional[float] = None,
                  vmax: Optional[float] = None,
                  clip_percentile: float = 99.0,
                  title: Optional[str] = None,
                  xlabel: str = 'X (m)',
                  ylabel: str = 'Z (m)',
                  add_colorbar: bool = True,
                  colorbar_label: str = 'Amplitude',
                  invert_y: bool = True) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 8))
    
    if x_axis is None:
        x_axis = np.arange(field.shape[1])
    if z_axis is None:
        z_axis = np.arange(field.shape[0])
    
    if vmin is None or vmax is None:
        clip_val = np.percentile(np.abs(field), clip_percentile)
        if vmin is None:
            vmin = -clip_val
        if vmax is None:
            vmax = clip_val
    
    im = ax.pcolormesh(x_axis, z_axis, field, cmap=cmap, vmin=vmin, vmax=vmax, shading='auto')
    
    if invert_y:
        ax.invert_yaxis()
    
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.tick_params(axis='both', labelsize=9)
    
    if add_colorbar:
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(colorbar_label, fontsize=9)
        cbar.ax.tick_params(labelsize=8)
    
    return ax


def animate_snapshots(snapshots: List[dict], field_name: str = 'vx',
                      x_axis: Optional[np.ndarray] = None,
                      z_axis: Optional[np.ndarray] = None,
                      output_file: Optional[str] = None,
                      fps: int = 10,
                      dpi: int = 100,
                      cmap: str = 'seismic',
                      clip_percentile: float = 99.0,
                      title: Optional[str] = None,
                      figsize: Tuple[int, int] = (10, 8),
                      use_blit: bool = False) -> animation.Animation:
    if not snapshots:
        raise ValueError("No snapshots provided")
    
    fig, ax = plt.subplots(figsize=figsize)
    
    all_data = np.array([s[field_name] for s in snapshots])
    clip_val = np.percentile(np.abs(all_data), clip_percentile)
    vmin, vmax = -clip_val, clip_val
    
    if x_axis is None:
        x_axis = np.arange(snapshots[0][field_name].shape[1])
    if z_axis is None:
        z_axis = np.arange(snapshots[0][field_name].shape[0])
    
    im = ax.pcolormesh(x_axis, z_axis, snapshots[0][field_name],
                       cmap=cmap, vmin=vmin, vmax=vmax, shading='auto')
    
    ax.invert_yaxis()
    ax.set_xlabel('X (m)', fontsize=10)
    ax.set_ylabel('Z (m)', fontsize=10)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Amplitude', fontsize=9)
    
    time_label = ax.text(0.02, 0.98, '', transform=ax.transAxes,
                        va='top', ha='left', fontsize=11, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                  edgecolor='gray', alpha=0.9))
    
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold')
    
    def update(frame):
        data = snapshots[frame][field_name]
        im.set_array(data.ravel())
        time_str = f"Time: {snapshots[frame]['time']*1000:.1f} ms"
        time_label.set_text(time_str)
        
        time_label.set_visible(False)
        time_label.set_visible(True)
        
        if use_blit:
            return im, time_label
        else:
            return [im, time_label]
    
    ani = animation.FuncAnimation(fig, update, frames=len(snapshots),
                                  interval=max(1000/fps, 50), blit=use_blit)
    
    if output_file:
        if output_file.endswith('.gif'):
            writer = animation.PillowWriter(fps=min(fps, 30))
        elif output_file.endswith('.mp4'):
            try:
                writer = animation.FFMpegWriter(fps=min(fps, 30), bitrate=5000)
            except:
                writer = animation.PillowWriter(fps=min(fps, 30))
        else:
            writer = animation.PillowWriter(fps=min(fps, 30))
        
        ani.save(output_file, writer=writer, dpi=dpi)
        print(f"Animation saved to {output_file}")
    
    return ani


def plot_particle_motion(displacement_x: np.ndarray,
                         displacement_z: np.ndarray,
                         time_axis: Optional[np.ndarray] = None,
                         ax: Optional[plt.Axes] = None,
                         colormap: str = 'viridis',
                         show_colorbar: bool = True,
                         title: Optional[str] = None,
                         xlabel: str = 'X displacement (m)',
                         ylabel: str = 'Z displacement (m)',
                         equal_aspect: bool = True,
                         show_arrow: bool = True) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))
    
    if time_axis is None:
        time_axis = np.arange(len(displacement_x))
    
    points = np.array([displacement_x, displacement_z]).T
    segments = np.array([points[i:i+2] for i in range(len(points)-1)])
    
    norm = Normalize(vmin=time_axis[0], vmax=time_axis[-1])
    
    from matplotlib.collections import LineCollection
    lc = LineCollection(segments, cmap=colormap, norm=norm, linewidth=1.5)
    lc.set_array(time_axis[:-1])
    ax.add_collection(lc)
    
    if show_colorbar:
        cbar = plt.colorbar(lc, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Time (s)', fontsize=9)
    
    ax.scatter(displacement_x[0], displacement_z[0],
               c='green', s=80, label='Start', zorder=5)
    ax.scatter(displacement_x[-1], displacement_z[-1],
               c='red', s=80, label='End', zorder=5)
    
    if show_arrow and len(displacement_x) > 1:
        mid = len(displacement_x) // 2
        dx_dir = displacement_x[mid+1] - displacement_x[mid]
        dz_dir = displacement_z[mid+1] - displacement_z[mid]
        ax.annotate('', xy=(displacement_x[mid] + dx_dir, displacement_z[mid] + dz_dir),
                   xytext=(displacement_x[mid], displacement_z[mid]),
                   arrowprops=dict(arrowstyle='->', color='black', lw=2))
    
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    if title:
        ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', labelsize=10)
    
    if equal_aspect:
        ax.set_aspect('equal', adjustable='datalim')
    
    return ax


def plot_polarization_ellipse(cov_matrix: np.ndarray,
                              ax: Optional[plt.Axes] = None,
                              n_points: int = 100,
                              color: str = 'red',
                              alpha: float = 0.5,
                              show_axes: bool = True) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))
    
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    theta = np.linspace(0, 2 * np.pi, n_points)
    ellipse = np.zeros((2, n_points))
    for i, angle in enumerate(theta):
        ellipse[:, i] = (np.sqrt(eigenvalues[0]) * np.cos(angle) * eigenvectors[:, 0] +
                        np.sqrt(eigenvalues[1]) * np.sin(angle) * eigenvectors[:, 1])
    
    ax.fill(ellipse[0], ellipse[1], color=color, alpha=alpha)
    ax.plot(ellipse[0], ellipse[1], color=color, linewidth=2)
    
    if show_axes:
        for i in range(2):
            scale = np.sqrt(eigenvalues[i])
            ax.plot([0, scale * eigenvectors[0, i]],
                   [0, scale * eigenvectors[1, i]],
                   'k--', linewidth=2, label=f'Eigenvalue {i+1}: {eigenvalues[i]:.4e}')
    
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    return ax


def plot_velocity_model(vp: np.ndarray, vs: Optional[np.ndarray] = None,
                        rho: Optional[np.ndarray] = None,
                        x_axis: Optional[np.ndarray] = None,
                        z_axis: Optional[np.ndarray] = None,
                        output_file: Optional[str] = None,
                        dpi: int = 100,
                        invert_y: bool = True) -> plt.Figure:
    if vs is None and rho is None:
        fig, ax = plt.subplots(figsize=(12, 6))
        plot_snapshot(vp, x_axis, z_axis, ax=ax, cmap='jet',
                     colorbar_label='Vp (m/s)', title='P-wave Velocity',
                     invert_y=invert_y)
    else:
        n_plots = 1 + (vs is not None) + (rho is not None)
        fig, axes = plt.subplots(1, n_plots, figsize=(6*n_plots, 6))
        if n_plots == 1:
            axes = [axes]
        
        idx = 0
        plot_snapshot(vp, x_axis, z_axis, ax=axes[idx], cmap='jet',
                     colorbar_label='Vp (m/s)', title='P-wave Velocity',
                     invert_y=invert_y)
        idx += 1
        
        if vs is not None:
            plot_snapshot(vs, x_axis, z_axis, ax=axes[idx], cmap='jet',
                         colorbar_label='Vs (m/s)', title='S-wave Velocity',
                         invert_y=invert_y)
            idx += 1
        
        if rho is not None:
            plot_snapshot(rho, x_axis, z_axis, ax=axes[idx], cmap='jet',
                         colorbar_label='Density (kg/m³)', title='Density',
                         invert_y=invert_y)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
        print(f"Velocity model plot saved to {output_file}")
    
    return fig


def plot_wavelet(wavelet: np.ndarray, time_axis: np.ndarray,
                 spectrum: Optional[Tuple[np.ndarray, np.ndarray]] = None,
                 output_file: Optional[str] = None,
                 dpi: int = 100) -> plt.Figure:
    if spectrum is not None:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    else:
        fig, ax1 = plt.subplots(figsize=(8, 5))
    
    ax1.plot(time_axis * 1000, wavelet, 'b-', linewidth=2)
    ax1.set_xlabel('Time (ms)', fontsize=11)
    ax1.set_ylabel('Amplitude', fontsize=11)
    ax1.set_title('Ricker Wavelet', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='both', labelsize=10)
    
    if spectrum is not None:
        freqs, spec = spectrum
        spec = spec / np.max(spec)
        ax2.plot(freqs, spec, 'r-', linewidth=2)
        ax2.set_xlabel('Frequency (Hz)', fontsize=11)
        ax2.set_ylabel('Normalized Amplitude', fontsize=11)
        ax2.set_title('Amplitude Spectrum', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='both', labelsize=10)
        ax2.set_xlim(0, freqs[-1] // 2)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
        print(f"Wavelet plot saved to {output_file}")
    
    return fig


def plot_shot_gather_comparison(receivers, components: List[str] = ['vx', 'vz'],
                                output_file: Optional[str] = None,
                                dpi: int = 100,
                                scale: float = 0.8,
                                invert_y: bool = True) -> plt.Figure:
    n_comp = len(components)
    fig, axes = plt.subplots(1, n_comp, figsize=(6*n_comp, 8))
    if n_comp == 1:
        axes = [axes]
    
    time_axis = receivers.get_time_axis() * 1000
    offset_axis = receivers.get_offset_axis()
    
    for ax, comp in zip(axes, components):
        data = receivers.get_seismogram(comp)
        plot_wiggle(data, time_axis=time_axis, offset_axis=offset_axis,
                   ax=ax, scale=scale, title=f'{comp.upper()} Component',
                   xlabel='Offset (m)', ylabel='Time (ms)',
                   invert_y=invert_y)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
        print(f"Shot gather plot saved to {output_file}")
    
    return fig


def create_summary_figure(results: dict, output_dir: str, dpi: int = 150) -> None:
    os.makedirs(output_dir, exist_ok=True)
    
    config = results['config']
    receivers = results['receivers']
    snapshots = results['snapshots']
    source = results['source']
    medium = results['medium']
    
    x_axis = config.get_axis('x')
    z_axis = config.get_axis('z')
    
    vp = medium.get_velocity('p')
    vs = medium.get_velocity('s')
    plot_velocity_model(vp, vs, medium.rho_field, x_axis, z_axis,
                       output_file=os.path.join(output_dir, 'velocity_model.png'),
                       dpi=dpi)
    
    freqs, spec = source.get_wavelet_spectrum()
    plot_wavelet(source.wavelet, config.get_axis('t'), (freqs, spec),
                output_file=os.path.join(output_dir, 'source_wavelet.png'),
                dpi=dpi)
    
    plot_shot_gather_comparison(receivers, ['vx', 'vz', 'pressure'],
                               output_file=os.path.join(output_dir, 'shot_gather.png'),
                               dpi=dpi)
    
    if snapshots:
        for field_name in ['vx', 'vz', 'tau_xx', 'tau_zz', 'tau_xz']:
            mid_idx = len(snapshots) // 2
            snapshot = snapshots[mid_idx]
            
            fig, ax = plt.subplots(figsize=(10, 8))
            plot_snapshot(snapshot[field_name], x_axis, z_axis, ax=ax,
                         title=f'{field_name.upper()} at t={snapshot["time"]*1000:.1f} ms',
                         colorbar_label='Amplitude')
            
            output_file = os.path.join(output_dir, f'snapshot_{field_name}.png')
            plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
            plt.close(fig)
            print(f"Snapshot {field_name} saved to {output_file}")
    
    if 'particle_motion' in results:
        pm = results['particle_motion']
        n_points = len(pm.points)
        
        for i in range(n_points):
            dx, dz = pm.get_particle_motion(i)
            fig, ax = plt.subplots(figsize=(8, 8))
            plot_particle_motion(dx, dz, pm.get_time_axis(), ax=ax,
                               title=f'Particle Motion at {pm.point_positions[i]}')
            
            output_file = os.path.join(output_dir, f'particle_motion_{i}.png')
            plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
            plt.close(fig)
            print(f"Particle motion {i} saved to {output_file}")
    
    print(f"\nAll summary figures saved to {output_dir}")
