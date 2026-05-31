import numpy as np
from scipy.stats import entropy


class NonlinearDynamicsAnalyzer:
    def __init__(self, n_clusters=4):
        self.n_clusters = n_clusters
        self.lz_complexity = None
        self._sample_entropy = None
        self._shannon_entropy = None
        self.markov_entropy = None

    def _symbolize_sequence(self, sequence):
        n = len(sequence)
        symbols = []
        for i in range(n):
            symbols.append(str(int(sequence[i])))
        return ''.join(symbols)

    def lempel_ziv_complexity(self, sequence):
        s = self._symbolize_sequence(sequence)
        n = len(s)
        if n == 0:
            return 0.0
        
        complexity = 1
        u = 0
        v = 1
        v_max = 1
        
        while True:
            if s[u + v - 1] == s[v + v - 1]:
                v += 1
                if v + v > n:
                    complexity += 1
                    break
            else:
                if v > v_max:
                    v_max = v
                u += 1
                if u == v:
                    complexity += 1
                    v += 1
                    break
        
        return complexity

    def normalized_lempel_ziv(self, sequence):
        n = len(sequence)
        if n < 2:
            return 0.0
        
        c = self.lempel_ziv_complexity(sequence)
        normalization = n / np.log2(n)
        self.lz_complexity = c / normalization if normalization > 0 else 0.0
        
        return self.lz_complexity

    def sample_entropy(self, sequence, m=2, r=None):
        n = len(sequence)
        if r is None:
            r = 0.2 * np.std(sequence)
        
        if n <= m + 1:
            return 0.0
        
        def _count_matches(data, m):
            N = len(data)
            count = 0
            for i in range(N - m):
                for j in range(i + 1, N - m):
                    if np.max(np.abs(data[i:i + m] - data[j:j + m])) < r:
                        count += 1
            return count
        
        B = _count_matches(sequence, m)
        A = _count_matches(sequence, m + 1)
        
        if B == 0 or A == 0:
            self._sample_entropy = np.inf
            return np.inf
        
        self._sample_entropy = -np.log(A / B)
        
        return self._sample_entropy

    def multiscale_sample_entropy(self, sequence, scales=20, m=2, r=None):
        n = len(sequence)
        mse_values = []
        
        for scale in range(1, scales + 1):
            coarse_grained_len = n // scale
            if coarse_grained_len < m + 1:
                break
            
            coarse_grained = np.zeros(coarse_grained_len)
            for i in range(coarse_grained_len):
                coarse_grained[i] = np.mean(sequence[i * scale:(i + 1) * scale])
            
            se = self.sample_entropy(coarse_grained, m=m, r=r)
            mse_values.append(se)
        
        return np.array(mse_values)

    def shannon_entropy(self, sequence):
        counts = np.bincount(sequence.astype(int), minlength=self.n_clusters)
        probs = counts / len(sequence)
        probs = probs[probs > 0]
        
        self._shannon_entropy = entropy(probs, base=2)
        
        return self._shannon_entropy

    def markov_entropy_rate(self, transition_matrix):
        n_states = transition_matrix.shape[0]
        entropy_rate = 0.0
        
        for i in range(n_states):
            row = transition_matrix[i, :]
            row = row[row > 0]
            if len(row) > 0:
                entropy_rate += -np.sum(row * np.log2(row))
        
        self.markov_entropy = entropy_rate / n_states
        
        return self.markov_entropy

    def hurst_exponent(self, sequence):
        n = len(sequence)
        if n < 10:
            return 0.5
        
        lags = np.arange(2, n // 4)
        if len(lags) < 5:
            lags = np.arange(2, min(n // 2, 20))
        
        rs = []
        for lag in lags:
            num_segments = n // lag
            if num_segments < 2:
                continue
            
            segments = sequence[:num_segments * lag].reshape(num_segments, lag)
            
            mean_centered = segments - np.mean(segments, axis=1, keepdims=True)
            
            cumulative = np.cumsum(mean_centered, axis=1)
            
            r = np.max(cumulative, axis=1) - np.min(cumulative, axis=1)
            s = np.std(segments, axis=1)
            
            s[s == 0] = 1e-10
            rs.append(np.mean(r / s))
        
        if len(rs) < 2:
            return 0.5
        
        log_lags = np.log10(lags[:len(rs)])
        log_rs = np.log10(rs)
        
        hurst = np.polyfit(log_lags, log_rs, 1)[0]
        
        return max(0.0, min(1.0, hurst))

    def detrended_fluctuation_analysis(self, sequence, scales=None):
        n = len(sequence)
        if scales is None:
            scales = np.logspace(np.log10(10), np.log10(n // 4), 10).astype(int)
            scales = np.unique(scales)
        
        integrated = np.cumsum(sequence - np.mean(sequence))
        
        fluctuations = []
        for scale in scales:
            num_segments = n // scale
            if num_segments < 2:
                continue
            
            segments = integrated[:num_segments * scale].reshape(num_segments, scale)
            
            x = np.arange(scale)
            rms = []
            
            for seg in segments:
                coeffs = np.polyfit(x, seg, 1)
                trend = np.polyval(coeffs, x)
                rms.append(np.sqrt(np.mean((seg - trend)**2)))
            
            fluctuations.append(np.mean(rms))
        
        if len(fluctuations) < 2:
            return 0.5
        
        log_scales = np.log10(scales[:len(fluctuations)])
        log_fluctuations = np.log10(fluctuations)
        
        alpha = np.polyfit(log_scales, log_fluctuations, 1)[0]
        
        return alpha

    def complexity_index(self, sequence):
        lz = self.normalized_lempel_ziv(sequence)
        se = self.sample_entropy(sequence)
        sh = self.shannon_entropy(sequence)
        
        lz_norm = lz
        se_norm = se / 2.0 if np.isfinite(se) else 0.0
        sh_norm = sh / np.log2(self.n_clusters) if self.n_clusters > 1 else 0.0
        
        ci = (lz_norm + se_norm + sh_norm) / 3.0
        
        return ci

    def analyze(self, microstate_sequence, transition_matrix=None):
        results = {}
        
        results['lempel_ziv_complexity'] = self.normalized_lempel_ziv(microstate_sequence)
        results['sample_entropy'] = self.sample_entropy(microstate_sequence)
        results['shannon_entropy'] = self.shannon_entropy(microstate_sequence)
        
        if transition_matrix is not None:
            results['markov_entropy_rate'] = self.markov_entropy_rate(transition_matrix)
        
        results['hurst_exponent'] = self.hurst_exponent(microstate_sequence.astype(float))
        results['dfa_alpha'] = self.detrended_fluctuation_analysis(microstate_sequence.astype(float))
        results['complexity_index'] = self.complexity_index(microstate_sequence)
        
        return results

    def sliding_window_analysis(self, microstate_sequence, window_size=1000, step_size=100):
        n = len(microstate_sequence)
        time_points = []
        lz_values = []
        se_values = []
        ci_values = []
        
        for start in range(0, n - window_size + 1, step_size):
            window = microstate_sequence[start:start + window_size]
            if len(np.unique(window)) < 2:
                continue
            
            time_points.append(start + window_size // 2)
            lz_values.append(self.normalized_lempel_ziv(window))
            se_values.append(self.sample_entropy(window))
            ci_values.append(self.complexity_index(window))
        
        return {
            'time_points': np.array(time_points),
            'lempel_ziv': np.array(lz_values),
            'sample_entropy': np.array(se_values),
            'complexity_index': np.array(ci_values)
        }
