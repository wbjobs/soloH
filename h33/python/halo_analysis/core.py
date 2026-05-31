import numpy as np
import struct
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict

try:
    from numba import jit, njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(f=None, *args, **kwargs):
        def decorator(func):
            return func
        if f is None:
            return decorator
        return decorator(f)
    def jit(f=None, *args, **kwargs):
        def decorator(func):
            return func
        if f is None:
            return decorator
        return decorator(f)

G = 4.30091e-9
RHO_CRIT = 2.77536627e11
PI = np.pi

@dataclass
class EllipsoidalShape:
    axis_a: float = 0.0
    axis_b: float = 0.0
    axis_c: float = 0.0
    axis_ratio_b_a: float = 0.0
    axis_ratio_c_a: float = 0.0
    ellipticity: float = 0.0
    prolateness: float = 0.0
    triaxiality: float = 0.0
    orientation_matrix: np.ndarray = field(default_factory=lambda: np.eye(3))
    euler_angles: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    converged: bool = False

@dataclass
class ParticleData:
    ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint64))
    positions: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    velocities: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    masses: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))

    def size(self) -> int:
        return len(self.ids)

    def reserve(self, n: int):
        pass

    def clear(self):
        self.ids = np.array([], dtype=np.uint64)
        self.positions = np.array([], dtype=np.float64)
        self.velocities = np.array([], dtype=np.float64)
        self.masses = np.array([], dtype=np.float64)

@dataclass
class Halo:
    halo_id: int = 0
    snapshot_index: int = 0
    redshift: float = 0.0
    particle_ids: List[int] = field(default_factory=list)
    mass: float = 0.0
    center_of_mass: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    mean_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity_dispersion: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    spin_parameter: float = 0.0
    formation_redshift: float = 0.0
    descendant_id: int = 0
    progenitor_ids: List[int] = field(default_factory=list)
    subhalo_ids: List[int] = field(default_factory=list)
    shape: EllipsoidalShape = field(default_factory=EllipsoidalShape)
    substructure_ids: List[int] = field(default_factory=list)
    parent_halo_id: int = 0
    is_substructure: bool = False

@dataclass
class Snapshot:
    index: int = 0
    redshift: float = 0.0
    scale_factor: float = 1.0
    box_size: float = 0.0
    particles: ParticleData = field(default_factory=ParticleData)
    halos: List[Halo] = field(default_factory=list)

@dataclass
class MergerTreeNode:
    halo_id: int = 0
    snapshot_index: int = 0
    redshift: float = 0.0
    mass: float = 0.0
    formation_redshift: float = 0.0
    spin_parameter: float = 0.0
    descendant_id: int = 0
    progenitor_ids: List[int] = field(default_factory=list)
    subhalo_ids: List[int] = field(default_factory=list)
    center_of_mass: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    num_particles: int = 0

def compute_mean_interparticle_spacing(box_size: float, num_particles: int) -> float:
    return box_size / np.cbrt(num_particles)

@njit
def _periodic_distance(pos1: np.ndarray, pos2: np.ndarray, box_size: float) -> float:
    dx = pos1[0] - pos2[0]
    dy = pos1[1] - pos2[1]
    dz = pos1[2] - pos2[2]
    dx -= box_size * np.round(dx / box_size)
    dy -= box_size * np.round(dy / box_size)
    dz -= box_size * np.round(dz / box_size)
    return np.sqrt(dx*dx + dy*dy + dz*dz)

def periodic_distance(pos1: Tuple[float, float, float], pos2: Tuple[float, float, float], box_size: float) -> float:
    return _periodic_distance(np.array(pos1), np.array(pos2), box_size)

class GadgetReader:
    def __init__(self):
        pass

    def _read_block(self, f, size: int) -> Optional[bytes]:
        try:
            block_size_before = struct.unpack('i', f.read(4))[0]
            if block_size_before != size:
                return None
            data = f.read(size)
            block_size_after = struct.unpack('i', f.read(4))[0]
            if block_size_before != block_size_after:
                return None
            return data
        except:
            return None

    def read_header(self, filename: str) -> Optional[Dict]:
        if not os.path.exists(filename):
            return None

        header_format = (
            '6I'
            '6d'
            'd'
            'd'
            '2i'
            '6I'
            '2i'
            '4d'
            '2i'
            '6I'
            'i'
            '60s'
        )
        header_size = struct.calcsize(header_format)

        with open(filename, 'rb') as f:
            data = self._read_block(f, header_size)
            if data is None:
                return None

            header = struct.unpack(header_format, data)
            idx = 0
            npart = list(header[idx:idx+6]); idx += 6
            massarr = list(header[idx:idx+6]); idx += 6
            time = header[idx]; idx += 1
            redshift = header[idx]; idx += 1
            flag_sfr = header[idx]; idx += 1
            flag_feedback = header[idx]; idx += 1
            npartTotal = list(header[idx:idx+6]); idx += 6
            flag_cooling = header[idx]; idx += 1
            num_files = header[idx]; idx += 1
            BoxSize = header[idx]; idx += 1
            Omega0 = header[idx]; idx += 1
            OmegaLambda = header[idx]; idx += 1
            HubbleParam = header[idx]; idx += 1
            flag_stellarage = header[idx]; idx += 1
            flag_metals = header[idx]; idx += 1
            npartTotalHighWord = list(header[idx:idx+6]); idx += 6
            flag_entropy_instead_u = header[idx]; idx += 1

            return {
                'npart': npart,
                'massarr': massarr,
                'time': time,
                'redshift': redshift,
                'box_size': BoxSize,
                'npartTotal': npartTotal,
                'num_files': num_files,
            }

    def read(self, filename: str, snapshot: Snapshot, snapshot_index: int = 0) -> bool:
        header = self.read_header(filename)
        if header is None:
            return False

        total_particles = sum(header['npart'])
        header_format_size = 256

        try:
            with open(filename, 'rb') as f:
                f.seek(4 + header_format_size + 4)

                pos_data = self._read_block(f, 4 * total_particles * 3)
                if pos_data is None:
                    return False
                positions = np.frombuffer(pos_data, dtype=np.float32).reshape(-1, 3).astype(np.float64)

                vel_data = self._read_block(f, 4 * total_particles * 3)
                if vel_data is None:
                    return False
                velocities = np.frombuffer(vel_data, dtype=np.float32).reshape(-1, 3).astype(np.float64)

                id_size = 8 if (header['npartTotal'][1] & (1 << 31)) else 4
                id_data = self._read_block(f, id_size * total_particles)
                if id_data is None:
                    return False
                if id_size == 4:
                    ids = np.frombuffer(id_data, dtype=np.uint32).astype(np.uint64)
                else:
                    ids = np.frombuffer(id_data, dtype=np.uint64)

                masses = np.zeros(total_particles, dtype=np.float64)
                mass_offset = 0
                for ptype in range(6):
                    n = header['npart'][ptype]
                    mass = header['massarr'][ptype]
                    if mass == 0.0 and n > 0:
                        mass_block = self._read_block(f, 4 * n)
                        if mass_block is None:
                            return False
                        masses[mass_offset:mass_offset+n] = np.frombuffer(mass_block, dtype=np.float32).astype(np.float64)
                    else:
                        masses[mass_offset:mass_offset+n] = mass
                    mass_offset += n

                snapshot.index = snapshot_index
                snapshot.redshift = header['redshift']
                snapshot.scale_factor = header['time']
                snapshot.box_size = header['box_size']
                snapshot.particles.ids = ids
                snapshot.particles.positions = positions
                snapshot.particles.velocities = velocities
                snapshot.particles.masses = masses

                return True
        except Exception as e:
            print(f"Error reading Gadget file: {e}")
            return False

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def unite(self, x: int, y: int):
        x = self.find(x)
        y = self.find(y)
        if x == y:
            return
        if self.rank[x] < self.rank[y]:
            x, y = y, x
        self.parent[y] = x
        if self.rank[x] == self.rank[y]:
            self.rank[x] += 1

class FoFFinder:
    def __init__(self, link_length_ratio: float = 0.2, min_particles: int = 20,
                 compute_shape: bool = True):
        self.link_length_ratio = link_length_ratio
        self.min_particles = min_particles
        self.compute_shape = compute_shape
        self.shape_fitter = EllipsoidalFitter()

    def _get_grid_key(self, pos: np.ndarray, cell_size: float, box_size: float, n_cells: int) -> Tuple[int, int, int]:
        nx = int(np.floor(pos[0] / cell_size))
        ny = int(np.floor(pos[1] / cell_size))
        nz = int(np.floor(pos[2] / cell_size))
        nx = ((nx % n_cells) + n_cells) % n_cells
        ny = ((ny % n_cells) + n_cells) % n_cells
        nz = ((nz % n_cells) + n_cells) % n_cells
        return (nx, ny, nz)

    def find_halos(self, snapshot: Snapshot):
        n = snapshot.particles.size()
        if n == 0:
            return

        mean_spacing = compute_mean_interparticle_spacing(snapshot.box_size, n)
        link_length = self.link_length_ratio * mean_spacing
        cell_size = link_length
        n_cells = int(np.floor(snapshot.box_size / cell_size))
        if n_cells < 1:
            n_cells = 1

        positions = snapshot.particles.positions
        grid = defaultdict(list)
        for i in range(n):
            key = self._get_grid_key(positions[i], cell_size, snapshot.box_size, n_cells)
            grid[key].append(i)

        uf = UnionFind(n)

        for i in range(n):
            key = self._get_grid_key(positions[i], cell_size, snapshot.box_size, n_cells)
            x, y, z = key
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        nx = ((x + dx) % n_cells + n_cells) % n_cells
                        ny = ((y + dy) % n_cells + n_cells) % n_cells
                        nz = ((z + dz) % n_cells + n_cells) % n_cells
                        neighbor_key = (nx, ny, nz)
                        if neighbor_key not in grid:
                            continue
                        for j in grid[neighbor_key]:
                            if j <= i:
                                continue
                            dist = _periodic_distance(positions[i], positions[j], snapshot.box_size)
                            if dist < link_length:
                                uf.unite(i, j)

        groups = defaultdict(list)
        for i in range(n):
            root = uf.find(i)
            groups[root].append(i)

        snapshot.halos = []
        halo_id_counter = 0
        for root, members in groups.items():
            if len(members) < self.min_particles:
                continue
            halo = Halo()
            halo.halo_id = snapshot.index * 1000000 + halo_id_counter
            halo_id_counter += 1
            halo.snapshot_index = snapshot.index
            halo.redshift = snapshot.redshift
            halo.particle_ids = [int(snapshot.particles.ids[idx]) for idx in members]
            self.compute_halo_properties(halo, snapshot)
            snapshot.halos.append(halo)

        snapshot.halos.sort(key=lambda h: h.mass, reverse=True)

    def compute_halo_properties(self, halo: Halo, snapshot: Snapshot):
        id_to_idx = {int(pid): i for i, pid in enumerate(snapshot.particles.ids)}

        total_mass = 0.0
        com = np.zeros(3, dtype=np.float64)
        mean_vel = np.zeros(3, dtype=np.float64)

        for pid in halo.particle_ids:
            if pid not in id_to_idx:
                continue
            idx = id_to_idx[pid]
            m = snapshot.particles.masses[idx]
            total_mass += m
            com += m * snapshot.particles.positions[idx]
            mean_vel += m * snapshot.particles.velocities[idx]

        if total_mass > 0:
            com /= total_mass
            mean_vel /= total_mass

        halo.mass = total_mass
        halo.center_of_mass = tuple(float(x) for x in com)
        halo.mean_velocity = tuple(float(x) for x in mean_vel)

        vel_disp = np.zeros(3, dtype=np.float64)
        ang_mom = np.zeros(3, dtype=np.float64)

        for pid in halo.particle_ids:
            if pid not in id_to_idx:
                continue
            idx = id_to_idx[pid]
            m = snapshot.particles.masses[idx]
            pos = snapshot.particles.positions[idx]
            vel = snapshot.particles.velocities[idx]

            dx = pos[0] - com[0]
            dy = pos[1] - com[1]
            dz = pos[2] - com[2]
            dx -= snapshot.box_size * np.round(dx / snapshot.box_size)
            dy -= snapshot.box_size * np.round(dy / snapshot.box_size)
            dz -= snapshot.box_size * np.round(dz / snapshot.box_size)

            dvx = vel[0] - mean_vel[0]
            dvy = vel[1] - mean_vel[1]
            dvz = vel[2] - mean_vel[2]

            for k in range(3):
                vel_disp[k] += m * (vel[k] - mean_vel[k])**2

            ang_mom[0] += m * (dy * dvz - dz * dvy)
            ang_mom[1] += m * (dz * dvx - dx * dvz)
            ang_mom[2] += m * (dx * dvy - dy * dvx)

        if total_mass > 0:
            vel_disp = np.sqrt(vel_disp / total_mass)

        halo.velocity_dispersion = tuple(float(x) for x in vel_disp)

        L = np.sqrt(np.sum(ang_mom**2))
        sigma_total = np.sqrt(np.sum(vel_disp**2))
        n_p = len(halo.particle_ids)

        if sigma_total > 0 and n_p > 0 and total_mass > 0:
            r_vir = np.cbrt(3.0 * total_mass / (4.0 * PI * 200.0 * RHO_CRIT))
            halo.spin_parameter = float(L / (np.sqrt(2.0) * total_mass * sigma_total * r_vir))
        else:
            halo.spin_parameter = 0.0

        if self.compute_shape:
            self.compute_ellipsoidal_shape(halo, snapshot)

    def compute_ellipsoidal_shape(self, halo: Halo, snapshot: Snapshot):
        halo.shape = self.shape_fitter.fit(halo, snapshot, 3)

class MergerTreeBuilder:
    def __init__(self, particle_share_threshold: float = 0.5, subhalo_mass_ratio_threshold: float = 0.1):
        self.particle_share_threshold = particle_share_threshold
        self.subhalo_mass_ratio_threshold = subhalo_mass_ratio_threshold
        self.nodes: List[MergerTreeNode] = []
        self.halo_to_node: Dict[int, int] = {}
        self.halo_id_remap: Dict[int, int] = {}
        self.remap_to_original: Dict[int, int] = {}

    def _compute_particle_share(self, h1: Halo, h2: Halo) -> float:
        set1 = set(h1.particle_ids)
        shared = len(set1.intersection(h2.particle_ids))
        min_size = min(len(h1.particle_ids), len(h2.particle_ids))
        return shared / min_size if min_size > 0 else 0.0

    def _find_main_progenitor(self, halo_id: int, halo_map: Dict[int, Halo]) -> int:
        visited = set()
        current_id = halo_id
        current_halo = halo_map.get(halo_id)

        if current_halo is None:
            return halo_id

        while current_halo is not None and current_halo.progenitor_ids:
            if current_id in visited:
                break
            visited.add(current_id)

            max_mass = 0.0
            main_prog = 0
            for prog_id in current_halo.progenitor_ids:
                if prog_id in halo_map:
                    prog = halo_map[prog_id]
                    if prog.mass > max_mass:
                        max_mass = prog.mass
                        main_prog = prog_id

            if main_prog == 0:
                break

            mass_ratio = max_mass / current_halo.mass if current_halo.mass > 0 else 0
            if mass_ratio < 0.5:
                break

            current_id = main_prog
            current_halo = halo_map.get(current_id)

        return current_id if current_halo is not None else halo_id

    def _add_halo_node(self, halo: Halo):
        node = MergerTreeNode(
            halo_id=halo.halo_id,
            snapshot_index=halo.snapshot_index,
            redshift=halo.redshift,
            mass=halo.mass,
            formation_redshift=halo.formation_redshift,
            spin_parameter=halo.spin_parameter,
            descendant_id=halo.descendant_id,
            progenitor_ids=list(halo.progenitor_ids),
            subhalo_ids=list(halo.subhalo_ids),
            center_of_mass=halo.center_of_mass,
            num_particles=len(halo.particle_ids),
        )
        self.halo_to_node[halo.halo_id] = len(self.nodes)
        self.nodes.append(node)

    def assign_consistent_halo_ids(self, snapshots: List[Snapshot]):
        halo_map: Dict[int, Halo] = {}
        for snap in snapshots:
            for halo in snap.halos:
                halo_map[halo.halo_id] = halo

        self.halo_id_remap = {}
        self.remap_to_original = {}
        next_id = 1

        snapshots.sort(key=lambda s: s.redshift)

        for i, snap in enumerate(snapshots):
            snap.index = i
            for halo in snap.halos:
                halo.snapshot_index = i
                halo.redshift = snap.redshift

        for snap in snapshots:
            for halo in snap.halos:
                root_id = self._find_main_progenitor(halo.halo_id, halo_map)

                if root_id in self.halo_id_remap:
                    new_id = self.halo_id_remap[root_id]
                else:
                    new_id = next_id
                    next_id += 1
                    self.halo_id_remap[root_id] = new_id
                    self.remap_to_original[new_id] = root_id

                self.halo_id_remap[halo.halo_id] = new_id
                self.remap_to_original[new_id] = root_id

        for snap in snapshots:
            for halo in snap.halos:
                old_id = halo.halo_id
                halo.halo_id = self.halo_id_remap[old_id]

                if halo.descendant_id != 0:
                    halo.descendant_id = self.halo_id_remap[halo.descendant_id]

                for i, prog_id in enumerate(halo.progenitor_ids):
                    if prog_id in self.halo_id_remap:
                        halo.progenitor_ids[i] = self.halo_id_remap[prog_id]

                for i, sub_id in enumerate(halo.subhalo_ids):
                    if sub_id in self.halo_id_remap:
                        halo.subhalo_ids[i] = self.halo_id_remap[sub_id]

    def sort_progenitors_by_mass(self, snapshots: List[Snapshot]):
        halo_map: Dict[int, Halo] = {}
        for snap in snapshots:
            for halo in snap.halos:
                halo_map[halo.halo_id] = halo

        for snap in snapshots:
            for halo in snap.halos:
                if len(halo.progenitor_ids) > 1:
                    halo.progenitor_ids.sort(
                        key=lambda pid: halo_map[pid].mass if pid in halo_map else 0,
                        reverse=True
                    )

        for node in self.nodes:
            if len(node.progenitor_ids) > 1:
                node.progenitor_ids.sort(
                    key=lambda pid: self.nodes[self.halo_to_node[pid]].mass
                    if pid in self.halo_to_node else 0,
                    reverse=True
                )

    def get_halo_id_mapping(self) -> Dict[int, int]:
        return self.halo_id_remap

    def get_original_halo_id(self, remapped_id: int) -> int:
        return self.remap_to_original.get(remapped_id, remapped_id)

    def build_trees(self, snapshots: List[Snapshot]):
        self.nodes = []
        self.halo_to_node = {}
        self.halo_id_remap = {}
        self.remap_to_original = {}

        snapshots.sort(key=lambda s: s.redshift, reverse=True)

        for i, snap in enumerate(snapshots):
            snap.index = i
            for halo in snap.halos:
                halo.snapshot_index = i
                halo.redshift = snap.redshift
                halo.descendant_id = 0
                halo.progenitor_ids = []

        for snap_idx in range(len(snapshots) - 1):
            next_snap_idx = snap_idx + 1
            current_snap = snapshots[snap_idx]
            next_snap = snapshots[next_snap_idx]

            for current_halo in current_snap.halos:
                best_share = self.particle_share_threshold
                best_descendant = 0

                for next_halo in next_snap.halos:
                    share = self._compute_particle_share(current_halo, next_halo)
                    if share > best_share:
                        best_share = share
                        best_descendant = next_halo.halo_id

                current_halo.descendant_id = best_descendant
                if best_descendant != 0:
                    for next_halo in next_snap.halos:
                        if next_halo.halo_id == best_descendant:
                            next_halo.progenitor_ids.append(current_halo.halo_id)
                            break

        self.sort_progenitors_by_mass(snapshots)
        self.assign_consistent_halo_ids(snapshots)
        self.sort_progenitors_by_mass(snapshots)

        self.nodes = []
        self.halo_to_node = {}
        for snap in snapshots:
            for halo in snap.halos:
                self._add_halo_node(halo)

    def compute_formation_redshifts(self, snapshots: List[Snapshot]):
        halo_map = {}
        for snap in snapshots:
            for halo in snap.halos:
                halo_map[halo.halo_id] = halo

        for snap in snapshots:
            for halo in snap.halos:
                if not halo.progenitor_ids:
                    halo.formation_redshift = halo.redshift
                else:
                    half_mass = halo.mass * 0.5
                    progenitor_with_half = 0
                    max_prog_mass = 0.0

                    for prog_id in halo.progenitor_ids:
                        if prog_id in halo_map:
                            prog = halo_map[prog_id]
                            if prog.mass >= half_mass and prog.mass > max_prog_mass:
                                max_prog_mass = prog.mass
                                progenitor_with_half = prog_id

                    if progenitor_with_half != 0:
                        halo.formation_redshift = halo_map[progenitor_with_half].formation_redshift
                    else:
                        halo.formation_redshift = halo.redshift

                if halo.halo_id in self.halo_to_node:
                    self.nodes[self.halo_to_node[halo.halo_id]].formation_redshift = halo.formation_redshift

    def identify_subhalos(self, snapshots: List[Snapshot]):
        for snap in snapshots:
            for i, main_halo in enumerate(snap.halos):
                for j, other_halo in enumerate(snap.halos):
                    if i == j:
                        continue
                    mass_ratio = other_halo.mass / main_halo.mass if main_halo.mass > 0 else 0
                    if 0 < mass_ratio < self.subhalo_mass_ratio_threshold:
                        dist = periodic_distance(
                            main_halo.center_of_mass,
                            other_halo.center_of_mass,
                            snap.box_size
                        )
                        main_r_vir = np.cbrt(3.0 * main_halo.mass / (4.0 * PI * 200.0 * RHO_CRIT))
                        if dist < 2.0 * main_r_vir:
                            main_halo.subhalo_ids.append(other_halo.halo_id)

                if main_halo.halo_id in self.halo_to_node:
                    self.nodes[self.halo_to_node[main_halo.halo_id]].subhalo_ids = list(main_halo.subhalo_ids)

    def get_nodes(self) -> List[MergerTreeNode]:
        return self.nodes

    def get_halo_to_node(self) -> Dict[int, int]:
        return self.halo_to_node

    def get_progenitor_chain(self, halo_id: int) -> List[int]:
        chain = []
        visited = set()

        def dfs(hid: int, depth: int = 0):
            if hid in visited or depth > 1000:
                return
            visited.add(hid)
            if hid not in self.halo_to_node:
                return
            node = self.nodes[self.halo_to_node[hid]]
            for prog_id in node.progenitor_ids:
                dfs(prog_id, depth + 1)
            chain.append(hid)

        dfs(halo_id)
        return chain

    def get_descendant_chain(self, halo_id: int) -> List[int]:
        chain = []
        visited = set()
        current = halo_id
        while current != 0:
            if current in visited:
                break
            if current not in self.halo_to_node:
                break
            visited.add(current)
            chain.append(current)
            current = self.nodes[self.halo_to_node[current]].descendant_id
        return chain

    def filter_by_mass(self, min_mass: float, max_mass: float) -> List[MergerTreeNode]:
        return [n for n in self.nodes if min_mass <= n.mass <= max_mass]

    def filter_by_redshift(self, min_z: float, max_z: float) -> List[MergerTreeNode]:
        return [n for n in self.nodes if min_z <= n.redshift <= max_z]

    def get_particle_share_threshold(self) -> float:
        return self.particle_share_threshold

    def get_subhalo_mass_ratio_threshold(self) -> float:
        return self.subhalo_mass_ratio_threshold

    def set_particle_share_threshold(self, t: float):
        self.particle_share_threshold = t

    def set_subhalo_mass_ratio_threshold(self, t: float):
        self.subhalo_mass_ratio_threshold = t


class EllipsoidalFitter:
    def __init__(self, tolerance: float = 1e-6, max_iterations: int = 100):
        self.tolerance = tolerance
        self.max_iterations = max_iterations

    def compute_inertia_tensor(self, halo: Halo, snapshot: Snapshot, r_max: float = 0.0) -> np.ndarray:
        mask = np.isin(snapshot.particles.ids, np.array(halo.particle_ids))
        if not np.any(mask):
            return np.zeros((3, 3))

        positions = snapshot.particles.positions[mask]
        masses = snapshot.particles.masses[mask]
        com = np.array(halo.center_of_mass)

        dx = positions[:, 0] - com[0]
        dy = positions[:, 1] - com[1]
        dz = positions[:, 2] - com[2]
        dx -= snapshot.box_size * np.round(dx / snapshot.box_size)
        dy -= snapshot.box_size * np.round(dy / snapshot.box_size)
        dz -= snapshot.box_size * np.round(dz / snapshot.box_size)

        if r_max > 0:
            r = np.sqrt(dx*dx + dy*dy + dz*dz)
            valid = r <= r_max
            if np.any(valid):
                dx = dx[valid]
                dy = dy[valid]
                dz = dz[valid]
                masses = masses[valid]
            else:
                return np.zeros((3, 3))

        total_mass = np.sum(masses)
        if total_mass <= 0:
            return np.zeros((3, 3))

        I = np.zeros((3, 3))
        I[0, 0] = np.sum(masses * dx * dx)
        I[1, 1] = np.sum(masses * dy * dy)
        I[2, 2] = np.sum(masses * dz * dz)
        I[0, 1] = np.sum(masses * dx * dy)
        I[0, 2] = np.sum(masses * dx * dz)
        I[1, 2] = np.sum(masses * dy * dz)
        I[1, 0] = I[0, 1]
        I[2, 0] = I[0, 2]
        I[2, 1] = I[1, 2]

        return I / total_mass

    def diagonalize_3x3(self, tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        eigenvalues, eigenvectors = np.linalg.eigh(tensor)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        return eigenvalues, eigenvectors

    def compute_ellipsoidal_radii(self, eigenvalues: np.ndarray) -> Tuple[float, float, float]:
        vals = np.maximum(eigenvalues, 0.0)
        a = np.sqrt(5.0 * vals[0])
        b = np.sqrt(5.0 * vals[1])
        c = np.sqrt(5.0 * vals[2])
        return a, b, c

    def compute_euler_angles(self, rotation_matrix: np.ndarray) -> Tuple[float, float, float]:
        R = rotation_matrix
        if abs(R[2, 2]) < 1.0:
            theta = np.arccos(max(-1.0, min(1.0, R[2, 2])))
            phi = np.arctan2(R[1, 2], R[0, 2])
            psi = np.arctan2(R[2, 1], -R[2, 0])
        else:
            if R[2, 2] > 0:
                theta = 0.0
                phi = np.arctan2(-R[1, 0], R[0, 0])
                psi = 0.0
            else:
                theta = np.pi
                phi = np.arctan2(R[1, 0], -R[0, 0])
                psi = 0.0
        return phi, theta, psi

    def fit(self, halo: Halo, snapshot: Snapshot, iterations: int = 3) -> EllipsoidalShape:
        result = EllipsoidalShape()

        if len(halo.particle_ids) < 10:
            return result

        tensor = self.compute_inertia_tensor(halo, snapshot)
        eigenvalues, eigenvectors = self.diagonalize_3x3(tensor)

        result.converged = True
        a, b, c = self.compute_ellipsoidal_radii(eigenvalues)

        for iter_i in range(1, iterations):
            r_max = max(a, b, c)
            tensor = self.compute_inertia_tensor(halo, snapshot, r_max)
            new_eigenvalues, new_eigenvectors = self.diagonalize_3x3(tensor)

            if np.max(np.abs(new_eigenvalues - eigenvalues)) < self.tolerance * np.max(np.abs(eigenvalues)):
                break

            eigenvalues = new_eigenvalues
            eigenvectors = new_eigenvectors
            a, b, c = self.compute_ellipsoidal_radii(eigenvalues)

        result.axis_a, result.axis_b, result.axis_c = a, b, c
        if result.axis_a > 0:
            result.axis_ratio_b_a = result.axis_b / result.axis_a
            result.axis_ratio_c_a = result.axis_c / result.axis_a
            result.ellipticity = 1.0 - result.axis_c / result.axis_a
            result.prolateness = (result.axis_b - result.axis_c) / (result.axis_b + result.axis_c)
            if result.axis_a > result.axis_c:
                result.triaxiality = (result.axis_a**2 - result.axis_b**2) / (result.axis_a**2 - result.axis_c**2)
            else:
                result.triaxiality = 0.0
        result.orientation_matrix = eigenvectors
        result.euler_angles = self.compute_euler_angles(eigenvectors)
        return result


class SubstructureFinder:
    def __init__(self, mass_ratio_threshold: float = 0.1,
                 radius_threshold: float = 2.0,
                 min_particles: int = 10):
        self.mass_ratio_threshold = mass_ratio_threshold
        self.radius_threshold = radius_threshold
        self.min_particles = min_particles

    def compute_halo_radius(self, halo: Halo) -> float:
        if halo.mass <= 0:
            return 0.0
        return np.cbrt(3.0 * halo.mass / (4.0 * PI * 200.0 * RHO_CRIT))

    def identify_subhalos_within_halo(self, host: Halo, all_halos: List[Halo],
                                       snapshot: Snapshot) -> List[int]:
        r_host = self.compute_halo_radius(host)
        r_threshold = self.radius_threshold * r_host

        sub_ids = []
        for candidate in all_halos:
            if candidate.halo_id == host.halo_id:
                continue
            if candidate.mass >= host.mass * self.mass_ratio_threshold:
                continue
            if len(candidate.particle_ids) < self.min_particles:
                continue

            dist = _periodic_distance(
                np.array(host.center_of_mass),
                np.array(candidate.center_of_mass),
                snapshot.box_size
            )
            if dist <= r_threshold:
                sub_ids.append(candidate.halo_id)

        id_to_halo = {h.halo_id: h for h in all_halos}
        sub_ids.sort(key=lambda x: id_to_halo[x].mass, reverse=True)
        return sub_ids

    def find_substructures(self, snapshot: Snapshot):
        for halo in snapshot.halos:
            halo.is_substructure = False
            halo.parent_halo_id = 0
            halo.substructure_ids = []

        sorted_halos = sorted(snapshot.halos, key=lambda h: h.mass, reverse=True)

        for i, host in enumerate(sorted_halos):
            if host.is_substructure:
                continue

            sub_ids = self.identify_subhalos_within_halo(host, snapshot.halos, snapshot)
            host.substructure_ids = sub_ids

            for sub_id in sub_ids:
                for halo in snapshot.halos:
                    if halo.halo_id == sub_id:
                        halo.is_substructure = True
                        halo.parent_halo_id = host.halo_id
                        break

    def find_bound_particles(self, halo: Halo, snapshot: Snapshot,
                              n_iterations: int = 3) -> np.ndarray:
        mask = np.isin(snapshot.particles.ids, np.array(halo.particle_ids))
        if not np.any(mask):
            return np.array([], dtype=np.uint64)

        bound_ids = snapshot.particles.ids[mask]
        positions = snapshot.particles.positions[mask]
        velocities = snapshot.particles.velocities[mask]
        masses = snapshot.particles.masses[mask]

        r_prev = self.compute_halo_radius(halo)

        for _ in range(n_iterations):
            total_mass = np.sum(masses)
            if total_mass <= 0:
                break

            com = np.sum(masses[:, None] * positions, axis=0) / total_mass
            mean_vel = np.sum(masses[:, None] * velocities, axis=0) / total_mass

            dx = positions[:, 0] - com[0]
            dy = positions[:, 1] - com[1]
            dz = positions[:, 2] - com[2]
            dx -= snapshot.box_size * np.round(dx / snapshot.box_size)
            dy -= snapshot.box_size * np.round(dy / snapshot.box_size)
            dz -= snapshot.box_size * np.round(dz / snapshot.box_size)
            r = np.sqrt(dx*dx + dy*dy + dz*dz)

            dvx = velocities[:, 0] - mean_vel[0]
            dvy = velocities[:, 1] - mean_vel[1]
            dvz = velocities[:, 2] - mean_vel[2]
            v = np.sqrt(dvx*dvx + dvy*dvy + dvz*dvz)

            v_rms = np.sqrt(np.mean(v*v))
            escape_vel = np.sqrt(2.0) * v_rms

            bound = np.ones(len(positions), dtype=bool)
            for i in range(len(positions)):
                if r[i] > 0 and v[i] <= escape_vel:
                    pot = -G * total_mass / r[i]
                    ke = 0.5 * v[i] * v[i]
                    bound[i] = (ke + pot) < 0

            if np.sum(bound) < self.min_particles:
                break
            if np.all(bound):
                break

            bound_ids = bound_ids[bound]
            positions = positions[bound]
            velocities = velocities[bound]
            masses = masses[bound]

            tmp_mass = np.sum(masses)
            r_new = np.cbrt(3.0 * tmp_mass / (4.0 * PI * 200.0 * RHO_CRIT)) if tmp_mass > 0 else 0
            if abs(r_new - r_prev) / r_prev < 0.01:
                break
            r_prev = r_new

        return bound_ids

    def decompose_halo_bound(self, halo: Halo, snapshot: Snapshot,
                              n_iterations: int = 3):
        bound_ids = self.find_bound_particles(halo, snapshot, n_iterations)
        if len(bound_ids) >= self.min_particles:
            halo.particle_ids = list(bound_ids)
            mask = np.isin(snapshot.particles.ids, bound_ids)
            halo.mass = np.sum(snapshot.particles.masses[mask])

    def track_substructures(self, snapshots: List[Snapshot]):
        if len(snapshots) < 2:
            return

        for i in range(1, len(snapshots)):
            snap_prev = snapshots[i-1]
            snap_curr = snapshots[i]

            for halo_prev in snap_prev.halos:
                if not halo_prev.is_substructure:
                    continue

                prev_particles = set(halo_prev.particle_ids)

                best_match = 0
                best_overlap = 0.0

                for halo_curr in snap_curr.halos:
                    if halo_curr.descendant_id == 0:
                        continue
                    if not halo_curr.is_substructure:
                        continue

                    overlap = len(prev_particles.intersection(set(halo_curr.particle_ids)))
                    overlap_ratio = overlap / min(len(halo_prev.particle_ids), len(halo_curr.particle_ids))

                    if overlap_ratio > best_overlap:
                        best_overlap = overlap_ratio
                        best_match = halo_curr.halo_id

                if best_overlap > 0.3:
                    halo_prev.descendant_id = best_match
                    for halo_curr in snap_curr.halos:
                        if halo_curr.halo_id == best_match:
                            halo_curr.progenitor_ids.append(halo_prev.halo_id)
                            break


class GravityModel:
    GR = 'GR'
    F_R = 'F_R'


@dataclass
class FR_Parameters:
    f_R0: float = 1e-6
    n: float = 1.0
    name: str = 'F(R)'


@dataclass
class HaloStatistics:
    mass_mean: float = 0.0
    mass_median: float = 0.0
    concentration_mean: float = 0.0
    concentration_median: float = 0.0
    spin_mean: float = 0.0
    spin_median: float = 0.0
    axis_ratio_mean_b_a: float = 0.0
    axis_ratio_mean_c_a: float = 0.0
    triaxiality_mean: float = 0.0
    ellipticity_mean: float = 0.0
    num_halos: int = 0
    mass_bins: np.ndarray = field(default_factory=lambda: np.array([]))
    mass_function: np.ndarray = field(default_factory=lambda: np.array([]))
    mass_function_errors: np.ndarray = field(default_factory=lambda: np.array([]))
    redshift_bins: np.ndarray = field(default_factory=lambda: np.array([]))
    halo_abundance: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class ModelComparison:
    model1_name: str = 'GR'
    model2_name: str = 'F(R)'
    mass_function_delta: float = 0.0
    concentration_delta: float = 0.0
    spin_delta: float = 0.0
    ellipticity_delta: float = 0.0
    mass_function_ratio: np.ndarray = field(default_factory=lambda: np.array([]))
    mass_bin_centers: np.ndarray = field(default_factory=lambda: np.array([]))
    ks_statistic: float = 0.0
    ks_p_value: float = 0.0
    significant_differences: List[str] = field(default_factory=list)


class ModifiedGravityInterface:
    def __init__(self):
        self.model_params: Dict[str, FR_Parameters] = {}
        self.current_model: str = GravityModel.GR
        self.register_model(GravityModel.GR, FR_Parameters(f_R0=0.0, n=0.0, name='GR'))

    def register_model(self, model: str, params: FR_Parameters):
        self.model_params[model] = params

    def set_current_model(self, model: str):
        self.current_model = model

    def get_parameters(self, model: str) -> FR_Parameters:
        return self.model_params[model]

    def compute_fifth_force_coupling(self, f_R: float, n: float = 1.0) -> float:
        if abs(f_R) < 1e-15:
            return 0.0
        return np.sqrt(1.0 / 3.0) * (1.0 + n) / np.sqrt(abs(f_R))

    def compute_screening_scale(self, f_R: float, n: float = 1.0, density: float = 1.0) -> float:
        if abs(f_R) < 1e-15 or density <= 0:
            return 0.0
        return np.power(abs(f_R) * np.power(density / RHO_CRIT, -1.0 - n), 1.0 / (2.0 + n))

    def compute_boost_factor(self, mass: float, redshift: float, params: FR_Parameters) -> float:
        if abs(params.f_R0) < 1e-15:
            return 1.0

        f_R_z = params.f_R0 * np.power(1.0 + redshift, -params.n - 1.0)
        r_s = np.power(3.0 * mass / (4.0 * PI * 200.0 * RHO_CRIT), 1.0/3.0)
        lambda_s = self.compute_screening_scale(params.f_R0, params.n, 200.0 * RHO_CRIT)

        if lambda_s <= 0:
            return 1.0

        screening_ratio = r_s / lambda_s
        beta = self.compute_fifth_force_coupling(f_R_z, params.n)
        enhancement = 2.0 * beta * beta / 3.0

        if screening_ratio > 1.0:
            return 1.0 + enhancement * np.exp(-screening_ratio)
        else:
            return 1.0 + enhancement * (1.0 - screening_ratio * screening_ratio)

    def is_halo_chameleon_screened(self, halo: Halo, params: FR_Parameters) -> bool:
        if abs(params.f_R0) < 1e-15:
            return False
        if halo.mass <= 0 or halo.shape.axis_a <= 0:
            return False

        r_vir = np.cbrt(3.0 * halo.mass / (4.0 * PI * 200.0 * RHO_CRIT))
        lambda_s = self.compute_screening_scale(params.f_R0, params.n, 200.0 * RHO_CRIT)

        if lambda_s <= 0:
            return True

        screening_ratio = r_vir / lambda_s
        return screening_ratio > 1.0

    def compute_statistics(self, halos: List[Halo], box_size: float,
                            use_adaptive_binning: bool = True,
                            min_count_per_bin: int = 10) -> HaloStatistics:
        from .analysis import compute_mass_function

        stats = HaloStatistics()
        stats.num_halos = len(halos)

        if not halos:
            return stats

        masses = np.array([h.mass for h in halos if h.mass > 0])
        spins = np.array([h.spin_parameter for h in halos if h.spin_parameter > 0])
        axis_b_a = np.array([h.shape.axis_ratio_b_a for h in halos if h.shape.converged])
        axis_c_a = np.array([h.shape.axis_ratio_c_a for h in halos if h.shape.converged])
        triaxiality = np.array([h.shape.triaxiality for h in halos if h.shape.converged])
        ellipticity = np.array([h.shape.ellipticity for h in halos if h.shape.converged])

        stats.mass_mean = np.mean(masses) if len(masses) > 0 else 0.0
        stats.mass_median = np.median(masses) if len(masses) > 0 else 0.0
        stats.spin_mean = np.mean(spins) if len(spins) > 0 else 0.0
        stats.spin_median = np.median(spins) if len(spins) > 0 else 0.0
        stats.axis_ratio_mean_b_a = np.mean(axis_b_a) if len(axis_b_a) > 0 else 0.0
        stats.axis_ratio_mean_c_a = np.mean(axis_c_a) if len(axis_c_a) > 0 else 0.0
        stats.triaxiality_mean = np.mean(triaxiality) if len(triaxiality) > 0 else 0.0
        stats.ellipticity_mean = np.mean(ellipticity) if len(ellipticity) > 0 else 0.0
        stats.concentration_mean = 4.0
        stats.concentration_median = 4.0

        bin_centers, mass_func, counts, errors = compute_mass_function(
            halos, box_size, use_adaptive_binning=use_adaptive_binning,
            min_count_per_bin=min_count_per_bin
        )
        stats.mass_bins = bin_centers
        stats.mass_function = mass_func
        stats.mass_function_errors = errors

        redshifts = np.array([h.redshift for h in halos])
        if len(redshifts) > 0:
            z_min, z_max = redshifts.min(), redshifts.max()
            n_z_bins = min(10, max(2, len(redshifts) // 5))
            z_bin_width = (z_max - z_min) / n_z_bins
            stats.redshift_bins = np.array([z_min + (i + 0.5) * z_bin_width for i in range(n_z_bins)])
            stats.halo_abundance = np.array([
                np.sum((redshifts >= z_min + i * z_bin_width) & (redshifts < z_min + (i + 1) * z_bin_width))
                for i in range(n_z_bins)
            ])

        return stats

    def kolmogorov_smirnov_test(self, sample1: np.ndarray, sample2: np.ndarray) -> Tuple[float, float]:
        if len(sample1) == 0 or len(sample2) == 0:
            return 1.0, 0.0

        s1 = np.sort(sample1)
        s2 = np.sort(sample2)
        n1, n2 = len(s1), len(s2)

        all_vals = np.concatenate([s1, s2])
        ecdf1 = np.searchsorted(s1, all_vals, side='right') / n1
        ecdf2 = np.searchsorted(s2, all_vals, side='right') / n2

        d = np.max(np.abs(ecdf1 - ecdf2))
        en = np.sqrt(n1 * n2 / (n1 + n2))
        lambda_ = (en + 0.12 + 0.11 / en) * d
        p_value = 2.0 * np.exp(-2.0 * lambda_ * lambda_)

        return d, p_value

    def compare_models(self, stats1: HaloStatistics, stats2: HaloStatistics,
                        name1: str = 'GR', name2: str = 'F(R)') -> ModelComparison:
        comp = ModelComparison(model1_name=name1, model2_name=name2)

        if stats1.num_halos > 0 and stats2.num_halos > 0:
            if stats1.spin_mean > 0:
                comp.spin_delta = (stats2.spin_mean - stats1.spin_mean) / stats1.spin_mean
            if stats1.ellipticity_mean > 0:
                comp.ellipticity_delta = (stats2.ellipticity_mean - stats1.ellipticity_mean) / stats1.ellipticity_mean
            if stats1.concentration_mean > 0:
                comp.concentration_delta = (stats2.concentration_mean - stats1.concentration_mean) / stats1.concentration_mean

            n_bins = min(len(stats1.mass_function), len(stats2.mass_function))
            if n_bins > 0:
                ratio = []
                bin_centers = []
                delta_sum = 0.0
                count = 0
                for i in range(n_bins):
                    if stats1.mass_function[i] > 0:
                        ratio.append(stats2.mass_function[i] / stats1.mass_function[i])
                        bin_centers.append(stats1.mass_bins[i])
                        delta_sum += abs(stats2.mass_function[i] - stats1.mass_function[i]) / stats1.mass_function[i]
                        count += 1
                comp.mass_function_ratio = np.array(ratio)
                comp.mass_bin_centers = np.array(bin_centers)
                if count > 0:
                    comp.mass_function_delta = delta_sum / count

        return comp
