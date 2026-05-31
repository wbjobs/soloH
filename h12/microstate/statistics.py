import numpy as np


class StatisticsAnalyzer:
    def __init__(self, sfreq=250.0, n_clusters=4):
        self.sfreq = sfreq
        self.n_clusters = n_clusters
        self.durations = None
        self.frequencies = None
        self.transition_probabilities = None
        self.mean_durations = None
        self.std_durations = None

    def compute_durations(self, microstate_sequence):
        segments = []
        current_state = microstate_sequence[0]
        start_idx = 0

        for i in range(1, len(microstate_sequence)):
            if microstate_sequence[i] != current_state:
                duration_samples = i - start_idx
                duration_ms = (duration_samples / self.sfreq) * 1000
                segments.append({
                    'state': int(current_state),
                    'start_idx': start_idx,
                    'end_idx': i,
                    'duration_samples': duration_samples,
                    'duration_ms': duration_ms
                })
                current_state = microstate_sequence[i]
                start_idx = i

        duration_samples = len(microstate_sequence) - start_idx
        duration_ms = (duration_samples / self.sfreq) * 1000
        segments.append({
            'state': int(current_state),
            'start_idx': start_idx,
            'end_idx': len(microstate_sequence),
            'duration_samples': duration_samples,
            'duration_ms': duration_ms
        })

        self.durations = segments
        self._compute_duration_stats()
        return self.durations

    def _compute_duration_stats(self):
        self.mean_durations = np.zeros(self.n_clusters)
        self.std_durations = np.zeros(self.n_clusters)

        for state in range(self.n_clusters):
            state_durations = [seg['duration_ms'] for seg in self.durations 
                               if seg['state'] == state]
            if state_durations:
                self.mean_durations[state] = np.mean(state_durations)
                self.std_durations[state] = np.std(state_durations)

    def compute_frequencies(self, microstate_sequence):
        total_samples = len(microstate_sequence)
        self.frequencies = np.zeros(self.n_clusters)

        for state in range(self.n_clusters):
            self.frequencies[state] = np.sum(microstate_sequence == state) / total_samples

        return self.frequencies

    def compute_transition_probabilities(self, microstate_sequence):
        self.transition_probabilities = np.zeros((self.n_clusters, self.n_clusters))

        for i in range(len(microstate_sequence) - 1):
            current_state = int(microstate_sequence[i])
            next_state = int(microstate_sequence[i + 1])
            self.transition_probabilities[current_state, next_state] += 1

        row_sums = self.transition_probabilities.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        self.transition_probabilities = self.transition_probabilities / row_sums

        return self.transition_probabilities

    def get_transition_counts(self, microstate_sequence):
        transition_counts = np.zeros((self.n_clusters, self.n_clusters))

        for i in range(len(microstate_sequence) - 1):
            current_state = int(microstate_sequence[i])
            next_state = int(microstate_sequence[i + 1])
            transition_counts[current_state, next_state] += 1

        return transition_counts

    def analyze(self, microstate_sequence):
        durations = self.compute_durations(microstate_sequence)
        frequencies = self.compute_frequencies(microstate_sequence)
        transition_probs = self.compute_transition_probabilities(microstate_sequence)

        return {
            'durations': durations,
            'mean_durations': self.mean_durations,
            'std_durations': self.std_durations,
            'frequencies': frequencies,
            'transition_probabilities': transition_probs,
            'transition_counts': self.get_transition_counts(microstate_sequence)
        }

    def set_sampling_rate(self, sfreq):
        self.sfreq = sfreq

    def set_n_clusters(self, n_clusters):
        self.n_clusters = n_clusters
