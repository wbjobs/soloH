import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from collections import defaultdict
from config import LanguageModelConfig, KEY_POSITIONS, KEYBOARD_KEYS
from utils import get_key_index, get_key_name


@dataclass
class NGramModel:
    order: int = 2
    counts: Dict[Tuple[str, ...], Dict[str, float]] = field(default_factory=dict)
    totals: Dict[Tuple[str, ...], float] = field(default_factory=dict)
    vocab: List[str] = field(default_factory=list)
    smoothing: float = 1e-10
    
    def fit(self, sequences: List[List[str]]):
        self.vocab = list(set(key for seq in sequences for key in seq))
        self.vocab.extend([k for k in KEYBOARD_KEYS if k not in self.vocab])
        
        for seq in sequences:
            for n in range(1, self.order + 1):
                for i in range(len(seq) - n + 1):
                    context = tuple(seq[i:i + n - 1]) if n > 1 else tuple()
                    target = seq[i + n - 1]
                    
                    if context not in self.counts:
                        self.counts[context] = defaultdict(float)
                        self.totals[context] = 0.0
                    
                    self.counts[context][target] += 1.0
                    self.totals[context] += 1.0
    
    def probability(self, context: Tuple[str, ...], target: str) -> float:
        if len(context) >= self.order:
            context = context[-(self.order - 1):]
        
        if context not in self.counts:
            return self.smoothing / (len(self.vocab) * self.smoothing)
        
        count = self.counts[context].get(target, 0.0)
        total = self.totals[context]
        
        return (count + self.smoothing) / (total + len(self.vocab) * self.smoothing)
    
    def log_probability(self, context: Tuple[str, ...], target: str) -> float:
        return np.log(self.probability(context, target))


class KeyboardLayoutModel:
    def __init__(self):
        self.key_positions = KEY_POSITIONS
        self.neighbor_cache: Dict[str, List[Tuple[str, float]]] = {}
        self._build_neighbor_cache()
    
    def _build_neighbor_cache(self):
        all_keys = list(self.key_positions.keys())
        
        for key in all_keys:
            neighbors = []
            pos1 = np.array(self.key_positions[key])
            
            for other_key in all_keys:
                if other_key == key:
                    continue
                pos2 = np.array(self.key_positions[other_key])
                distance = np.linalg.norm(pos1 - pos2)
                neighbors.append((other_key, distance))
            
            neighbors.sort(key=lambda x: x[1])
            self.neighbor_cache[key] = neighbors
    
    def get_distance(self, key1: str, key2: str) -> float:
        if key1 not in self.key_positions or key2 not in self.key_positions:
            return 1.0
        
        pos1 = np.array(self.key_positions[key1])
        pos2 = np.array(self.key_positions[key2])
        return np.linalg.norm(pos1 - pos2)
    
    def get_neighbors(self, key: str, max_distance: float = 0.08) -> List[Tuple[str, float]]:
        if key not in self.neighbor_cache:
            return []
        
        return [(k, d) for k, d in self.neighbor_cache[key] if d <= max_distance]
    
    def transition_log_prob(self, prev_key: str, curr_key: str, 
                            weight: float = 0.3) -> float:
        distance = self.get_distance(prev_key, curr_key)
        max_dist = 0.6
        normalized_dist = min(distance / max_dist, 1.0)
        
        prob = np.exp(-normalized_dist * 5.0)
        prob = (1.0 - weight) + weight * prob
        
        return np.log(prob)


@dataclass
class ViterbiState:
    key_index: int
    key_name: str
    log_prob: float
    backpointer: Optional['ViterbiState'] = None
    acoustic_prob: float = 0.0
    language_prob: float = 0.0


class ViterbiDecoder:
    def __init__(self, config: LanguageModelConfig, num_classes: int = 104):
        self.config = config
        self.num_classes = num_classes
        self.keyboard_model = KeyboardLayoutModel()
        self.ngram_model = self._build_default_ngram()
        self.key_index_to_name = self._build_key_mapping()
    
    def _build_key_mapping(self) -> Dict[int, str]:
        mapping = {}
        for idx in range(self.num_classes):
            name = get_key_name(idx)
            if name:
                mapping[idx] = name
        return mapping
    
    def _build_default_ngram(self) -> NGramModel:
        common_texts = [
            "the quick brown fox jumps over the lazy dog",
            "hello world",
            "python programming",
            "keyboard recognition",
            "audio signal processing",
            "machine learning",
            "deep neural network",
            "natural language processing",
            "computer science",
            "software engineering",
            "artificial intelligence",
            "data analysis",
            "information technology",
            "web development",
            "mobile application",
            "cloud computing",
            "cyber security",
            "database management",
            "user interface design",
            "quality assurance",
            "qwerty keyboard",
            "mechanical switch",
            "membrane keyboard",
            "touch typing",
            "typing speed test",
            "password security",
            "encryption algorithm",
            "authentication protocol",
            "virtual private network",
            "firewall protection",
            "malware detection",
            "phishing attack",
            "ransomware threat",
            "zero day exploit",
            "social engineering",
            "biometric authentication",
            "two factor authentication",
            "access control list",
            "intrusion detection system",
            "security operation center"
        ]
        
        sequences = []
        for text in common_texts:
            seq = []
            for c in text:
                if c == ' ':
                    seq.append('Space')
                elif c.lower() in 'abcdefghijklmnopqrstuvwxyz':
                    seq.append(c.lower())
                elif c in '0123456789':
                    seq.append(c)
            if seq:
                sequences.append(seq)
        
        ngram = NGramModel(order=self.config.ngram_order)
        ngram.fit(sequences)
        return ngram
    
    def train_ngram(self, texts: List[str]):
        sequences = []
        for text in texts:
            seq = []
            for c in text.lower():
                if c == ' ':
                    seq.append('Space')
                elif c in 'abcdefghijklmnopqrstuvwxyz':
                    seq.append(c)
                elif c in '0123456789':
                    seq.append(c)
            if seq:
                sequences.append(seq)
        
        if sequences:
            self.ngram_model.fit(sequences)
    
    def decode(self, classifications: List) -> List:
        if not classifications:
            return []
        
        num_timesteps = len(classifications)
        beam_width = self.config.viterbi_beam_width
        
        beams: List[ViterbiState] = []
        
        first_class = classifications[0]
        logits = first_class.logits
        probs = np.exp(logits - np.max(logits))
        probs = probs / np.sum(probs)
        
        top_indices = np.argsort(probs)[::-1][:beam_width]
        
        for idx in top_indices:
            key_name = self.key_index_to_name.get(int(idx), f"Unknown_{idx}")
            acoustic_log_prob = np.log(probs[idx] + 1e-10)
            
            lang_log_prob = 0.0
            
            total_log_prob = (self.config.acoustic_model_weight * acoustic_log_prob +
                            self.config.language_model_weight * lang_log_prob)
            
            beams.append(ViterbiState(
                key_index=int(idx),
                key_name=key_name,
                log_prob=total_log_prob,
                acoustic_prob=float(probs[idx]),
                language_prob=float(np.exp(lang_log_prob))
            ))
        
        all_beams = [beams.copy()]
        
        for t in range(1, num_timesteps):
            current_class = classifications[t]
            logits = current_class.logits
            probs = np.exp(logits - np.max(logits))
            probs = probs / np.sum(probs)
            
            candidates: List[ViterbiState] = []
            
            for prev_state in beams:
                top_indices = np.argsort(probs)[::-1][:beam_width]
                
                for idx in top_indices:
                    key_name = self.key_index_to_name.get(int(idx), f"Unknown_{idx}")
                    acoustic_log_prob = np.log(probs[idx] + 1e-10)
                    
                    lang_log_prob = 0.0
                    
                    if self.config.use_keyboard_layout:
                        kbd_prob = self.keyboard_model.transition_log_prob(
                            prev_state.key_name, key_name,
                            self.config.keyboard_distance_weight
                        )
                        lang_log_prob += kbd_prob
                    
                    if self.config.use_ngram:
                        context = (prev_state.key_name,)
                        ngram_prob = self.ngram_model.log_probability(context, key_name)
                        lang_log_prob += ngram_prob
                    
                    total_log_prob = (self.config.acoustic_model_weight * acoustic_log_prob +
                                    self.config.language_model_weight * lang_log_prob)
                    
                    total_log_prob += prev_state.log_prob
                    
                    candidates.append(ViterbiState(
                        key_index=int(idx),
                        key_name=key_name,
                        log_prob=total_log_prob,
                        backpointer=prev_state,
                        acoustic_prob=float(probs[idx]),
                        language_prob=float(np.exp(lang_log_prob))
                    ))
            
            candidates.sort(key=lambda x: x.log_prob, reverse=True)
            beams = candidates[:beam_width]
            all_beams.append(beams.copy())
        
        if not beams:
            return classifications
        
        best_state = beams[0]
        corrected_states: List[ViterbiState] = []
        
        current = best_state
        while current is not None:
            corrected_states.append(current)
            current = current.backpointer
        
        corrected_states.reverse()
        
        corrected_results = []
        for t, state in enumerate(corrected_states):
            orig_class = classifications[t]
            
            top_k_preds = []
            for j in range(min(5, len(orig_class.top_k_predictions))):
                top_k_preds.append(orig_class.top_k_predictions[j])
            
            found = False
            for j, (idx, name, prob) in enumerate(top_k_preds):
                if idx == state.key_index:
                    top_k_preds[j] = (state.key_index, state.key_name, 
                                    max(prob, state.acoustic_prob))
                    found = True
                    break
            
            if not found:
                top_k_preds.insert(0, (state.key_index, state.key_name, state.acoustic_prob))
                top_k_preds = top_k_preds[:5]
            
            new_logits = orig_class.logits.copy()
            new_logits[state.key_index] = max(new_logits[state.key_index], 
                                              np.log(state.acoustic_prob + 1e-10))
            
            from classifier import ClassificationResult
            corrected_results.append(ClassificationResult(
                key_index=state.key_index,
                key_name=state.key_name,
                confidence=max(state.acoustic_prob, orig_class.confidence),
                logits=new_logits,
                top_k_predictions=top_k_preds
            ))
        
        return corrected_results
    
    def get_keyboard_correction_candidates(self, key_name: str, 
                                           max_distance: float = 0.06) -> List[Tuple[str, float]]:
        return self.keyboard_model.get_neighbors(key_name, max_distance)


def build_language_model_from_config(config: LanguageModelConfig, 
                                     num_classes: int = 104) -> ViterbiDecoder:
    return ViterbiDecoder(config, num_classes)
