import numpy as np
from typing import List, Optional
from .models import (
    OptimizationConfig,
    OptimizationResult,
    OptimizationStatus,
    SimulationParameters
)
from .droplet_model import DropletFormationModel


class OptimizationEngine:
    def __init__(self, droplet_model: DropletFormationModel):
        self.droplet_model = droplet_model
        self._running = False
        self._progress = 0.0
        self._results: List[OptimizationResult] = []
        self._best_result: Optional[OptimizationResult] = None
        self._current_iteration = 0
        self._total_iterations = 0

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> OptimizationStatus:
        return OptimizationStatus(
            running=self._running,
            progress=self._progress,
            totalIterations=self._total_iterations,
            completedIterations=self._current_iteration,
            bestResult=self._best_result,
            results=self._results[-100:] if len(self._results) > 100 else self._results
        )

    def run_optimization(
        self,
        config: OptimizationConfig,
        base_params: SimulationParameters
    ):
        self._running = True
        self._progress = 0.0
        self._results = []
        self._best_result = None
        self._current_iteration = 0

        Qc_min, Qc_max = config.continuousFlowRateRange
        Qd_min, Qd_max = config.dispersedFlowRateRange
        resolution = config.resolution

        Qc_values = np.linspace(Qc_min, Qc_max, resolution)
        Qd_values = np.linspace(Qd_min, Qd_max, resolution)

        self._total_iterations = resolution * resolution
        best_error = float('inf')

        for i, Qc in enumerate(Qc_values):
            for j, Qd in enumerate(Qd_values):
                if not self._running:
                    break

                D, f, _, _ = self.droplet_model.simulate_step(
                    params=base_params,
                    Qc_actual=Qc,
                    Qd_actual=Qd,
                    time=0.0,
                    add_noise=False
                )

                error = abs(D - config.targetSize)

                if config.objective == 'maximize_frequency':
                    error = -f
                elif config.objective == 'minimize_polydispersity':
                    sizes = []
                    for _ in range(10):
                        d, _, _, _ = self.droplet_model.simulate_step(
                            params=base_params,
                            Qc_actual=Qc,
                            Qd_actual=Qd,
                            time=0.0,
                            add_noise=True
                        )
                        sizes.append(d)
                    error = np.std(sizes) / np.mean(sizes) * 100

                result = OptimizationResult(
                    continuousFlowRate=float(Qc),
                    dispersedFlowRate=float(Qd),
                    dropletSize=float(D),
                    frequency=float(f),
                    error=float(error)
                )

                self._results.append(result)

                if error < best_error:
                    best_error = error
                    self._best_result = result

                self._current_iteration += 1
                self._progress = self._current_iteration / self._total_iterations

            if not self._running:
                break

        self._running = False
        self._progress = 1.0

    def stop(self):
        self._running = False
