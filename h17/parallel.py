import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import warnings


try:
    from mpi4py import MPI
    MPI_AVAILABLE = True
except ImportError:
    MPI_AVAILABLE = False
    warnings.warn("mpi4py not available. MPI parallelization disabled.")


try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    warnings.warn("cupy not available. GPU acceleration disabled.")


class ParallelManager:
    def __init__(self, use_mpi: bool = False, use_gpu: bool = False):
        self.use_mpi = use_mpi and MPI_AVAILABLE
        self.use_gpu = use_gpu and CUPY_AVAILABLE
        
        self.comm = None
        self.rank = 0
        self.size = 1
        self.gpu_id = 0
        
        if self.use_mpi:
            self._init_mpi()
        
        if self.use_gpu:
            self._init_gpu()
        
        self.xp = cp if self.use_gpu else np
    
    def _init_mpi(self):
        self.comm = MPI.COMM_WORLD
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()
        
        if self.rank == 0:
            print(f"MPI initialized: {self.size} processes")
    
    def _init_gpu(self):
        if self.use_mpi:
            n_gpus = cp.cuda.runtime.getDeviceCount()
            self.gpu_id = self.rank % n_gpus
            cp.cuda.Device(self.gpu_id).use()
            print(f"Rank {self.rank}: Using GPU {self.gpu_id}")
        else:
            self.gpu_id = 0
            print(f"Using GPU {self.gpu_id}")
    
    def get_array_module(self):
        return self.xp
    
    def to_device(self, array: np.ndarray) -> Any:
        if self.use_gpu:
            return cp.asarray(array)
        return array
    
    def to_host(self, array: Any) -> np.ndarray:
        if self.use_gpu:
            return cp.asnumpy(array)
        return array
    
    def barrier(self):
        if self.use_mpi:
            self.comm.Barrier()
    
    def bcast(self, data: Any, root: int = 0) -> Any:
        if not self.use_mpi or self.size == 1:
            return data
        return self.comm.bcast(data, root=root)
    
    def gather(self, data: Any, root: int = 0) -> Optional[List[Any]]:
        if not self.use_mpi or self.size == 1:
            return [data]
        return self.comm.gather(data, root=root)
    
    def allreduce(self, data: Any, op: str = 'sum') -> Any:
        if not self.use_mpi or self.size == 1:
            return data
        
        mpi_op = {
            'sum': MPI.SUM,
            'max': MPI.MAX,
            'min': MPI.MIN,
            'prod': MPI.PROD
        }.get(op, MPI.SUM)
        
        return self.comm.allreduce(data, op=mpi_op)
    
    def split_domain_1d(self, nx: int, nz: int,
                        axis: str = 'x') -> Tuple[int, int, int, int]:
        if not self.use_mpi or self.size == 1:
            return 0, nx, 0, nz
        
        if axis == 'x':
            local_nx = nx // self.size
            remainder = nx % self.size
            
            x_start = self.rank * local_nx + min(self.rank, remainder)
            x_end = x_start + local_nx + (1 if self.rank < remainder else 0)
            
            return x_start, x_end, 0, nz
        elif axis == 'z':
            local_nz = nz // self.size
            remainder = nz % self.size
            
            z_start = self.rank * local_nz + min(self.rank, remainder)
            z_end = z_start + local_nz + (1 if self.rank < remainder else 0)
            
            return 0, nx, z_start, z_end
        else:
            raise ValueError(f"Unknown axis: {axis}")
    
    def get_halo_sizes(self, space_order: int) -> Tuple[int, int]:
        halo = space_order // 2 + 1
        return halo, halo
    
    def exchange_halo(self, array: np.ndarray, halo: int,
                     neighbors: Optional[Dict[str, int]] = None) -> np.ndarray:
        if not self.use_mpi or self.size == 1:
            return array
        
        if neighbors is None:
            neighbors = {
                'left': self.rank - 1 if self.rank > 0 else MPI.PROC_NULL,
                'right': self.rank + 1 if self.rank < self.size - 1 else MPI.PROC_NULL
            }
        
        nz, nx = array.shape
        dtype = array.dtype
        
        send_buf_left = np.ascontiguousarray(array[:, halo:2*halo])
        send_buf_right = np.ascontiguousarray(array[:, -2*halo:-halo])
        
        recv_buf_left = np.empty((nz, halo), dtype=dtype)
        recv_buf_right = np.empty((nz, halo), dtype=dtype)
        
        requests = []
        
        if neighbors['left'] != MPI.PROC_NULL:
            req_send = self.comm.Isend(send_buf_left, dest=neighbors['left'], tag=0)
            req_recv = self.comm.Irecv(recv_buf_right, source=neighbors['left'], tag=1)
            requests.extend([req_send, req_recv])
        
        if neighbors['right'] != MPI.PROC_NULL:
            req_send = self.comm.Isend(send_buf_right, dest=neighbors['right'], tag=1)
            req_recv = self.comm.Irecv(recv_buf_left, source=neighbors['right'], tag=0)
            requests.extend([req_send, req_recv])
        
        for req in requests:
            req.Wait()
        
        if neighbors['left'] != MPI.PROC_NULL:
            array[:, :halo] = recv_buf_left
        
        if neighbors['right'] != MPI.PROC_NULL:
            array[:, -halo:] = recv_buf_right
        
        return array
    
    def gather_field(self, local_field: np.ndarray,
                     global_shape: Tuple[int, int],
                     x_range: Tuple[int, int],
                     z_range: Tuple[int, int],
                     root: int = 0) -> Optional[np.ndarray]:
        if not self.use_mpi or self.size == 1:
            return local_field
        
        x_start, x_end = x_range
        z_start, z_end = z_range
        
        local_data = {
            'data': local_field,
            'x_start': x_start,
            'x_end': x_end,
            'z_start': z_start,
            'z_end': z_end
        }
        
        all_data = self.comm.gather(local_data, root=root)
        
        if self.rank == root:
            global_field = np.zeros(global_shape, dtype=local_field.dtype)
            for data in all_data:
                xs, xe = data['x_start'], data['x_end']
                zs, ze = data['z_start'], data['z_end']
                global_field[zs:ze, xs:xe] = data['data']
            return global_field
        
        return None
    
    def is_main_process(self) -> bool:
        return self.rank == 0
    
    def print(self, *args, **kwargs):
        if self.is_main_process():
            print(*args, **kwargs)


class DomainDecomposer:
    def __init__(self, nx: int, nz: int, n_procs: int,
                 space_order: int, axis: str = 'x'):
        self.nx = nx
        self.nz = nz
        self.n_procs = n_procs
        self.space_order = space_order
        self.axis = axis
        self.halo = space_order // 2 + 1
        
        self._compute_decomposition()
    
    def _compute_decomposition(self):
        self.domains = []
        
        if self.axis == 'x':
            for rank in range(self.n_procs):
                local_nx = self.nx // self.n_procs
                remainder = self.nx % self.n_procs
                
                x_start = rank * local_nx + min(rank, remainder)
                x_end = x_start + local_nx + (1 if rank < remainder else 0)
                
                x_start_halo = max(0, x_start - self.halo)
                x_end_halo = min(self.nx, x_end + self.halo)
                
                self.domains.append({
                    'rank': rank,
                    'x_start': x_start,
                    'x_end': x_end,
                    'x_start_halo': x_start_halo,
                    'x_end_halo': x_end_halo,
                    'z_start': 0,
                    'z_end': self.nz,
                    'local_nx': x_end - x_start,
                    'local_nx_halo': x_end_halo - x_start_halo,
                    'local_nz': self.nz,
                    'left_halo_width': x_start - x_start_halo,
                    'right_halo_width': x_end_halo - x_end,
                    'left_neighbor': rank - 1 if rank > 0 else None,
                    'right_neighbor': rank + 1 if rank < self.n_procs - 1 else None
                })
        elif self.axis == 'z':
            for rank in range(self.n_procs):
                local_nz = self.nz // self.n_procs
                remainder = self.nz % self.n_procs
                
                z_start = rank * local_nz + min(rank, remainder)
                z_end = z_start + local_nz + (1 if rank < remainder else 0)
                
                z_start_halo = max(0, z_start - self.halo)
                z_end_halo = min(self.nz, z_end + self.halo)
                
                self.domains.append({
                    'rank': rank,
                    'x_start': 0,
                    'x_end': self.nx,
                    'z_start': z_start,
                    'z_end': z_end,
                    'z_start_halo': z_start_halo,
                    'z_end_halo': z_end_halo,
                    'local_nx': self.nx,
                    'local_nz': z_end - z_start,
                    'local_nz_halo': z_end_halo - z_start_halo,
                    'bottom_halo_width': z_start - z_start_halo,
                    'top_halo_width': z_end_halo - z_end,
                    'bottom_neighbor': rank - 1 if rank > 0 else None,
                    'top_neighbor': rank + 1 if rank < self.n_procs - 1 else None
                })
    
    def get_domain(self, rank: int) -> dict:
        return self.domains[rank]
    
    def extract_local_data(self, global_data: np.ndarray, rank: int) -> np.ndarray:
        d = self.domains[rank]
        return global_data[d['z_start_halo']:d['z_end_halo'], 
                          d['x_start_halo']:d['x_end_halo']].copy()
    
    def insert_local_data(self, local_data: np.ndarray, 
                         global_data: np.ndarray, rank: int) -> np.ndarray:
        d = self.domains[rank]
        
        if self.axis == 'x':
            inner = local_data[:, d['left_halo_width']:-d['right_halo_width']] \
                if d['right_halo_width'] > 0 else local_data[:, d['left_halo_width']:]
        else:
            inner = local_data[d['bottom_halo_width']:-d['top_halo_width'], :] \
                if d['top_halo_width'] > 0 else local_data[d['bottom_halo_width']:, :]
        
        global_data[d['z_start']:d['z_end'], d['x_start']:d['x_end']] = inner
        return global_data


if CUPY_AVAILABLE:
    class GPUKernelManager:
        def __init__(self, device_id: int = 0):
            self.device_id = device_id
            self.device = cp.cuda.Device(device_id)
            self.device.use()
            
            self._kernels = {}
            self._streams = {}
        
        def create_stream(self, name: str = 'default'):
            stream = cp.cuda.Stream()
            self._streams[name] = stream
            return stream
        
        def get_stream(self, name: str = 'default'):
            if name not in self._streams:
                self.create_stream(name)
            return self._streams[name]
        
        def synchronize(self):
            cp.cuda.runtime.deviceSynchronize()
        
        def get_memory_info(self) -> Tuple[int, int]:
            return cp.cuda.runtime.memGetInfo()
        
        def print_memory_info(self):
            free, total = self.get_memory_info()
            print(f"GPU {self.device_id} Memory: {free/1e9:.2f} GB free / {total/1e9:.2f} GB total "
                  f"({100*free/total:.1f}% free)")
else:
    class GPUKernelManager:
        def __init__(self, device_id: int = 0):
            raise RuntimeError("CuPy is not available. Cannot use GPUKernelManager.")
        
        def create_stream(self, name: str = 'default'):
            raise RuntimeError("CuPy is not available.")
        
        def get_stream(self, name: str = 'default'):
            raise RuntimeError("CuPy is not available.")
        
        def synchronize(self):
            raise RuntimeError("CuPy is not available.")
        
        def get_memory_info(self) -> Tuple[int, int]:
            raise RuntimeError("CuPy is not available.")
        
        def print_memory_info(self):
            raise RuntimeError("CuPy is not available.")


def check_parallel_availability() -> dict:
    return {
        'mpi_available': MPI_AVAILABLE,
        'cupy_available': CUPY_AVAILABLE,
        'numba_available': _check_numba(),
        'numba_threads': _get_numba_threads()
    }


def _check_numba() -> bool:
    try:
        import numba
        return True
    except ImportError:
        return False


def _get_numba_threads() -> int:
    try:
        import numba
        return numba.config.NUMBA_NUM_THREADS
    except (ImportError, AttributeError):
        return 1


def print_system_info():
    info = check_parallel_availability()
    print("=" * 60)
    print("System Parallelization Capabilities")
    print("=" * 60)
    print(f"MPI (mpi4py): {'✓ Available' if info['mpi_available'] else '✗ Not available'}")
    print(f"GPU (cupy): {'✓ Available' if info['cupy_available'] else '✗ Not available'}")
    print(f"CPU (numba): {'✓ Available' if info['numba_available'] else '✗ Not available'}")
    print(f"Numba threads: {info['numba_threads']}")
    print("=" * 60)
