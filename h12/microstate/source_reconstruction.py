import numpy as np
from scipy.spatial.distance import cdist


class SourceReconstructor:
    def __init__(self, sfreq=250.0, method='eloreta'):
        self.sfreq = sfreq
        self.method = method
        self.leadfield = None
        self.inverse_operator = None
        self.source_space = None
        self.n_sources = None
        self.n_channels = None
        self.noise_cov = None

    def create_leadfield(self, pos, n_sources=200, head_radius=0.5):
        self.n_channels = pos.shape[0]
        self.n_sources = n_sources
        
        self.source_space = self._create_source_space(n_sources, head_radius)
        self.leadfield = self._compute_leadfield(pos, self.source_space)
        
        return self.leadfield, self.source_space

    def _create_source_space(self, n_sources, head_radius):
        theta = np.linspace(0, np.pi, int(np.sqrt(n_sources)))
        phi = np.linspace(0, 2 * np.pi, int(np.sqrt(n_sources)))
        theta, phi = np.meshgrid(theta, phi)
        theta = theta.flatten()
        phi = phi.flatten()
        
        r = head_radius * 0.95
        x = r * np.sin(theta) * np.cos(phi)
        y = r * np.sin(theta) * np.sin(phi)
        z = r * np.cos(theta)
        
        source_space = np.column_stack((x, y, z))
        
        keep = z > -head_radius * 0.3
        source_space = source_space[keep]
        
        if source_space.shape[0] > n_sources:
            idx = np.random.choice(source_space.shape[0], n_sources, replace=False)
            source_space = source_space[idx]
        
        self.n_sources = source_space.shape[0]
        
        return source_space

    def _compute_leadfield(self, channel_pos, source_pos):
        n_channels = channel_pos.shape[0]
        n_sources = source_pos.shape[0]
        
        leadfield = np.zeros((n_channels, 3, n_sources))
        
        for ch in range(n_channels):
            for src in range(n_sources):
                r = source_pos[src] - np.array([channel_pos[ch, 0], channel_pos[ch, 1], 0])
                r_norm = np.linalg.norm(r)
                
                if r_norm < 1e-10:
                    r_norm = 1e-10
                
                leadfield[ch, :, src] = r / r_norm**3
        
        return leadfield

    def compute_noise_covariance(self, data, n_samples=1000):
        if data.shape[1] > n_samples:
            noise_data = data[:, :n_samples]
        else:
            noise_data = data
        
        self.noise_cov = np.cov(noise_data)
        
        return self.noise_cov

    def compute_inverse_operator(self, lambda_reg=0.1):
        if self.leadfield is None:
            raise ValueError("请先计算leadfield矩阵")
        if self.noise_cov is None:
            raise ValueError("请先计算噪声协方差矩阵")
        
        n_channels = self.leadfield.shape[0]
        n_sources = self.leadfield.shape[2]
        
        L = self.leadfield.reshape(n_channels, 3 * n_sources)
        
        if self.method == 'eloreta':
            C = self.noise_cov + lambda_reg * np.eye(n_channels)
            C_inv = np.linalg.inv(C)
            
            W = L.T @ C_inv
            self.inverse_operator = W
            
        elif self.method == 'minimum_norm':
            C = self.noise_cov + lambda_reg * np.eye(n_channels)
            C_inv = np.linalg.inv(C)
            
            LTL = L.T @ L + lambda_reg * np.eye(3 * n_sources)
            W = np.linalg.inv(LTL) @ L.T
            
            self.inverse_operator = W
        
        elif self.method == 'dSPM':
            C = self.noise_cov + lambda_reg * np.eye(n_channels)
            C_inv = np.linalg.inv(C)
            
            W = L.T @ C_inv
            
            noise_std = np.sqrt(np.diag(W @ self.noise_cov @ W.T))
            noise_std[noise_std < 1e-10] = 1e-10
            W = W / noise_std[:, np.newaxis]
            
            self.inverse_operator = W
        
        return self.inverse_operator

    def apply_inverse(self, data):
        if self.inverse_operator is None:
            raise ValueError("请先计算逆算子")
        
        n_samples = data.shape[1]
        n_sources = self.n_sources
        
        source_data = self.inverse_operator @ data
        source_data = source_data.reshape(3, n_sources, n_samples)
        
        source_power = np.sqrt(np.sum(source_data**2, axis=0))
        
        return source_data, source_power

    def reconstruct(self, data, pos, lambda_reg=0.1, n_sources=200):
        self.create_leadfield(pos, n_sources)
        self.compute_noise_covariance(data)
        self.compute_inverse_operator(lambda_reg)
        source_data, source_power = self.apply_inverse(data)
        
        return source_data, source_power, self.source_space


class CorticalMicrostateAnalyzer:
    def __init__(self, n_clusters=4, sfreq=250.0):
        self.n_clusters = n_clusters
        self.sfreq = sfreq
        self.cortical_templates = None
        self.cortical_sequence = None
        self.source_templates = None
        self.region_labels = None

    def create_source_space_labels(self, source_space, n_regions=8):
        n_sources = source_space.shape[0]
        
        regions = []
        for i in range(n_regions):
            angle = 2 * np.pi * i / n_regions
            center = np.array([np.cos(angle), np.sin(angle), 0])
            
            dist = cdist(source_space, center.reshape(1, -1)).flatten()
            region_mask = np.argsort(dist)[:n_sources // n_regions]
            regions.append(region_mask)
        
        self.region_labels = np.zeros(n_sources, dtype=int)
        for i, region in enumerate(regions):
            self.region_labels[region] = i
        
        return self.region_labels

    def compute_source_gfp(self, source_power):
        source_gfp = np.sqrt(np.mean(source_power**2, axis=0))
        return source_gfp

    def extract_source_peaks(self, source_power, min_distance_ms=20):
        source_gfp = self.compute_source_gfp(source_power)
        
        from .gfp import GFPAnalyzer
        gfp_analyzer = GFPAnalyzer(sfreq=self.sfreq)
        peak_indices, peak_times, peak_props = gfp_analyzer.find_peaks(
            source_gfp, min_distance_ms=min_distance_ms
        )
        
        peak_source_data = source_power[:, peak_indices]
        
        return peak_source_data, peak_indices, peak_times

    def cluster_cortical_microstates(self, peak_source_data, n_init=50):
        from sklearn.cluster import KMeans
        
        data_for_clustering = peak_source_data.T
        
        kmeans = KMeans(
            n_clusters=self.n_clusters,
            n_init=n_init,
            max_iter=1000,
            random_state=42
        )
        
        labels = kmeans.fit_predict(data_for_clustering)
        self.cortical_templates = kmeans.cluster_centers_.T
        
        self.cortical_templates = self._polarity_normalization(self.cortical_templates, peak_source_data)
        self.cortical_templates, labels = self._sort_templates(self.cortical_templates, peak_source_data, labels)
        
        return self.cortical_templates, labels

    def _polarity_normalization(self, templates, peak_data):
        for i in range(self.n_clusters):
            template = templates[:, i]
            
            template_norm = template - np.mean(template)
            data_norm = peak_data - np.mean(peak_data, axis=0, keepdims=True)
            
            numerator = np.sum(template_norm[:, np.newaxis] * data_norm, axis=0)
            denominator = np.sqrt(np.sum(template_norm ** 2) * np.sum(data_norm ** 2, axis=0))
            correlations = numerator / (denominator + 1e-10)
            
            mean_corr = np.mean(correlations)
            
            if mean_corr < 0:
                templates[:, i] = -templates[:, i]
        
        return templates

    def _sort_templates(self, templates, peak_data, labels):
        gfp_peaks = np.sqrt(np.mean(peak_data ** 2, axis=0))
        weighted_labels = np.zeros(self.n_clusters)
        
        for i in range(self.n_clusters):
            mask = labels == i
            if np.sum(mask) > 0:
                weighted_labels[i] = np.sum(gfp_peaks[mask])
        
        sorted_indices = np.argsort(-weighted_labels)
        sorted_templates = templates[:, sorted_indices]
        
        sorted_labels = np.zeros_like(labels)
        for new_idx, old_idx in enumerate(sorted_indices):
            sorted_labels[labels == old_idx] = new_idx
        
        return sorted_templates, sorted_labels

    def fit_cortical_sequence(self, source_power, templates):
        n_samples = source_power.shape[1]
        correlation_values = np.zeros((self.n_clusters, n_samples))
        
        for i in range(self.n_clusters):
            template = templates[:, i]
            
            template_norm = template - np.mean(template)
            data_norm = source_power - np.mean(source_power, axis=0, keepdims=True)
            
            numerator = np.sum(template_norm[:, np.newaxis] * data_norm, axis=0)
            denominator = np.sqrt(np.sum(template_norm ** 2) * np.sum(data_norm ** 2, axis=0))
            correlations = numerator / (denominator + 1e-10)
            
            correlation_values[i] = correlations
        
        self.cortical_sequence = np.argmax(correlation_values, axis=0)
        
        return self.cortical_sequence, correlation_values

    def analyze_region_distribution(self, sequence, source_power, region_labels):
        n_regions = len(np.unique(region_labels))
        n_sources = len(region_labels)
        region_distribution = np.zeros((self.n_clusters, n_regions))
        
        for state in range(self.n_clusters):
            state_mask = sequence == state
            if np.sum(state_mask) == 0:
                continue
            
            state_power = source_power[:, state_mask]
            mean_state_power = np.mean(state_power, axis=1)
            
            for region in range(n_regions):
                region_source_mask = region_labels == region
                region_power = np.sum(mean_state_power[region_source_mask])
                total_power = np.sum(mean_state_power)
                
                if total_power > 0:
                    region_distribution[state, region] = np.sum(region_power) / total_power
                else:
                    region_distribution[state, region] = 0.0
        
        return region_distribution

    def analyze(self, source_power, source_space, peak_min_distance_ms=20):
        results = {}
        
        peak_source_data, peak_indices, peak_times = self.extract_source_peaks(
            source_power, min_distance_ms=peak_min_distance_ms
        )
        
        cortical_templates, labels = self.cluster_cortical_microstates(peak_source_data)
        results['cortical_templates'] = cortical_templates
        results['peak_labels'] = labels
        
        cortical_sequence, correlation_values = self.fit_cortical_sequence(
            source_power, cortical_templates
        )
        results['cortical_sequence'] = cortical_sequence
        results['correlation_values'] = correlation_values
        
        if self.region_labels is None:
            self.create_source_space_labels(source_space)
        
        region_dist = self.analyze_region_distribution(cortical_sequence, source_power, self.region_labels)
        results['region_distribution'] = region_dist
        
        results['peak_indices'] = peak_indices
        results['peak_times'] = peak_times
        
        return results
