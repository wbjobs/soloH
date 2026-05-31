"""
VTK output and visualization utilities.
"""

import os
import numpy as np
from dolfin import *
import pyvista as pv
import meshio
from typing import Optional, List, Union
import matplotlib.pyplot as plt


class VTKWriter:
    """
    Writes thermal conductivity and temperature fields to VTK format.
    Supports both XDMF (FEniCS native) and legacy VTK formats.
    """

    def __init__(self, output_dir: str = "output"):
        """
        Initialize VTK writer.

        Parameters
        ----------
        output_dir : str
            Output directory for VTK files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def write_conductivity(self, k: Function, filename: str,
                           name: str = "thermal_conductivity"):
        """
        Write thermal conductivity field to VTK file.

        Parameters
        ----------
        k : dolfin.Function
            Thermal conductivity field
        filename : str
            Output filename (without extension)
        name : str, optional
            Field name in VTK file
        """
        filepath = os.path.join(self.output_dir, filename + ".vtk")

        mesh = k.function_space().mesh()
        dim = mesh.topology().dim()

        coords = mesh.coordinates()
        cell_list = []
        cell_types = []

        if dim == 2:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("triangle", cell_array)]
        else:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("tetra", cell_array)]

        k_values = k.compute_vertex_values(mesh)

        meshio_mesh = meshio.Mesh(
            points=coords,
            cells=cell_block,
            point_data={name: k_values}
        )

        meshio.write(filepath, meshio_mesh)
        print(f"Thermal conductivity saved to: {filepath}")

        return filepath

    def write_temperature(self, T: Function, filename: str,
                          name: str = "temperature"):
        """
        Write temperature field to VTK file.

        Parameters
        ----------
        T : dolfin.Function
            Temperature field
        filename : str
            Output filename (without extension)
        name : str, optional
            Field name in VTK file
        """
        filepath = os.path.join(self.output_dir, filename + ".vtk")

        mesh = T.function_space().mesh()
        dim = mesh.topology().dim()

        coords = mesh.coordinates()
        cell_list = []

        if dim == 2:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("triangle", cell_array)]
        else:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("tetra", cell_array)]

        T_values = T.compute_vertex_values(mesh)

        meshio_mesh = meshio.Mesh(
            points=coords,
            cells=cell_block,
            point_data={name: T_values}
        )

        meshio.write(filepath, meshio_mesh)
        print(f"Temperature field saved to: {filepath}")

        return filepath

    def write_transient(self, T_solutions: List[Function], times: np.ndarray,
                        filename: str, name: str = "temperature"):
        """
        Write transient temperature field to PVD format (time series).

        Parameters
        ----------
        T_solutions : list of Functions
            Temperature fields at each time step
        times : np.ndarray
            Time points
        filename : str
            Output filename (without extension)
        name : str, optional
            Field name
        """
        filepath = os.path.join(self.output_dir, filename + ".pvd")

        with XDMFFile(os.path.join(self.output_dir, filename + ".xdmf")) as f:
            f.parameters["flush_output"] = True
            f.parameters["functions_share_mesh"] = True

            for i, T in enumerate(T_solutions):
                f.write_checkpoint(T, name, times[i], XDMFFile.Encoding.HDF5, append=(i > 0))

        print(f"Transient solution saved to: {filepath}")
        return filepath

    def write_combined(self, k: Function, T: Function, filename: str,
                       uncertainty: Optional[Function] = None):
        """
        Write multiple fields to a single VTK file.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T : Function
            Temperature
        filename : str
            Output filename
        uncertainty : Function, optional
            Uncertainty field (standard deviation)
        """
        filepath = os.path.join(self.output_dir, filename + ".vtk")

        mesh = k.function_space().mesh()
        dim = mesh.topology().dim()

        coords = mesh.coordinates()
        cell_list = []

        if dim == 2:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("triangle", cell_array)]
        else:
            for cell in cells(mesh):
                vertices = cell.entities(0)
                cell_list.append(vertices)
            cell_array = np.array(cell_list)
            cell_block = [("tetra", cell_array)]

        point_data = {
            "thermal_conductivity": k.compute_vertex_values(mesh),
            "temperature": T.compute_vertex_values(mesh)
        }

        if uncertainty is not None:
            point_data["conductivity_std_dev"] = uncertainty.compute_vertex_values(mesh)

        meshio_mesh = meshio.Mesh(
            points=coords,
            cells=cell_block,
            point_data=point_data
        )

        meshio.write(filepath, meshio_mesh)
        print(f"Combined results saved to: {filepath}")

        return filepath


class ResultsVisualizer:
    """Visualization utilities for inverse problem results."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_conductivity_2d(self, k: Function, filename: str = "conductivity.png",
                             title: str = "Thermal Conductivity",
                             cmap: str = "viridis"):
        """Plot 2D thermal conductivity field."""
        plt.figure(figsize=(10, 8))
        p = plot(k, cmap=cmap, title=title)
        plt.colorbar(p, label='k (W/m·K)')
        plt.xlabel('x (m)')
        plt.ylabel('y (m)')
        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Conductivity plot saved to: {filepath}")
        return filepath

    def plot_temperature_2d(self, T: Function, filename: str = "temperature.png",
                            title: str = "Temperature",
                            cmap: str = "hot"):
        """Plot 2D temperature field."""
        plt.figure(figsize=(10, 8))
        p = plot(T, cmap=cmap, title=title)
        plt.colorbar(p, label='T (K)')
        plt.xlabel('x (m)')
        plt.ylabel('y (m)')
        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Temperature plot saved to: {filepath}")
        return filepath

    def plot_uncertainty_2d(self, sigma: Function, filename: str = "uncertainty.png",
                            title: str = "Conductivity Uncertainty (1σ)",
                            cmap: str = "Reds"):
        """Plot 2D uncertainty field."""
        plt.figure(figsize=(10, 8))
        p = plot(sigma, cmap=cmap, title=title)
        plt.colorbar(p, label='σ (W/m·K)')
        plt.xlabel('x (m)')
        plt.ylabel('y (m)')
        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Uncertainty plot saved to: {filepath}")
        return filepath

    def plot_optimization_history(self, J_history: List[float],
                                  grad_history: Optional[List[float]] = None,
                                  filename: str = "convergence.png"):
        """Plot optimization convergence history."""
        fig, ax1 = plt.subplots(figsize=(10, 6))

        color = 'tab:blue'
        ax1.set_xlabel('Iteration')
        ax1.set_ylabel('Objective J', color=color)
        ax1.semilogy(J_history, color=color, marker='o', markersize=3, label='J')
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.grid(True, alpha=0.3)

        if grad_history is not None:
            ax2 = ax1.twinx()
            color = 'tab:red'
            ax2.set_ylabel('||∇J||', color=color)
            ax2.semilogy(grad_history, color=color, marker='s', markersize=3, label='||∇J||')
            ax2.tick_params(axis='y', labelcolor=color)

        plt.title('Optimization Convergence History')
        fig.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Convergence plot saved to: {filepath}")
        return filepath

    def plot_measured_vs_simulated(self, T_meas: np.ndarray, T_sim: np.ndarray,
                                   std_dev: Optional[np.ndarray] = None,
                                   filename: str = "meas_vs_sim.png"):
        """Plot measured vs simulated temperatures."""
        plt.figure(figsize=(8, 8))

        min_val = min(T_meas.min(), T_sim.min())
        max_val = max(T_meas.max(), T_sim.max())

        plt.plot([min_val, max_val], [min_val, max_val], 'k--', label='Perfect agreement')

        if std_dev is not None:
            plt.errorbar(T_meas, T_sim, yerr=std_dev, fmt='o', alpha=0.6,
                         label='Measurements')
        else:
            plt.scatter(T_meas, T_sim, alpha=0.6, label='Measurements')

        plt.xlabel('Measured Temperature (K)')
        plt.ylabel('Simulated Temperature (K)')
        plt.title('Measured vs Simulated Temperatures')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.axis('equal')

        rmse = np.sqrt(np.mean((T_meas - T_sim)**2))
        plt.figtext(0.02, 0.02, f'RMSE = {rmse:.4f} K', fontsize=10)

        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Measurement comparison plot saved to: {filepath}")
        return filepath

    def plot_transient_comparison(self, times: np.ndarray, T_meas: np.ndarray,
                                  T_sim: np.ndarray, point_idx: int = 0,
                                  filename: str = "transient_comparison.png"):
        """Plot transient temperature comparison at a measurement point."""
        plt.figure(figsize=(10, 6))
        plt.plot(times, T_meas, 'o-', label='Measured', markersize=4)
        plt.plot(times, T_sim, 's--', label='Simulated', markersize=4)
        plt.xlabel('Time (s)')
        plt.ylabel('Temperature (K)')
        plt.title(f'Transient Comparison at Measurement Point {point_idx}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Transient comparison plot saved to: {filepath}")
        return filepath
