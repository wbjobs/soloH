import os
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, asdict


@dataclass
class TechniqueFeatures:
    vibrato_rate: float
    vibrato_depth: float
    glissando_speed: float
    harmonic_purity: float
    attack_sharpness: float
    sustain_decay: float
    noise_level: float
    spectral_centroid: float


@dataclass
class NoteDifficulty:
    sequence_id: int
    technique: str
    string: str
    hui: str
    difficulty_score: float
    technique_complexity: float
    physical_difficulty: float
    features: TechniqueFeatures
    explanations: List[str]


@dataclass
class ScoreDifficulty:
    overall_score: float
    level: str
    note_difficulties: List[NoteDifficulty]
    category_scores: Dict[str, float]
    recommendations: List[str]
    summary: Dict[str, Any]


class DifficultyEvaluator:
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.technique_difficulty_weights = {
            "sanyin": 1.0,
            "anyin": 2.5,
            "fanyin": 3.0,
            "tiao": 1.2,
            "gou": 1.0,
            "mo": 1.3,
            "ti": 1.1,
            "da": 1.4,
            "zhai": 1.5,
            "tuo": 1.3,
            "bo": 1.6,
            "an": 2.0,
            "fan": 2.8,
            "san": 1.0
        }
        
        self.string_difficulty = {
            "一": 1.0,
            "二": 1.1,
            "三": 1.2,
            "四": 1.3,
            "五": 1.4,
            "六": 1.5,
            "七": 1.6
        }
        
        self.hui_difficulty = {
            "一": 1.8, "二": 1.7, "三": 1.6, "四": 1.3,
            "五": 1.2, "六": 1.1, "七": 1.0, "八": 1.1,
            "九": 1.2, "十": 1.3, "十一": 1.5, "十二": 1.6, "十三": 1.7
        }

    def compute_spectrogram(
        self,
        audio: np.ndarray,
        nperseg: int = 2048,
        noverlap: int = 1024
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        f, t, Sxx = signal.spectrogram(
            audio,
            fs=self.sample_rate,
            nperseg=nperseg,
            noverlap=noverlap,
            window='hann'
        )
        return f, t, Sxx

    def extract_technique_features(
        self,
        audio: np.ndarray,
        technique: str
    ) -> TechniqueFeatures:
        audio = audio.astype(np.float32)
        audio = audio / np.max(np.abs(audio)) if np.max(np.abs(audio)) > 0 else audio
        
        n = len(audio)
        yf = fft(audio)
        xf = fftfreq(n, 1 / self.sample_rate)[:n // 2]
        spectrum = 2.0 / n * np.abs(yf[0:n // 2])
        
        fundamental_idx = np.argmax(spectrum[1:]) + 1
        fundamental_freq = xf[fundamental_idx] if fundamental_idx < len(xf) else 440.0
        
        harmonics = []
        for h in range(1, 10):
            target_freq = fundamental_freq * h
            if target_freq > self.sample_rate / 2:
                break
            idx = np.argmin(np.abs(xf - target_freq))
            harmonics.append(spectrum[idx])
        
        harmonic_purity = harmonics[0] / (np.sum(harmonics) + 1e-10) if len(harmonics) > 0 else 0.0
        
        env = np.abs(signal.hilbert(audio))
        env = env / np.max(env) if np.max(env) > 0 else env
        
        peak_idx = np.argmax(env)
        attack_time = peak_idx / self.sample_rate
        attack_sharpness = 1.0 / (attack_time + 0.01)
        
        decay_mask = np.zeros_like(env)
        decay_mask[peak_idx:] = 1.0
        decay_env = env * decay_mask
        decay_threshold = 0.5 * np.max(decay_env)
        decay_indices = np.where(decay_env > decay_threshold)[0]
        sustain_decay = len(decay_indices) / self.sample_rate if len(decay_indices) > 0 else 0.0
        
        low_freq_mask = (xf > 20) & (xf < fundamental_freq * 0.5)
        high_freq_mask = xf > fundamental_freq * 10
        noise_level = np.mean(spectrum[high_freq_mask]) / (np.max(spectrum) + 1e-10)
        
        weighted_freqs = xf[:n // 2] * spectrum
        spectral_centroid = np.sum(weighted_freqs) / (np.sum(spectrum) + 1e-10)
        
        if technique == "anyin":
            vibrato_range = int(0.5 * self.sample_rate)
            if len(env) > vibrato_range:
                vibrato_section = env[-vibrato_range:]
            else:
                vibrato_section = env
            
            vibrato_section = vibrato_section - np.mean(vibrato_section)
            vibrato_fft = fft(vibrato_section)
            vibrato_freqs = fftfreq(len(vibrato_section), 1 / self.sample_rate)
            vibrato_spectrum = np.abs(vibrato_fft)
            
            low_mask = (vibrato_freqs > 3) & (vibrato_freqs < 8)
            if np.any(low_mask):
                vibrato_idx = np.argmax(vibrato_spectrum[low_mask])
                vibrato_rate = vibrato_freqs[low_mask][vibrato_idx]
                vibrato_depth = np.max(vibrato_spectrum[low_mask]) / (np.max(vibrato_spectrum) + 1e-10)
            else:
                vibrato_rate = 0.0
                vibrato_depth = 0.0
            
            glissando_speed = 0.0
            if len(env) > 2:
                grad = np.gradient(env)
                glissando_speed = np.mean(np.abs(grad)) * self.sample_rate
        else:
            vibrato_rate = 0.0
            vibrato_depth = 0.0
            glissando_speed = 0.0
        
        return TechniqueFeatures(
            vibrato_rate=float(vibrato_rate),
            vibrato_depth=float(vibrato_depth),
            glissando_speed=float(glissando_speed),
            harmonic_purity=float(harmonic_purity),
            attack_sharpness=float(attack_sharpness),
            sustain_decay=float(sustain_decay),
            noise_level=float(noise_level),
            spectral_centroid=float(spectral_centroid)
        )

    def evaluate_note_difficulty(
        self,
        audio: np.ndarray,
        jianzi_info: Dict[str, Any],
        sequence_id: int
    ) -> NoteDifficulty:
        technique = jianzi_info.get('technique', 'sanyin')
        string = jianzi_info.get('string', '四')
        hui = jianzi_info.get('hui', '')
        
        features = self.extract_technique_features(audio, technique)
        
        tech_weight = self.technique_difficulty_weights.get(technique, 1.0)
        string_weight = self.string_difficulty.get(string, 1.0)
        hui_weight = self.hui_difficulty.get(hui.replace('徽', ''), 1.0)
        
        technique_complexity = tech_weight * 2.0
        physical_difficulty = (string_weight * 0.4 + hui_weight * 0.6) * 2.0
        
        feature_score = 0.0
        explanations = []
        
        if technique == "anyin":
            if features.vibrato_rate > 5.0:
                feature_score += 0.5
                explanations.append(f"颤音速率较快 ({features.vibrato_rate:.1f}Hz)")
            if features.vibrato_depth > 0.3:
                feature_score += 0.3
                explanations.append(f"颤音幅度较大 ({features.vibrato_depth:.2f})")
            if features.glissando_speed > 0.1:
                feature_score += 0.4
                explanations.append(f"滑音速度较快 ({features.glissando_speed:.3f})")
        
        if technique == "fanyin":
            if features.harmonic_purity > 0.6:
                feature_score += 0.3
                explanations.append(f"泛音纯度较高 ({features.harmonic_purity:.2f})")
        
        if features.attack_sharpness > 20.0:
            feature_score += 0.2
            explanations.append(f"起音较锐 ({features.attack_sharpness:.1f})")
        
        if features.spectral_centroid > 2000:
            feature_score += 0.2
            explanations.append(f"音色较明亮 (频谱质心: {features.spectral_centroid:.0f}Hz)")
        
        if features.noise_level > 0.1:
            feature_score += 0.2
            explanations.append(f"噪音控制要求高 (噪音水平: {features.noise_level:.2f})")
        
        difficulty_score = (
            technique_complexity * 0.4 +
            physical_difficulty * 0.3 +
            feature_score * 0.3
        )
        
        difficulty_score = min(10.0, max(1.0, difficulty_score))
        
        if technique_complexity > 3.0:
            explanations.append(f"技法复杂度较高 ({technique})")
        
        if string_weight > 1.5:
            explanations.append(f"使用高音弦 ({string}弦)")
        
        if hui_weight > 1.5:
            explanations.append(f"徽位偏难 ({hui})")
        
        return NoteDifficulty(
            sequence_id=sequence_id,
            technique=technique,
            string=string,
            hui=hui,
            difficulty_score=float(difficulty_score),
            technique_complexity=float(technique_complexity),
            physical_difficulty=float(physical_difficulty),
            features=features,
            explanations=explanations
        )

    def evaluate_sequence(
        self,
        audio_segments: List[np.ndarray],
        jianzi_sequence: List[Dict[str, Any]]
    ) -> ScoreDifficulty:
        note_difficulties = []
        
        for i, (audio, jianzi) in enumerate(zip(audio_segments, jianzi_sequence)):
            note_diff = self.evaluate_note_difficulty(audio, jianzi, i)
            note_difficulties.append(note_diff)
        
        avg_score = np.mean([nd.difficulty_score for nd in note_difficulties]) if note_difficulties else 0.0
        max_score = np.max([nd.difficulty_score for nd in note_difficulties]) if note_difficulties else 0.0
        std_score = np.std([nd.difficulty_score for nd in note_difficulties]) if note_difficulties else 0.0
        
        technique_complexity_avg = np.mean([nd.technique_complexity for nd in note_difficulties]) if note_difficulties else 0.0
        physical_difficulty_avg = np.mean([nd.physical_difficulty for nd in note_difficulties]) if note_difficulties else 0.0
        
        techniques = [nd.technique for nd in note_difficulties]
        technique_variety = len(set(techniques)) / len(techniques) if techniques else 0.0
        
        strings = [nd.string for nd in note_difficulties]
        string_changes = sum(1 for i in range(1, len(strings)) if strings[i] != strings[i-1])
        string_change_rate = string_changes / len(strings) if strings else 0.0
        
        tempo_factor = min(2.0, len(jianzi_sequence) / 30.0)
        
        overall_score = (
            avg_score * 0.4 +
            max_score * 0.3 +
            technique_complexity_avg * 0.1 +
            physical_difficulty_avg * 0.1 +
            technique_variety * 1.5 +
            string_change_rate * 1.0 +
            tempo_factor * 0.5
        )
        
        overall_score = min(10.0, max(1.0, overall_score))
        
        if overall_score < 2.5:
            level = "入门级"
        elif overall_score < 4.0:
            level = "初级"
        elif overall_score < 5.5:
            level = "中级"
        elif overall_score < 7.0:
            level = "高级"
        else:
            level = "演奏级"
        
        category_scores = {
            "指法复杂度": min(10.0, technique_complexity_avg),
            "物理难度": min(10.0, physical_difficulty_avg),
            "技巧多样性": min(10.0, technique_variety * 5.0),
            "把位移动": min(10.0, string_change_rate * 10.0),
            "速度要求": min(10.0, tempo_factor * 5.0)
        }
        
        recommendations = []
        if avg_score < 3.0:
            recommendations.append("此曲适合初学者练习，重点掌握基础指法")
        elif avg_score < 5.0:
            recommendations.append("建议加强按音颤音技巧的练习")
        else:
            recommendations.append("此曲难度较高，建议分段落慢练")
        
        if technique_variety > 0.5:
            recommendations.append("包含多种技法转换，注意衔接流畅性")
        
        if string_change_rate > 0.3:
            recommendations.append("弦位变化频繁，注意左手移动的准确性")
        
        if any('fanyin' in nd.technique for nd in note_difficulties):
            recommendations.append("包含泛音技法，注意轻触徽位的准确度")
        
        hard_notes = sorted(note_difficulties, key=lambda x: x.difficulty_score, reverse=True)[:3]
        if hard_notes:
            hard_note_desc = ", ".join([
                f"第{nd.sequence_id+1}音({nd.technique} {nd.string}弦{nd.hui})" 
                for nd in hard_notes
            ])
            recommendations.append(f"重点难点: {hard_note_desc}")
        
        summary = {
            "total_notes": len(note_difficulties),
            "avg_difficulty": float(avg_score),
            "max_difficulty": float(max_score),
            "std_difficulty": float(std_score),
            "technique_variety": float(technique_variety),
            "string_change_rate": float(string_change_rate),
            "techniques_used": list(set(techniques)),
            "strings_used": list(set(strings))
        }
        
        return ScoreDifficulty(
            overall_score=float(overall_score),
            level=level,
            note_difficulties=note_difficulties,
            category_scores=category_scores,
            recommendations=recommendations,
            summary=summary
        )

    def evaluate_from_score(
        self,
        score_id: str,
        temp_dir: Optional[str] = None
    ) -> Optional[ScoreDifficulty]:
        try:
            from services import ScoreSerializer, AudioSynthesizer
            
            if temp_dir is None:
                temp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'temp')
            
            serializer = ScoreSerializer(temp_dir)
            score = serializer.load_score(score_id)
            
            if not score:
                return None
            
            synthesizer = AudioSynthesizer()
            
            audio_segments = []
            for jz in score.jianzi_sequence:
                midi = jz.get('midi', 60)
                technique = jz.get('technique', 'sanyin')
                duration = jz.get('duration', 1.0)
                string_id = jz.get('string', None)
                
                audio = synthesizer.synthesize_note(midi, technique, duration, string_id)
                audio_segments.append(audio)
            
            return self.evaluate_sequence(audio_segments, score.jianzi_sequence)
            
        except Exception as e:
            return None

    def generate_difficulty_report(
        self,
        difficulty: ScoreDifficulty
    ) -> Dict[str, Any]:
        return {
            "overall": {
                "score": difficulty.overall_score,
                "level": difficulty.level,
                "description": self._get_level_description(difficulty.level)
            },
            "categories": difficulty.category_scores,
            "summary": difficulty.summary,
            "recommendations": difficulty.recommendations,
            "note_details": [
                {
                    "sequence_id": nd.sequence_id,
                    "technique": nd.technique,
                    "string": nd.string,
                    "hui": nd.hui,
                    "difficulty_score": nd.difficulty_score,
                    "technique_complexity": nd.technique_complexity,
                    "physical_difficulty": nd.physical_difficulty,
                    "explanations": nd.explanations,
                    "features": asdict(nd.features)
                }
                for nd in difficulty.note_difficulties
            ]
        }

    def _get_level_description(self, level: str) -> str:
        descriptions = {
            "入门级": "适合零基础学习者，主要练习基础散音和简单按音",
            "初级": "适合有1-3个月学习基础，开始接触简单按音和泛音",
            "中级": "适合有半年以上学习基础，需要掌握颤音、滑音等技巧",
            "高级": "适合有1年以上学习基础，技巧丰富，转换频繁",
            "演奏级": "适合专业演奏者，难度高，技巧全面，表现力要求高"
        }
        return descriptions.get(level, "未知级别")

    def visualize_difficulty(
        self,
        difficulty: ScoreDifficulty,
        output_path: str
    ) -> bool:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            
            scores = [nd.difficulty_score for nd in difficulty.note_difficulties]
            seq_ids = [nd.sequence_id for nd in difficulty.note_difficulties]
            axes[0, 0].plot(seq_ids, scores, 'b-', linewidth=2, marker='o')
            axes[0, 0].axhline(y=difficulty.overall_score, color='r', linestyle='--', label=f'平均分: {difficulty.overall_score:.1f}')
            axes[0, 0].set_xlabel('音符序号')
            axes[0, 0].set_ylabel('难度评分')
            axes[0, 0].set_title('各音符难度分布')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            categories = list(difficulty.category_scores.keys())
            values = list(difficulty.category_scores.values())
            axes[0, 1].bar(categories, values, color='steelblue')
            axes[0, 1].set_ylim(0, 10)
            axes[0, 1].set_ylabel('评分')
            axes[0, 1].set_title('各项难度指标')
            axes[0, 1].tick_params(axis='x', rotation=45)
            
            level_colors = {"入门级": "green", "初级": "limegreen", "中级": "gold", "高级": "orange", "演奏级": "red"}
            color = level_colors.get(difficulty.level, "gray")
            axes[1, 0].pie(
                [difficulty.overall_score, 10 - difficulty.overall_score],
                labels=[f'难度 {difficulty.overall_score:.1f}', '剩余'],
                colors=[color, 'lightgray'],
                autopct='%1.1f%%',
                startangle=90
            )
            axes[1, 0].set_title(f'总体难度: {difficulty.level}')
            
            techniques = [nd.technique for nd in difficulty.note_difficulties]
            tech_counts = {}
            for t in techniques:
                tech_counts[t] = tech_counts.get(t, 0) + 1
            axes[1, 1].bar(tech_counts.keys(), tech_counts.values(), color='darkseagreen')
            axes[1, 1].set_ylabel('出现次数')
            axes[1, 1].set_title('技法使用分布')
            axes[1, 1].tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=100, bbox_inches='tight')
            plt.close()
            
            return True
        except Exception:
            return False
