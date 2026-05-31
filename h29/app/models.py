import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Point:
    x: float
    z: float
    y: float = 0.0

    def to_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

    def to_2d_array(self) -> np.ndarray:
        return np.array([self.x, self.z])

    def distance_to(self, other: 'Point') -> float:
        return np.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def distance_2d(self, other: 'Point') -> float:
        return np.sqrt((self.x - other.x) ** 2 + (self.z - other.z) ** 2)

    def offset_distance(self) -> float:
        return abs(self.y)

    def project_to_plane(self, y0: float = 0.0) -> 'Point':
        return Point(x=self.x, z=self.z, y=y0)

    def midpoint_to(self, other: 'Point') -> 'Point':
        return Point(
            x=0.5 * (self.x + other.x),
            y=0.5 * (self.y + other.y),
            z=0.5 * (self.z + other.z)
        )


@dataclass
class Shot(Point):
    id: int = 0

    def __repr__(self) -> str:
        return f"Shot(id={self.id}, x={self.x:.2f}, z={self.z:.2f})"


@dataclass
class Receiver(Point):
    id: int = 0

    def __repr__(self) -> str:
        return f"Receiver(id={self.id}, x={self.x:.2f}, z={self.z:.2f})"


@dataclass
class TravelTimeData:
    shot_id: int
    receiver_id: int
    travel_time: float
    shot: Optional[Shot] = None
    receiver: Optional[Receiver] = None
    residual: float = 0.0
    calculated_time: float = 0.0
    uncertainty: float = 0.001
    weight: float = 1.0

    def __repr__(self) -> str:
        return f"TravelTimeData(shot={self.shot_id}, recv={self.receiver_id}, t_obs={self.travel_time:.4f}, t_calc={self.calculated_time:.4f})"


@dataclass
class AnisotropicParams:
    epsilon: np.ndarray = None
    delta: np.ndarray = None
    gamma: np.ndarray = None
    
    @classmethod
    def create_isotropic(cls, nx: int, nz: int) -> 'AnisotropicParams':
        return cls(
            epsilon=np.zeros((nz, nx)),
            delta=np.zeros((nz, nx)),
            gamma=np.zeros((nz, nx))
        )
    
    def copy(self) -> 'AnisotropicParams':
        return AnisotropicParams(
            epsilon=self.epsilon.copy() if self.epsilon is not None else None,
            delta=self.delta.copy() if self.delta is not None else None,
            gamma=self.gamma.copy() if self.gamma is not None else None
        )


@dataclass
class UncertaintyConfig:
    velocity_prior_std: float = 100.0
    travel_time_std: float = 0.001
    epsilon_prior_std: float = 0.02
    delta_prior_std: float = 0.02
    n_monte_carlo_samples: int = 100
    use_likelihood_weighting: bool = True


@dataclass
class VelocityModel:
    nx: int
    nz: int
    dx: float
    dz: float
    x0: float = 0.0
    z0: float = 0.0
    velocity: np.ndarray = None
    slowness: np.ndarray = None
    ray_density: np.ndarray = None
    anisotropy: Optional[AnisotropicParams] = None
    is_anisotropic: bool = False
    velocity_std: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.velocity is None:
            self.velocity = np.ones((self.nz, self.nx)) * 2000.0
        if self.slowness is None:
            self.slowness = 1.0 / self.velocity
        if self.ray_density is None:
            self.ray_density = np.zeros((self.nz, self.nx))
        if self.is_anisotropic and self.anisotropy is None:
            self.anisotropy = AnisotropicParams.create_isotropic(self.nx, self.nz)
        if self.velocity_std is None:
            self.velocity_std = np.zeros((self.nz, self.nx))

    def x_max(self) -> float:
        return self.x0 + (self.nx - 1) * self.dx

    def z_max(self) -> float:
        return self.z0 + (self.nz - 1) * self.dz

    def x_coords(self) -> np.ndarray:
        return np.linspace(self.x0, self.x_max(), self.nx)

    def z_coords(self) -> np.ndarray:
        return np.linspace(self.z0, self.z_max(), self.nz)

    def get_velocity_at(self, x: float, z: float) -> float:
        ix = int(round((x - self.x0) / self.dx))
        iz = int(round((z - self.z0) / self.dz))
        ix = max(0, min(ix, self.nx - 1))
        iz = max(0, min(iz, self.nz - 1))
        return self.velocity[iz, ix]

    def update_velocity(self, velocity_update: np.ndarray):
        self.velocity += velocity_update
        self.slowness = 1.0 / self.velocity

    def update_slowness(self, slowness_update: np.ndarray):
        self.slowness += slowness_update
        self.velocity = 1.0 / self.slowness

    def reset_ray_density(self):
        self.ray_density = np.zeros((self.nz, self.nx))

    def copy(self) -> 'VelocityModel':
        return VelocityModel(
            nx=self.nx,
            nz=self.nz,
            dx=self.dx,
            dz=self.dz,
            x0=self.x0,
            z0=self.z0,
            velocity=self.velocity.copy(),
            slowness=self.slowness.copy(),
            ray_density=self.ray_density.copy(),
            anisotropy=self.anisotropy.copy() if self.anisotropy else None,
            is_anisotropic=self.is_anisotropic,
            velocity_std=self.velocity_std.copy() if self.velocity_std is not None else None
        )


@dataclass
class RayPath:
    points: List[Point] = field(default_factory=list)
    travel_time: float = 0.0

    def add_point(self, p: Point):
        self.points.append(p)

    def to_arrays(self) -> Tuple[np.ndarray, np.ndarray]:
        xs = np.array([p.x for p in self.points])
        zs = np.array([p.z for p in self.points])
        return xs, zs

    def length(self) -> float:
        total = 0.0
        for i in range(len(self.points) - 1):
            total += self.points[i].distance_to(self.points[i + 1])
        return total


@dataclass
class InversionConfig:
    max_iterations: int = 20
    lsqr_tol: float = 1e-6
    regularization: float = 0.1
    damping: float = 0.01
    update_scale: float = 1.0
    min_velocity: float = 1000.0
    max_velocity: float = 5000.0
    adaptive_regularization: bool = True
    reg_min: float = 0.01
    reg_max: float = 1.0
    damping_min: float = 0.001
    damping_max: float = 0.1
    use_ray_weighted_reg: bool = True
    curvature_regularization: bool = False
    second_derivative_weight: float = 0.5
