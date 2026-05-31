import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from scipy.optimize import linear_sum_assignment


class MicrostateClustering:
    def __init__(self, n_clusters=4, n_init=100, max_iter=1000, random_state=42):
        self.n_clusters = n_clusters
        self.n_init = n_init
        self.max_iter = max_iter
        self.random_state = random_state
        self.kmeans = None
        self.templates = None
        self.labels = None
        self.explained_variance = None
        self._reference_templates = None

    def _create_reference_templates(self, n_channels):
        ref = np.zeros((n_channels, 4))
        
        theta = np.linspace(0, 2 * np.pi, n_channels, endpoint=False)
        r = 0.4 + 0.1 * np.sin(4 * theta)
        
        x = r * np.cos(theta)
        y = r * np.sin(theta)
        
        ref[:, 0] = -x * y
        ref[:, 1] = x * y
        ref[:, 2] = y
        ref[:, 3] = x
        
        ref = ref / (np.linalg.norm(ref, axis=0, keepdims=True) + 1e-10)
        
        return ref

    def _spatial_correlation(self, map1, map2):
        map1_norm = map1 - np.mean(map1)
        map2_norm = map2 - np.mean(map2)
        
        corr = np.sum(map1_norm * map2_norm) / (
            np.sqrt(np.sum(map1_norm ** 2)) * np.sqrt(np.sum(map2_norm ** 2)) + 1e-10
        )
        return corr

    def _match_templates_to_reference(self, templates, reference_templates):
        n_clusters = templates.shape[1]
        cost_matrix = np.zeros((n_clusters, n_clusters))
        
        for i in range(n_clusters):
            for j in range(n_clusters):
                corr_pos = self._spatial_correlation(templates[:, i], reference_templates[:, j])
                corr_neg = self._spatial_correlation(-templates[:, i], reference_templates[:, j])
                cost_matrix[i, j] = -max(corr_pos, corr_neg)
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        return col_ind

    def normalize_data(self, data):
        normalized_data = normalize(data.T, norm='l2').T
        return normalized_data

    def fit(self, peak_data):
        data_for_clustering = peak_data.T
        
        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            n_init=self.n_init,
            max_iter=self.max_iter,
            random_state=self.random_state
        )
        
        self.labels = self.kmeans.fit_predict(data_for_clustering)
        raw_templates = self.kmeans.cluster_centers_.T
        
        self.templates = self._polarity_normalization(raw_templates, peak_data)
        self.templates, self.labels = self._sort_templates_consistent(self.templates, peak_data)
        
        self._compute_explained_variance(peak_data)
        
        return self.templates, self.labels

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

    def _sort_templates_consistent(self, templates, peak_data):
        n_channels = templates.shape[0]
        
        if self._reference_templates is None or self._reference_templates.shape[0] != n_channels:
            self._reference_templates = self._create_reference_templates(n_channels)
        
        matched_order = self._match_templates_to_reference(templates, self._reference_templates)
        
        for i in range(self.n_clusters):
            ref_template = self._reference_templates[:, matched_order[i]]
            corr_pos = self._spatial_correlation(templates[:, i], ref_template)
            corr_neg = self._spatial_correlation(-templates[:, i], ref_template)
            if corr_neg > corr_pos:
                templates[:, i] = -templates[:, i]
        
        sorted_templates = templates[:, matched_order]
        
        sorted_labels = np.zeros_like(self.labels)
        for new_idx, old_idx in enumerate(matched_order):
            mask = self.labels == old_idx
            sorted_labels[mask] = new_idx
        
        gfp_peaks = np.sqrt(np.mean(peak_data ** 2, axis=0))
        gfp_by_state = np.zeros(self.n_clusters)
        for i in range(self.n_clusters):
            mask = sorted_labels == i
            if np.sum(mask) > 0:
                gfp_by_state[i] = np.mean(gfp_peaks[mask])
        
        gfp_sorted_order = np.argsort(-gfp_by_state)
        final_templates = sorted_templates[:, gfp_sorted_order]
        final_labels = np.zeros_like(sorted_labels)
        for new_idx, old_idx in enumerate(gfp_sorted_order):
            mask = sorted_labels == old_idx
            final_labels[mask] = new_idx
        
        self.labels = final_labels
        return final_templates, final_labels

    def _sort_templates(self, templates, peak_data):
        sorted_templates, sorted_labels = self._sort_templates_consistent(templates, peak_data)
        return sorted_templates

    def _compute_explained_variance(self, peak_data):
        reconstructed = np.zeros_like(peak_data)
        
        for i in range(peak_data.shape[1]):
            label = self.labels[i]
            template = self.templates[:, label]
            
            template_norm = template - np.mean(template)
            data_norm = peak_data[:, i] - np.mean(peak_data[:, i])
            
            pos_corr = np.sum(template_norm * data_norm) / (
                np.sqrt(np.sum(template_norm ** 2)) * np.sqrt(np.sum(data_norm ** 2)) + 1e-10
            )
            
            if pos_corr < 0:
                reconstructed[:, i] = -template
            else:
                reconstructed[:, i] = template
        
        total_variance = np.sum(peak_data ** 2)
        residual_variance = np.sum((peak_data - reconstructed) ** 2)
        self.explained_variance = max(0.0, 1 - (residual_variance / total_variance))
        
        return self.explained_variance

    def fit_predict(self, peak_data):
        return self.fit(peak_data)
