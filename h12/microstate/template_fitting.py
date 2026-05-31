import numpy as np


class TemplateFitting:
    def __init__(self, templates, sfreq=250.0):
        self.templates = templates
        self.sfreq = sfreq
        self.n_clusters = templates.shape[1]
        self.microstate_sequence = None
        self.correlation_values = None
        self.assignment_correlation = None

    def spatial_correlation(self, data, template):
        data_norm = data - np.mean(data, axis=0, keepdims=True)
        template_norm = template - np.mean(template)
        
        numerator = np.sum(data_norm * template_norm[:, np.newaxis], axis=0)
        denominator = np.sqrt(np.sum(data_norm ** 2, axis=0) * np.sum(template_norm ** 2))
        
        correlation = numerator / (denominator + 1e-10)
        return correlation

    def fit(self, data):
        n_samples = data.shape[1]
        self.correlation_values = np.zeros((self.n_clusters, n_samples))
        
        for i in range(self.n_clusters):
            template = self.templates[:, i]
            corr_pos = self.spatial_correlation(data, template)
            corr_neg = self.spatial_correlation(data, -template)
            self.correlation_values[i] = np.maximum(corr_pos, corr_neg)
        
        self.microstate_sequence = np.argmax(self.correlation_values, axis=0)
        self.assignment_correlation = np.max(self.correlation_values, axis=0)
        
        return self.microstate_sequence, self.correlation_values

    def get_sequence(self):
        if self.microstate_sequence is None:
            raise ValueError("请先进行模板拟合")
        return self.microstate_sequence

    def get_correlation_values(self):
        if self.correlation_values is None:
            raise ValueError("请先进行模板拟合")
        return self.correlation_values

    def set_sampling_rate(self, sfreq):
        self.sfreq = sfreq

    def set_templates(self, templates):
        self.templates = templates
        self.n_clusters = templates.shape[1]
