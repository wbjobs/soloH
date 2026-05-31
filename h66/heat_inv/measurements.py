"""
Measurement data handling for inverse heat conduction problems.
"""

import os
import numpy as np
import h5py
from dataclasses import dataclass, field
from typing import List, Optional, Union
from dolfin import *


@dataclass
class MeasurementPoint:
    """Represents a single temperature measurement point."""
    x: float
    y: float
    z: float = 0.0
    temperature: Optional[float] = None
    time_series: Optional[np.ndarray] = None
    times: Optional[np.ndarray] = None
    std_dev: float = 1.0
    point_id: int = 0

    @property
    def is_transient(self):
        """Check if measurement is transient (time series)."""
        return self.time_series is not None and self.times is not None

    def get_temperature_at(self, t):
        """Get temperature at a specific time."""
        if not self.is_transient:
            return self.temperature
        return np.interp(t, self.times, self.time_series)

    def as_array(self):
        """Get coordinates as numpy array."""
        return np.array([self.x, self.y, self.z])


class MeasurementData:
    """
    Handles temperature measurement data for inverse problems.

    Supports both steady-state (single temperature per point) and
    transient (time series) measurements.
    """

    def __init__(self):
        self.points: List[MeasurementPoint] = []
        self._is_transient = False
        self._time_grid: Optional[np.ndarray] = None

    @property
    def is_transient(self):
        """Check if data contains transient measurements."""
        return self._is_transient

    @property
    def time_grid(self):
        """Get the common time grid for transient measurements."""
        return self._time_grid

    @property
    def num_points(self):
        """Number of measurement points."""
        return len(self.points)

    def add_point(self, x, y, z=0.0, temperature=None, time_series=None,
                  times=None, std_dev=1.0):
        """
        Add a measurement point.

        Parameters
        ----------
        x, y, z : float
            Spatial coordinates
        temperature : float, optional
            Steady-state temperature measurement
        time_series : np.ndarray, optional
            Temperature time series for transient measurement
        times : np.ndarray, optional
            Time points corresponding to time_series
        std_dev : float, optional
            Standard deviation of measurement noise
        """
        point = MeasurementPoint(
            x=x, y=y, z=z,
            temperature=temperature,
            time_series=time_series,
            times=times,
            std_dev=std_dev,
            point_id=len(self.points)
        )

        if point.is_transient:
            self._is_transient = True
            if self._time_grid is None:
                self._time_grid = times.copy()
            else:
                if not np.allclose(self._time_grid, times):
                    raise ValueError("All transient measurements must share the same time grid")

        self.points.append(point)
        return point

    def generate_synthetic(self, geometry_handler, num_points=10, mode='random',
                           true_k=None, forward_solver=None, noise_std=0.5,
                           transient=False, t_start=0, t_end=10, num_times=20):
        """
        Generate synthetic measurement data for testing.

        Parameters
        ----------
        geometry_handler : GeometryHandler
            Geometry handler with mesh
        num_points : int
            Number of measurement points to generate
        mode : str
            'random' for random interior points, 'grid' for structured grid
        true_k : float or dolfin.Function
            True thermal conductivity for forward simulation
        forward_solver : HeatForwardSolver
            Forward solver to generate synthetic data
        noise_std : float
            Standard deviation of Gaussian noise to add
        transient : bool
            Generate transient measurements
        t_start, t_end : float
            Time range for transient data
        num_times : int
            Number of time steps for transient data
        """
        mesh = geometry_handler.mesh
        dim = mesh.topology().dim()

        if mode == 'random':
            points = self._generate_random_points(mesh, num_points, dim)
        else:
            points = self._generate_grid_points(mesh, num_points, dim)

        if forward_solver is not None and true_k is not None:
            if transient:
                times = np.linspace(t_start, t_end, num_times)
                self._time_grid = times
                self._is_transient = True

                T_all = forward_solver.solve_transient(true_k, times=times)

                for i, (x, y, z) in enumerate(points):
                    time_series = np.array([
                        self._evaluate_function(T_all[j], x, y, z, dim)
                        for j in range(len(times))
                    ])
                    noise = np.random.normal(0, noise_std, time_series.shape)
                    self.add_point(x, y, z, time_series=time_series + noise,
                                   times=times, std_dev=noise_std)
            else:
                T = forward_solver.solve(true_k)

                for x, y, z in points:
                    temp = self._evaluate_function(T, x, y, z, dim)
                    noise = np.random.normal(0, noise_std)
                    self.add_point(x, y, z, temperature=temp + noise, std_dev=noise_std)
        else:
            for x, y, z in points:
                self.add_point(x, y, z, temperature=0.0, std_dev=noise_std)

        print(f"Generated {num_points} synthetic measurement points"
              f"{' (transient)' if transient else ''}")
        return self.points

    def _generate_random_points(self, mesh, num_points, dim):
        """Generate random interior points."""
        points = []
        bbox = mesh.bounding_box_tree()
        attempts = 0
        max_attempts = num_points * 100

        coords = mesh.coordinates()
        min_coords = coords.min(axis=0)
        max_coords = coords.max(axis=0)

        while len(points) < num_points and attempts < max_attempts:
            attempts += 1
            if dim == 2:
                x = np.random.uniform(min_coords[0], max_coords[0])
                y = np.random.uniform(min_coords[1], max_coords[1])
                z = 0.0
                pt = Point(x, y)
            else:
                x = np.random.uniform(min_coords[0], max_coords[0])
                y = np.random.uniform(min_coords[1], max_coords[1])
                z = np.random.uniform(min_coords[2], max_coords[2])
                pt = Point(x, y, z)

            if bbox.compute_first_entity_collision(pt) < mesh.num_cells():
                points.append((x, y, z))

        return points

    def _generate_grid_points(self, mesh, num_points, dim):
        """Generate structured grid of points."""
        coords = mesh.coordinates()
        min_coords = coords.min(axis=0)
        max_coords = coords.max(axis=0)

        n_per_dim = int(np.ceil(num_points ** (1 / dim)))
        points = []
        bbox = mesh.bounding_box_tree()

        if dim == 2:
            xs = np.linspace(min_coords[0], max_coords[0], n_per_dim + 2)[1:-1]
            ys = np.linspace(min_coords[1], max_coords[1], n_per_dim + 2)[1:-1]
            for x in xs:
                for y in ys:
                    if len(points) >= num_points:
                        break
                    pt = Point(x, y)
                    if bbox.compute_first_entity_collision(pt) < mesh.num_cells():
                        points.append((x, y, 0.0))
        else:
            xs = np.linspace(min_coords[0], max_coords[0], n_per_dim + 2)[1:-1]
            ys = np.linspace(min_coords[1], max_coords[1], n_per_dim + 2)[1:-1]
            zs = np.linspace(min_coords[2], max_coords[2], n_per_dim + 2)[1:-1]
            for x in xs:
                for y in ys:
                    for z in zs:
                        if len(points) >= num_points:
                            break
                        pt = Point(x, y, z)
                        if bbox.compute_first_entity_collision(pt) < mesh.num_cells():
                            points.append((x, y, z))

        return points

    def _evaluate_function(self, func, x, y, z, dim):
        """Evaluate FEniCS function at a point."""
        try:
            if dim == 2:
                return func(Point(x, y))
            else:
                return func(Point(x, y, z))
        except Exception:
            tree = func.function_space().mesh().bounding_box_tree()
            pt = Point(x, y) if dim == 2 else Point(x, y, z)
            cell_id = tree.compute_first_entity_collision(pt)
            if cell_id < func.function_space().mesh().num_cells():
                return func(pt)
            return 0.0

    def get_measurement_vector(self, time_idx=None):
        """
        Get measurements as a numpy array.

        Parameters
        ----------
        time_idx : int, optional
            Time index for transient data

        Returns
        -------
        np.ndarray
            Measurement values
        """
        if self._is_transient and time_idx is not None:
            return np.array([p.time_series[time_idx] for p in self.points])
        else:
            return np.array([p.temperature for p in self.points])

    def get_std_dev_vector(self):
        """Get measurement standard deviations as numpy array."""
        return np.array([p.std_dev for p in self.points])

    def get_coordinates(self):
        """Get measurement point coordinates as numpy array."""
        return np.array([[p.x, p.y, p.z] for p in self.points])

    def save_h5(self, filepath):
        """Save measurement data to HDF5 file."""
        with h5py.File(filepath, 'w') as f:
            f.attrs['is_transient'] = self._is_transient
            f.attrs['num_points'] = self.num_points

            coords = self.get_coordinates()
            f.create_dataset('coordinates', data=coords)
            f.create_dataset('std_dev', data=self.get_std_dev_vector())

            if self._is_transient:
                f.create_dataset('time_grid', data=self._time_grid)
                time_series_data = np.array([p.time_series for p in self.points])
                f.create_dataset('time_series', data=time_series_data)
            else:
                f.create_dataset('temperatures', data=self.get_measurement_vector())

        print(f"Measurement data saved to: {filepath}")

    def load_h5(self, filepath):
        """Load measurement data from HDF5 file."""
        self.points = []

        with h5py.File(filepath, 'r') as f:
            self._is_transient = f.attrs['is_transient']
            coords = f['coordinates'][:]
            std_devs = f['std_dev'][:]

            if self._is_transient:
                self._time_grid = f['time_grid'][:]
                time_series_data = f['time_series'][:]

                for i in range(len(coords)):
                    self.add_point(
                        x=coords[i, 0], y=coords[i, 1], z=coords[i, 2],
                        time_series=time_series_data[i],
                        times=self._time_grid,
                        std_dev=std_devs[i]
                    )
            else:
                temps = f['temperatures'][:]
                for i in range(len(coords)):
                    self.add_point(
                        x=coords[i, 0], y=coords[i, 1], z=coords[i, 2],
                        temperature=temps[i],
                        std_dev=std_devs[i]
                    )

        print(f"Measurement data loaded from: {filepath}")
        return self

    def save_csv(self, filepath):
        """Save measurement data to CSV file."""
        with open(filepath, 'w') as f:
            if self._is_transient:
                header = ['point_id', 'x', 'y', 'z', 'std_dev'] + \
                         [f't={t:.4f}' for t in self._time_grid]
                f.write(','.join(header) + '\n')
                for p in self.points:
                    row = [p.point_id, p.x, p.y, p.z, p.std_dev] + list(p.time_series)
                    f.write(','.join(str(v) for v in row) + '\n')
            else:
                f.write('point_id,x,y,z,temperature,std_dev\n')
                for p in self.points:
                    f.write(f'{p.point_id},{p.x},{p.y},{p.z},{p.temperature},{p.std_dev}\n')
        print(f"Measurement data saved to: {filepath}")
