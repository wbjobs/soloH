import numpy as np
from collections import deque
from .models import PIDParameters, PIDStatus


class PIDController:
    def __init__(self, params: PIDParameters):
        self.params = params
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = None
        self._integral_limit = 10.0

        self._measurement_delay = 0.5
        self._delay_buffer_size = 50
        self._output_history: deque = deque(maxlen=self._delay_buffer_size)
        self._time_history: deque = deque(maxlen=self._delay_buffer_size)

        self._smith_predictor_enabled = True
        self._process_gain = 2.0
        self._process_time_constant = 0.8

        self._filtered_measurement = None
        self._filter_alpha = 0.3

        self._prev_derivative = 0.0
        self._derivative_filter_alpha = 0.2

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = None
        self._output_history.clear()
        self._time_history.clear()
        self._filtered_measurement = None
        self._prev_derivative = 0.0

    def update_parameters(self, params: PIDParameters):
        self.params = params

    def _estimate_delay_compensated_measurement(
        self,
        measurement: float,
        current_time: float
    ) -> float:
        if not self._smith_predictor_enabled or len(self._output_history) < 2:
            return measurement

        delta_u = 0.0
        tau = self._process_time_constant
        K = self._process_gain

        for i in range(len(self._output_history) - 1):
            t_old = self._time_history[i]
            u_old = self._output_history[i]
            t_new = self._time_history[i + 1]
            u_new = self._output_history[i + 1]

            if current_time - t_new < self._measurement_delay:
                continue

            du = u_new - u_old
            dt = max(t_new - t_old, 0.001)
            time_since = current_time - t_new - self._measurement_delay

            if time_since > 0:
                response = du * K * (1 - np.exp(-time_since / tau))
                delta_u += response

        predicted_effect = delta_u
        compensated = measurement - predicted_effect

        return compensated

    def _filter_measurement(self, measurement: float) -> float:
        if self._filtered_measurement is None:
            self._filtered_measurement = measurement
        else:
            self._filtered_measurement = (
                self._filter_alpha * measurement +
                (1 - self._filter_alpha) * self._filtered_measurement
            )
        return self._filtered_measurement

    def compute(self, measurement: float, current_time: float) -> tuple[float, PIDStatus]:
        if not self.params.enabled:
            self._output_history.clear()
            self._time_history.clear()
            return 0.0, PIDStatus(
                enabled=False,
                targetSize=self.params.targetDropletSize,
                currentSize=measurement,
                error=0.0,
                controlOutput=0.0,
                integralTerm=0.0,
                derivativeTerm=0.0
            )

        if self.prev_time is None:
            dt = 0.1
        else:
            dt = max(current_time - self.prev_time, 0.001)

        filtered_meas = self._filter_measurement(measurement)
        compensated_meas = self._estimate_delay_compensated_measurement(filtered_meas, current_time)

        error = self.params.targetDropletSize - compensated_meas

        self.integral += error * dt
        self.integral = max(min(self.integral, self._integral_limit), -self._integral_limit)

        unfiltered_derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        derivative = (
            self._derivative_filter_alpha * unfiltered_derivative +
            (1 - self._derivative_filter_alpha) * self._prev_derivative
        )

        p_term = self.params.Kp * error
        i_term = self.params.Ki * self.integral
        d_term = self.params.Kd * derivative

        output = p_term + i_term + d_term

        base_flow = 5.0
        adjusted_flow = base_flow + output
        adjusted_flow = max(min(adjusted_flow, self.params.outputMax), self.params.outputMin)

        self._output_history.append(adjusted_flow - base_flow)
        self._time_history.append(current_time)

        self.prev_error = error
        self.prev_derivative = derivative
        self.prev_time = current_time

        status = PIDStatus(
            enabled=True,
            targetSize=self.params.targetDropletSize,
            currentSize=measurement,
            error=self.params.targetDropletSize - measurement,
            controlOutput=adjusted_flow,
            integralTerm=i_term,
            derivativeTerm=d_term
        )

        return adjusted_flow, status
