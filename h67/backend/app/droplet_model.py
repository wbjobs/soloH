import numpy as np
from typing import Tuple, Optional
from .models import SimulationParameters, JunctionType


class DropletFormationModel:
    def __init__(self):
        self.noise_std = 0.02
        self._transition_width = 0.3

    def _smooth_transition(self, x: float, x0: float, width: float) -> float:
        return 0.5 * (1 + np.tanh((x - x0) / width))

    def _classify_regime(self, Ca_c: float, Q_ratio: float, lambda_: float) -> str:
        Ca_threshold = 0.01 * (1 + 0.5 * Q_ratio)
        if Ca_c < Ca_threshold * 0.5:
            return 'dripping'
        elif Ca_c > Ca_threshold * 1.5:
            return 'jetting'
        else:
            return 'transition'

    def predict_droplet_size(
        self,
        Qc: float,
        Qd: float,
        muc: float,
        mud: float,
        sigma: float,
        W: float,
        H: float,
        junction_type: JunctionType,
        add_noise: bool = True
    ) -> float:
        Q_ratio = Qd / Qc if Qc > 0 else 1e6

        Ca_c = (muc * Qc * 1e3) / (60 * W * H * sigma) if sigma > 0 else 0
        Ca_c = max(Ca_c, 1e-6)
        lambda_ = mud / muc if muc > 0 else 1

        if junction_type == JunctionType.T:
            alpha_d, beta_d = 1.0, 0.4
            alpha_j, beta_j = 0.7, 0.6

            D_dripping = W * (alpha_d * Q_ratio + beta_d * Ca_c**(1/3)) / (1 + Q_ratio)
            D_jetting = W * (alpha_j * Q_ratio + beta_j * Ca_c**0.5) / (1 + Q_ratio)

            Ca_threshold = 0.008 * (1 + 0.3 * Q_ratio) * (1 + 0.2 * lambda_)
            blend = self._smooth_transition(Ca_c, Ca_threshold, self._transition_width * Ca_threshold)

            D = (1 - blend) * D_dripping + blend * D_jetting

        elif junction_type == JunctionType.FLOW_FOCUSING:
            alpha_d, beta_d = 0.8, 0.35
            alpha_j, beta_j = 0.6, 0.5

            Uc = (Qc * 1e-9 / 60) / (W * H * 1e-12) if W * H > 0 else 0
            We_c = (muc * 1e-3 * Uc**2 * W * 1e-6) / (sigma * 1e-3) if sigma > 0 else 0
            We_c = max(We_c, 1e-4)

            D_dripping = W * (alpha_d * Q_ratio**0.5 + beta_d * We_c**(-0.25)) / (1 + Q_ratio)
            D_jetting = W * (alpha_j * Q_ratio**0.4 + beta_j * We_c**(-0.35)) / (1 + Q_ratio)

            We_threshold = 0.5 * (1 + 0.4 * Q_ratio)
            blend = self._smooth_transition(We_c, We_threshold, self._transition_width * We_threshold)

            D = (1 - blend) * D_dripping + blend * D_jetting

        else:
            alpha_d, beta_d = 1.2, 0.5
            alpha_j, beta_j = 0.9, 0.7

            D_dripping = W * (alpha_d * Q_ratio + beta_d * Ca_c**0.5) / (1 + Q_ratio)
            D_jetting = W * (alpha_j * Q_ratio + beta_j * Ca_c**0.65) / (1 + Q_ratio)

            Ca_threshold = 0.015 * (1 + 0.25 * Q_ratio)
            blend = self._smooth_transition(Ca_c, Ca_threshold, self._transition_width * Ca_threshold)

            D = (1 - blend) * D_dripping + blend * D_jetting

        if add_noise:
            noise_scale = self.noise_std * (1 + 0.5 * Ca_c**0.5)
            noise = np.random.normal(0, noise_scale * D)
            D += noise

        return max(D, 0.1 * W)

    def get_regime_info(self, Ca_c: float, Q_ratio: float, lambda_: float, junction_type: JunctionType) -> dict:
        if junction_type == JunctionType.FLOW_FOCUSING:
            Uc = 1.0
            We_c = 0.01
            We_threshold = 0.5 * (1 + 0.4 * Q_ratio)
            blend = self._smooth_transition(We_c, We_threshold, self._transition_width * We_threshold)
            regime = self._classify_regime(Ca_c, Q_ratio, lambda_)
        else:
            Ca_threshold = 0.01 * (1 + 0.5 * Q_ratio)
            blend = self._smooth_transition(Ca_c, Ca_threshold, self._transition_width * Ca_threshold)
            regime = self._classify_regime(Ca_c, Q_ratio, lambda_)

        return {
            'regime': regime,
            'blend_factor': float(blend),
            'dripping_contribution': float(1 - blend),
            'jetting_contribution': float(blend)
        }

    def predict_frequency(
        self,
        Qc: float,
        Qd: float,
        D: float,
        W: float,
        H: float
    ) -> float:
        Q_total_m3s = (Qc + Qd) * 1e-9 / 60
        D_m = D * 1e-6
        droplet_volume = (np.pi * D_m**3) / 6
        if droplet_volume <= 0:
            return 0.0
        f = Q_total_m3s / droplet_volume
        return max(f, 0.01)

    def compute_polydispersity(
        self,
        sizes: np.ndarray,
        min_samples: int = 10,
        bootstrap: bool = True,
        n_bootstrap: int = 100
    ) -> float:
        n = len(sizes)
        if n < 2:
            return 0.0

        mean = np.mean(sizes)
        if mean <= 0:
            return 0.0

        if n < 3:
            std = np.std(sizes)
            cv = std / mean
            return float(cv * 100)

        std_unbiased = np.std(sizes, ddof=1)
        cv = std_unbiased / mean

        if n < min_samples and bootstrap:
            rng = np.random.default_rng(42)
            bootstrap_cvs = []
            for _ in range(n_bootstrap):
                sample = rng.choice(sizes, size=n, replace=True)
                if np.mean(sample) > 0:
                    bootstrap_cvs.append(np.std(sample, ddof=1) / np.mean(sample))
            if len(bootstrap_cvs) > 0:
                cv_bias = np.mean(bootstrap_cvs) - cv
                cv_corrected = cv - cv_bias
                n_correction = 1.0 + (1.0 / (4 * n)) + (1.0 / (2 * n * n))
                cv_corrected *= n_correction
                return float(max(cv_corrected, 0) * 100)

        n_correction = 1.0 + (1.0 / (4 * n)) + (1.0 / (2 * n * n))
        cv_corrected = cv * n_correction

        return float(max(cv_corrected, 0) * 100)

    def compute_polydispersity_with_ci(
        self,
        sizes: np.ndarray,
        confidence: float = 0.95,
        n_bootstrap: int = 1000
    ) -> dict:
        n = len(sizes)
        if n < 2:
            return {'cv': 0.0, 'ci_lower': 0.0, 'ci_upper': 0.0, 'n_samples': n}

        cv = self.compute_polydispersity(sizes, bootstrap=False)

        if n < 5:
            return {
                'cv': cv,
                'ci_lower': cv * 0.5,
                'ci_upper': cv * 2.0,
                'n_samples': n
            }

        rng = np.random.default_rng(42)
        bootstrap_cvs = []
        for _ in range(n_bootstrap):
            sample = rng.choice(sizes, size=n, replace=True)
            bootstrap_cv = self.compute_polydispersity(sample, bootstrap=False)
            bootstrap_cvs.append(bootstrap_cv)

        alpha = 1 - confidence
        ci_lower = np.percentile(bootstrap_cvs, alpha / 2 * 100)
        ci_upper = np.percentile(bootstrap_cvs, (1 - alpha / 2) * 100)

        return {
            'cv': cv,
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'n_samples': n
        }

    def compute_capillary_number(
        self,
        Qc: float,
        muc: float,
        sigma: float,
        W: float,
        H: float
    ) -> float:
        Ca_c = (muc * Qc * 1e3) / (60 * W * H * sigma) if sigma > 0 else 0
        return max(Ca_c, 1e-6)

    def simulate_step(
        self,
        params: SimulationParameters,
        Qc_actual: Optional[float] = None,
        Qd_actual: Optional[float] = None,
        time: float = 0.0,
        add_noise: bool = True
    ) -> Tuple[float, float, float, float]:
        Qc = Qc_actual if Qc_actual is not None else params.continuousPhase.flowRate
        Qd = Qd_actual if Qd_actual is not None else params.dispersedPhase.flowRate

        D = self.predict_droplet_size(
            Qc=Qc,
            Qd=Qd,
            muc=params.continuousPhase.viscosity,
            mud=params.dispersedPhase.viscosity,
            sigma=params.interfacialTension,
            W=params.channel.width,
            H=params.channel.height,
            junction_type=params.channel.junctionType,
            add_noise=add_noise
        )

        f = self.predict_frequency(
            Qc=Qc,
            Qd=Qd,
            D=D,
            W=params.channel.width,
            H=params.channel.height
        )

        Ca_c = self.compute_capillary_number(
            Qc=Qc,
            muc=params.continuousPhase.viscosity,
            sigma=params.interfacialTension,
            W=params.channel.width,
            H=params.channel.height
        )

        Q_ratio = Qd / Qc if Qc > 0 else 0

        return D, f, Q_ratio, Ca_c
