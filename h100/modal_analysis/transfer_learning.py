import numpy as np
from scipy import stats
from scipy.signal import welch, stft
from scipy.stats import skew, kurtosis


def extract_time_domain_features(signal):
    features = {}
    features['mean'] = np.mean(signal)
    features['std'] = np.std(signal)
    features['rms'] = np.sqrt(np.mean(signal ** 2))
    features['peak'] = np.max(np.abs(signal))
    features['crest_factor'] = features['peak'] / (features['rms'] + 1e-10)
    features['skewness'] = skew(signal)
    features['kurtosis'] = kurtosis(signal)
    features['impulse_factor'] = features['peak'] / (np.mean(np.abs(signal)) + 1e-10)
    features['margin_factor'] = features['peak'] / (np.mean(np.sqrt(np.abs(signal))) ** 2 + 1e-10)
    features['shape_factor'] = features['rms'] / (np.mean(np.abs(signal)) + 1e-10)
    return features


def extract_frequency_domain_features(signal, fs, nperseg=1024):
    freqs, psd = welch(signal, fs=fs, nperseg=nperseg)
    features = {}
    features['freq_center'] = np.sum(freqs * psd) / (np.sum(psd) + 1e-10)
    features['freq_rms'] = np.sqrt(np.sum(freqs ** 2 * psd) / (np.sum(psd) + 1e-10))
    features['freq_std'] = np.sqrt(np.sum((freqs - features['freq_center']) ** 2 * psd) / (np.sum(psd) + 1e-10))
    features['freq_skew'] = np.sum((freqs - features['freq_center']) ** 3 * psd) / (features['freq_std'] ** 3 * np.sum(psd) + 1e-10)
    features['freq_kurt'] = np.sum((freqs - features['freq_center']) ** 4 * psd) / (features['freq_std'] ** 4 * np.sum(psd) + 1e-10)
    psd_norm = psd / (np.sum(psd) + 1e-10)
    features['spectral_entropy'] = -np.sum(psd_norm * np.log2(psd_norm + 1e-10))
    features['band_energy_ratio_low'] = np.sum(psd[freqs < 5]) / (np.sum(psd) + 1e-10)
    features['band_energy_ratio_mid'] = np.sum(psd[(freqs >= 5) & (freqs < 20)]) / (np.sum(psd) + 1e-10)
    features['band_energy_ratio_high'] = np.sum(psd[freqs >= 20]) / (np.sum(psd) + 1e-10)
    return features


def extract_modal_features(natural_frequencies, damping_ratios, mode_shapes):
    features = {}
    for i, (f, d) in enumerate(zip(natural_frequencies, damping_ratios)):
        features[f'freq_{i+1}'] = f
        features[f'damping_{i+1}'] = d
    if len(natural_frequencies) > 1:
        for i in range(len(natural_frequencies)):
            for j in range(i + 1, len(natural_frequencies)):
                features[f'freq_ratio_{i+1}_{j+1}'] = natural_frequencies[j] / natural_frequencies[i]
    mode_shape_curvature = np.diff(mode_shapes, n=2, axis=0)
    features['max_curvature'] = np.max(np.abs(mode_shape_curvature))
    features['mean_curvature'] = np.mean(np.abs(mode_shape_curvature))
    return features


def extract_damage_feature_vector(data, fs, modal_params=None):
    n_samples, n_channels = data.shape
    all_features = []
    for ch in range(n_channels):
        signal = data[:, ch]
        td = extract_time_domain_features(signal)
        fd = extract_frequency_domain_features(signal, fs)
        ch_features = {**td, **fd}
        all_features.append(ch_features)
    feature_names = list(all_features[0].keys())
    feature_matrix = np.zeros((n_channels, len(feature_names)))
    for ch in range(n_channels):
        for i, name in enumerate(feature_names):
            feature_matrix[ch, i] = all_features[ch][name]
    global_features = {}
    for i, name in enumerate(feature_names):
        global_features[f'{name}_mean'] = np.mean(feature_matrix[:, i])
        global_features[f'{name}_std'] = np.std(feature_matrix[:, i])
        global_features[f'{name}_max'] = np.max(feature_matrix[:, i])
    if modal_params is not None:
        modal_feat = extract_modal_features(
            modal_params['natural_frequencies'],
            modal_params['damping_ratios'],
            modal_params['mode_shapes']
        )
        global_features.update(modal_feat)
    return global_features, feature_matrix, feature_names


class TransferDamageClassifier:
    def __init__(self, n_features=None, source_domain_name='source'):
        self.n_features = n_features
        self.source_domain_name = source_domain_name
        self.source_features = []
        self.source_labels = []
        self.target_features = []
        self.target_labels = []
        self.feature_means = None
        self.feature_stds = None
        self.domain_adaptation_weights = None
        self.damage_thresholds = None

    def fit_source(self, features_list, labels_list):
        self.source_features = np.array(features_list)
        self.source_labels = np.array(labels_list)
        self.n_features = self.source_features.shape[1]
        self.feature_means = np.mean(self.source_features, axis=0)
        self.feature_stds = np.std(self.source_features, axis=0)
        self.feature_stds[self.feature_stds < 1e-10] = 1.0
        self._compute_damage_thresholds()

    def _compute_damage_thresholds(self, confidence_level=0.95):
        healthy_features = self.source_features[self.source_labels == 0]
        if len(healthy_features) == 0:
            healthy_features = self.source_features
        normalized = self._normalize(healthy_features)
        mahalanobis_dist = self._mahalanobis_distance(normalized)
        self.damage_thresholds = {
            'mean': np.mean(mahalanobis_dist),
            'std': np.std(mahalanobis_dist),
            'confidence': np.percentile(mahalanobis_dist, confidence_level * 100)
        }

    def _normalize(self, features):
        if features.ndim == 1:
            features = features.reshape(1, -1)
        return (features - self.feature_means) / self.feature_stds

    def _mahalanobis_distance(self, normalized_features):
        if normalized_features.ndim == 1:
            normalized_features = normalized_features.reshape(1, -1)
        cov_matrix = np.cov(normalized_features.T)
        try:
            inv_cov = np.linalg.inv(cov_matrix + 1e-6 * np.eye(cov_matrix.shape[0]))
        except:
            inv_cov = np.eye(cov_matrix.shape[0])
        mean_vec = np.mean(normalized_features, axis=0)
        diff = normalized_features - mean_vec
        distances = np.sqrt(np.sum(diff @ inv_cov * diff, axis=1))
        return distances

    def domain_adaptation_mmd(self, source_features, target_features, kernel_width=1.0):
        n_source = len(source_features)
        n_target = len(target_features)
        def rbf_kernel(x, y, width):
            return np.exp(-np.sum((x - y) ** 2) / (2 * width ** 2))
        K_ss = 0
        for i in range(n_source):
            for j in range(n_source):
                K_ss += rbf_kernel(source_features[i], source_features[j], kernel_width)
        K_ss /= n_source ** 2
        K_tt = 0
        for i in range(n_target):
            for j in range(n_target):
                K_tt += rbf_kernel(target_features[i], target_features[j], kernel_width)
        K_tt /= n_target ** 2
        K_st = 0
        for i in range(n_source):
            for j in range(n_target):
                K_st += rbf_kernel(source_features[i], target_features[j], kernel_width)
        K_st /= (n_source * n_target)
        mmd_distance = K_ss + K_tt - 2 * K_st
        return mmd_distance

    def compute_instance_weights(self, target_feature_sample, lambda_reg=0.1):
        if self.feature_means is None:
            raise ValueError("Model not trained with source data first")
        source_norm = self._normalize(self.source_features)
        target_norm = self._normalize(target_feature_sample.reshape(1, -1))
        distances = np.linalg.norm(source_norm - target_norm, axis=1)
        weights = np.exp(-lambda_reg * distances)
        weights = weights / np.sum(weights)
        return weights

    def predict_damage(self, target_features, use_domain_adaptation=True, target_data_sample=None):
        if self.feature_means is None:
            raise ValueError("Model not trained with source data first")
        target_norm = self._normalize(target_features)
        if use_domain_adaptation and target_data_sample is not None:
            weights = self.compute_instance_weights(target_data_sample)
            weighted_mean = np.average(self._normalize(self.source_features), weights=weights, axis=0)
            diff = target_norm - weighted_mean
        else:
            source_mean = np.mean(self._normalize(self.source_features), axis=0)
            diff = target_norm - source_mean
        damage_index = np.linalg.norm(diff, axis=1) if diff.ndim > 1 else np.linalg.norm(diff)
        is_damaged = damage_index > self.damage_thresholds['confidence']
        damage_severity = np.clip(
            (damage_index - self.damage_thresholds['mean']) /
            (self.damage_thresholds['std'] + 1e-10),
            0, 5
        ) / 5
        return {
            'damage_index': damage_index,
            'is_damaged': is_damaged,
            'severity': damage_severity,
            'threshold': self.damage_thresholds['confidence'],
            'threshold_mean': self.damage_thresholds['mean'],
        }

    def transfer_learning_fine_tune(self, target_healthy_features, n_fine_tune_samples=5):
        if len(target_healthy_features) < n_fine_tune_samples:
            n_fine_tune_samples = len(target_healthy_features)
        idx = np.random.choice(len(target_healthy_features), n_fine_tune_samples, replace=False)
        target_sample = target_healthy_features[idx]
        all_features = np.vstack([self.source_features, target_sample])
        all_labels = np.hstack([self.source_labels, np.zeros(n_fine_tune_samples)])
        self.feature_means = np.mean(all_features, axis=0)
        self.feature_stds = np.std(all_features, axis=0)
        self.feature_stds[self.feature_stds < 1e-10] = 1.0
        self._compute_damage_thresholds()
        return {
            'fine_tune_samples': n_fine_tune_samples,
            'new_threshold': self.damage_thresholds['confidence']
        }


class CrossStructureKnowledgeBase:
    def __init__(self):
        self.structures = {}
        self.structure_metadata = {}

    def add_structure(self, structure_id, features_list, labels_list, metadata=None):
        classifier = TransferDamageClassifier()
        classifier.fit_source(features_list, labels_list)
        self.structures[structure_id] = classifier
        self.structure_metadata[structure_id] = metadata or {}

    def find_most_similar_structure(self, target_feature_sample):
        best_match = None
        best_similarity = -np.inf
        for struct_id, classifier in self.structures.items():
            weights = classifier.compute_instance_weights(target_feature_sample)
            similarity = 1.0 / (1.0 + np.mean(-np.log(weights + 1e-10)))
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = struct_id
        return best_match, best_similarity

    def ensemble_predict(self, target_features, target_sample=None):
        predictions = []
        for struct_id, classifier in self.structures.items():
            pred = classifier.predict_damage(target_features, target_data_sample=target_sample)
            predictions.append({
                'structure_id': struct_id,
                **pred
            })
        ensemble_di = np.mean([p['damage_index'] for p in predictions], axis=0)
        ensemble_vote = np.mean([p['is_damaged'] for p in predictions], axis=0) > 0.5
        ensemble_severity = np.mean([p['severity'] for p in predictions], axis=0)
        return {
            'ensemble_damage_index': ensemble_di,
            'ensemble_is_damaged': ensemble_vote,
            'ensemble_severity': ensemble_severity,
            'individual_predictions': predictions
        }
