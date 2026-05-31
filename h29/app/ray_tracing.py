import numpy as np
from heapq import heappush, heappop
from typing import List, Tuple, Optional
from .models import VelocityModel, Shot, Receiver, TravelTimeData, RayPath, Point


class ShortestPathRayTracer:
    def __init__(self, model: VelocityModel, neighbor_order: int = 2):
        self.model = model
        self.nx = model.nx
        self.nz = model.nz
        self.dx = model.dx
        self.dz = model.dz
        self.neighbor_order = neighbor_order
        self.neighbors = self._build_neighbors()

    def _build_neighbors(self) -> List[List[Tuple[int, int, float]]]:
        neighbors = [[] for _ in range(self.nx * self.nz)]
        
        max_offset = self.neighbor_order
        
        for ix in range(self.nx):
            for iz in range(self.nz):
                idx = iz * self.nx + ix
                
                for dix in range(-max_offset, max_offset + 1):
                    for diz in range(-max_offset, max_offset + 1):
                        if dix == 0 and diz == 0:
                            continue
                        nix = ix + dix
                        niz = iz + diz
                        if 0 <= nix < self.nx and 0 <= niz < self.nz:
                            dist = np.sqrt((dix * self.dx) ** 2 + (diz * self.dz) ** 2)
                            nidx = niz * self.nx + nix
                            neighbors[idx].append((nidx, nix, niz, dist))
        
        return neighbors

    def _apply_offset_correction(self, travel_time: float, shot: Point, receiver: Point) -> float:
        if abs(shot.y) < 1e-6 and abs(receiver.y) < 1e-6:
            return travel_time
        
        y_diff = receiver.y - shot.y
        if abs(y_diff) < 1e-6:
            return travel_time
        
        dist_2d = shot.distance_2d(receiver)
        
        if dist_2d < 1e-6:
            return abs(y_diff) / 2000.0
        
        dist_3d = shot.distance_to(receiver)
        correction_factor = dist_3d / dist_2d
        
        return travel_time * correction_factor

    def _point_to_grid(self, p: Point) -> Tuple[int, int]:
        ix = int(round((p.x - self.model.x0) / self.dx))
        iz = int(round((p.z - self.model.z0) / self.dz))
        ix = max(0, min(ix, self.nx - 1))
        iz = max(0, min(iz, self.nz - 1))
        return ix, iz

    def _grid_to_point(self, ix: int, iz: int) -> Point:
        return Point(
            x=self.model.x0 + ix * self.dx,
            z=self.model.z0 + iz * self.dz
        )

    def compute_traveltimes(self, source: Point, n_passes: int = 2) -> Tuple[np.ndarray, np.ndarray]:
        times = np.full((self.nz, self.nx), np.inf)
        backtrack = np.full((self.nz, self.nx, 2), -1, dtype=np.int32)
        
        six, siz = self._point_to_grid(source)
        sidx = siz * self.nx + six
        times[siz, six] = 0.0
        
        for pass_num in range(n_passes):
            heap = []
            heappush(heap, (0.0, six, siz, sidx))
            visited = set()
            
            updated = False
            
            while heap:
                current_time, ix, iz, idx = heappop(heap)
                
                if idx in visited:
                    continue
                visited.add(idx)
                
                if current_time > times[iz, ix]:
                    continue
                
                slowness_ij = self.model.slowness[iz, ix]
                
                for nidx, nix, niz, dist in self.neighbors[idx]:
                    if nidx in visited and pass_num == n_passes - 1:
                        continue
                    
                    slowness_n = self.model.slowness[niz, nix]
                    
                    if abs(ix - nix) <= 1 and abs(iz - niz) <= 1:
                        avg_slowness = 0.5 * (slowness_ij + slowness_n)
                    else:
                        mid_ix = (ix + nix) // 2
                        mid_iz = (iz + niz) // 2
                        if 0 <= mid_ix < self.nx and 0 <= mid_iz < self.nz:
                            s_mid = self.model.slowness[mid_iz, mid_ix]
                            avg_slowness = (slowness_ij + 2 * s_mid + slowness_n) / 4.0
                        else:
                            avg_slowness = 0.5 * (slowness_ij + slowness_n)
                    
                    new_time = current_time + dist * avg_slowness
                    
                    if new_time < times[niz, nix] - 1e-12:
                        times[niz, nix] = new_time
                        backtrack[niz, nix, 0] = ix
                        backtrack[niz, nix, 1] = iz
                        heappush(heap, (new_time, nix, niz, nidx))
                        updated = True
            
            if not updated:
                break
        
        inf_mask = np.isinf(times)
        if np.any(inf_mask):
            from scipy.ndimage import distance_transform_edt
            mask = ~inf_mask
            if np.any(mask):
                indices = np.indices(times.shape)
                valid_times = times[mask]
                valid_points = np.array([indices[0][mask], indices[1][mask]]).T
                
                for iz in range(self.nz):
                    for ix in range(self.nx):
                        if inf_mask[iz, ix]:
                            dists = np.sqrt((valid_points[:, 0] - iz) ** 2 * self.dz ** 2 +
                                          (valid_points[:, 1] - ix) ** 2 * self.dx ** 2)
                            nearest = np.argmin(dists)
                            nearest_iz, nearest_ix = valid_points[nearest]
                            avg_slowness = 0.5 * (self.model.slowness[iz, ix] + 
                                                self.model.slowness[nearest_iz, nearest_ix])
                            times[iz, ix] = times[nearest_iz, nearest_ix] + dists[nearest] * avg_slowness
                            backtrack[iz, ix, 0] = nearest_ix
                            backtrack[iz, ix, 1] = nearest_iz
        
        return times, backtrack

    def trace_ray(self, backtrack: np.ndarray, receiver: Point) -> RayPath:
        rix, riz = self._point_to_grid(receiver)
        
        ray = RayPath()
        ray.add_point(receiver)
        
        cx, cz = rix, riz
        
        max_steps = self.nx * self.nz
        steps = 0
        
        while cx >= 0 and cz >= 0 and steps < max_steps:
            p = self._grid_to_point(cx, cz)
            ray.add_point(p)
            
            px = backtrack[cz, cx, 0]
            pz = backtrack[cz, cx, 1]
            
            if px == -1 or pz == -1:
                break
            
            cx, cz = px, pz
            steps += 1
        
        ray.points.reverse()
        return ray

    def _add_ray_to_density(self, ray: RayPath):
        for i in range(len(ray.points) - 1):
            p1 = ray.points[i]
            p2 = ray.points[i + 1]
            
            steps = max(
                abs(int((p2.x - p1.x) / self.dx)),
                abs(int((p2.z - p1.z) / self.dz))
            )
            steps = max(steps, 1)
            
            for s in range(steps + 1):
                t = s / steps
                x = p1.x + t * (p2.x - p1.x)
                z = p1.z + t * (p2.z - p1.z)
                ix, iz = self._point_to_grid(Point(x, z))
                self.model.ray_density[iz, ix] += 1

    def compute_sensitivity_row(self, ray: RayPath) -> np.ndarray:
        sens = np.zeros(self.nz * self.nx)
        
        for i in range(len(ray.points) - 1):
            p1 = ray.points[i]
            p2 = ray.points[i + 1]
            
            segment_length = p1.distance_to(p2)
            mid_x = 0.5 * (p1.x + p2.x)
            mid_z = 0.5 * (p1.z + p2.z)
            
            ix, iz = self._point_to_grid(Point(mid_x, mid_z))
            
            if 0 <= ix < self.nx and 0 <= iz < self.nz:
                idx = iz * self.nx + ix
                sens[idx] += segment_length
        
        return sens

    def forward_modeling(self, shots: List[Shot], receivers: List[Receiver],
                         data: List[TravelTimeData], compute_rays: bool = True,
                         update_density: bool = True,
                         apply_25d_correction: bool = True) -> Tuple[List[TravelTimeData], np.ndarray]:
        if update_density:
            self.model.reset_ray_density()
        
        shot_dict = {s.id: s for s in shots}
        recv_dict = {r.id: r for r in receivers}
        
        ndata = len(data)
        nmodel = self.nx * self.nz
        sensitivity = np.zeros((ndata, nmodel))
        
        times_cache = {}
        backtrack_cache = {}
        
        for i, d in enumerate(data):
            shot = shot_dict.get(d.shot_id)
            receiver = recv_dict.get(d.receiver_id)
            
            if shot is None or receiver is None:
                d.calculated_time = np.nan
                continue
            
            shot_proj = shot.project_to_plane(0.0)
            
            if shot.id not in times_cache:
                times, backtrack = self.compute_traveltimes(shot_proj)
                times_cache[shot.id] = times
                backtrack_cache[shot.id] = backtrack
            
            times = times_cache[shot.id]
            backtrack = backtrack_cache[shot.id]
            
            recv_proj = receiver.project_to_plane(0.0)
            rix, riz = self._point_to_grid(recv_proj)
            travel_time_2d = times[riz, rix]
            
            if apply_25d_correction:
                travel_time = self._apply_offset_correction(travel_time_2d, shot, receiver)
            else:
                travel_time = travel_time_2d
            
            d.calculated_time = travel_time
            d.residual = d.travel_time - d.calculated_time
            
            if compute_rays:
                ray = self.trace_ray(backtrack, recv_proj)
                ray.travel_time = travel_time
                
                y_offset = abs(receiver.y - shot.y)
                if y_offset > 1e-6 and apply_25d_correction:
                    correction_factor = ray.travel_time / travel_time_2d if travel_time_2d > 0 else 1.0
                    sens = self.compute_sensitivity_row(ray)
                    sensitivity[i, :] = sens * correction_factor
                else:
                    sensitivity[i, :] = self.compute_sensitivity_row(ray)
                
                if update_density:
                    self._add_ray_to_density(ray)
        
        return data, sensitivity
