import numpy as np
from typing import List, Tuple, Optional
import os
from .models import VelocityModel, Shot, Receiver, TravelTimeData


def load_velocity_model_ascii(filepath: str) -> VelocityModel:
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    header = {}
    data_start = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#') or line.startswith('!'):
            parts = line[1:].strip().split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                value = parts[1].strip()
                header[key] = value
            continue
        if line[0].isdigit() or line[0] == '.' or line[0] == '-':
            data_start = i
            break
    
    nx = int(header.get('nx', header.get('n', 0)))
    nz = int(header.get('nz', 0))
    dx = float(header.get('dx', header.get('dx', 1.0)))
    dz = float(header.get('dz', 1.0))
    x0 = float(header.get('x0', 0.0))
    z0 = float(header.get('z0', 0.0))
    
    data_lines = [line for line in lines[data_start:] if line.strip()]
    
    if nx == 0 or nz == 0:
        nz = len(data_lines)
        if nz > 0:
            first_line = data_lines[0].split()
            nx = len(first_line)
    
    velocity = np.zeros((nz, nx))
    
    for iz in range(nz):
        parts = data_lines[iz].split()
        for ix in range(nx):
            velocity[iz, ix] = float(parts[ix])
    
    return VelocityModel(
        nx=nx, nz=nz, dx=dx, dz=dz,
        x0=x0, z0=z0, velocity=velocity
    )


def save_velocity_model_ascii(model: VelocityModel, filepath: str,
                              include_header: bool = True):
    with open(filepath, 'w') as f:
        if include_header:
            f.write(f"# nx = {model.nx}\n")
            f.write(f"# nz = {model.nz}\n")
            f.write(f"# dx = {model.dx}\n")
            f.write(f"# dz = {model.dz}\n")
            f.write(f"# x0 = {model.x0}\n")
            f.write(f"# z0 = {model.z0}\n")
            f.write(f"# velocity units: m/s\n")
            f.write("# format: each row is a depth slice (z constant), columns are x\n")
        
        for iz in range(model.nz):
            line = " ".join([f"{model.velocity[iz, ix]:.4f}" for ix in range(model.nx)])
            f.write(line + "\n")


def load_geometry(filepath: str) -> Tuple[List[Shot], List[Receiver]]:
    shots = []
    receivers = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    mode = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            if 'shot' in line.lower():
                mode = 'shot'
            elif 'receiver' in line.lower():
                mode = 'receiver'
            continue
        
        parts = line.split()
        if len(parts) >= 3:
            pid = int(parts[0])
            x = float(parts[1])
            z = float(parts[2])
            
            if mode == 'shot':
                shots.append(Shot(id=pid, x=x, z=z))
            elif mode == 'receiver':
                receivers.append(Receiver(id=pid, x=x, z=z))
    
    return shots, receivers


def save_geometry(shots: List[Shot], receivers: List[Receiver], filepath: str):
    with open(filepath, 'w') as f:
        f.write("# Shots: id x z (units: meters)\n")
        for shot in shots:
            f.write(f"{shot.id} {shot.x:.2f} {shot.z:.2f}\n")
        
        f.write("\n# Receivers: id x z (units: meters)\n")
        for rec in receivers:
            f.write(f"{rec.id} {rec.x:.2f} {rec.z:.2f}\n")


def load_travel_times(filepath: str) -> List[TravelTimeData]:
    data = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) >= 3:
            shot_id = int(parts[0])
            receiver_id = int(parts[1])
            travel_time = float(parts[2])
            
            data.append(TravelTimeData(
                shot_id=shot_id,
                receiver_id=receiver_id,
                travel_time=travel_time
            ))
    
    return data


def save_travel_times(data: List[TravelTimeData], filepath: str,
                      include_calculated: bool = False):
    with open(filepath, 'w') as f:
        f.write("# Travel time data: shot_id receiver_id observed_time [calculated_time] [residual]\n")
        f.write("# Units: time in seconds\n")
        
        for d in data:
            line = f"{d.shot_id} {d.receiver_id} {d.travel_time:.6f}"
            if include_calculated:
                line += f" {d.calculated_time:.6f} {d.residual:.6f}"
            f.write(line + "\n")


def load_full_dataset(model_file: str, geometry_file: str,
                      travel_time_file: str) -> Tuple[VelocityModel, List[Shot],
                                                      List[Receiver], List[TravelTimeData]]:
    model = load_velocity_model_ascii(model_file)
    shots, receivers = load_geometry(geometry_file)
    data = load_travel_times(travel_time_file)
    
    shot_dict = {s.id: s for s in shots}
    rec_dict = {r.id: r for r in receivers}
    
    for d in data:
        d.shot = shot_dict.get(d.shot_id)
        d.receiver = rec_dict.get(d.receiver_id)
    
    return model, shots, receivers, data
