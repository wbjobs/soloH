import numpy as np
from typing import List, Tuple, Optional
from heapq import heappush, heappop
from .models import VelocityModel, Shot, Receiver, TravelTimeData, RayPath, Point, AnisotropicParams


def vti_phase_velocity(theta: float, v0: float, epsilon: float, delta: float) -> float:
    sin_theta = np.sin(theta)
    cos_theta = np.cos(theta)
    sin2 = sin_theta ** 2
    cos2 = cos_theta ** 2
    
    term1 = 1.0 + 2 * delta * sin2 * cos2
    term2 = 2 * (epsilon - delta) * sin2 * sin2
    
    return v0 * np.sqrt(1.0 + term1 + term2 - 1.0)


def vti_group_velocity(theta: float, v0: float, epsilon: float, delta: float) -> float:
    sin_theta = np.sin(theta)
    cos_theta = np.cos(theta)
    sin2 = sin_theta ** 2
    cos2 = cos_theta ** 2
    
    D = 1.0 + 2 * delta * sin2 * cos2 + 2 * (epsilon - delta) * sin2 ** 2
    
    dD_dtheta = 2 * delta * (2 * sin_theta * cos_theta * cos2 - sin2 * 2 * cos_theta * sin_theta) + \
                4 * (epsilon - delta) * sin2 * sin_theta * cos_theta
    
    v_phase = v0 * np.sqrt(D)
    
    dV_dtheta = v0 * (0.5 / np.sqrt(D)) * dD_dtheta
    
    Vx = v_phase * cos_theta - dV_dtheta * sin_theta
    Vz = v_phase * sin_theta + dV_dtheta * cos_theta
    
    return np.sqrt(Vx ** 2 + Vz ** 2)


def vti_slowness(theta: float, v0: float, epsilon: float, delta: float) -> float:
    return 1.0 / vti_phase_velocity(theta, v0, epsilon, delta)


def compute_group_angle(phase_angle: float, v0: float,
                        epsilon: float, delta: float) -> float:
    sin_theta = np.sin(phase_angle)
    cos_theta = np.cos(phase_angle)
    sin2 = sin_theta ** 2
    cos2 = cos_theta ** 2
    
    D = 1.0 + 2 * delta * sin2 * cos2 + 2 * (epsilon - delta) * sin2 ** 2
    
    dD_dtheta = 2 * delta * (2 * sin_theta * cos_theta * cos2 - sin2 * 2 * cos_theta * sin_theta) + \
                4 * (epsilon - delta) * sin2 * sin_theta * cos_theta
    
    v_phase = v0 * np.sqrt(D)
    dV_dtheta = v0 * (0.5 / np.sqrt(D)) * dD_dtheta
    
    numerator = v_phase * sin_theta + dV_dtheta * cos_theta
    denominator = v_phase * cos_theta - dV_dtheta * sin_theta
    
    if abs(denominator) < 1e-10:
        return np.pi / 2 if numerator > 0 else -np.pi / 2
    
    return np.arctan2(numerator, denominator)


class VTIRayTracer:
    def __init__(self, model: VelocityModel, neighbor_order: int = 2):
        self.model = model
        self.nx = model.nx
        self.nz = model.nz
        self.dx = model.dx
        self.dz = model.dz
        self.neighbor_order = neighbor_order
        self.neighbors = self._build_neighbors()
        
        if not model.is_anisotropic or model.anisotropy is None:
            self.aniso = AnisotropicParams.create_isotropic(self.nx, self.nz)
        else:
            self.aniso = model.anisotropy
    
    def _build_neighbors(self) -> List[List[Tuple[int, int, float, float, float]]]:
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
                            angle = np.arctan2(diz * self.dz, dix * self.dx)
                            nidx = niz * self.nx + nix
                            neighbors[idx].append((nidx, nix, niz, dist, angle))
        
        return neighbors
    
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
    
    def _get_anisotropic_slowness(self, ix: int, iz: int, angle: float) -> float:
        v0 = self.model.velocity[iz, ix]
        eps = self.aniso.epsilon[iz, ix]
        delta = self.aniso.delta[iz, ix]
        return vti_slowness(angle, v0, eps, delta)
    
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
                
                for nidx, nix, niz, dist, angle in self.neighbors[idx]:
                    if nidx in visited and pass_num == n_passes - 1:
                        continue
                    
                    s_ij = self._get_anisotropic_slowness(ix, iz, angle)
                    s_n = self._get_anisotropic_slowness(nix, niz, angle)
                    avg_slowness = 0.5 * (s_ij + s_n)
                    
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
            mask = ~inf_mask
            if np.any(mask):
                indices = np.indices(times.shape)
                valid_points = np.array([indices[0][mask], indices[1][mask]]).T
                valid_times = times[mask]
                
                for iz in range(self.nz):
                    for ix in range(self.nx):
                        if inf_mask[iz, ix]:
                            dists = np.sqrt((valid_points[:, 0] - iz) ** 2 * self.dz ** 2 +
                                          (valid_points[:, 1] - ix) ** 2 * self.dx ** 2)
                            nearest = np.argmin(dists)
                            nearest_iz, nearest_ix = valid_points[nearest]
                            s_avg = 0.5 * (
                                self._get_anisotropic_slowness(ix, iz, 0.0) +
                                self._get_anisotropic_slowness(nearest_ix, nearest_iz, 0.0)
                            )
                            times[iz, ix] = times[nearest_iz, nearest_ix] + dists[nearest] * s_avg
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
    
    def compute_sensitivity_row(self, ray: RayPath) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = self.nx * self.nz
        sens_v = np.zeros(n)
        sens_eps = np.zeros(n)
        sens_delta = np.zeros(n)
        
        for i in range(len(ray.points) - 1):
            p1 = ray.points[i]
            p2 = ray.points[i + 1]
            
            segment_length = p1.distance_2d(p2)
            angle = np.arctan2(p2.z - p1.z, p2.x - p1.x)
            
            mid_x = 0.5 * (p1.x + p2.x)
            mid_z = 0.5 * (p1.z + p2.z)
            
            ix, iz = self._point_to_grid(Point(mid_x, mid_z))
            
            if 0 <= ix < self.nx and 0 <= iz < self.nz:
                idx = iz * self.nx + ix
                v0 = self.model.velocity[iz, ix]
                eps = self.aniso.epsilon[iz, ix]
                delta = self.aniso.delta[iz, ix]
                
                v = vti_phase_velocity(angle, v0, eps, delta)
                dv_dv0 = v / v0
                
                sin_theta = np.sin(angle)
                cos_theta = np.cos(angle)
                sin2 = sin_theta ** 2
                cos2 = cos_theta ** 2
                D = 1.0 + 2 * delta * sin2 * cos2 + 2 * (eps - delta) * sin2 ** 2
                
                dv_deps = v0 * (0.5 / np.sqrt(D)) * 2 * sin2 ** 2
                dv_ddelta = v0 * (0.5 / np.sqrt(D)) * 2 * (sin2 * cos2 - sin2 ** 2)
                
                sens_v[idx] += -segment_length / v ** 2 * dv_dv0
                sens_eps[idx] += -segment_length / v ** 2 * dv_deps
                sens_delta[idx] += -segment_length / v ** 2 * dv_ddelta
        
        return sens_v, sens_eps, sens_delta
    
    def forward_modeling(self, shots: List[Shot], receivers: List[Receiver],
                         data: List[TravelTimeData], compute_rays: bool = True,
                         update_density: bool = True) -> Tuple[List[TravelTimeData], np.ndarray]:
        if update_density:
            self.model.reset_ray_density()
        
        shot_dict = {s.id: s for s in shots}
        recv_dict = {r.id: r for r in receivers}
        
        ndata = len(data)
        nmodel = self.nx * self.nz
        
        if self.model.is_anisotropic:
            sensitivity = np.zeros((ndata, nmodel * 3))
        else:
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
            
            y_diff = receiver.y - shot.y
            if abs(y_diff) > 1e-6:
                dist_2d = shot.distance_2d(receiver)
                dist_3d = shot.distance_to(receiver)
                if dist_2d > 1e-6:
                    correction = dist_3d / dist_2d
                    travel_time = travel_time_2d * correction
                else:
                    travel_time = abs(y_diff) / self.model.velocity[riz, rix]
            else:
                travel_time = travel_time_2d
            
            d.calculated_time = travel_time
            d.residual = d.travel_time - d.calculated_time
            
            if compute_rays:
                ray = self.trace_ray(backtrack, recv_proj)
                ray.travel_time = travel_time
                
                if self.model.is_anisotropic:
                    sens_v, sens_eps, sens_delta = self.compute_sensitivity_row(ray)
                    sensitivity[i, :nmodel] = sens_v
                    sensitivity[i, nmodel:2*nmodel] = sens_eps
                    sensitivity[i, 2*nmodel:] = sens_delta
                else:
                    sens_v, _, _ = self.compute_sensitivity_row(ray)
                    sensitivity[i, :] = sens_v
                
                if update_density:
                    self._add_ray_to_density(ray)
        
        return data, sensitivity


class AnisotropicTomography:
    def __init__(self, model: VelocityModel, config=None):
        self.model = model
        self.config = config
        self.initial_model = model.copy()
        self.history = []
        self.current_iteration = 0
        
        if not model.is_anisotropic:
            model.is_anisotropic = True
            model.anisotropy = AnisotropicParams.create_isotropic(model.nx, model.nz)
    
    def reset(self):
        self.model = self.initial_model.copy()
        self.history = []
        self.current_iteration = 0
    
    def compute_residuals(self, data: List[TravelTimeData]) -> np.ndarray:
        residuals = []
        for d in data:
            if np.isfinite(d.residual):
                residuals.append(d.residual)
        return np.array(residuals)
    
    def compute_rms(self, residuals: np.ndarray) -> float:
        if len(residuals) == 0:
            return 0.0
        return np.sqrt(np.mean(residuals ** 2))
    
    def run_iteration(self, shots: List[Shot], receivers: List[Receiver],
                      data: List[TravelTimeData], invert_epsilon: bool = True,
                      invert_delta: bool = True) -> dict:
        self.current_iteration += 1
        
        ray_tracer = VTIRayTracer(self.model)
        updated_data, sensitivity = ray_tracer.forward_modeling(
            shots, receivers, data, compute_rays=True, update_density=True
        )
        
        residuals = self.compute_residuals(updated_data)
        rms_obs = self.compute_rms(residuals)
        
        valid_indices = [i for i, d in enumerate(updated_data) if np.isfinite(d.residual)]
        if len(valid_indices) < 10:
            return {
                'iteration': self.current_iteration,
                'rms_before': rms_obs,
                'rms_after': rms_obs,
                'error': 'Not enough valid data'
            }
        
        nmodel = self.model.nx * self.model.nz
        
        if self.model.is_anisotropic and invert_epsilon and invert_delta:
            G = sensitivity[valid_indices, :]
            nparams = nmodel * 3
        elif self.model.is_anisotropic and invert_epsilon:
            G = sensitivity[valid_indices, :2*nmodel]
            nparams = nmodel * 2
        elif self.model.is_anisotropic and invert_delta:
            G = np.hstack([sensitivity[valid_indices, :nmodel],
                          sensitivity[valid_indices, 2*nmodel:]])
            nparams = nmodel * 2
        else:
            G = sensitivity[valid_indices, :nmodel]
            nparams = nmodel
        
        dt = residuals[valid_indices]
        
        weights = np.array([1.0 / max(d.uncertainty, 1e-6) for d in updated_data if np.isfinite(d.residual)])
        W = np.diag(weights)
        G = W @ G
        dt = W @ dt
        
        if self.config and self.config.regularization > 0:
            from .inversion import build_regularization_matrix
            
            L_v = build_regularization_matrix(
                self.model.nx, self.model.nz, self.config.regularization,
                ray_density=self.model.ray_density,
                use_ray_weighting=self.config.use_ray_weighted_reg
            )
            
            if nparams > nmodel:
                L_full = np.zeros((L_v.shape[0] * (nparams // nmodel), nparams))
                for ip in range(nparams // nmodel):
                    L_full[ip*L_v.shape[0]:(ip+1)*L_v.shape[0],
                           ip*nmodel:(ip+1)*nmodel] = L_v * (0.5 if ip > 0 else 1.0)
                L = L_full
            else:
                L = L_v
            
            G_aug = np.vstack([G, L])
            dt_aug = np.hstack([dt, np.zeros(L.shape[0])])
        else:
            G_aug = G
            dt_aug = dt
        
        from .inversion import lsqr
        update, lsqr_info = lsqr(
            G_aug, dt_aug,
            damp=self.config.damping if self.config else 0.01,
            atol=1e-6, btol=1e-6, maxiter=100
        )
        
        update = update * (self.config.update_scale if self.config else 1.0)
        
        v_update = update[:nmodel].reshape((self.model.nz, self.model.nx))
        self.model.velocity += v_update
        self.model.velocity = np.clip(self.model.velocity,
                                     self.config.min_velocity if self.config else 1000.0,
                                     self.config.max_velocity if self.config else 5000.0)
        self.model.slowness = 1.0 / self.model.velocity
        
        if self.model.is_anisotropic and invert_epsilon:
            eps_update = update[nmodel:2*nmodel].reshape((self.model.nz, self.model.nx))
            self.model.anisotropy.epsilon += eps_update * 0.1
            self.model.anisotropy.epsilon = np.clip(self.model.anisotropy.epsilon, -0.1, 0.5)
        
        if self.model.is_anisotropic and invert_delta:
            if nparams > nmodel * 2:
                delta_update = update[2*nmodel:].reshape((self.model.nz, self.model.nx))
            else:
                delta_update = update[nmodel:].reshape((self.model.nz, self.model.nx))
            self.model.anisotropy.delta += delta_update * 0.1
            self.model.anisotropy.delta = np.clip(self.model.anisotropy.delta, -0.2, 0.3)
        
        ray_tracer2 = VTIRayTracer(self.model)
        final_data, _ = ray_tracer2.forward_modeling(
            shots, receivers, updated_data, compute_rays=False, update_density=False
        )
        
        final_residuals = self.compute_residuals(final_data)
        rms_final = self.compute_rms(final_residuals)
        
        iter_info = {
            'iteration': self.current_iteration,
            'rms_before': rms_obs,
            'rms_after': rms_final,
            'rms_reduction': (rms_obs - rms_final) / rms_obs * 100 if rms_obs > 0 else 0,
            'velocity_update_norm': np.linalg.norm(v_update),
            'lsqr_info': lsqr_info,
            'n_valid_data': len(valid_indices),
            'final_data': final_data,
            'inverted_anisotropy': self.model.is_anisotropic
        }
        
        if self.model.is_anisotropic:
            iter_info['epsilon_update_norm'] = np.linalg.norm(
                self.model.anisotropy.epsilon - self.initial_model.anisotropy.epsilon
            ) if self.initial_model.anisotropy else 0.0
            iter_info['delta_update_norm'] = np.linalg.norm(
                self.model.anisotropy.delta - self.initial_model.anisotropy.delta
            ) if self.initial_model.anisotropy else 0.0
        
        self.history.append(iter_info)
        
        return iter_info
    
    def run_full_inversion(self, shots: List[Shot], receivers: List[Receiver],
                           data: List[TravelTimeData],
                           progress_callback=None,
                           invert_epsilon: bool = True,
                           invert_delta: bool = True) -> List[dict]:
        self.reset()
        
        max_iter = self.config.max_iterations if self.config else 20
        
        for i in range(max_iter):
            info = self.run_iteration(shots, receivers, data, invert_epsilon, invert_delta)
            
            if progress_callback:
                progress_callback(info)
            
            if 'error' in info:
                break
            
            if info['rms_reduction'] < 0.1 and i > 2:
                break
            
            if i > 0 and abs(self.history[i]['rms_after'] - self.history[i-1]['rms_after']) < 1e-6:
                break
        
        return self.history
