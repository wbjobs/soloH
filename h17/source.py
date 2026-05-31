import numpy as np
from numba import njit, prange
from scipy import signal
from typing import Optional, Tuple, List


def ricker_wavelet(t: np.ndarray, f0: float, t0: float = 0.0,
                   amplitude: float = 1.0) -> np.ndarray:
    tau = np.pi * f0 * (t - t0)
    return amplitude * (1 - 2 * tau**2) * np.exp(-tau**2)


def gaussian_derivative(t: np.ndarray, f0: float, t0: float = 0.0,
                        amplitude: float = 1.0, order: int = 1) -> np.ndarray:
    sigma = 1.0 / (np.pi * f0)
    tau = (t - t0) / sigma
    if order == 1:
        return -amplitude * tau * np.exp(-0.5 * tau**2) / sigma
    elif order == 2:
        return amplitude * (tau**2 - 1) * np.exp(-0.5 * tau**2) / sigma**2
    else:
        raise ValueError(f"Unsupported derivative order: {order}")


class Source:
    def __init__(self, nx: int, nz: int, dx: float, dz: float, dt: float, nt: int,
                 source_type: str = 'explosive',
                 sx: int = 0, sz: int = 0, f0: float = 20.0,
                 amplitude: float = 1e9, t0: float = 0.05,
                 wavelet_type: str = 'ricker',
                 dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dt = dt
        self.nt = nt
        self.source_type = source_type
        self.sx = sx
        self.sz = sz
        self.f0 = f0
        self.amplitude = amplitude
        self.t0 = t0
        self.wavelet_type = wavelet_type
        self.dtype = dtype
        
        self._validate_source()
        self._generate_wavelet()
        self._init_source_distribution()
    
    def _validate_source(self):
        if self.sx < 0 or self.sx >= self.nx:
            raise ValueError(f"Source x index {self.sx} out of bounds [0, {self.nx})")
        if self.sz < 0 or self.sz >= self.nz:
            raise ValueError(f"Source z index {self.sz} out of bounds [0, {self.nz})")
        
        valid_types = ['explosive', 'shear_x', 'shear_z', 'shear', 'force_x', 'force_z']
        if self.source_type not in valid_types:
            raise ValueError(f"Unknown source type: {self.source_type}. "
                           f"Valid types: {valid_types}")
    
    def _generate_wavelet(self):
        t = np.arange(self.nt) * self.dt
        
        if self.wavelet_type == 'ricker':
            self.wavelet = ricker_wavelet(t, self.f0, self.t0, self.amplitude)
        elif self.wavelet_type == 'gaussian1':
            self.wavelet = gaussian_derivative(t, self.f0, self.t0, self.amplitude, order=1)
        elif self.wavelet_type == 'gaussian2':
            self.wavelet = gaussian_derivative(t, self.f0, self.t0, self.amplitude, order=2)
        else:
            raise ValueError(f"Unknown wavelet type: {self.wavelet_type}")
        
        self.wavelet = self.wavelet.astype(self.dtype)
    
    def _init_source_distribution(self):
        self.mask_xx = np.zeros((self.nz, self.nx), dtype=self.dtype)
        self.mask_zz = np.zeros((self.nz, self.nx), dtype=self.dtype)
        self.mask_xz = np.zeros((self.nz, self.nx), dtype=self.dtype)
        self.mask_fx = np.zeros((self.nz, self.nx), dtype=self.dtype)
        self.mask_fz = np.zeros((self.nz, self.nx), dtype=self.dtype)
        
        self._compute_gaussian_source_mask()
    
    def _compute_gaussian_source_mask(self):
        sigma = 1.0
        half_width = 3
        
        for dz in range(-half_width, half_width + 1):
            for dx in range(-half_width, half_width + 1):
                iz = self.sz + dz
                ix = self.sx + dx
                
                if 0 <= iz < self.nz and 0 <= ix < self.nx:
                    weight = np.exp(-(dx**2 + dz**2) / (2 * sigma**2))
                    weight = weight / (2 * np.pi * sigma**2 * self.dx * self.dz)
                    
                    if self.source_type == 'explosive':
                        self.mask_xx[iz, ix] = weight
                        self.mask_zz[iz, ix] = weight
                    elif self.source_type == 'shear_x':
                        self.mask_xz[iz, ix] = weight
                    elif self.source_type == 'shear_z':
                        self.mask_xz[iz, ix] = weight
                    elif self.source_type == 'shear':
                        self.mask_xz[iz, ix] = weight
                    elif self.source_type == 'force_x':
                        self.mask_fx[iz, ix] = weight
                    elif self.source_type == 'force_z':
                        self.mask_fz[iz, ix] = weight
    
    def add_source(self, tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                   vx: np.ndarray, vz: np.ndarray, it: int) -> None:
        source_term = self.wavelet[it]
        _add_source_term(tau_xx, tau_zz, tau_xz, vx, vz,
                        self.mask_xx, self.mask_zz, self.mask_xz,
                        self.mask_fx, self.mask_fz, source_term, self.dt)
    
    def get_wavelet_spectrum(self, nfft: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        if nfft is None:
            nfft = self.nt
        
        freqs = np.fft.fftfreq(nfft, self.dt)
        spectrum = np.abs(np.fft.fft(self.wavelet, nfft))
        
        pos_mask = freqs >= 0
        return freqs[pos_mask], spectrum[pos_mask]
    
    def get_source_position(self) -> Tuple[float, float]:
        return self.sx * self.dx, self.sz * self.dz


@njit(parallel=True)
def _add_source_term(tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                     vx: np.ndarray, vz: np.ndarray,
                     mask_xx: np.ndarray, mask_zz: np.ndarray, mask_xz: np.ndarray,
                     mask_fx: np.ndarray, mask_fz: np.ndarray,
                     source_term: float, dt: float):
    nz, nx = tau_xx.shape
    
    for z in prange(nz):
        for x in range(nx):
            m_xx = mask_xx[z, x]
            m_zz = mask_zz[z, x]
            m_xz = mask_xz[z, x]
            m_fx = mask_fx[z, x]
            m_fz = mask_fz[z, x]
            
            if m_xx != 0:
                tau_xx[z, x] += dt * m_xx * source_term
            if m_zz != 0:
                tau_zz[z, x] += dt * m_zz * source_term
            if m_xz != 0:
                tau_xz[z, x] += dt * m_xz * source_term
            if m_fx != 0:
                vx[z, x] += dt * m_fx * source_term
            if m_fz != 0:
                vz[z, x] += dt * m_fz * source_term


class MultipleSources:
    def __init__(self, sources: List[Source], use_encoding: bool = True,
                 encoding_type: str = 'random_phase', seed: Optional[int] = None):
        self.sources = sources
        self.use_encoding = use_encoding
        self.encoding_type = encoding_type
        self.seed = seed
        
        self._init_encodings()
    
    def _init_encodings(self):
        n_sources = len(self.sources)
        nt = self.sources[0].nt if n_sources > 0 else 0
        
        if self.seed is not None:
            rng = np.random.RandomState(self.seed)
        else:
            rng = np.random
        
        self.encodings = []
        
        for i in range(n_sources):
            if not self.use_encoding:
                code = np.ones(nt, dtype=self.sources[i].dtype)
            elif self.encoding_type == 'random_phase':
                random_phases = rng.uniform(0, 2 * np.pi, nt)
                code = np.exp(1j * random_phases).real.astype(self.sources[i].dtype)
            elif self.encoding_type == 'polarity':
                code = rng.choice([-1.0, 1.0], size=nt).astype(self.sources[i].dtype)
            elif self.encoding_type == 'gaussian':
                code = rng.randn(nt).astype(self.sources[i].dtype)
            elif self.encoding_type == 'hadamard':
                hadamard_size = 1
                while hadamard_size < n_sources:
                    hadamard_size *= 2
                H = np.zeros((hadamard_size, hadamard_size))
                H[0, 0] = 1
                h = 1
                while h < hadamard_size:
                    for k in range(h):
                        for l in range(h):
                            H[k + h, l] = H[k, l]
                            H[k, l + h] = H[k, l]
                            H[k + h, l + h] = -H[k, l]
                    h *= 2
                code = np.ones(nt, dtype=self.sources[i].dtype) * H[i % hadamard_size, i % hadamard_size]
            else:
                raise ValueError(f"Unknown encoding type: {self.encoding_type}")
            
            self.encodings.append(code)
    
    def regenerate_encodings(self, seed: Optional[int] = None):
        self.seed = seed
        self._init_encodings()
    
    def add_sources(self, tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                    vx: np.ndarray, vz: np.ndarray, it: int) -> None:
        for source, code in zip(self.sources, self.encodings):
            source_term = source.wavelet[it] * code[it]
            _add_source_term(tau_xx, tau_zz, tau_xz, vx, vz,
                            source.mask_xx, source.mask_zz, source.mask_xz,
                            source.mask_fx, source.mask_fz, source_term, source.dt)
    
    def decode_seismogram(self, encoded_data: np.ndarray, source_idx: int) -> np.ndarray:
        if not self.use_encoding:
            return encoded_data
        
        code = self.encodings[source_idx]
        return np.fft.ifft(np.fft.fft(encoded_data, axis=-1) * np.conj(np.fft.fft(code))
                          / (np.abs(np.fft.fft(code))**2 + 1e-10)).real
    
    def get_source_position(self, idx: int) -> Tuple[float, float]:
        return self.sources[idx].get_source_position()
    
    def get_wavelet(self, idx: int) -> np.ndarray:
        if self.use_encoding:
            return self.sources[idx].wavelet * self.encodings[idx]
        else:
            return self.sources[idx].wavelet
    
    def __len__(self) -> int:
        return len(self.sources)
    
    def __getitem__(self, idx: int) -> Source:
        return self.sources[idx]
