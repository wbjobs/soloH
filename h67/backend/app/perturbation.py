import numpy as np
from .models import PerturbationConfig, PerturbationType, PerturbationPhase


class PerturbationGenerator:
    def __init__(self, config: PerturbationConfig):
        self.config = config
        self._last_step_value = 0.0
        self._step_applied = False

    def update_config(self, config: PerturbationConfig):
        self.config = config
        self._step_applied = False

    def get_perturbation(self, time: float) -> tuple[float, float]:
        if not self.config.enabled:
            return 0.0, 0.0

        amplitude = self.config.amplitude / 100.0
        freq = self.config.frequency

        if self.config.type == PerturbationType.SINUSOIDAL:
            perturbation = amplitude * np.sin(2 * np.pi * freq * time)
        elif self.config.type == PerturbationType.STEP:
            if not self._step_applied and time > 1.0:
                self._step_applied = True
                self._last_step_value = amplitude
            perturbation = self._last_step_value
        else:
            np.random.seed(int(time * 1000) % 100000)
            perturbation = amplitude * np.random.uniform(-1, 1)

        pert_c = 0.0
        pert_d = 0.0

        if self.config.phase == PerturbationPhase.CONTINUOUS:
            pert_c = perturbation
        elif self.config.phase == PerturbationPhase.DISPERSED:
            pert_d = perturbation
        else:
            pert_c = perturbation * 0.5
            pert_d = perturbation * 0.5

        return pert_c, pert_d

    def apply_perturbation(
        self,
        Qc_base: float,
        Qd_base: float,
        time: float
    ) -> tuple[float, float]:
        pert_c, pert_d = self.get_perturbation(time)
        Qc = Qc_base * (1 + pert_c)
        Qd = Qd_base * (1 + pert_d)
        return max(Qc, 0.01), max(Qd, 0.01)

    def reset(self):
        self._last_step_value = 0.0
        self._step_applied = False
