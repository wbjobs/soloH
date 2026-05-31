"""Cryptographic protocol detection using entropy and randomness tests."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import math
from collections import Counter
import numpy as np


@dataclass
class RandomnessTestResult:
    """Result of a randomness test."""
    test_name: str
    passed: bool
    score: float
    threshold: float
    details: Dict = field(default_factory=dict)


@dataclass
class CryptoDetectionResult:
    """Result of cryptographic protocol detection."""
    is_encrypted: bool
    confidence: float
    overall_entropy: float
    tests: List[RandomnessTestResult] = field(default_factory=list)
    block_analysis: List[Dict] = field(default_factory=list)
    likely_algorithm: str = "unknown"
    entropy_per_offset: List[float] = field(default_factory=list)
    suspicious_regions: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def test_results(self) -> Dict[str, Dict]:
        """Get test results as a dictionary (compatibility)."""
        return {t.test_name: {'passed': t.passed, 'score': t.score, 'threshold': t.threshold} for t in self.tests}

    @property
    def high_entropy_regions(self) -> List[Tuple[int, int]]:
        """Alias for suspicious_regions (compatibility)."""
        return self.suspicious_regions

    @property
    def avg_entropy(self) -> float:
        """Alias for overall_entropy (compatibility)."""
        return self.overall_entropy

    @property
    def entropy_std(self) -> float:
        """Calculate entropy standard deviation."""
        if not self.entropy_per_offset:
            return 0.0
        return float(np.std(self.entropy_per_offset))

    @property
    def likely_algorithm_details(self) -> Dict:
        """Get likely algorithm details."""
        return {'algorithm': self.likely_algorithm, 'confidence': self.confidence}

    def to_dict(self) -> dict:
        return {
            'is_encrypted': self.is_encrypted,
            'confidence': self.confidence,
            'overall_entropy': self.overall_entropy,
            'likely_algorithm': self.likely_algorithm,
            'tests': [
                {
                    'name': t.test_name,
                    'passed': t.passed,
                    'score': t.score,
                    'threshold': t.threshold,
                    'details': t.details
                }
                for t in self.tests
            ],
            'block_analysis': self.block_analysis,
            'suspicious_regions': [
                {'start': r[0], 'end': r[1], 'description': 'High entropy region'}
                for r in self.suspicious_regions
            ]
        }


class CryptoDetector:
    """Detects encrypted content using statistical randomness tests."""

    def __init__(self, block_size: int = 16, entropy_threshold: float = 7.0):
        self.block_size = block_size
        self.entropy_threshold = entropy_threshold

    def shannon_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy."""
        if not data:
            return 0.0

        length = len(data)
        counts = Counter(data)
        entropy = 0.0

        for count in counts.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def chi_square_test(self, data: bytes) -> RandomnessTestResult:
        """Chi-square test for uniform distribution."""
        if len(data) < 256:
            return RandomnessTestResult(
                'chi_square', False, 0.0, 0.05,
                {'error': 'Insufficient data for chi-square test'}
            )

        expected = len(data) / 256
        counts = Counter(data)
        chi_square = sum(((counts.get(b, 0) - expected) ** 2) / expected for b in range(256))

        critical_value = 293.2478  # df=255, p=0.05

        passed = chi_square < critical_value
        score = max(0.0, min(1.0, 1 - abs(chi_square - 255) / 255))

        return RandomnessTestResult(
            'chi_square', passed, score, 0.05,
            {
                'chi_square': chi_square,
                'critical_value': critical_value,
                'degrees_of_freedom': 255
            }
        )

    def runs_test(self, data: bytes) -> RandomnessTestResult:
        """Runs test for randomness (up/down runs)."""
        if len(data) < 10:
            return RandomnessTestResult(
                'runs_test', False, 0.0, 0.05,
                {'error': 'Insufficient data for runs test'}
            )

        up_runs = 0
        down_runs = 0
        current_run = 0
        prev = data[0]

        for i in range(1, len(data)):
            if data[i] > prev:
                if current_run <= 0:
                    up_runs += 1
                    current_run = 1
                else:
                    current_run += 1
            elif data[i] < prev:
                if current_run >= 0:
                    down_runs += 1
                    current_run = -1
                else:
                    current_run -= 1
            prev = data[i]

        total_runs = up_runs + down_runs
        n = len(data)

        expected_runs = (2 * n - 1) / 3
        variance = (16 * n - 29) / 90
        std_dev = math.sqrt(variance) if variance > 0 else 1

        z_score = abs(total_runs - expected_runs) / std_dev

        passed = z_score < 1.96
        score = max(0.0, min(1.0, 1 - z_score / 3))

        return RandomnessTestResult(
            'runs_test', passed, score, 1.96,
            {
                'total_runs': total_runs,
                'expected_runs': expected_runs,
                'z_score': z_score
            }
        )

    def autocorrelation_test(self, data: bytes, lag: int = 1) -> RandomnessTestResult:
        """Autocorrelation test for randomness."""
        if len(data) < lag * 2:
            return RandomnessTestResult(
                'autocorrelation', False, 0.0, 0.1,
                {'error': 'Insufficient data for autocorrelation test'}
            )

        n = len(data) - lag
        mean = sum(data[:n]) / n
        numerator = sum((data[i] - mean) * (data[i + lag] - mean) for i in range(n))
        denominator = sum((data[i] - mean) ** 2 for i in range(n))

        if denominator == 0:
            autocorr = 0.0
        else:
            autocorr = numerator / denominator

        passed = abs(autocorr) < 0.1
        score = max(0.0, min(1.0, 1 - abs(autocorr)))

        return RandomnessTestResult(
            'autocorrelation', passed, score, 0.1,
            {
                'autocorrelation': autocorr,
                'lag': lag
            }
        )

    def kolmogorov_smirnov_test(self, data: bytes) -> RandomnessTestResult:
        """Kolmogorov-Smirnov test for uniform distribution."""
        if len(data) < 50:
            return RandomnessTestResult(
                'kolmogorov_smirnov', False, 0.0, 0.05,
                {'error': 'Insufficient data for KS test'}
            )

        n = len(data)
        sorted_data = sorted(data)
        empirical_cdf = [(i + 1) / n for i in range(n)]
        theoretical_cdf = [(x + 1) / 256 for x in sorted_data]

        d_statistic = max(abs(e - t) for e, t in zip(empirical_cdf, theoretical_cdf))
        critical_value = 1.36 / math.sqrt(n)

        passed = d_statistic < critical_value
        score = max(0.0, min(1.0, 1 - d_statistic / (critical_value * 2)))

        return RandomnessTestResult(
            'kolmogorov_smirnov', passed, score, critical_value,
            {
                'd_statistic': d_statistic,
                'critical_value': critical_value
            }
        )

    def block_frequency_test(self, data: bytes) -> RandomnessTestResult:
        """Block frequency test (NIST SP 800-22)."""
        if len(data) < self.block_size * 10:
            return RandomnessTestResult(
                'block_frequency', False, 0.0, 0.05,
                {'error': 'Insufficient data for block frequency test'}
            )

        num_blocks = len(data) // self.block_size
        block_proportions = []

        for i in range(num_blocks):
            block = data[i * self.block_size:(i + 1) * self.block_size]
            ones = sum(bin(b).count('1') for b in block)
            proportion = ones / (self.block_size * 8)
            block_proportions.append(proportion)

        chi_square = 4 * self.block_size * sum((p - 0.5) ** 2 for p in block_proportions)
        critical_value = 3.841  # df=1, p=0.05

        passed = chi_square < critical_value
        score = max(0.0, min(1.0, 1 - chi_square / 10))

        return RandomnessTestResult(
            'block_frequency', passed, score, 0.05,
            {
                'chi_square': chi_square,
                'num_blocks': num_blocks,
                'block_size': self.block_size
            }
        )

    def longest_run_test(self, data: bytes) -> RandomnessTestResult:
        """Longest run of ones test."""
        if len(data) < 128:
            return RandomnessTestResult(
                'longest_run', False, 0.0, 0.05,
                {'error': 'Insufficient data for longest run test'}
            )

        bit_string = ''.join(format(b, '08b') for b in data)
        n = len(bit_string)
        block_size = 128 if n >= 10000 else 8
        num_blocks = n // block_size

        longest_runs = []
        for i in range(num_blocks):
            block = bit_string[i * block_size:(i + 1) * block_size]
            max_run = 0
            current_run = 0
            for bit in block:
                if bit == '1':
                    current_run += 1
                    max_run = max(max_run, current_run)
                else:
                    current_run = 0
            longest_runs.append(max_run)

        avg_longest_run = sum(longest_runs) / num_blocks if num_blocks > 0 else 0

        expected = block_size / 2
        passed = 2 <= avg_longest_run <= 8
        score = max(0.0, min(1.0, 1 - abs(avg_longest_run - expected) / expected))

        return RandomnessTestResult(
            'longest_run', passed, score, 0.05,
            {
                'avg_longest_run': avg_longest_run,
                'block_size': block_size,
                'num_blocks': num_blocks
            }
        )

    def analyze_blocks(self, data: bytes) -> List[Dict]:
        """Analyze entropy in sliding blocks."""
        results = []
        for i in range(0, len(data), self.block_size):
            block = data[i:i + self.block_size]
            if len(block) < self.block_size // 2:
                continue

            entropy = self.shannon_entropy(block)
            chi = self.chi_square_test(block)

            results.append({
                'offset': i,
                'length': len(block),
                'entropy': entropy,
                'is_high_entropy': entropy >= self.entropy_threshold,
                'chi_square_passed': chi.passed
            })

        return results

    def find_high_entropy_regions(self, data: bytes, min_length: int = 16) -> List[Tuple[int, int]]:
        """Find contiguous regions of high entropy."""
        block_analysis = self.analyze_blocks(data)

        regions = []
        current_start = None

        for i, block in enumerate(block_analysis):
            if block['is_high_entropy']:
                if current_start is None:
                    current_start = block['offset']
            else:
                if current_start is not None:
                    region_end = block_analysis[i - 1]['offset'] + block_analysis[i - 1]['length']
                    if region_end - current_start >= min_length:
                        regions.append((current_start, region_end))
                    current_start = None

        if current_start is not None:
            region_end = block_analysis[-1]['offset'] + block_analysis[-1]['length']
            if region_end - current_start >= min_length:
                regions.append((current_start, region_end))

        return regions

    def calculate_entropy_per_offset(self, messages: List[bytes]) -> List[float]:
        """Calculate entropy for each byte position across messages."""
        if not messages:
            return []

        max_len = max(len(m) for m in messages)
        entropies = []

        for offset in range(max_len):
            bytes_at_offset = []
            for msg in messages:
                if offset < len(msg):
                    bytes_at_offset.append(msg[offset])

            if bytes_at_offset:
                length = len(bytes_at_offset)
                counts = Counter(bytes_at_offset)
                entropy = 0.0
                for count in counts.values():
                    p = count / length
                    if p > 0:
                        entropy -= p * math.log2(p)
                entropies.append(entropy)
            else:
                entropies.append(0.0)

        return entropies

    def detect(self, messages: List[bytes]) -> CryptoDetectionResult:
        """Detect if messages contain encrypted content."""
        if not messages:
            return CryptoDetectionResult(is_encrypted=False, confidence=0.0, overall_entropy=0.0)

        print(f"[*] Performing cryptographic detection on {len(messages)} messages...")

        combined = b''.join(messages)
        overall_entropy = self.shannon_entropy(combined)

        tests = []
        tests.append(self.chi_square_test(combined))
        tests.append(self.runs_test(combined))
        tests.append(self.autocorrelation_test(combined))
        tests.append(self.kolmogorov_smirnov_test(combined))
        tests.append(self.block_frequency_test(combined))
        tests.append(self.longest_run_test(combined))

        passed_count = sum(1 for t in tests if t.passed)
        avg_score = sum(t.score for t in tests) / max(len(tests), 1)

        block_analysis = self.analyze_blocks(combined)
        high_entropy_blocks = sum(1 for b in block_analysis if b['is_high_entropy'])
        high_entropy_ratio = high_entropy_blocks / max(len(block_analysis), 1)

        entropy_per_offset = self.calculate_entropy_per_offset(messages)
        avg_offset_entropy = sum(entropy_per_offset) / max(len(entropy_per_offset), 1)

        suspicious_regions = self.find_high_entropy_regions(combined)

        entropy_score = 1.0 if overall_entropy >= self.entropy_threshold else overall_entropy / self.entropy_threshold
        test_score = passed_count / max(len(tests), 1)

        confidence = (entropy_score * 0.4 + test_score * 0.3 + high_entropy_ratio * 0.3)

        likely_algorithm = "unknown"
        if confidence > 0.7:
            if high_entropy_ratio > 0.9:
                likely_algorithm = "AES-like"
            elif high_entropy_ratio > 0.7:
                likely_algorithm = "stream_cipher"
            elif len(suspicious_regions) >= 2:
                likely_algorithm = "block_cipher_with_header"

        is_encrypted = confidence > 0.6

        result = CryptoDetectionResult(
            is_encrypted=is_encrypted,
            confidence=confidence,
            overall_entropy=overall_entropy,
            tests=tests,
            block_analysis=block_analysis,
            likely_algorithm=likely_algorithm,
            entropy_per_offset=entropy_per_offset,
            suspicious_regions=suspicious_regions
        )

        status = "LIKELY ENCRYPTED" if is_encrypted else "LIKELY PLAINTEXT"
        print(f"[+] Crypto detection: {status} (confidence: {confidence:.1%})")
        if is_encrypted:
            print(f"    Likely algorithm: {likely_algorithm}")
            print(f"    Overall entropy: {overall_entropy:.2f}/8.0")

        return result

    def _calculate_entropy(self, data: bytes) -> float:
        """Alias for shannon_entropy (compatibility)."""
        return self.shannon_entropy(data)

    def _chi_square_test(self, data: bytes) -> Dict:
        """Alias for chi_square_test returning dict (compatibility)."""
        result = self.chi_square_test(data)
        return {'passed': result.passed, 'score': result.score, 'threshold': result.threshold}

    def _runs_test(self, data: bytes) -> Dict:
        """Alias for runs_test returning dict (compatibility)."""
        result = self.runs_test(data)
        return {'passed': result.passed, 'score': result.score, 'threshold': result.threshold}

    def _autocorrelation_test(self, data: bytes) -> Dict:
        """Alias for autocorrelation_test returning dict (compatibility)."""
        result = self.autocorrelation_test(data)
        return {'passed': result.passed, 'score': result.score, 'threshold': result.threshold}

    def _block_entropy_analysis(self, data: bytes) -> List[Dict]:
        """Alias for analyze_blocks (compatibility)."""
        return self.analyze_blocks(data)
