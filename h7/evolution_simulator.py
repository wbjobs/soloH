import numpy as np
import numba
from numba import jit, prange
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import label
import time
import random

@jit(nopython=True, parallel=True)
def diffuse_numba(grid, D, dt, dx, dy):
    N = grid.shape[0]
    new_grid = np.copy(grid)
    laplacian = np.zeros_like(grid)
    
    for i in prange(N):
        for j in range(N):
            ip = (i + 1) % N
            im = (i - 1) % N
            jp = (j + 1) % N
            jm = (j - 1) % N
            
            laplacian[i, j] = (grid[ip, j] + grid[im, j] + grid[i, jp] + grid[i, jm] - 4 * grid[i, j]) / (dx * dy)
    
    new_grid += D * laplacian * dt
    return new_grid

@jit(nopython=True, parallel=True)
def calculate_fitness(cells, public_good, r, k, delta):
    N = cells.shape[0]
    fitness = np.zeros((N, N), dtype=np.float64)
    
    for i in prange(N):
        for j in range(N):
            concentration = public_good[i, j]
            base_fitness = 1.0 + r * concentration / (k + concentration)
            
            if cells[i, j] == 1:
                fitness[i, j] = base_fitness - delta
            else:
                fitness[i, j] = base_fitness
    
    return fitness

@jit(nopython=True)
def moran_update(cells, fitness, N):
    total_cells = N * N
    
    death_i = random.randint(0, N - 1)
    death_j = random.randint(0, N - 1)
    
    neighbors = [
        ((death_i - 1) % N, death_j),
        ((death_i + 1) % N, death_j),
        (death_i, (death_j - 1) % N),
        (death_i, (death_j + 1) % N),
        (death_i, death_j)
    ]
    
    neighbor_fitness = np.zeros(5, dtype=np.float64)
    for k in range(5):
        ni, nj = neighbors[k]
        neighbor_fitness[k] = fitness[ni, nj]
    
    total_neighbor_fitness = np.sum(neighbor_fitness)
    if total_neighbor_fitness <= 0:
        return cells
    
    rand_val = random.random() * total_neighbor_fitness
    cum_sum = 0.0
    birth_idx = 0
    
    for k in range(5):
        cum_sum += neighbor_fitness[k]
        if cum_sum >= rand_val:
            birth_idx = k
            break
    
    birth_i, birth_j = neighbors[birth_idx]
    cells[death_i, death_j] = cells[birth_i, birth_j]
    
    return cells

@jit(nopython=True)
def moran_update_batch(cells, fitness, N, num_updates):
    for _ in range(num_updates):
        cells = moran_update(cells, fitness, N)
    return cells

@jit(nopython=True, parallel=True)
def produce_public_good(cells, public_good, delta, N):
    for i in prange(N):
        for j in range(N):
            if cells[i, j] == 1:
                public_good[i, j] += delta
    return public_good

@jit(nopython=True)
def degrade_public_good(public_good, gamma, dt):
    return public_good * (1 - gamma * dt)

def generate_resource_gradient(N, direction='x', min_val=0.1, max_val=1.0):
    resources = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(N):
            if direction == 'x':
                resources[i, j] = min_val + (max_val - min_val) * (j / (N - 1))
            elif direction == 'y':
                resources[i, j] = min_val + (max_val - min_val) * (i / (N - 1))
            elif direction == 'radial':
                cx, cy = N / 2, N / 2
                dist = np.sqrt((i - cx) ** 2 + (j - cy) ** 2)
                max_dist = np.sqrt(2) * N / 2
                resources[i, j] = max_val - (max_val - min_val) * (dist / max_dist)
    return resources

def generate_resource_patches(N, num_patches=10, patch_size=5, min_val=0.0, max_val=1.0, seed=None):
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState()
    resources = np.ones((N, N), dtype=np.float64) * min_val
    for _ in range(num_patches):
        cx = rng.randint(patch_size, N - patch_size)
        cy = rng.randint(patch_size, N - patch_size)
        for i in range(cx - patch_size, cx + patch_size + 1):
            for j in range(cy - patch_size, cy + patch_size + 1):
                dist = np.sqrt((i - cx) ** 2 + (j - cy) ** 2)
                if dist <= patch_size:
                    resources[i % N, j % N] = max_val * (1 - dist / patch_size)
    return resources

def generate_resource_random(N, min_val=0.0, max_val=1.0, smooth_sigma=2.0):
    from scipy.ndimage import gaussian_filter
    noise = np.random.rand(N, N)
    resources = gaussian_filter(noise, sigma=smooth_sigma)
    resources = (resources - resources.min()) / (resources.max() - resources.min())
    resources = min_val + (max_val - min_val) * resources
    return resources

@jit(nopython=True)
def calculate_fitness_with_resources(cells, public_good, resources, r, k, delta, resource_weight):
    N = cells.shape[0]
    fitness = np.zeros((N, N), dtype=np.float64)
    
    for i in prange(N):
        for j in range(N):
            pg_concentration = public_good[i, j]
            resource = resources[i, j]
            base_fitness = 1.0 + r * pg_concentration / (k + pg_concentration)
            resource_benefit = resource_weight * resource
            
            if cells[i, j] == 1:
                fitness[i, j] = base_fitness + resource_benefit - delta
            else:
                fitness[i, j] = base_fitness + resource_benefit
    
    return fitness

@jit(nopython=True)
def move_cell_random(cells, N, move_prob):
    for i in range(N):
        for j in range(N):
            if random.random() < move_prob:
                neighbors = [
                    ((i - 1) % N, j),
                    ((i + 1) % N, j),
                    (i, (j - 1) % N),
                    (i, (j + 1) % N)
                ]
                idx = random.randint(0, 3)
                ni, nj = neighbors[idx]
                
                temp = cells[i, j]
                cells[i, j] = cells[ni, nj]
                cells[ni, nj] = temp
    return cells

@jit(nopython=True)
def move_cell_chemotaxis(cells, public_good, N, move_prob, chemotaxis_strength):
    for i in range(N):
        for j in range(N):
            if random.random() < move_prob:
                neighbors = [
                    ((i - 1) % N, j),
                    ((i + 1) % N, j),
                    (i, (j - 1) % N),
                    (i, (j + 1) % N)
                ]
                
                pg_current = public_good[i, j]
                neighbor_pg = np.zeros(4, dtype=np.float64)
                for k in range(4):
                    ni, nj = neighbors[k]
                    neighbor_pg[k] = public_good[ni, nj]
                
                pg_diff = neighbor_pg - pg_current
                weights = np.exp(chemotaxis_strength * pg_diff)
                total_weight = np.sum(weights)
                
                if total_weight > 0:
                    rand_val = random.random() * total_weight
                    cum_sum = 0.0
                    move_idx = 0
                    for k in range(4):
                        cum_sum += weights[k]
                        if cum_sum >= rand_val:
                            move_idx = k
                            break
                    
                    ni, nj = neighbors[move_idx]
                    temp = cells[i, j]
                    cells[i, j] = cells[ni, nj]
                    cells[ni, nj] = temp
    return cells

@jit(nopython=True)
def epigenetic_switch(cells, switch_rate_coop_to_cheat, switch_rate_cheat_to_coop, N):
    for i in range(N):
        for j in range(N):
            if cells[i, j] == 1:
                if random.random() < switch_rate_coop_to_cheat:
                    cells[i, j] = 0
            else:
                if random.random() < switch_rate_cheat_to_coop:
                    cells[i, j] = 1
    return cells

@jit(nopython=True)
def epigenetic_switch_density_dependent(cells, public_good, threshold, switch_rate, N):
    for i in range(N):
        for j in range(N):
            pg = public_good[i, j]
            if pg < threshold:
                if cells[i, j] == 1:
                    if random.random() < switch_rate:
                        cells[i, j] = 0
            else:
                if cells[i, j] == 0:
                    if random.random() < switch_rate:
                        cells[i, j] = 1
    return cells

def compute_spatial_autocorrelation(cells):
    N_side = cells.shape[0]
    N_total = N_side * N_side
    cells_flat = cells.flatten()
    mean_c = np.mean(cells_flat)
    
    numerator = 0.0
    denominator = np.sum((cells_flat - mean_c) ** 2)
    W = 0.0
    
    if denominator == 0:
        return 0.0
    
    for i in range(N_side):
        for j in range(N_side):
            neighbors = [
                ((i - 1) % N_side, j),
                ((i + 1) % N_side, j),
                (i, (j - 1) % N_side),
                (i, (j + 1) % N_side)
            ]
            
            for ni, nj in neighbors:
                numerator += (cells[i, j] - mean_c) * (cells[ni, nj] - mean_c)
                W += 1.0
    
    return (N_total / W) * (numerator / denominator)

def get_cluster_analysis(cells):
    c_labeled, c_clusters = label(cells == 1)
    ch_labeled, ch_clusters = label(cells == 0)
    
    cooperator_clusters = [np.sum(c_labeled == i) for i in range(1, c_clusters + 1)]
    cheater_clusters = [np.sum(ch_labeled == i) for i in range(1, ch_clusters + 1)]
    
    return {
        'cooperator_clusters': cooperator_clusters,
        'cheater_clusters': cheater_clusters,
        'avg_cooperator_cluster_size': np.mean(cooperator_clusters) if cooperator_clusters else 0,
        'avg_cheater_cluster_size': np.mean(cheater_clusters) if cheater_clusters else 0,
        'max_cooperator_cluster': max(cooperator_clusters) if cooperator_clusters else 0,
        'max_cheater_cluster': max(cheater_clusters) if cheater_clusters else 0
    }

class EvolutionSimulator:
    def __init__(self, N=100, D=0.5, r=1.5, k=0.1, delta=0.05, gamma=0.1, 
                 initial_cooperator_freq=0.5, dt=0.01, dx=1.0, dy=1.0, time_per_gen=1.0,
                 resource_mode='uniform', resource_kwargs=None,
                 movement_mode='none', move_prob=0.01, chemotaxis_strength=1.0,
                 switch_mode='none', switch_rate_coop_to_cheat=0.001, switch_rate_cheat_to_coop=0.001,
                 switch_threshold=0.5, resource_weight=0.5):
        self.N = N
        self.D = D
        self.r = r
        self.k = k
        self.delta = delta
        self.gamma = gamma
        self.dt = dt
        self.dx = dx
        self.dy = dy
        self.time_per_gen = time_per_gen
        
        self.resource_mode = resource_mode
        self.resource_kwargs = resource_kwargs if resource_kwargs is not None else {}
        self.resources = self._initialize_resources()
        self.resource_weight = resource_weight
        
        self.movement_mode = movement_mode
        self.move_prob = move_prob
        self.chemotaxis_strength = chemotaxis_strength
        
        self.switch_mode = switch_mode
        self.switch_rate_coop_to_cheat = switch_rate_coop_to_cheat
        self.switch_rate_cheat_to_coop = switch_rate_cheat_to_coop
        self.switch_threshold = switch_threshold
        
        self.cells = np.random.choice([0, 1], size=(N, N), p=[1 - initial_cooperator_freq, initial_cooperator_freq])
        self.public_good = np.zeros((N, N), dtype=np.float64)
        self.fitness = np.ones((N, N), dtype=np.float64)
        
        self.generation = 0
        self.time = 0.0
        self.trajectory_data = []
        self.switch_events = 0
        
        self.fig = None
        self.axes = None
    
    def _initialize_resources(self):
        if self.resource_mode == 'uniform':
            return np.ones((self.N, self.N), dtype=np.float64)
        elif self.resource_mode == 'gradient_x':
            return generate_resource_gradient(self.N, direction='x', **self.resource_kwargs)
        elif self.resource_mode == 'gradient_y':
            return generate_resource_gradient(self.N, direction='y', **self.resource_kwargs)
        elif self.resource_mode == 'radial':
            return generate_resource_gradient(self.N, direction='radial', **self.resource_kwargs)
        elif self.resource_mode == 'patches':
            return generate_resource_patches(self.N, **self.resource_kwargs)
        elif self.resource_mode == 'random':
            return generate_resource_random(self.N, **self.resource_kwargs)
        else:
            return np.ones((self.N, self.N), dtype=np.float64)
    
    def _apply_movement(self):
        if self.movement_mode == 'random':
            self.cells = move_cell_random(self.cells, self.N, self.move_prob)
        elif self.movement_mode == 'chemotaxis':
            self.cells = move_cell_chemotaxis(self.cells, self.public_good, self.N, 
                                               self.move_prob, self.chemotaxis_strength)
    
    def _apply_epigenetic_switch(self):
        initial_cooperators = np.sum(self.cells == 1)
        
        if self.switch_mode == 'constant':
            self.cells = epigenetic_switch(self.cells, 
                                            self.switch_rate_coop_to_cheat,
                                            self.switch_rate_cheat_to_coop,
                                            self.N)
        elif self.switch_mode == 'density_dependent':
            self.cells = epigenetic_switch_density_dependent(self.cells,
                                                              self.public_good,
                                                              self.switch_threshold,
                                                              max(self.switch_rate_coop_to_cheat, 
                                                                  self.switch_rate_cheat_to_coop),
                                                              self.N)
        
        final_cooperators = np.sum(self.cells == 1)
        self.switch_events = abs(final_cooperators - initial_cooperators)
    
    def step(self, diffusion_steps=10, moran_steps_per_gen=None):
        if moran_steps_per_gen is None:
            moran_steps_per_gen = self.N * self.N
        
        for _ in range(diffusion_steps):
            self.public_good = diffuse_numba(self.public_good, self.D, self.dt, self.dx, self.dy)
        
        self.public_good = produce_public_good(self.cells, self.public_good, self.delta, self.N)
        self.public_good = degrade_public_good(self.public_good, self.gamma, self.dt)
        
        if self.resource_mode == 'uniform':
            self.fitness = calculate_fitness(self.cells, self.public_good, self.r, self.k, self.delta)
        else:
            self.fitness = calculate_fitness_with_resources(
                self.cells, self.public_good, self.resources,
                self.r, self.k, self.delta, self.resource_weight
            )
        
        self._apply_epigenetic_switch()
        self._apply_movement()
        
        self.cells = moran_update_batch(self.cells, self.fitness, self.N, moran_steps_per_gen)
        
        self.generation += 1
        self.time += self.time_per_gen
        
        self._record_data()
    
    def _record_data(self):
        num_cooperators = np.sum(self.cells == 1)
        num_cheaters = np.sum(self.cells == 0)
        total_cells = self.N * self.N
        
        cooperator_freq = num_cooperators / total_cells
        cheater_freq = num_cheaters / total_cells
        
        spatial_auto = compute_spatial_autocorrelation(self.cells)
        cluster_info = get_cluster_analysis(self.cells)
        
        record = {
            'time': self.time,
            'generation': self.generation,
            'cooperator_frequency': cooperator_freq,
            'cheater_frequency': cheater_freq,
            'spatial_autocorrelation': spatial_auto,
            'avg_public_good': np.mean(self.public_good),
            'max_public_good': np.max(self.public_good),
            'min_public_good': np.min(self.public_good),
            'avg_fitness': np.mean(self.fitness),
            'num_cooperator_clusters': len(cluster_info['cooperator_clusters']),
            'num_cheater_clusters': len(cluster_info['cheater_clusters']),
            'avg_cooperator_cluster_size': cluster_info['avg_cooperator_cluster_size'],
            'avg_cheater_cluster_size': cluster_info['avg_cheater_cluster_size'],
            'max_cooperator_cluster': cluster_info['max_cooperator_cluster'],
            'max_cheater_cluster': cluster_info['max_cheater_cluster'],
            'switch_events': self.switch_events
        }
        
        if self.resource_mode != 'uniform':
            record['avg_resource'] = np.mean(self.resources)
            record['max_resource'] = np.max(self.resources)
            record['min_resource'] = np.min(self.resources)
            
            coop_resource = np.sum(self.cells * self.resources) / num_cooperators if num_cooperators > 0 else 0
            cheat_resource = np.sum((1 - self.cells) * self.resources) / num_cheaters if num_cheaters > 0 else 0
            record['avg_cooperator_resource'] = coop_resource
            record['avg_cheater_resource'] = cheat_resource
        
        self.trajectory_data.append(record)
    
    def get_trajectory(self):
        df = pd.DataFrame(self.trajectory_data)
        if len(df) > 0:
            df = df.sort_values('generation').reset_index(drop=True)
            df = df.set_index('time', drop=False)
            df.index.name = None
        return df
    
    def save_trajectory(self, filename='evolution_trajectory.csv'):
        df = self.get_trajectory()
        df.to_csv(filename, index=False)
        return df
    
    def setup_visualization(self):
        if self.resource_mode != 'uniform':
            self.fig, self.axes = plt.subplots(2, 3, figsize=(16, 10))
            self.fig.suptitle('Evolution Simulator - With Spatial Resource Heterogeneity', fontsize=14)
            
            self.im_resource = self.axes[0, 2].imshow(self.resources, cmap='YlOrBr', interpolation='nearest')
            self.axes[0, 2].set_title('Resource Distribution')
            plt.colorbar(self.im_resource, ax=self.axes[0, 2])
            
            self.ax_freq = self.axes[1, 0]
            self.ax_auto = self.axes[1, 1]
            self.ax_extra = self.axes[1, 2]
            
            self.line_switch, = self.ax_extra.plot([], [], 'm-', label='Switch Events')
            self.ax_extra.set_xlabel('Time')
            self.ax_extra.set_ylabel('Switch Events')
            self.ax_extra.set_title('Epigenetic Switching')
            self.ax_extra.grid(True, alpha=0.3)
        else:
            self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 10))
            self.fig.suptitle('Evolution Simulator - Individual-Based Model', fontsize=14)
            
            self.ax_freq = self.axes[1, 0]
            self.ax_auto = self.axes[1, 1]
        
        self.im_cells = self.axes[0, 0].imshow(self.cells, cmap='coolwarm', vmin=0, vmax=1, interpolation='nearest')
        self.axes[0, 0].set_title('Cell Types (Red=Cooperator, Blue=Cheater)')
        plt.colorbar(self.im_cells, ax=self.axes[0, 0])
        
        self.im_pg = self.axes[0, 1].imshow(self.public_good, cmap='viridis', interpolation='nearest')
        self.axes[0, 1].set_title('Public Good Concentration')
        plt.colorbar(self.im_pg, ax=self.axes[0, 1])
        
        self.line_freq, = self.ax_freq.plot([], [], 'r-', label='Cooperators')
        self.line_freq2, = self.ax_freq.plot([], [], 'b-', label='Cheaters')
        self.ax_freq.set_xlabel('Time')
        self.ax_freq.set_ylabel('Frequency')
        self.ax_freq.set_title('Cell Type Frequencies')
        self.ax_freq.legend()
        self.ax_freq.set_ylim(0, 1)
        self.ax_freq.grid(True, alpha=0.3)
        
        self.line_auto, = self.ax_auto.plot([], [], 'g-')
        self.ax_auto.set_xlabel('Time')
        self.ax_auto.set_ylabel('Spatial Autocorrelation')
        self.ax_auto.set_title('Spatial Clustering')
        self.ax_auto.set_ylim(-1, 1)
        self.ax_auto.grid(True, alpha=0.3)
        
        plt.tight_layout()
    
    def update_visualization(self):
        if self.fig is None:
            self.setup_visualization()
        
        self.im_cells.set_data(self.cells)
        self.im_pg.set_data(self.public_good)
        self.im_pg.set_clim(vmin=np.min(self.public_good), vmax=np.max(self.public_good))
        
        if self.resource_mode != 'uniform':
            self.im_resource.set_data(self.resources)
        
        df = self.get_trajectory()
        if len(df) > 0:
            self.line_freq.set_data(df['time'], df['cooperator_frequency'])
            self.line_freq2.set_data(df['time'], df['cheater_frequency'])
            self.line_auto.set_data(df['time'], df['spatial_autocorrelation'])
            
            self.ax_freq.set_xlim(0, max(df['time']))
            self.ax_auto.set_xlim(0, max(df['time']))
            
            if self.resource_mode != 'uniform' and 'switch_events' in df.columns:
                self.line_switch.set_data(df['time'], df['switch_events'])
                self.ax_extra.set_xlim(0, max(df['time']))
                if max(df['switch_events']) > 0:
                    self.ax_extra.set_ylim(0, max(df['switch_events']) * 1.1)
        
        self.fig.canvas.draw()
    
    def save_visualization(self, filename='snapshot.png'):
        if self.fig is None:
            self.setup_visualization()
        
        self.update_visualization()
        self.fig.savefig(filename, dpi=150)
    
    def run(self, num_generations, visualize=True, record_interval=1, save_interval=50):
        if visualize:
            self.setup_visualization()
        
        start_time = time.time()
        
        for gen in range(num_generations):
            self.step()
            
            if (gen + 1) % record_interval == 0:
                df = self.get_trajectory()
                latest = df.iloc[-1]
                elapsed = time.time() - start_time
                print(f"\rGeneration {self.generation}/{num_generations} [{elapsed:.1f}s]: "
                      f"Coop={latest['cooperator_frequency']:.3f}, "
                      f"Cheat={latest['cheater_frequency']:.3f}, "
                      f"AutoCorr={latest['spatial_autocorrelation']:.3f}, "
                      f"AvgPG={latest['avg_public_good']:.4f}", end='', flush=True)
                
                if visualize and (gen + 1) % save_interval == 0:
                    self.save_visualization(f'snapshot_gen_{self.generation}.png')
        
        print()
        if visualize:
            self.save_visualization('final_snapshot.png')
        
        return self.get_trajectory()
    
    def gillespie_validate(self, max_time=100.0, num_samples=100):
        N = self.N
        total_cells = N * N
        
        t = 0.0
        cells_gill = self.cells.copy()
        pg_gill = self.public_good.copy()
        
        results = []
        sample_times = np.linspace(0, max_time, num_samples)
        sample_idx = 0
        
        while t < max_time and sample_idx < num_samples:
            pg_gill = diffuse_numba(pg_gill, self.D, self.dt, self.dx, self.dy)
            pg_gill = produce_public_good(cells_gill, pg_gill, self.delta, N)
            pg_gill = degrade_public_good(pg_gill, self.gamma, self.dt)
            
            fitness_gill = calculate_fitness(cells_gill, pg_gill, self.r, self.k, self.delta)
            
            total_fitness = np.sum(fitness_gill)
            birth_rate = total_fitness
            death_rate = total_cells * 1.0
            total_rate = birth_rate + death_rate
            
            if total_rate <= 0:
                break
            
            tau = np.random.exponential(1.0 / total_rate)
            t += tau
            
            rand = np.random.random() * total_rate
            
            if rand < birth_rate:
                rand_val = np.random.random() * total_fitness
                cum_sum = 0.0
                birth_i, birth_j = 0, 0
                
                for i in range(N):
                    for j in range(N):
                        cum_sum += fitness_gill[i, j]
                        if cum_sum >= rand_val:
                            birth_i, birth_j = i, j
                            break
                    if cum_sum >= rand_val:
                        break
                
                death_i = np.random.randint(0, N)
                death_j = np.random.randint(0, N)
                cells_gill[death_i, death_j] = cells_gill[birth_i, birth_j]
            else:
                death_i = np.random.randint(0, N)
                death_j = np.random.randint(0, N)
                
                rand_val = np.random.random() * total_fitness
                cum_sum = 0.0
                birth_i, birth_j = 0, 0
                
                for i in range(N):
                    for j in range(N):
                        cum_sum += fitness_gill[i, j]
                        if cum_sum >= rand_val:
                            birth_i, birth_j = i, j
                            break
                    if cum_sum >= rand_val:
                        break
                
                cells_gill[death_i, death_j] = cells_gill[birth_i, birth_j]
            
            while sample_idx < len(sample_times) and t >= sample_times[sample_idx]:
                num_cooperators = np.sum(cells_gill == 1)
                results.append({
                    'time': t,
                    'cooperator_frequency': num_cooperators / total_cells,
                    'avg_public_good': np.mean(pg_gill),
                    'spatial_autocorrelation': compute_spatial_autocorrelation(cells_gill)
                })
                sample_idx += 1
        
        return pd.DataFrame(results)

def plot_comparison(deterministic_df, gillespie_df, filename='comparison_plot.png'):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    axes[0].plot(deterministic_df['time'], deterministic_df['cooperator_frequency'], 
                 'r-', linewidth=2, label='Moran Process')
    axes[0].plot(gillespie_df['time'], gillespie_df['cooperator_frequency'], 
                 'b--', linewidth=1.5, alpha=0.7, label='Gillespie Algorithm')
    axes[0].set_xlabel('Time', fontsize=12)
    axes[0].set_ylabel('Cooperator Frequency', fontsize=12)
    axes[0].set_title('Cooperator Frequency Comparison', fontsize=14)
    axes[0].legend(fontsize=10)
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(deterministic_df['time'], deterministic_df['avg_public_good'], 
                 'r-', linewidth=2, label='Moran Process')
    axes[1].plot(gillespie_df['time'], gillespie_df['avg_public_good'], 
                 'b--', linewidth=1.5, alpha=0.7, label='Gillespie Algorithm')
    axes[1].set_xlabel('Time', fontsize=12)
    axes[1].set_ylabel('Average Public Good', fontsize=12)
    axes[1].set_title('Public Good Comparison', fontsize=14)
    axes[1].legend(fontsize=10)
    axes[1].grid(True, alpha=0.3)
    
    axes[2].plot(deterministic_df['time'], deterministic_df['spatial_autocorrelation'], 
                 'r-', linewidth=2, label='Moran Process')
    axes[2].plot(gillespie_df['time'], gillespie_df['spatial_autocorrelation'], 
                 'b--', linewidth=1.5, alpha=0.7, label='Gillespie Algorithm')
    axes[2].set_xlabel('Time', fontsize=12)
    axes[2].set_ylabel('Spatial Autocorrelation', fontsize=12)
    axes[2].set_title('Spatial Autocorrelation Comparison', fontsize=14)
    axes[2].legend(fontsize=10)
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

def plot_trajectory_summary(df, filename='trajectory_summary.png'):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    
    axes[0, 0].plot(df['time'], df['cooperator_frequency'], 'r-', label='Cooperators')
    axes[0, 0].plot(df['time'], df['cheater_frequency'], 'b-', label='Cheaters')
    axes[0, 0].set_xlabel('Time')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Cell Type Frequencies')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_ylim(0, 1)
    
    axes[0, 1].plot(df['time'], df['spatial_autocorrelation'], 'g-')
    axes[0, 1].set_xlabel('Time')
    axes[0, 1].set_ylabel('Spatial Autocorrelation')
    axes[0, 1].set_title('Spatial Clustering (Moran\'s I)')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].axhline(y=0, color='k', linestyle='--', alpha=0.5)
    
    axes[0, 2].plot(df['time'], df['avg_public_good'], 'm-', label='Average')
    axes[0, 2].fill_between(df['time'], df['min_public_good'], df['max_public_good'], alpha=0.2, color='m')
    axes[0, 2].set_xlabel('Time')
    axes[0, 2].set_ylabel('Public Good Concentration')
    axes[0, 2].set_title('Public Good Distribution')
    axes[0, 2].legend()
    axes[0, 2].grid(True, alpha=0.3)
    
    axes[1, 0].plot(df['time'], df['avg_fitness'], 'k-')
    axes[1, 0].set_xlabel('Time')
    axes[1, 0].set_ylabel('Average Fitness')
    axes[1, 0].set_title('Population Average Fitness')
    axes[1, 0].grid(True, alpha=0.3)
    
    axes[1, 1].plot(df['time'], df['num_cooperator_clusters'], 'r-', label='Cooperator Clusters')
    axes[1, 1].plot(df['time'], df['num_cheater_clusters'], 'b-', label='Cheater Clusters')
    axes[1, 1].set_xlabel('Time')
    axes[1, 1].set_ylabel('Number of Clusters')
    axes[1, 1].set_title('Cluster Number Dynamics')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    axes[1, 2].plot(df['time'], df['avg_cooperator_cluster_size'], 'r-', label='Cooperators')
    axes[1, 2].plot(df['time'], df['avg_cheater_cluster_size'], 'b-', label='Cheaters')
    axes[1, 2].set_xlabel('Time')
    axes[1, 2].set_ylabel('Average Cluster Size')
    axes[1, 2].set_title('Average Cluster Size Dynamics')
    axes[1, 2].legend()
    axes[1, 2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

def main():
    print("=" * 80)
    print("Evolution Simulator - Individual-Based Model with Public Goods")
    print("Enhanced Features: Spatial Heterogeneity, Cell Movement, Epigenetic Switching")
    print("=" * 80)
    print()
    
    print("Model Parameters:")
    print(f"  Grid size: 100x100")
    print(f"  Diffusion coefficient (D): 0.5")
    print(f"  Maximum growth rate (r): 1.5")
    print(f"  Half-saturation constant (k): 0.1")
    print(f"  Production cost (delta): 0.05")
    print(f"  Degradation rate (gamma): 0.1")
    print(f"  Initial cooperator frequency: 0.5")
    print()
    
    print("Available Enhanced Features:")
    print("  1. Spatial resource heterogeneity: gradient_x, gradient_y, radial, patches, random")
    print("  2. Cell movement: random walk, chemotaxis (toward public good)")
    print("  3. Epigenetic switching: constant rate, density-dependent")
    print()
    
    scenarios = [
        {
            'name': 'Control (uniform_resources_random_movement',
            'resource_mode': 'uniform',
            'movement_mode': 'random',
            'move_prob': 0.02,
            'switch_mode': 'none',
            'generations': 30
        },
        {
            'name': 'Spatial_gradient_chemotaxis',
            'resource_mode': 'gradient_x',
            'resource_kwargs': {'min_val': 0.2, 'max_val': 1.0},
            'movement_mode': 'chemotaxis',
            'move_prob': 0.03,
            'chemotaxis_strength': 2.0,
            'switch_mode': 'none',
            'generations': 30
        },
        {
            'name': 'Patchy_resources_epigenetic_switch',
            'resource_mode': 'patches',
            'resource_kwargs': {'num_patches': 15, 'patch_size': 6, 'seed': 42},
            'movement_mode': 'random',
            'move_prob': 0.01,
            'switch_mode': 'density_dependent',
            'switch_threshold': 0.3,
            'switch_rate_coop_to_cheat': 0.01,
            'switch_rate_cheat_to_coop': 0.01,
            'generations': 30
        }
    ]
    
    for idx, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*60}")
        print(f"Scenario {idx}: {scenario['name']}")
        print(f"{'='*60}")
        print(f"  Resource mode: {scenario['resource_mode']}")
        print(f"  Movement mode: {scenario['movement_mode']}")
        print(f"  Switch mode: {scenario['switch_mode']}")
        print(f"  Generations: {scenario['generations']}")
        print()
        
        np.random.seed(42)
        random.seed(42)
        
        sim = EvolutionSimulator(
            N=50,
            D=0.5,
            r=1.5,
            k=0.1,
            delta=0.05,
            gamma=0.1,
            initial_cooperator_freq=0.5,
            resource_mode=scenario['resource_mode'],
            resource_kwargs=scenario.get('resource_kwargs', None),
            movement_mode=scenario['movement_mode'],
            move_prob=scenario.get('move_prob', 0.0),
            chemotaxis_strength=scenario.get('chemotaxis_strength', 1.0),
            switch_mode=scenario['switch_mode'],
            switch_rate_coop_to_cheat=scenario.get('switch_rate_coop_to_cheat', 0.0),
            switch_rate_cheat_to_coop=scenario.get('switch_rate_cheat_to_coop', 0.0),
            switch_threshold=scenario.get('switch_threshold', 0.5)
        )
        
        trajectory = sim.run(
            num_generations=scenario['generations'],
            visualize=True,
            record_interval=1,
            save_interval=10
        )
        print()
        
        final = trajectory.iloc[-1]
        print(f"  Final Statistics:")
        print(f"    Cooperator frequency: {final['cooperator_frequency']:.4f}")
        print(f"    Cheater frequency: {final['cheater_frequency']:.4f}")
        print(f"    Spatial autocorrelation: {final['spatial_autocorrelation']:.4f}")
        print(f"    Average public good: {final['avg_public_good']:.4f}")
        print(f"    Average fitness: {final['avg_fitness']:.4f}")
        
        if 'avg_resource' in final:
            print(f"    Average resource: {final['avg_resource']:.4f}")
            print(f"    Cooperator avg resource: {final['avg_cooperator_resource']:.4f}")
            print(f"    Cheater avg resource: {final['avg_cheater_resource']:.4f}")
        
        if 'switch_events' in final:
            print(f"    Total switch events: {trajectory['switch_events'].sum()}")
        
        sim.save_visualization(f"{scenario['name']}_final.png")
        trajectory.to_csv(f"{scenario['name']}_trajectory.csv", index=False)
        print(f"\n  Saved: {scenario['name']}_final.png, {scenario['name']}_trajectory.csv")
    
    print("\n" + "=" * 80)
    print("Running full simulation with all features (100x100, 100 generations)...")
    print("=" * 80)
    
    np.random.seed(123)
    random.seed(123)
    
    sim_full = EvolutionSimulator(
        N=100,
        D=0.5,
        r=1.5,
        k=0.1,
        delta=0.05,
        gamma=0.1,
        initial_cooperator_freq=0.5,
        resource_mode='random',
        resource_kwargs={'min_val': 0.2, 'max_val': 1.0, 'smooth_sigma': 3.0},
        movement_mode='chemotaxis',
        move_prob=0.02,
        chemotaxis_strength=1.5,
        switch_mode='constant',
        switch_rate_coop_to_cheat=0.005,
        switch_rate_cheat_to_coop=0.005
    )
    
    print()
    print("Full Simulation Configuration:")
    print(f"  Resource: random smooth field")
    print(f"  Movement: chemotaxis (move_prob=0.02, strength=1.5")
    print(f"  Epigenetic switching: constant rate (0.005 per generation)")
    print()
    
    start_time = time.time()
    trajectory_full = sim_full.run(
        num_generations=100,
        visualize=True,
        record_interval=1,
        save_interval=20
    )
    elapsed = time.time() - start_time
    
    print()
    print(f"\nFull simulation completed in {elapsed:.2f} seconds")
    
    sim_full.save_trajectory('full_simulation_trajectory.csv')
    plot_trajectory_summary(trajectory_full, 'full_simulation_summary.png')
    sim_full.save_visualization('full_simulation_final.png')
    
    print("\nFinal Statistics:")
    final = trajectory_full.iloc[-1]
    print(f"  Cooperator frequency: {final['cooperator_frequency']:.4f}")
    print(f"  Cheater frequency: {final['cheater_frequency']:.4f}")
    print(f"  Spatial autocorrelation: {final['spatial_autocorrelation']:.4f}")
    print(f"  Average public good: {final['avg_public_good']:.4f}")
    print(f"  Average resource: {final['avg_resource']:.4f}")
    print(f"  Total switch events: {trajectory_full['switch_events'].sum()}")
    
    print("\nRunning Gillespie algorithm validation (max_time=100)...")
    gillespie_results = sim_full.gillespie_validate(max_time=100.0, num_samples=100)
    gillespie_results.to_csv('gillespie_validation.csv', index=False)
    print("  -> Saved to 'gillespie_validation.csv'")
    
    print("Generating comparison plots...")
    plot_comparison(trajectory, gillespie_results, 'comparison_plot.png')
    print("  -> Saved to 'comparison_plot.png'")
    print()
    
    print("=" * 70)
    print("All simulations completed successfully!")
    print("=" * 70)
    print()
    print("Output files generated:")
    print("  - evolution_trajectory.csv: Full Moran process trajectory")
    print("  - gillespie_validation.csv: Gillespie algorithm validation data")
    print("  - trajectory_summary.png: Summary of evolutionary dynamics")
    print("  - comparison_plot.png: Moran vs Gillespie comparison")
    print("  - snapshot_gen_*.png: Periodic snapshots during simulation")
    print("  - final_snapshot.png: Final state visualization")
    
    return sim, trajectory, gillespie_results

if __name__ == "__main__":
    main()
