import numpy as np
import librosa
from scipy import signal
from scipy.cluster import hierarchy
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Dict, Any, Optional, List
from . import utils
from .embedding import SpeakerEmbeddingExtractor


class SpeakerSeparator:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160, n_mels: int = 80):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels

    def _compute_features(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        audio = utils.normalize_audio(audio)

        mfcc = utils.compute_mfcc(
            audio, sample_rate=self.sample_rate,
            n_fft=self.n_fft, hop_length=self.hop_length, n_mfcc=20
        )
        delta = librosa.feature.delta(mfcc)
        delta2 = librosa.feature.delta(mfcc, order=2)

        features = np.concatenate([mfcc, delta, delta2], axis=0)

        mag, phase = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        return features, mag, phase

    def _compute_spectral_features(self, mag: np.ndarray) -> np.ndarray:
        centroid = librosa.feature.spectral_centroid(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        bandwidth = librosa.feature.spectral_bandwidth(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        rolloff = librosa.feature.spectral_rolloff(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        flatness = librosa.feature.spectral_flatness(
            S=mag, hop_length=self.hop_length
        )
        contrast = librosa.feature.spectral_contrast(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )

        return np.concatenate([
            centroid, bandwidth, rolloff, flatness, contrast
        ], axis=0)

    def _compute_pitch_features(self, audio: np.ndarray) -> np.ndarray:
        pitches, magnitudes = librosa.piptrack(
            y=audio, sr=self.sample_rate, fmin=80, fmax=400,
            n_fft=self.n_fft, hop_length=self.hop_length
        )

        pitch_track = np.zeros(pitches.shape[1])
        mag_track = np.zeros(magnitudes.shape[1])

        for i in range(pitches.shape[1]):
            idx = magnitudes[:, i].argmax()
            if magnitudes[idx, i] > 0.1:
                pitch_track[i] = pitches[idx, i]
                mag_track[i] = magnitudes[idx, i]

        pitch_diff = np.diff(pitch_track, prepend=pitch_track[0])

        return np.vstack([pitch_track, mag_track, pitch_diff])

    def _segment_audio(self, features: np.ndarray,
                       max_speakers: int = 5,
                       min_segments: int = 10) -> np.ndarray:
        n_frames = features.shape[1]

        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features.T)

        silhouette_scores = []
        cluster_range = range(2, min(max_speakers + 1, n_frames // min_segments + 1))

        if len(cluster_range) < 2:
            return np.zeros(n_frames, dtype=int)

        best_n_clusters = 2
        best_score = -1

        for n_clusters in cluster_range:
            if n_frames < n_clusters * 2:
                continue

            try:
                gmm = GaussianMixture(
                    n_components=n_clusters,
                    covariance_type='diag',
                    random_state=42,
                    max_iter=100
                )
                labels = gmm.fit_predict(features_scaled)

                if len(np.unique(labels)) == n_clusters:
                    score = self._compute_silhouette(features_scaled, labels)
                    silhouette_scores.append(score)

                    if score > best_score:
                        best_score = score
                        best_n_clusters = n_clusters
            except:
                continue

        if best_score < 0.1:
            best_n_clusters = 2

        gmm = GaussianMixture(
            n_components=best_n_clusters,
            covariance_type='diag',
            random_state=42,
            max_iter=200
        )
        labels = gmm.fit_predict(features_scaled)

        labels = self._smooth_labels(labels, window_size=5)

        return labels

    def _compute_silhouette(self, X: np.ndarray, labels: np.ndarray) -> float:
        unique_labels = np.unique(labels)
        if len(unique_labels) < 2:
            return -1.0

        n_samples = len(X)
        silhouette_scores = []

        for i in range(n_samples):
            same_cluster = labels == labels[i]
            other_clusters = [l for l in unique_labels if l != labels[i]]

            if np.sum(same_cluster) < 2 or not other_clusters:
                continue

            a_i = np.mean(np.linalg.norm(X[i] - X[same_cluster], axis=1))

            b_i_min = np.inf
            for l in other_clusters:
                other_cluster = labels == l
                if np.sum(other_cluster) > 0:
                    b_i = np.mean(np.linalg.norm(X[i] - X[other_cluster], axis=1))
                    b_i_min = min(b_i_min, b_i)

            if b_i_min < np.inf and max(a_i, b_i_min) > 0:
                s_i = (b_i_min - a_i) / max(a_i, b_i_min)
                silhouette_scores.append(s_i)

        return np.mean(silhouette_scores) if silhouette_scores else -1.0

    def _smooth_labels(self, labels: np.ndarray, window_size: int = 5) -> np.ndarray:
        smoothed = labels.copy()
        half_window = window_size // 2

        for i in range(len(labels)):
            start = max(0, i - half_window)
            end = min(len(labels), i + half_window + 1)
            window = labels[start:end]

            counts = np.bincount(window)
            smoothed[i] = np.argmax(counts)

        return smoothed

    def _reconstruct_audio(self, mag: np.ndarray, phase: np.ndarray,
                           mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 1:
            mask = mask[np.newaxis, :]

        if mask.shape[1] != mag.shape[1]:
            mask = np.tile(mask, (1, mag.shape[1] // mask.shape[1] + 1))
            mask = mask[:, :mag.shape[1]]

        if mask.shape[0] != mag.shape[0]:
            mask = np.tile(mask, (mag.shape[0] // mask.shape[0] + 1, 1))
            mask = mask[:mag.shape[0], :]

        masked_mag = mag * mask

        D = masked_mag * np.exp(1j * phase)
        audio = librosa.istft(D, hop_length=self.hop_length, length=None)

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.9

        return audio

    def separate_speakers(self, audio: np.ndarray,
                          max_speakers: int = 5,
                          use_pitch: bool = True) -> Dict[str, Any]:
        features, mag, phase = self._compute_features(audio)
        spectral_features = self._compute_spectral_features(mag)

        all_features = np.concatenate([features, spectral_features], axis=0)

        if use_pitch:
            pitch_features = self._compute_pitch_features(audio)
            all_features = np.concatenate([all_features, pitch_features], axis=0)

        labels = self._segment_audio(all_features, max_speakers=max_speakers)

        n_speakers = len(np.unique(labels))

        separated_audios = []
        speaker_masks = []

        for speaker_id in range(n_speakers):
            speaker_frames = labels == speaker_id

            mask = np.zeros((mag.shape[0], mag.shape[1]))
            for t in range(mag.shape[1]):
                if t < len(speaker_frames) and speaker_frames[t]:
                    mask[:, t] = 1.0
                else:
                    mask[:, t] = 0.01

            from scipy.ndimage import gaussian_filter1d
            mask = gaussian_filter1d(mask, sigma=2, axis=1)

            separated = self._reconstruct_audio(mag, phase, mask)

            if len(separated) < len(audio):
                separated = np.pad(
                    separated,
                    (0, len(audio) - len(separated)),
                    mode='constant'
                )
            elif len(separated) > len(audio):
                separated = separated[:len(audio)]

            separated_audios.append(separated)
            speaker_masks.append(mask)

        speaker_segments = []
        for speaker_id in range(n_speakers):
            speaker_frames = labels == speaker_id
            segments = []
            current_start = None

            for t, is_speaker in enumerate(speaker_frames):
                if is_speaker and current_start is None:
                    current_start = t
                elif not is_speaker and current_start is not None:
                    segments.append({
                        'start_time': current_start * self.hop_length / self.sample_rate,
                        'end_time': t * self.hop_length / self.sample_rate,
                        'duration': (t - current_start) * self.hop_length / self.sample_rate
                    })
                    current_start = None

            if current_start is not None:
                segments.append({
                    'start_time': current_start * self.hop_length / self.sample_rate,
                    'end_time': len(speaker_frames) * self.hop_length / self.sample_rate,
                    'duration': (len(speaker_frames) - current_start) * self.hop_length / self.sample_rate
                })

            speaker_segments.append({
                'speaker_id': speaker_id,
                'segments': segments,
                'total_duration': sum(s['duration'] for s in segments)
            })

        return {
            'n_speakers': int(n_speakers),
            'labels': labels,
            'separated_audios': separated_audios,
            'speaker_masks': speaker_masks,
            'speaker_segments': speaker_segments,
            'features': all_features
        }


class MultiSpeakerIdentifier:
    def __init__(self, sample_rate: int = 16000,
                 model_type: str = 'ecapa', embedding_dim: int = 192,
                 device: str = 'cpu'):
        self.sample_rate = sample_rate
        self.device = device

        self.embedding_extractor = SpeakerEmbeddingExtractor(
            model_type=model_type,
            embedding_dim=embedding_dim,
            sample_rate=sample_rate,
            device=device
        )

        self.separator = SpeakerSeparator(
            sample_rate=sample_rate
        )

        self.registered_speakers: Dict[str, np.ndarray] = {}

    def register_speaker(self, speaker_name: str,
                         audio_paths: List[str]) -> Dict[str, Any]:
        audios = []
        for path in audio_paths:
            audio, _ = utils.load_audio(path, sample_rate=self.sample_rate)
            audio = utils.normalize_audio(audio)
            audio = utils.apply_vad(audio, sample_rate=self.sample_rate)
            audios.append(audio)

        embedding = self.embedding_extractor.enroll_speaker(audios)
        self.registered_speakers[speaker_name] = embedding

        return {
            'speaker_name': speaker_name,
            'embedding_dim': len(embedding),
            'num_samples': len(audios),
            'registered': True
        }

    def identify_speaker(self, audio: np.ndarray) -> Dict[str, Any]:
        embedding = self.embedding_extractor.extract_embedding(audio)

        best_match = None
        best_score = -1.0
        all_scores = {}

        for name, registered_emb in self.registered_speakers.items():
            score = utils.cosine_similarity(embedding, registered_emb)
            all_scores[name] = float(score)
            if score > best_score:
                best_score = score
                best_match = name

        return {
            'identified_speaker': best_match,
            'confidence': float(best_score),
            'all_scores': all_scores,
            'embedding': embedding
        }

    def separate_and_identify(self, audio: np.ndarray,
                              max_speakers: int = 5) -> Dict[str, Any]:
        separation_result = self.separator.separate_speakers(
            audio, max_speakers=max_speakers
        )

        n_speakers = separation_result['n_speakers']
        separated_audios = separation_result['separated_audios']

        identifications = []
        for i, separated in enumerate(separated_audios):
            if np.sum(np.abs(separated)) < 1e-3:
                identifications.append({
                    'speaker_index': i,
                    'identified_speaker': None,
                    'confidence': 0.0,
                    'segments': separation_result['speaker_segments'][i]
                })
                continue

            result = self.identify_speaker(separated)
            result['speaker_index'] = i
            result['segments'] = separation_result['speaker_segments'][i]
            identifications.append(result)

        timeline = []
        for speaker_id, seg_info in enumerate(separation_result['speaker_segments']):
            for seg in seg_info['segments']:
                speaker_ident = identifications[speaker_id]
                timeline.append({
                    'start_time': seg['start_time'],
                    'end_time': seg['end_time'],
                    'duration': seg['duration'],
                    'speaker_index': speaker_id,
                    'identified_speaker': speaker_ident.get('identified_speaker'),
                    'confidence': speaker_ident.get('confidence', 0.0)
                })

        timeline.sort(key=lambda x: x['start_time'])

        identified_speakers = list(set(
            ident['identified_speaker']
            for ident in identifications
            if ident['identified_speaker'] is not None
        ))

        return {
            'n_detected_speakers': int(n_speakers),
            'n_identified_speakers': int(len(identified_speakers)),
            'identified_speakers': identified_speakers,
            'identifications': identifications,
            'timeline': timeline,
            'separation_result': separation_result
        }

    def diarize(self, audio: np.ndarray,
                max_speakers: int = 5) -> Dict[str, Any]:
        result = self.separate_and_identify(audio, max_speakers=max_speakers)

        diarization_report = []
        for entry in result['timeline']:
            speaker = entry['identified_speaker'] or f"Speaker_{entry['speaker_index']}"
            diarization_report.append(
                f"{entry['start_time']:.2f} - {entry['end_time']:.2f}: {speaker}"
            )

        result['diarization_report'] = diarization_report

        return result


class Beamforming:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

    def delay_and_sum(self, audio_signals: List[np.ndarray],
                      doa: float = 0.0) -> np.ndarray:
        if len(audio_signals) < 2:
            return audio_signals[0] if audio_signals else np.array([])

        n_channels = len(audio_signals)
        n_samples = max(len(sig) for sig in audio_signals)

        mic_spacing = 0.1
        sound_speed = 343.0

        output = np.zeros(n_samples)

        for i, sig in enumerate(audio_signals):
            angle_rad = np.deg2rad(doa)
            delay_samples = int(
                i * mic_spacing * np.sin(angle_rad) / sound_speed * self.sample_rate
            )

            if delay_samples > 0:
                delayed = np.pad(sig, (delay_samples, 0), mode='constant')
            elif delay_samples < 0:
                delayed = sig[-delay_samples:]
                delayed = np.pad(delayed, (0, -delay_samples), mode='constant')
            else:
                delayed = sig.copy()

            if len(delayed) > n_samples:
                delayed = delayed[:n_samples]
            elif len(delayed) < n_samples:
                delayed = np.pad(delayed, (0, n_samples - len(delayed)), mode='constant')

            output += delayed

        output /= n_channels

        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 0.9

        return output

    def mvdr(self, audio_signals: List[np.ndarray]) -> np.ndarray:
        if len(audio_signals) < 2:
            return audio_signals[0] if audio_signals else np.array([])

        n_channels = len(audio_signals)
        n_frames = min(
            (len(sig) - self.n_fft) // self.hop_length + 1
            for sig in audio_signals
        )

        spec = np.zeros((self.n_fft // 2 + 1, n_frames, n_channels), dtype=np.complex128)

        for ch, sig in enumerate(audio_signals):
            stft = librosa.stft(sig, n_fft=self.n_fft, hop_length=self.hop_length)
            spec[:, :n_frames, ch] = stft[:, :n_frames]

        output_spec = np.zeros((self.n_fft // 2 + 1, n_frames), dtype=np.complex128)

        for f in range(self.n_fft // 2 + 1):
            R = np.zeros((n_channels, n_channels), dtype=np.complex128)
            for t in range(n_frames):
                x = spec[f, t, :, np.newaxis]
                R += x @ x.conj().T
            R /= n_frames

            R += 1e-6 * np.eye(n_channels)
            R_inv = np.linalg.inv(R)

            a = np.ones((n_channels, 1))
            w = (R_inv @ a) / (a.conj().T @ R_inv @ a)

            output_spec[f, :] = (w.conj().T @ spec[f, :, :].T).squeeze()

        output = librosa.istft(output_spec, hop_length=self.hop_length, length=None)

        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 0.9

        return output
