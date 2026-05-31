"""Field type inference for protocol reverse engineering."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import struct
import math
from collections import Counter
from datetime import datetime, timezone
import numpy as np


@dataclass
class TypeCandidate:
    """A candidate type for a field."""
    type_name: str
    confidence: float
    details: Dict = field(default_factory=dict)


@dataclass
class InferredField:
    """A field with inferred type information."""
    offset: int
    length: int
    best_type: str
    confidence: float
    candidates: List[TypeCandidate] = field(default_factory=list)
    sample_values: List[bytes] = field(default_factory=list)
    is_enum: bool = False
    enum_values: Dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'offset': self.offset,
            'length': self.length,
            'best_type': self.best_type,
            'confidence': self.confidence,
            'candidates': [
                {'type': c.type_name, 'confidence': c.confidence, 'details': c.details}
                for c in self.candidates
            ],
            'is_enum': self.is_enum,
            'enum_values': {str(k): v for k, v in self.enum_values.items()},
            'sample_hex': [v.hex() for v in self.sample_values[:10]]
        }


class TypeInferrer:
    """Infers field types from byte values."""

    def __init__(self, endianness: str = 'auto'):
        self.endianness = endianness

    def _try_unpack(self, data: bytes, fmt: str) -> Optional[Tuple]:
        """Try to unpack bytes with a given format."""
        try:
            return struct.unpack(fmt, data)
        except (struct.error, TypeError):
            return None

    def _get_endian_formats(self, length: int) -> List[Tuple[str, str]]:
        """Get appropriate struct formats based on length."""
        formats = []
        endians = ['<', '>'] if self.endianness == 'auto' else [self.endianness]

        for endian in endians:
            if length == 1:
                formats.append((f'{endian}B', 'uint8'))
                formats.append((f'{endian}b', 'int8'))
            elif length == 2:
                formats.append((f'{endian}H', 'uint16'))
                formats.append((f'{endian}h', 'int16'))
            elif length == 4:
                formats.append((f'{endian}I', 'uint32'))
                formats.append((f'{endian}i', 'int32'))
                formats.append((f'{endian}f', 'float32'))
            elif length == 8:
                formats.append((f'{endian}Q', 'uint64'))
                formats.append((f'{endian}q', 'int64'))
                formats.append((f'{endian}d', 'float64'))

        return formats

    def _evaluate_endianness(self, values: List[bytes], length: int) -> Tuple[float, float]:
        """Evaluate likelihood of big-endian vs little-endian.

        Returns: (big_endian_score, little_endian_score) - relative scores, not normalized to 1.0
        """
        if length == 1:
            return (1.0, 1.0)

        big_values = []
        little_values = []

        for v in values:
            if len(v) != length:
                continue
            big_val = int.from_bytes(v, byteorder='big', signed=False)
            little_val = int.from_bytes(v, byteorder='little', signed=False)
            big_values.append(big_val)
            little_values.append(little_val)

        if not big_values:
            return (0.0, 0.0)

        big_score = 0.0
        little_score = 0.0

        big_max = max(big_values)
        little_max = max(little_values)
        big_min = min(big_values)
        little_min = min(little_values)

        if little_max > 1000000 and big_max < 100000:
            big_score += 3.0
            little_score -= 2.0

        if big_max > 0 and little_max / big_max > 100:
            big_score += 2.0
        elif little_max > 0 and big_max / little_max > 100:
            little_score += 2.0

        if big_min >= 0 and little_min < 0:
            big_score += 1.0
        elif little_min >= 0 and big_min < 0:
            little_score += 1.0

        if len(big_values) >= 3:
            big_sorted = sorted(big_values)
            little_sorted = sorted(little_values)

            big_diffs = [big_sorted[i + 1] - big_sorted[i] for i in range(len(big_sorted) - 1)]
            little_diffs = [little_sorted[i + 1] - little_sorted[i] for i in range(len(little_sorted) - 1)]

            if big_diffs:
                big_diff_var = np.var(big_diffs) if len(big_diffs) > 1 else float('inf')
                little_diff_var = np.var(little_diffs) if len(little_diffs) > 1 else float('inf')

                if big_diff_var < little_diff_var * 0.1 and big_diff_var >= 0:
                    big_score += 2.0
                elif little_diff_var < big_diff_var * 0.1 and little_diff_var >= 0:
                    little_score += 2.0
                elif big_diff_var < little_diff_var * 0.5 and big_diff_var >= 0:
                    big_score += 1.0
                elif little_diff_var < big_diff_var * 0.5 and little_diff_var >= 0:
                    little_score += 1.0

            big_negative_diffs = sum(1 for d in big_diffs if d < 0)
            little_negative_diffs = sum(1 for d in little_diffs if d < 0)
            if little_negative_diffs > big_negative_diffs * 2:
                big_score += 1.0
            elif big_negative_diffs > little_negative_diffs * 2:
                little_score += 1.0

            big_monotonic = all(d >= 0 for d in big_diffs) or all(d <= 0 for d in big_diffs)
            little_monotonic = all(d >= 0 for d in little_diffs) or all(d <= 0 for d in little_diffs)
            if big_monotonic and not little_monotonic:
                big_score += 1.5
            elif little_monotonic and not big_monotonic:
                little_score += 1.5

        first_bytes = [v[0] for v in values if len(v) >= 1]
        last_bytes = [v[-1] for v in values if len(v) >= 1]

        first_byte_zero = sum(1 for b in first_bytes if b == 0) / len(first_bytes)
        last_byte_zero = sum(1 for b in last_bytes if b == 0) / len(last_bytes)

        first_byte_ff = sum(1 for b in first_bytes if b == 0xFF) / len(first_bytes)
        last_byte_ff = sum(1 for b in last_bytes if b == 0xFF) / len(last_bytes)

        if last_byte_zero > first_byte_zero * 2 and last_byte_zero > 0.3:
            big_score += 2.0
            little_score -= 1.0

        if first_byte_zero > last_byte_zero * 2 and first_byte_zero > 0.3:
            little_score += 2.0
            big_score -= 1.0

        if first_byte_ff > last_byte_ff * 2 and first_byte_ff > 0.3:
            big_score += 1.0

        if last_byte_ff > first_byte_ff * 2 and last_byte_ff > 0.3:
            little_score += 1.0

        if length >= 2 and len(values) >= 3:
            high_bytes = [v[0] for v in values]
            low_bytes = [v[-1] for v in values]

            high_byte_var = np.var(high_bytes)
            low_byte_var = np.var(low_bytes)

            if low_byte_var > 0 and (high_byte_var == 0 or low_byte_var / max(high_byte_var, 1e-10) > 100):
                big_score += 2.0
            elif high_byte_var > 0 and (low_byte_var == 0 or high_byte_var / max(low_byte_var, 1e-10) > 100):
                little_score += 2.0
            elif low_byte_var > high_byte_var * 10 and low_byte_var > 0:
                big_score += 1.0
            elif high_byte_var > low_byte_var * 10 and high_byte_var > 0:
                little_score += 1.0

        for i in range(len(values) - 1):
            v1 = values[i]
            v2 = values[i + 1]

            big_inc = int.from_bytes(v2, 'big') - int.from_bytes(v1, 'big')
            little_inc = int.from_bytes(v2, 'little') - int.from_bytes(v1, 'little')

            if 0 < big_inc <= 10 and (little_inc <= 0 or little_inc > 1000):
                big_score += 0.5
            elif 0 < little_inc <= 10 and (big_inc <= 0 or big_inc > 1000):
                little_score += 0.5

        return (big_score, little_score)

    def is_integer_candidate(self, values: List[bytes]) -> TypeCandidate:
        """Check if values are likely integers."""
        if not values:
            return TypeCandidate('integer', 0.0)

        length = len(values[0])
        if length not in (1, 2, 4, 8):
            return TypeCandidate('integer', 0.0)

        big_score, little_score = self._evaluate_endianness(values, length)
        prefer_big = big_score > little_score

        formats = self._get_endian_formats(length)

        if self.endianness == 'auto' and length > 1:
            if prefer_big:
                formats = [f for f in formats if f[0].startswith('>')] + [f for f in formats if f[0].startswith('<')]
            else:
                formats = [f for f in formats if f[0].startswith('<')] + [f for f in formats if f[0].startswith('>')]

        best_confidence = 0.0
        best_details: Dict = {}

        for fmt, type_name in formats:
            if 'float' in type_name:
                continue

            unpacked = []
            all_valid = True
            for v in values:
                if len(v) != length:
                    all_valid = False
                    break
                result = self._try_unpack(v, fmt)
                if result is None:
                    all_valid = False
                    break
                unpacked.append(result[0])

            if not all_valid or not unpacked:
                continue

            unique = len(set(unpacked))
            total = len(unpacked)

            if unique == 1:
                confidence = 0.8
            elif unique < total * 0.3:
                confidence = 0.7
            elif unique < total * 0.5:
                confidence = 0.6
            else:
                confidence = 0.4

            if total >= 3 and unique >= 3:
                sorted_vals = sorted(unpacked)
                diffs = [sorted_vals[i + 1] - sorted_vals[i] for i in range(len(sorted_vals) - 1)]
                positive_ratio = sum(1 for d in diffs if d > 0) / len(diffs) if diffs else 0
                negative_ratio = sum(1 for d in diffs if d < 0) / len(diffs) if diffs else 0

                if positive_ratio >= 0.8 or negative_ratio >= 0.8:
                    if len(set(diffs)) <= max(2, len(diffs) * 0.3):
                        confidence += 0.2

                    if positive_ratio >= 0.9 or negative_ratio >= 0.9:
                        confidence += 0.1

            confidence = min(confidence, 0.95)

            min_val = min(unpacked)
            max_val = max(unpacked)

            if 'uint' in type_name and min_val < 0:
                confidence *= 0.5
            if 'int' in type_name and 'uint' not in type_name and min_val >= 0:
                confidence *= 0.9

            zeros = sum(1 for x in unpacked if x == 0)
            if zeros > total * 0.9:
                confidence *= 0.7

            if length > 1 and self.endianness == 'auto':
                is_big_endian = fmt.startswith('>')
                score_diff = big_score - little_score

                if is_big_endian and prefer_big:
                    if score_diff > 5:
                        confidence *= 1.2
                    elif score_diff > 2:
                        confidence *= 1.1
                    else:
                        confidence *= 1.05
                elif not is_big_endian and not prefer_big:
                    if score_diff < -5:
                        confidence *= 1.2
                    elif score_diff < -2:
                        confidence *= 1.1
                    else:
                        confidence *= 1.05
                else:
                    if abs(score_diff) > 5:
                        confidence *= 0.5
                    elif abs(score_diff) > 2:
                        confidence *= 0.7
                    else:
                        confidence *= 0.9

            if max_val > 1e18 and length <= 4:
                confidence *= 0.5

            details = {
                'format': type_name,
                'endianness': 'big' if fmt.startswith('>') else 'little',
                'min': min_val,
                'max': max_val,
                'mean': sum(unpacked) / len(unpacked),
                'unique_count': unique,
                'zero_count': zeros,
                'big_endian_score': big_score,
                'little_endian_score': little_score
            }

            if confidence > best_confidence:
                best_confidence = confidence
                best_details = details

        return TypeCandidate('integer', best_confidence, best_details)

    def is_float_candidate(self, values: List[bytes]) -> TypeCandidate:
        """Check if values are likely floating-point numbers."""
        if not values:
            return TypeCandidate('float', 0.0)

        length = len(values[0])
        if length not in (4, 8):
            return TypeCandidate('float', 0.0)

        formats = [('f', 'float32')] if length == 4 else [('d', 'float64')]
        endians = ['<', '>'] if self.endianness == 'auto' else [self.endianness]

        best_confidence = 0.0
        best_details: Dict = {}

        for endian in endians:
            for fmt, type_name in formats:
                full_fmt = endian + fmt
                unpacked = []
                all_valid = True

                for v in values:
                    if len(v) != length:
                        all_valid = False
                        break
                    result = self._try_unpack(v, full_fmt)
                    if result is None:
                        all_valid = False
                        break
                    val = result[0]
                    if math.isnan(val) or math.isinf(val):
                        all_valid = False
                        break
                    unpacked.append(val)

                if not all_valid or not unpacked:
                    continue

                unique = len(set(unpacked))
                if unique == 1:
                    confidence = 0.7
                else:
                    confidence = 0.5

                has_fractional = any(abs(v - int(v)) > 0.0001 for v in unpacked)
                if has_fractional:
                    confidence += 0.2

                reasonable_range = all(-1e6 < v < 1e6 for v in unpacked)
                if not reasonable_range:
                    confidence *= 0.5

                details = {
                    'format': type_name,
                    'min': min(unpacked),
                    'max': max(unpacked),
                    'mean': sum(unpacked) / len(unpacked),
                    'has_fractional': has_fractional
                }

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_details = details

        return TypeCandidate('float', best_confidence, best_details)

    def is_timestamp_candidate(self, values: List[bytes]) -> TypeCandidate:
        """Check if values are likely timestamps."""
        if not values:
            return TypeCandidate('timestamp', 0.0)

        length = len(values[0])
        if length not in (4, 8):
            return TypeCandidate('timestamp', 0.0)

        formats = self._get_endian_formats(length)
        best_confidence = 0.0
        best_details: Dict = {}

        current_time = datetime.now().timestamp()
        min_reasonable = datetime(2000, 1, 1).timestamp()
        max_reasonable = current_time + 86400 * 365

        for fmt, type_name in formats:
            if 'float' in type_name:
                continue

            unpacked = []
            all_valid = True
            for v in values:
                if len(v) != length:
                    all_valid = False
                    break
                result = self._try_unpack(v, fmt)
                if result is None:
                    all_valid = False
                    break
                unpacked.append(result[0])

            if not all_valid or not unpacked:
                continue

            in_range = sum(1 for ts in unpacked if min_reasonable <= ts <= max_reasonable)
            ratio = in_range / len(unpacked)

            if ratio < 0.5:
                continue

            unique = len(set(unpacked))
            if unique < 2:
                confidence = 0.5 * ratio
            else:
                sorted_vals = sorted(unpacked)
                diffs = [sorted_vals[i + 1] - sorted_vals[i] for i in range(len(sorted_vals) - 1)]
                positive_diffs = sum(1 for d in diffs if d > 0)
                monotonic_ratio = positive_diffs / len(diffs) if diffs else 0

                confidence = ratio * (0.5 + 0.5 * monotonic_ratio)

            try:
                sample_dt = datetime.fromtimestamp(unpacked[0], tz=timezone.utc)
                dt_str = sample_dt.isoformat()
            except (ValueError, OverflowError, OSError):
                dt_str = 'invalid'

            details = {
                'format': type_name,
                'min': min(unpacked),
                'max': max(unpacked),
                'in_range_ratio': ratio,
                'sample_datetime': dt_str
            }

            if confidence > best_confidence:
                best_confidence = confidence
                best_details = details

        return TypeCandidate('timestamp', best_confidence, best_details)

    def is_enum_candidate(self, values: List[bytes]) -> TypeCandidate:
        """Check if values are likely enumerations."""
        if not values:
            return TypeCandidate('enum', 0.0)

        length = len(values[0])
        if length > 4:
            return TypeCandidate('enum', 0.0)

        int_values = []
        for v in values:
            if len(v) == length:
                iv = int.from_bytes(v, byteorder='big', signed=False)
                int_values.append(iv)

        if not int_values:
            return TypeCandidate('enum', 0.0)

        counter = Counter(int_values)
        unique = len(counter)
        total = len(int_values)

        if unique > max(10, total * 0.3):
            return TypeCandidate('enum', 0.0)

        if unique == 1:
            confidence = 0.3
        elif unique <= 5:
            confidence = 0.8
        else:
            confidence = 0.6

        power_of_two = all(v & (v - 1) == 0 and v > 0 for v in counter.keys())
        if power_of_two:
            confidence += 0.1

        details = {
            'unique_count': unique,
            'total_count': total,
            'values': {str(k): v for k, v in counter.most_common()},
            'power_of_two': power_of_two
        }

        return TypeCandidate('enum', min(confidence, 1.0), details)

    def is_ascii_candidate(self, values: List[bytes]) -> TypeCandidate:
        """Check if values are likely ASCII strings."""
        if not values:
            return TypeCandidate('ascii', 0.0)

        printable_count = 0
        total_bytes = 0

        for v in values:
            for b in v:
                total_bytes += 1
                if 32 <= b <= 126 or b in (9, 10, 13):
                    printable_count += 1

        if total_bytes == 0:
            return TypeCandidate('ascii', 0.0)

        ratio = printable_count / total_bytes

        if ratio >= 0.95:
            confidence = 0.9
        elif ratio >= 0.8:
            confidence = 0.6
        elif ratio >= 0.5:
            confidence = 0.3
        else:
            confidence = 0.0

        null_terminated = any(v.endswith(b'\x00') for v in values)
        if null_terminated:
            confidence += 0.1

        details = {
            'printable_ratio': ratio,
            'null_terminated': null_terminated,
            'sample_text': values[0][:50].decode('ascii', errors='replace') if values else ''
        }

        return TypeCandidate('ascii', min(confidence, 1.0), details)

    def infer_field(self, values: List[bytes], offset: int = 0) -> InferredField:
        """Infer the type of a field from its values."""
        if not values:
            return InferredField(offset=offset, length=0, best_type='unknown', confidence=0.0)

        length = len(values[0])

        candidates = [
            self.is_integer_candidate(values),
            self.is_float_candidate(values),
            self.is_timestamp_candidate(values),
            self.is_enum_candidate(values),
            self.is_ascii_candidate(values),
        ]

        candidates.sort(key=lambda c: -c.confidence)

        enum_candidate = next((c for c in candidates if c.type_name == 'enum'), None)
        is_enum = enum_candidate is not None and enum_candidate.confidence >= 0.5

        best = candidates[0]

        return InferredField(
            offset=offset,
            length=length,
            best_type=best.type_name,
            confidence=best.confidence,
            candidates=candidates,
            sample_values=values[:20],
            is_enum=is_enum,
            enum_values=enum_candidate.details.get('values', {}) if enum_candidate else {}
        )

    def infer_fields(self, field_values: Dict[int, List[bytes]]) -> Dict[int, InferredField]:
        """Infer types for multiple fields."""
        results = {}
        for offset, values in field_values.items():
            results[offset] = self.infer_field(values, offset)
        return results
