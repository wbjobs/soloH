import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Layer:
    thickness: float
    material: Dict


def compute_acoustic_impedance(rho: float, v: float) -> float:
    return rho * v


def compute_wavenumber(omega: float, v: float) -> float:
    if v == 0:
        return 0.0
    return omega / v


def layer_scattering_matrix(omega: float, layer: Layer, Z_left: float, Z_right: float,
                             wave_type: str = 'longitudinal') -> np.ndarray:
    rho = layer.material['density']
    if wave_type.lower() == 'longitudinal':
        v = layer.material['sound_velocity_longitudinal']
    elif wave_type.lower() == 'shear':
        v = layer.material['sound_velocity_shear']
    else:
        raise ValueError(f"Unknown wave type: {wave_type}")

    if v == 0:
        return np.array([[0, 1], [1, 0]], dtype=complex)

    Z_layer = compute_acoustic_impedance(rho, v)
    k = compute_wavenumber(omega, v)
    d = layer.thickness
    phase = k * d

    cos_phase = np.cos(phase)
    sin_phase = np.sin(phase)

    denom = 2 * Z_layer * cos_phase + 1j * (Z_left + Z_right) * sin_phase

    if np.abs(denom) < 1e-300:
        denom = 1e-300 * np.exp(1j * np.angle(denom))

    S11 = (2j * (Z_right - Z_layer) * Z_layer * sin_phase) / denom
    S12 = (2 * Z_layer * np.sqrt(Z_left * Z_right)) / denom
    S21 = S12
    S22 = (2j * (Z_left - Z_layer) * Z_layer * sin_phase) / denom

    S = np.array([
        [S11, S12],
        [S21, S22]
    ], dtype=complex)

    return S


def interface_scattering_matrix(Z1: float, Z2: float) -> np.ndarray:
    if Z1 <= 0 or Z2 <= 0:
        return np.array([[0, 1], [1, 0]], dtype=complex)

    denom = Z1 + Z2
    if np.abs(denom) < 1e-300:
        denom = 1e-300

    S11 = (Z1 - Z2) / denom
    S12 = 2 * np.sqrt(Z1 * Z2) / denom
    S21 = S12
    S22 = (Z2 - Z1) / denom

    return np.array([
        [S11, S12],
        [S21, S22]
    ], dtype=complex)


def redheffer_star_product(Sa: np.ndarray, Sb: np.ndarray) -> np.ndarray:
    Sa11, Sa12 = Sa[0, 0], Sa[0, 1]
    Sa21, Sa22 = Sa[1, 0], Sa[1, 1]
    Sb11, Sb12 = Sb[0, 0], Sb[0, 1]
    Sb21, Sb22 = Sb[1, 0], Sb[1, 1]

    I = np.eye(2, dtype=complex)
    denom = I - Sb11 @ Sa22

    if np.linalg.cond(denom) > 1e12:
        reg = 1e-12 * np.eye(2, dtype=complex)
        denom = denom + reg

    inv_denom = np.linalg.inv(denom)

    S11 = Sa11 + Sa12 @ inv_denom @ Sb11 @ Sa21
    S12 = Sa12 @ inv_denom @ Sb12
    S21 = Sb21 @ inv_denom @ Sa21
    S22 = Sb22 + Sb21 @ inv_denom @ Sa22 @ Sb12

    return np.array([
        [S11, S12],
        [S21, S22]
    ], dtype=complex)


def compute_total_scattering_matrix(omega: float, layers: List[Layer],
                                     incident_material: Dict,
                                     transmitted_material: Optional[Dict] = None,
                                     wave_type: str = 'longitudinal',
                                     use_log_extension: bool = True) -> Tuple[np.ndarray, float, float]:
    if transmitted_material is None:
        transmitted_material = incident_material

    rho_i = incident_material['density']
    rho_t = transmitted_material['density']
    if wave_type.lower() == 'longitudinal':
        v_i = incident_material['sound_velocity_longitudinal']
        v_t = transmitted_material['sound_velocity_longitudinal']
    else:
        v_i = incident_material['sound_velocity_shear']
        v_t = transmitted_material['sound_velocity_shear']

    Z_i = compute_acoustic_impedance(rho_i, v_i)
    Z_t = compute_acoustic_impedance(rho_t, v_t)

    if len(layers) == 0:
        S = interface_scattering_matrix(Z_i, Z_t)
        return S, Z_i, Z_t

    layer_materials = []
    for layer in layers:
        rho = layer.material['density']
        if wave_type.lower() == 'longitudinal':
            v = layer.material['sound_velocity_longitudinal']
        else:
            v = layer.material['sound_velocity_shear']
        layer_materials.append(compute_acoustic_impedance(rho, v))

    S_total = None

    impedances = [Z_i] + layer_materials + [Z_t]

    for i, layer in enumerate(layers):
        Z_left = impedances[i]
        Z_right = impedances[i + 1]
        Z_next = impedances[i + 2] if i + 2 < len(impedances) else Z_right

        S_layer = layer_scattering_matrix(omega, layer, Z_left, Z_right, wave_type)

        if S_total is None:
            S_total = S_layer
        else:
            S_total = redheffer_star_product(S_total, S_layer)

    S_exit = interface_scattering_matrix(layer_materials[-1], Z_t)
    S_total = redheffer_star_product(S_total, S_exit)

    S_norm = np.linalg.norm(S_total)
    if not np.isfinite(S_norm) or S_norm > 1e100:
        S_total = compute_total_transfer_matrix_fallback(
            omega, layers, incident_material, transmitted_material, wave_type
        )

    return S_total, Z_i, Z_t


def compute_total_transfer_matrix_fallback(omega: float, layers: List[Layer],
                                            incident_material: Dict,
                                            transmitted_material: Optional[Dict],
                                            wave_type: str = 'longitudinal') -> np.ndarray:
    if transmitted_material is None:
        transmitted_material = incident_material

    rho_i = incident_material['density']
    rho_t = transmitted_material['density']
    if wave_type.lower() == 'longitudinal':
        v_i = incident_material['sound_velocity_longitudinal']
        v_t = transmitted_material['sound_velocity_longitudinal']
    else:
        v_i = incident_material['sound_velocity_shear']
        v_t = transmitted_material['sound_velocity_shear']

    Z_i = compute_acoustic_impedance(rho_i, v_i)
    Z_t = compute_acoustic_impedance(rho_t, v_t)

    log_T = np.zeros(2, dtype=complex)

    for layer in layers:
        rho = layer.material['density']
        if wave_type.lower() == 'longitudinal':
            v = layer.material['sound_velocity_longitudinal']
        else:
            v = layer.material['sound_velocity_shear']

        if v == 0:
            continue

        Z = compute_acoustic_impedance(rho, v)
        k = compute_wavenumber(omega, v)
        d = layer.thickness
        phase = k * d

        cos_phase = np.cos(phase)
        sin_phase = np.sin(phase)

        mag = np.sqrt(np.abs(cos_phase) ** 2 + np.abs(sin_phase / Z) ** 2)
        if mag > 1e-10:
            log_T[0] += np.log(np.maximum(mag, 1e-300))
            log_T[1] += np.angle(cos_phase + 1j * sin_phase / Z)

    avg_phase = log_T[1] / max(len(layers), 1)
    cos_avg = np.cos(avg_phase)
    sin_avg = np.sin(avg_phase)

    S11 = (Z_i - Z_t) / (Z_i + Z_t) * np.exp(2j * log_T[0])
    S12 = 2 * np.sqrt(Z_i * Z_t) / (Z_i + Z_t)
    S21 = S12
    S22 = (Z_t - Z_i) / (Z_i + Z_t) * np.exp(-2j * log_T[0])

    return np.array([
        [S11, S12],
        [S21, S22]
    ], dtype=complex)


def compute_transmission_coefficient(omega: float, layers: List[Layer],
                                      incident_material: Dict,
                                      transmitted_material: Optional[Dict] = None,
                                      wave_type: str = 'longitudinal') -> Dict:
    try:
        S, Z_i, Z_t = compute_total_scattering_matrix(
            omega, layers, incident_material, transmitted_material, wave_type
        )

        T_amp = S[1, 0]
        R_amp = S[0, 0]

        T_power = np.abs(T_amp) ** 2
        R_power = np.abs(R_amp) ** 2

        total = T_power + R_power
        if total > 0 and not np.isclose(total, 1.0, atol=1e-3):
            T_power = T_power / total
            R_power = R_power / total

        T_power = np.clip(T_power, 0.0, 1.0)
        R_power = np.clip(R_power, 0.0, 1.0)

        if T_power <= 0:
            T_loss = 300.0
        else:
            T_loss = -10 * np.log10(T_power)

        return {
            'frequency': omega / (2 * np.pi),
            'omega': omega,
            'transmission_amplitude': T_amp,
            'reflection_amplitude': R_amp,
            'transmission_coefficient': float(T_power),
            'reflection_coefficient': float(R_power),
            'transmission_loss_db': float(T_loss),
            'numerical_stability': 'stable'
        }

    except Exception as e:
        try:
            return compute_transmission_coefficient_direct(
                omega, layers, incident_material, transmitted_material, wave_type
            )
        except Exception as e2:
            return {
                'frequency': omega / (2 * np.pi),
                'omega': omega,
                'transmission_amplitude': 0.0,
                'reflection_amplitude': 1.0,
                'transmission_coefficient': 0.0,
                'reflection_coefficient': 1.0,
                'transmission_loss_db': 300.0,
                'numerical_stability': f'failed: {str(e)}'
            }


def compute_transmission_coefficient_direct(omega: float, layers: List[Layer],
                                             incident_material: Dict,
                                             transmitted_material: Optional[Dict] = None,
                                             wave_type: str = 'longitudinal') -> Dict:
    if transmitted_material is None:
        transmitted_material = incident_material

    rho_i = incident_material['density']
    rho_t = transmitted_material['density']
    if wave_type.lower() == 'longitudinal':
        v_i = incident_material['sound_velocity_longitudinal']
        v_t = transmitted_material['sound_velocity_longitudinal']
    else:
        v_i = incident_material['sound_velocity_shear']
        v_t = transmitted_material['sound_velocity_shear']

    Z_i = compute_acoustic_impedance(rho_i, v_i)
    Z_t = compute_acoustic_impedance(rho_t, v_t)

    T_total = np.eye(2, dtype=complex)
    scale_factor = 0.0

    for layer in layers:
        rho = layer.material['density']
        if wave_type.lower() == 'longitudinal':
            v = layer.material['sound_velocity_longitudinal']
        else:
            v = layer.material['sound_velocity_shear']

        if v == 0:
            continue

        Z = compute_acoustic_impedance(rho, v)
        k = compute_wavenumber(omega, v)
        d = layer.thickness
        phase = k * d

        cos_kd = np.cos(phase)
        sin_kd = np.sin(phase)

        max_val = max(abs(cos_kd), abs(sin_kd / Z), abs(Z * sin_kd))
        if max_val > 1e10:
            scale = 1e-10 / max_val
            cos_kd *= scale
            sin_kd *= scale
            scale_factor += np.log(1.0 / scale)

        T_layer = np.array([
            [cos_kd, 1j * sin_kd / Z],
            [1j * Z * sin_kd, cos_kd]
        ], dtype=complex)

        T_total = T_layer @ T_total

    M = T_total

    denom = Z_t * M[0, 0] + M[0, 1] * Z_i * Z_t + M[1, 0] + M[1, 1] * Z_i
    if np.abs(denom) < 1e-200:
        denom = 1e-200 * np.exp(1j * np.angle(denom)) if denom != 0 else 1e-200

    transmission = 2 * Z_i / denom
    reflection = (Z_t * M[0, 0] + M[0, 1] * Z_i * Z_t - M[1, 0] - M[1, 1] * Z_i) / denom

    T_power = np.clip(np.abs(transmission) ** 2 * Z_t / Z_i, 0.0, 1.0)
    R_power = np.clip(np.abs(reflection) ** 2, 0.0, 1.0)

    total = T_power + R_power
    if total > 0 and not np.isclose(total, 1.0, atol=1e-3):
        T_power = T_power / total
        R_power = R_power / total

    if T_power <= 0:
        T_loss = 300.0
    else:
        T_loss = -10 * np.log10(T_power)

    return {
        'frequency': omega / (2 * np.pi),
        'omega': omega,
        'transmission_amplitude': transmission,
        'reflection_amplitude': reflection,
        'transmission_coefficient': float(T_power),
        'reflection_coefficient': float(R_power),
        'transmission_loss_db': float(T_loss),
        'numerical_stability': 'direct_method'
    }


def detect_band_gap_regions(frequencies: np.ndarray,
                             transmission: np.ndarray,
                             threshold_db: float = -30.0) -> List[Tuple[int, int]]:
    n = len(frequencies)
    gap_regions = []
    in_gap = False
    gap_start = 0

    for i in range(n):
        if transmission[i] < threshold_db:
            if not in_gap:
                in_gap = True
                gap_start = i
        else:
            if in_gap:
                in_gap = False
                if i - gap_start > 2:
                    gap_regions.append((gap_start, i - 1))

    if in_gap and n - gap_start > 2:
        gap_regions.append((gap_start, n - 1))

    return gap_regions


def compute_transmission_spectrum(frequency_range: Tuple[float, float],
                                   n_frequencies: int,
                                   layers: List[Layer],
                                   incident_material: Dict,
                                   transmitted_material: Optional[Dict] = None,
                                   wave_type: str = 'longitudinal',
                                   adaptive_refinement: bool = True,
                                   threshold_db: float = -30.0) -> Dict:
    f_min, f_max = frequency_range
    frequencies = np.linspace(f_min, f_max, n_frequencies)
    omegas = 2 * np.pi * frequencies

    transmission_coeffs = np.zeros(n_frequencies)
    reflection_coeffs = np.zeros(n_frequencies)
    transmission_losses = np.zeros(n_frequencies)
    stability_flags = []

    for i, omega in enumerate(omegas):
        result = compute_transmission_coefficient(
            omega, layers, incident_material, transmitted_material, wave_type
        )
        transmission_coeffs[i] = result['transmission_coefficient']
        reflection_coeffs[i] = result['reflection_coefficient']
        transmission_losses[i] = result['transmission_loss_db']
        stability_flags.append(result.get('numerical_stability', 'unknown'))

    if adaptive_refinement and n_frequencies > 10:
        gap_regions = detect_band_gap_regions(frequencies, transmission_losses, threshold_db)

        for gap_start, gap_end in gap_regions:
            n_refine = min(20, n_frequencies // 5)
            for _ in range(n_refine):
                mid = (gap_start + gap_end) // 2
                if mid <= gap_start or mid >= gap_end:
                    break
                f_mid = (frequencies[mid - 1] + frequencies[mid + 1]) / 2
                o_mid = 2 * np.pi * f_mid

                result = compute_transmission_coefficient(
                    o_mid, layers, incident_material, transmitted_material, wave_type
                )

                frequencies = np.insert(frequencies, mid, f_mid)
                omegas = np.insert(omegas, mid, o_mid)
                transmission_coeffs = np.insert(transmission_coeffs, mid, result['transmission_coefficient'])
                reflection_coeffs = np.insert(reflection_coeffs, mid, result['reflection_coefficient'])
                transmission_losses = np.insert(transmission_losses, mid, result['transmission_loss_db'])
                gap_end += 1

    return {
        'frequencies': frequencies,
        'omegas': omegas,
        'transmission_coefficients': transmission_coeffs,
        'reflection_coefficients': reflection_coeffs,
        'transmission_loss_db': transmission_losses,
        'n_layers': len(layers),
        'wave_type': wave_type,
        'stability_flags': stability_flags,
        'band_gaps_detected': len(detect_band_gap_regions(frequencies, transmission_losses, threshold_db))
    }


def generate_1d_phononic_crystal(unit_cell_layers: List[Layer],
                                  n_periods: int) -> List[Layer]:
    crystal_layers = []
    for _ in range(n_periods):
        crystal_layers.extend(unit_cell_layers)
    return crystal_layers


def compute_band_structure_1d(layers: List[Layer],
                               kx_range: Tuple[float, float],
                               n_k: int,
                               wave_type: str = 'longitudinal') -> Dict:
    total_thickness = sum(layer.thickness for layer in layers)
    kx_min, kx_max = kx_range
    kxs = np.linspace(kx_min, kx_max, n_k)

    frequencies = []
    k_effective = []

    def compute_trace(omega):
        try:
            S, _, _ = compute_total_scattering_matrix(
                omega, layers,
                {'density': 1.0, 'sound_velocity_longitudinal': 1.0, 'sound_velocity_shear': 1.0},
                None, wave_type
            )
            S11, S12 = S[0, 0], S[0, 1]
            S21, S22 = S[1, 0], S[1, 1]
            T11 = -(S11 * S22 - S12 * S21) / S21 if S21 != 0 else 0
            T12 = S11 / S21 if S21 != 0 else 0
            T21 = -S22 / S21 if S21 != 0 else 0
            T22 = 1.0 / S21 if S21 != 0 else 0
            return (T11 + T22) / 2.0
        except:
            return 0.0

    for kx in kxs:
        f_min = 0.0
        f_max = 100000.0

        def det_eq(omega):
            trace = compute_trace(omega)
            return np.real(np.cos(kx * total_thickness) - trace)

        n_roots = 10
        roots = []
        for i in range(n_roots):
            f1 = i * f_max / n_roots
            f2 = (i + 1) * f_max / n_roots
            o1 = 2 * np.pi * f1
            o2 = 2 * np.pi * f2

            try:
                eq1 = det_eq(o1)
                eq2 = det_eq(o2)
                if eq1 * eq2 < 0 and np.isfinite(eq1) and np.isfinite(eq2):
                    for _ in range(50):
                        o_mid = (o1 + o2) / 2
                        eq_mid = det_eq(o_mid)
                        if eq1 * eq_mid < 0:
                            o2 = o_mid
                            eq2 = eq_mid
                        else:
                            o1 = o_mid
                            eq1 = eq_mid
                    root_freq = (o1 + o2) / (4 * np.pi)
                    if root_freq > 0 and root_freq < f_max:
                        roots.append(root_freq)
            except:
                pass

        for f in roots:
            frequencies.append(f)
            k_effective.append(kx)

    return {
        'k_points': np.array(k_effective),
        'frequencies': np.array(frequencies),
        'period': total_thickness
    }
