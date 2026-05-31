import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from collections import defaultdict
from config import KEYBOARD_KEYS


@dataclass
class ErrorAnalysisResult:
    total_samples: int
    correct_samples: int
    accuracy: float
    error_rate: float
    top_k_accuracy: Dict[int, float]
    confusion_matrix: np.ndarray
    per_class_accuracy: Dict[str, float]
    per_class_errors: Dict[str, List[str]]
    average_confidence: float
    average_correct_confidence: float
    average_error_confidence: float
    levenshtein_distance: Optional[float]
    insertion_errors: int
    deletion_errors: int
    substitution_errors: int


@dataclass
class PredictionResult:
    predicted_key: str
    predicted_index: int
    true_key: str
    true_index: int
    confidence: float
    is_correct: bool
    top_k_predictions: List[Tuple[int, str, float]]


class ErrorAnalyzer:
    def __init__(self, num_classes: int = 104):
        self.num_classes = num_classes
        self.predictions: List[PredictionResult] = []
        self.true_text: Optional[str] = None
        self.predicted_text: Optional[str] = None

    def add_prediction(self, predicted_index: int, true_index: int, 
                       confidence: float, top_k_predictions: List[Tuple[int, str, float]]):
        from utils import get_key_name
        
        predicted_key = get_key_name(predicted_index) or f"Unknown_{predicted_index}"
        true_key = get_key_name(true_index) or f"Unknown_{true_index}"
        
        self.predictions.append(PredictionResult(
            predicted_key=predicted_key,
            predicted_index=predicted_index,
            true_key=true_key,
            true_index=true_index,
            confidence=confidence,
            is_correct=(predicted_index == true_index),
            top_k_predictions=top_k_predictions
        ))

    def set_texts(self, true_text: str, predicted_text: str):
        self.true_text = true_text
        self.predicted_text = predicted_text

    def compute_accuracy(self) -> float:
        if not self.predictions:
            return 0.0
        correct = sum(1 for p in self.predictions if p.is_correct)
        return correct / len(self.predictions)

    def compute_top_k_accuracy(self, k: int) -> float:
        if not self.predictions:
            return 0.0
        
        correct = 0
        for p in self.predictions:
            top_k_indices = [idx for idx, _, _ in p.top_k_predictions[:k]]
            if p.true_index in top_k_indices:
                correct += 1
        
        return correct / len(self.predictions)

    def compute_confusion_matrix(self) -> np.ndarray:
        confusion = np.zeros((self.num_classes, self.num_classes), dtype=np.int64)
        
        for p in self.predictions:
            if 0 <= p.true_index < self.num_classes and 0 <= p.predicted_index < self.num_classes:
                confusion[p.true_index, p.predicted_index] += 1
        
        return confusion

    def compute_per_class_metrics(self) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
        from utils import get_key_name
        
        per_class_correct = defaultdict(int)
        per_class_total = defaultdict(int)
        per_class_errors = defaultdict(list)
        
        for p in self.predictions:
            per_class_total[p.true_key] += 1
            if p.is_correct:
                per_class_correct[p.true_key] += 1
            else:
                per_class_errors[p.true_key].append(p.predicted_key)
        
        per_class_accuracy = {}
        for key in per_class_total:
            per_class_accuracy[key] = per_class_correct[key] / per_class_total[key]
        
        return per_class_accuracy, per_class_errors

    def compute_levenshtein_distance(self) -> Tuple[int, int, int, int]:
        if self.true_text is None or self.predicted_text is None:
            return None, 0, 0, 0
        
        s1 = self.true_text
        s2 = self.predicted_text
        
        m = len(s1)
        n = len(s2)
        
        dp = np.zeros((m + 1, n + 1), dtype=np.int32)
        backtrack = np.zeros((m + 1, n + 1, 3), dtype=np.int32)
        
        for i in range(m + 1):
            dp[i, 0] = i
        for j in range(n + 1):
            dp[0, j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                
                substitute = dp[i - 1, j - 1] + cost
                delete = dp[i - 1, j] + 1
                insert = dp[i, j - 1] + 1
                
                min_val = min(substitute, delete, insert)
                dp[i, j] = min_val
                
                if min_val == substitute:
                    backtrack[i, j] = [i - 1, j - 1, cost]
                elif min_val == delete:
                    backtrack[i, j] = [i - 1, j, 2]
                else:
                    backtrack[i, j] = [i, j - 1, 1]
        
        i, j = m, n
        insertions = 0
        deletions = 0
        substitutions = 0
        
        while i > 0 or j > 0:
            prev_i, prev_j, op = backtrack[i, j]
            if op == 1:
                insertions += 1
            elif op == 2:
                deletions += 1
            elif op == 3:
                substitutions += 1
            i, j = prev_i, prev_j
        
        return int(dp[m, n]), insertions, deletions, substitutions

    def compute_confidence_metrics(self) -> Tuple[float, float, float]:
        if not self.predictions:
            return 0.0, 0.0, 0.0
        
        all_confidences = [p.confidence for p in self.predictions]
        correct_confidences = [p.confidence for p in self.predictions if p.is_correct]
        error_confidences = [p.confidence for p in self.predictions if not p.is_correct]
        
        avg_all = np.mean(all_confidences) if all_confidences else 0.0
        avg_correct = np.mean(correct_confidences) if correct_confidences else 0.0
        avg_error = np.mean(error_confidences) if error_confidences else 0.0
        
        return avg_all, avg_correct, avg_error

    def analyze(self) -> ErrorAnalysisResult:
        from utils import get_key_name
        
        total_samples = len(self.predictions)
        correct_samples = sum(1 for p in self.predictions if p.is_correct)
        accuracy = correct_samples / total_samples if total_samples > 0 else 0.0
        error_rate = 1.0 - accuracy
        
        top_k_accuracy = {}
        for k in [1, 3, 5, 10]:
            top_k_accuracy[k] = self.compute_top_k_accuracy(k)
        
        confusion_matrix = self.compute_confusion_matrix()
        
        per_class_accuracy, per_class_errors = self.compute_per_class_metrics()
        
        avg_conf, avg_correct_conf, avg_error_conf = self.compute_confidence_metrics()
        
        levenshtein, insertions, deletions, substitutions = self.compute_levenshtein_distance()
        
        return ErrorAnalysisResult(
            total_samples=total_samples,
            correct_samples=correct_samples,
            accuracy=accuracy,
            error_rate=error_rate,
            top_k_accuracy=top_k_accuracy,
            confusion_matrix=confusion_matrix,
            per_class_accuracy=per_class_accuracy,
            per_class_errors=per_class_errors,
            average_confidence=avg_conf,
            average_correct_confidence=avg_correct_conf,
            average_error_confidence=avg_error_conf,
            levenshtein_distance=levenshtein,
            insertion_errors=insertions,
            deletion_errors=deletions,
            substitution_errors=substitutions
        )

    def print_report(self, result: ErrorAnalysisResult):
        print("=" * 60)
        print("ERROR ANALYSIS REPORT")
        print("=" * 60)
        print(f"Total samples: {result.total_samples}")
        print(f"Correct samples: {result.correct_samples}")
        print(f"Accuracy: {result.accuracy * 100:.2f}%")
        print(f"Error rate: {result.error_rate * 100:.2f}%")
        print()
        
        print("Top-K Accuracy:")
        for k, acc in sorted(result.top_k_accuracy.items()):
            print(f"  Top-{k}: {acc * 100:.2f}%")
        print()
        
        print("Confidence Metrics:")
        print(f"  Average confidence: {result.average_confidence * 100:.2f}%")
        print(f"  Average confidence (correct): {result.average_correct_confidence * 100:.2f}%")
        print(f"  Average confidence (errors): {result.average_error_confidence * 100:.2f}%")
        print()
        
        if result.levenshtein_distance is not None:
            print("Text-level Errors:")
            print(f"  Levenshtein distance: {result.levenshtein_distance}")
            print(f"  Insertions: {result.insertion_errors}")
            print(f"  Deletions: {result.deletion_errors}")
            print(f"  Substitutions: {result.substitution_errors}")
            print()
        
        print("Per-class Accuracy (Top 10 Worst):")
        sorted_acc = sorted(result.per_class_accuracy.items(), key=lambda x: x[1])
        for key, acc in sorted_acc[:10]:
            if acc < 1.0:
                errors = result.per_class_errors.get(key, [])
                error_str = ", ".join(errors[:3]) if errors else "N/A"
                print(f"  {key:10s}: {acc * 100:6.2f}%  Errors: {error_str}")
        print()
        
        print("Confusion Matrix (Subset):")
        cm = result.confusion_matrix
        errors = cm - np.diag(np.diag(cm))
        error_indices = np.unravel_index(np.argsort(errors.flatten())[::-1][:5], errors.shape)
        from utils import get_key_name
        for i, j in zip(*error_indices):
            if errors[i, j] > 0:
                true_key = get_key_name(i) or f"Key_{i}"
                pred_key = get_key_name(j) or f"Key_{j}"
                print(f"  {true_key:10s} -> {pred_key:10s}: {errors[i, j]} times")
        print("=" * 60)

    def save_report(self, result: ErrorAnalysisResult, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("ERROR ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Total samples: {result.total_samples}\n")
            f.write(f"Correct samples: {result.correct_samples}\n")
            f.write(f"Accuracy: {result.accuracy * 100:.2f}%\n")
            f.write(f"Error rate: {result.error_rate * 100:.2f}%\n\n")
            
            f.write("Top-K Accuracy:\n")
            for k, acc in sorted(result.top_k_accuracy.items()):
                f.write(f"  Top-{k}: {acc * 100:.2f}%\n")
            f.write("\n")
            
            f.write("Confidence Metrics:\n")
            f.write(f"  Average confidence: {result.average_confidence * 100:.2f}%\n")
            f.write(f"  Average confidence (correct): {result.average_correct_confidence * 100:.2f}%\n")
            f.write(f"  Average confidence (errors): {result.average_error_confidence * 100:.2f}%\n\n")
            
            if result.levenshtein_distance is not None:
                f.write("Text-level Errors:\n")
                f.write(f"  Levenshtein distance: {result.levenshtein_distance}\n")
                f.write(f"  Insertions: {result.insertion_errors}\n")
                f.write(f"  Deletions: {result.deletion_errors}\n")
                f.write(f"  Substitutions: {result.substitution_errors}\n\n")
            
            f.write("Per-class Accuracy:\n")
            sorted_acc = sorted(result.per_class_accuracy.items(), key=lambda x: x[1])
            for key, acc in sorted_acc:
                errors = result.per_class_errors.get(key, [])
                error_str = ", ".join(errors[:5]) if errors else "N/A"
                f.write(f"  {key:10s}: {acc * 100:6.2f}%  Errors: {error_str}\n")
            
            f.write("\nDetailed Predictions:\n")
            for i, p in enumerate(self.predictions):
                status = "✓" if p.is_correct else "✗"
                f.write(f"  {i:4d}: {status} True={p.true_key:10s} Pred={p.predicted_key:10s} Conf={p.confidence*100:5.1f}%\n")


def calculate_cer(true_text: str, predicted_text: str) -> float:
    analyzer = ErrorAnalyzer()
    analyzer.set_texts(true_text, predicted_text)
    distance, _, _, _ = analyzer.compute_levenshtein_distance()
    if distance is None:
        return 0.0
    return distance / len(true_text) if len(true_text) > 0 else 0.0


def calculate_wer(true_words: List[str], predicted_words: List[str]) -> float:
    analyzer = ErrorAnalyzer()
    analyzer.set_texts(" ".join(true_words), " ".join(predicted_words))
    distance, _, _, _ = analyzer.compute_levenshtein_distance()
    if distance is None:
        return 0.0
    return distance / len(true_words) if len(true_words) > 0 else 0.0
