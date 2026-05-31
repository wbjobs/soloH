"""Offset-length relationship and checksum field detection."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import struct
from collections import defaultdict


@dataclass
class LengthRelation:
    """Represents a detected length field relationship."""
    length_offset: int
    length_length: int
    target_offset: int
    confidence: float
    matches: int
    total: int
    endianness: str = 'auto'


@dataclass
class ChecksumCandidate:
    """Represents a potential checksum field."""
    offset: int
    length: int
    checksum_type: str
    confidence: float
    matches: int
    total: int
    covered_range: Tuple[int, int] = (0, 0)


class RelationAnalyzer:
    """Analyzes relationships between fields in protocol messages."""

    def __init__(self, endianness: str = 'auto'):
        self.endianness = endianness
        self._crc_tables = {}

    def _get_endian_formats(self, length: int) -> List[Tuple[str, str]]:
        """Get struct formats for different endianness."""
        formats = []
        endians = ['<', '>'] if self.endianness == 'auto' else [self.endianness]

        for endian in endians:
            if length == 1:
                formats.append((f'{endian}B', 'little' if endian == '<' else 'big'))
            elif length == 2:
                formats.append((f'{endian}H', 'little' if endian == '<' else 'big'))
            elif length == 4:
                formats.append((f'{endian}I', 'little' if endian == '<' else 'big'))

        return formats

    def _parse_int(self, data: bytes, offset: int, length: int) -> Optional[Tuple[int, str]]:
        """Parse an integer from bytes at a given offset."""
        if offset + length > len(data):
            return None

        formats = self._get_endian_formats(length)
        for fmt, endian in formats:
            try:
                value = struct.unpack(fmt, data[offset:offset + length])[0]
                return value, endian
            except struct.error:
                continue

        return None

    def detect_length_fields(self, messages: List[bytes],
                             candidate_lengths: Optional[List[int]] = None) -> List[LengthRelation]:
        """Detect fields that specify the length of other parts of the message."""
        if candidate_lengths is None:
            candidate_lengths = [1, 2, 4]

        relations = []
        num_messages = len(messages)
        if num_messages < 2:
            return relations

        max_offset = max(len(m) for m in messages)

        for length_field_len in candidate_lengths:
            for length_offset in range(0, max_offset - length_field_len + 1):
                length_field_end = length_offset + length_field_len

                for target_offset in range(0, max_offset):
                    if target_offset >= length_offset and target_offset < length_field_end:
                        continue

                    if abs(target_offset - length_offset) < length_field_len:
                        continue

                    matches = 0
                    detected_endian = None
                    length_values = []

                    for msg in messages:
                        if length_offset + length_field_len > len(msg):
                            continue
                        if target_offset >= len(msg):
                            continue

                        result = self._parse_int(msg, length_offset, length_field_len)
                        if result is None:
                            continue
                        length_value, endian = result
                        detected_endian = endian
                        length_values.append(length_value)

                        remaining = len(msg) - target_offset
                        header_len = target_offset - length_field_end

                        exact_match = (length_value == remaining)
                        header_match = (length_value == remaining - header_len) if header_len >= 0 else False
                        total_match = (length_value == len(msg))

                        if length_value <= 0:
                            continue

                        if exact_match or header_match or total_match:
                            matches += 1

                    if matches >= 2:
                        confidence = matches / num_messages
                        if confidence >= 0.5:
                            unique_lengths = len(set(length_values))
                            payload_lengths = set()
                            for msg in messages:
                                if target_offset < len(msg):
                                    payload_lengths.add(len(msg) - target_offset)

                            if unique_lengths < 2 and len(payload_lengths) < 2:
                                confidence *= 0.3
                            elif unique_lengths < 2:
                                confidence *= 0.7

                            relations.append(LengthRelation(
                                length_offset=length_offset,
                                length_length=length_field_len,
                                target_offset=target_offset,
                                confidence=confidence,
                                matches=matches,
                                total=num_messages,
                                endianness=detected_endian or 'auto'
                            ))

        seen = set()
        unique_relations = []
        for r in relations:
            key = (r.length_offset, r.length_length, r.target_offset)
            if key not in seen:
                seen.add(key)
                unique_relations.append(r)

        unique_relations.sort(key=lambda r: -r.confidence)
        return unique_relations[:10]

    def _crc32_table(self, polynomial: int = 0xEDB88320) -> List[int]:
        """Generate CRC32 lookup table."""
        if polynomial not in self._crc_tables:
            table = []
            for i in range(256):
                crc = i
                for _ in range(8):
                    if crc & 1:
                        crc = (crc >> 1) ^ polynomial
                    else:
                        crc >>= 1
                table.append(crc)
            self._crc_tables[polynomial] = table
        return self._crc_tables[polynomial]

    def _crc32(self, data: bytes, polynomial: int = 0xEDB88320, init_value: int = 0xFFFFFFFF) -> int:
        """Calculate CRC32 checksum."""
        table = self._crc32_table(polynomial)
        crc = init_value
        for b in data:
            crc = (crc >> 8) ^ table[(crc ^ b) & 0xFF]
        return crc ^ 0xFFFFFFFF

    def _additive_checksum(self, data: bytes, length: int = 2) -> int:
        """Calculate additive checksum (sum of bytes)."""
        total = sum(data)
        if length == 1:
            return total & 0xFF
        elif length == 2:
            return total & 0xFFFF
        elif length == 4:
            return total & 0xFFFFFFFF
        return total

    def _ones_complement_checksum(self, data: bytes) -> int:
        """Calculate 16-bit one's complement checksum (like IP/TCP)."""
        if len(data) % 2 == 1:
            data = data + b'\x00'

        total = 0
        for i in range(0, len(data), 2):
            word = (data[i] << 8) | data[i + 1]
            total += word

        while (total >> 16) > 0:
            total = (total & 0xFFFF) + (total >> 16)

        return (~total) & 0xFFFF

    def detect_checksum_fields(self, messages: List[bytes],
                               candidate_lengths: Optional[List[int]] = None) -> List[ChecksumCandidate]:
        """Detect potential checksum fields."""
        if candidate_lengths is None:
            candidate_lengths = [1, 2, 4]

        candidates = []
        num_messages = len(messages)
        if num_messages < 3:
            return candidates

        max_len = max(len(m) for m in messages)

        checksum_types = [
            ('crc32', lambda d: self._crc32(d), 4),
            ('additive_8', lambda d: self._additive_checksum(d, 1), 1),
            ('additive_16', lambda d: self._additive_checksum(d, 2), 2),
            ('additive_32', lambda d: self._additive_checksum(d, 4), 4),
            ('ones_complement', lambda d: self._ones_complement_checksum(d), 2),
        ]

        for cs_type, cs_func, cs_len in checksum_types:
            if cs_len not in candidate_lengths:
                continue

            for cs_offset in range(0, max_len - cs_len + 1):
                for cover_start in [0, cs_offset + cs_len]:
                    for cover_end in [cs_offset, max_len]:
                        if cover_start >= cover_end:
                            continue

                        matches = 0
                        valid = 0

                        for msg in messages:
                            if cs_offset + cs_len > len(msg):
                                continue
                            if cover_end > len(msg):
                                continue

                            covered = msg[cover_start:cover_end]
                            if cs_offset >= cover_start and cs_offset < cover_end:
                                before = msg[cover_start:cs_offset]
                                after = msg[cs_offset + cs_len:cover_end]
                                covered = before + after

                            if not covered:
                                continue

                            calculated = cs_func(covered)

                            stored = self._parse_int(msg, cs_offset, cs_len)
                            if stored is None:
                                continue
                            stored_value, _ = stored

                            valid += 1
                            if calculated == stored_value:
                                matches += 1

                        if matches >= 2 and valid >= 3:
                            confidence = matches / valid
                            if confidence >= 0.6:
                                candidates.append(ChecksumCandidate(
                                    offset=cs_offset,
                                    length=cs_len,
                                    checksum_type=cs_type,
                                    confidence=confidence,
                                    matches=matches,
                                    total=valid,
                                    covered_range=(cover_start, cover_end)
                                ))

        seen = set()
        unique_candidates = []
        for c in candidates:
            key = (c.offset, c.length, c.checksum_type)
            if key not in seen:
                seen.add(key)
                unique_candidates.append(c)

        unique_candidates.sort(key=lambda c: -c.confidence)
        return unique_candidates[:10]

    def detect_sequence_numbers(self, messages: List[bytes],
                                candidate_lengths: Optional[List[int]] = None) -> List[Dict]:
        """Detect potential sequence number fields."""
        if candidate_lengths is None:
            candidate_lengths = [1, 2, 4]

        results = []
        num_messages = len(messages)
        if num_messages < 4:
            return results

        max_len = max(len(m) for m in messages)

        for length in candidate_lengths:
            for offset in range(0, max_len - length + 1):
                values = []
                for msg in messages:
                    if offset + length <= len(msg):
                        result = self._parse_int(msg, offset, length)
                        if result is not None:
                            values.append(result[0])

                if len(values) < 4:
                    continue

                diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
                positive = sum(1 for d in diffs if d > 0)
                negative = sum(1 for d in diffs if d < 0)

                if len(diffs) == 0:
                    continue

                monotonic_inc = positive / len(diffs)
                monotonic_dec = negative / len(diffs)

                small_diffs = sum(1 for d in diffs if 0 < abs(d) <= 10) / len(diffs)

                if monotonic_inc >= 0.7 and small_diffs >= 0.5:
                    confidence = monotonic_inc * small_diffs
                    results.append({
                        'offset': offset,
                        'length': length,
                        'type': 'sequence_increasing',
                        'confidence': confidence,
                        'values': values[:10]
                    })
                elif monotonic_dec >= 0.7 and small_diffs >= 0.5:
                    confidence = monotonic_dec * small_diffs
                    results.append({
                        'offset': offset,
                        'length': length,
                        'type': 'sequence_decreasing',
                        'confidence': confidence,
                        'values': values[:10]
                    })

        results.sort(key=lambda r: -r['confidence'])
        return results[:5]
