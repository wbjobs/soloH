import numpy as np
from config import Config


def compute_covariance_matrix(data):
    npts, ncomp = data.shape
    cov = np.zeros((ncomp, ncomp))
    for i in range(ncomp):
        for j in range(ncomp):
            cov[i, j] = np.mean(data[:, i] * data[:, j])
    return cov


def compute_eigenvalues(cov_matrix):
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    sorted_indices = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[sorted_indices]
    eigenvectors = eigenvectors[:, sorted_indices]
    return eigenvalues, eigenvectors


def compute_polarization_parameters(data, sampling_rate, window=None):
    if window is None:
        window = Config.polarization_window

    dt = 1.0 / sampling_rate
    window_npts = int(window / dt)
    if window_npts < 3:
        window_npts = 3

    npts = data.shape[0]
    rectilinearity = np.zeros(npts)
    incidence_angle = np.zeros(npts)
    azimuth = np.zeros(npts)
    planarity = np.zeros(npts)
    degree_of_polarization = np.zeros(npts)

    half_window = window_npts // 2

    for i in range(npts):
        start = max(0, i - half_window)
        end = min(npts, i + half_window + 1)
        window_data = data[start:end, :]

        if window_data.shape[0] < 3:
            rectilinearity[i] = 0
            incidence_angle[i] = 0
            azimuth[i] = 0
            planarity[i] = 0
            degree_of_polarization[i] = 0
            continue

        cov = compute_covariance_matrix(window_data)
        eigenvalues, eigenvectors = compute_eigenvalues(cov)

        lambda1, lambda2, lambda3 = eigenvalues

        if lambda1 > 1e-15:
            rectilinearity[i] = 1.0 - (lambda2 + lambda3) / (2.0 * lambda1)
            planarity[i] = 1.0 - (2.0 * lambda3) / (lambda1 + lambda2)
            degree_of_polarization[i] = 1.0 - (lambda1 * lambda2 * lambda3) / ((lambda1 + lambda2 + lambda3) / 3.0) ** 3
        else:
            rectilinearity[i] = 0
            planarity[i] = 0
            degree_of_polarization[i] = 0

        primary_vector = eigenvectors[:, 0]

        z_comp = np.abs(primary_vector[0])
        incidence_angle[i] = np.degrees(np.arccos(z_comp / np.linalg.norm(primary_vector)))

        h_comp = np.sqrt(primary_vector[1] ** 2 + primary_vector[2] ** 2)
        if h_comp > 1e-15:
            az = np.degrees(np.arctan2(primary_vector[2], primary_vector[1]))
            if az < 0:
                az += 360.0
            azimuth[i] = az
        else:
            azimuth[i] = 0

    return {
        'rectilinearity': rectilinearity,
        'incidence_angle': incidence_angle,
        'azimuth': azimuth,
        'planarity': planarity,
        'degree_of_polarization': degree_of_polarization
    }


def verify_p_wave(polarization_params, arrival_idx, threshold=None, rect_thresh=None):
    if threshold is None:
        threshold = Config.polarization_threshold
    if rect_thresh is None:
        rect_thresh = Config.rectilinearity_threshold

    npts = len(polarization_params['rectilinearity'])
    start = max(0, arrival_idx - 10)
    end = min(npts, arrival_idx + 20)

    avg_rect = np.mean(polarization_params['rectilinearity'][start:end])
    avg_dop = np.mean(polarization_params['degree_of_polarization'][start:end])

    is_p_wave = (avg_rect >= rect_thresh) and (avg_dop >= threshold)

    incidence = np.mean(polarization_params['incidence_angle'][start:end])
    azimuth = np.mean(polarization_params['azimuth'][start:end])

    confidence = min(1.0, (avg_rect + avg_dop) / 2.0)

    return {
        'is_p_wave': is_p_wave,
        'rectilinearity': avg_rect,
        'degree_of_polarization': avg_dop,
        'incidence_angle': incidence,
        'azimuth': azimuth,
        'confidence': confidence
    }


class PolarizationAnalyzer:
    def __init__(self, sampling_rate):
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        self.window_npts = int(Config.polarization_window / self.dt)
        self.data_buffer = []
        self.max_buffer = self.window_npts * 3

    def process_chunk(self, chunk_data, arrival_indices=None):
        self.data_buffer.extend(chunk_data.tolist())
        self.data_buffer = self.data_buffer[-self.max_buffer:]

        data_array = np.array(self.data_buffer)
        npts = data_array.shape[0]

        if npts < self.window_npts:
            return {
                'rectilinearity': np.zeros(len(chunk_data)),
                'incidence_angle': np.zeros(len(chunk_data)),
                'azimuth': np.zeros(len(chunk_data)),
                'planarity': np.zeros(len(chunk_data)),
                'degree_of_polarization': np.zeros(len(chunk_data)),
                'verifications': []
            }

        params = compute_polarization_parameters(data_array, self.sampling_rate)

        chunk_start = npts - len(chunk_data)
        chunk_params = {
            key: params[key][chunk_start:] for key in params
        }

        verifications = []
        if arrival_indices is not None:
            for arr_idx in arrival_indices:
                global_idx = chunk_start + arr_idx
                if 0 <= global_idx < npts:
                    verification = verify_p_wave(params, global_idx)
                    verifications.append(verification)

        chunk_params['verifications'] = verifications
        return chunk_params

    def reset(self):
        self.data_buffer = []
