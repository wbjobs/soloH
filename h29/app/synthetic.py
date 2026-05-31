import numpy as np
from typing import List, Tuple
from .models import VelocityModel, Shot, Receiver, TravelTimeData
from .ray_tracing import ShortestPathRayTracer


def create_test_velocity_model(nx: int = 40, nz: int = 40,
                               dx: float = 5.0, dz: float = 5.0,
                               x0: float = 0.0, z0: float = 0.0,
                               model_type: str = 'anomaly') -> VelocityModel:
    velocity = np.ones((nz, nx)) * 2000.0
    
    x_coords = np.linspace(x0, x0 + (nx - 1) * dx, nx)
    z_coords = np.linspace(z0, z0 + (nz - 1) * dz, nz)
    X, Z = np.meshgrid(x_coords, z_coords)
    
    if model_type == 'gradient':
        velocity = 1500.0 + 20.0 * Z
    elif model_type == 'anomaly':
        center_x = x0 + (nx - 1) * dx / 2.0
        center_z = z0 + (nz - 1) * dz / 2.0
        radius = min(nx * dx, nz * dz) * 0.2
        anomaly = -500.0 * np.exp(-((X - center_x) ** 2 + (Z - center_z) ** 2) / (2 * radius ** 2))
        velocity = 2000.0 + anomaly
    elif model_type == 'two_layer':
        layer_z = z0 + (nz - 1) * dz * 0.4
        velocity[Z < layer_z] = 1800.0
        velocity[Z >= layer_z] = 2500.0
    elif model_type == 'complex':
        velocity = 2000.0 + 300.0 * np.sin(X / 50.0) * np.cos(Z / 50.0)
        center_x1 = x0 + (nx - 1) * dx * 0.3
        center_z1 = z0 + (nz - 1) * dz * 0.5
        radius1 = min(nx * dx, nz * dz) * 0.15
        anomaly1 = 400.0 * np.exp(-((X - center_x1) ** 2 + (Z - center_z1) ** 2) / (2 * radius1 ** 2))
        
        center_x2 = x0 + (nx - 1) * dx * 0.7
        center_z2 = z0 + (nz - 1) * dz * 0.5
        radius2 = min(nx * dx, nz * dz) * 0.15
        anomaly2 = -300.0 * np.exp(-((X - center_x2) ** 2 + (Z - center_z2) ** 2) / (2 * radius2 ** 2))
        
        velocity += anomaly1 + anomaly2
    
    velocity = np.clip(velocity, 1000.0, 5000.0)
    
    return VelocityModel(
        nx=nx, nz=nz, dx=dx, dz=dz,
        x0=x0, z0=z0, velocity=velocity
    )


def create_crosswell_geometry(n_shots: int = 10, n_receivers: int = 40,
                              well_x1: float = 0.0, well_x2: float = 200.0,
                              z_min: float = 0.0, z_max: float = 200.0) -> Tuple[List[Shot], List[Receiver]]:
    shots = []
    receivers = []
    
    shot_z = np.linspace(z_min + (z_max - z_min) * 0.1,
                         z_max - (z_max - z_min) * 0.1,
                         n_shots)
    
    for i, z in enumerate(shot_z):
        shots.append(Shot(id=i + 1, x=well_x1, z=z))
    
    rec_z = np.linspace(z_min + (z_max - z_min) * 0.05,
                        z_max - (z_max - z_min) * 0.05,
                        n_receivers)
    
    for i, z in enumerate(rec_z):
        receivers.append(Receiver(id=i + 1, x=well_x2, z=z))
    
    return shots, receivers


def generate_synthetic_data(model: VelocityModel, shots: List[Shot],
                            receivers: List[Receiver],
                            noise_level: float = 0.01,
                            missing_fraction: float = 0.0) -> List[TravelTimeData]:
    ray_tracer = ShortestPathRayTracer(model)
    
    data = []
    
    for shot in shots:
        for receiver in receivers:
            if np.random.rand() < missing_fraction:
                continue
            
            times, backtrack = ray_tracer.compute_traveltimes(shot)
            rix = int(round((receiver.x - model.x0) / model.dx))
            riz = int(round((receiver.z - model.z0) / model.dz))
            rix = max(0, min(rix, model.nx - 1))
            riz = max(0, min(riz, model.nz - 1))
            
            tt = times[riz, rix]
            
            if np.isfinite(tt):
                if noise_level > 0:
                    noise = np.random.normal(0, noise_level * tt)
                    tt += noise
                
                data.append(TravelTimeData(
                    shot_id=shot.id,
                    receiver_id=receiver.id,
                    travel_time=tt,
                    shot=shot,
                    receiver=receiver
                ))
    
    return data


def create_synthetic_test(model_type: str = 'anomaly',
                          nx: int = 40, nz: int = 40,
                          dx: float = 5.0, dz: float = 5.0,
                          n_shots: int = 10, n_receivers: int = 40,
                          noise_level: float = 0.01) -> Tuple[VelocityModel, VelocityModel,
                                                                List[Shot], List[Receiver],
                                                                List[TravelTimeData]]:
    true_model = create_test_velocity_model(
        nx=nx, nz=nz, dx=dx, dz=dz,
        model_type=model_type
    )
    
    x_max = true_model.x_max()
    z_max = true_model.z_max()
    
    shots, receivers = create_crosswell_geometry(
        n_shots=n_shots, n_receivers=n_receivers,
        well_x1=true_model.x0 + dx,
        well_x2=x_max - dx,
        z_min=true_model.z0 + dz,
        z_max=z_max - dz
    )
    
    data = generate_synthetic_data(
        true_model, shots, receivers,
        noise_level=noise_level
    )
    
    initial_model = VelocityModel(
        nx=nx, nz=nz, dx=dx, dz=dz,
        x0=true_model.x0, z0=true_model.z0,
        velocity=np.ones((nz, nx)) * 2000.0
    )
    
    return true_model, initial_model, shots, receivers, data
