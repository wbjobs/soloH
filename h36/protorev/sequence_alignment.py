"""Sequence alignment using Needleman-Wunsch algorithm for protocol field detection."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import numpy as np
from collections import Counter


GAP_CHAR = b'\xff'
GAP_SYMBOL = -1


@dataclass
class Field:
    """Represents a detected field in the protocol."""
    name: str
    offset: int
    length: int
    field_type: str
    is_fixed: bool
    values: List[bytes] = field(default_factory=list)
    confidence: float = 0.0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'offset': self.offset,
            'length': self.length,
            'type': self.field_type,
            'is_fixed': self.is_fixed,
            'confidence': self.confidence,
            'description': self.description,
            'unique_values': len(set(self.values)),
            'sample_values': [v.hex() for v in list(set(self.values))[:5]]
        }


@dataclass
class AlignmentResult:
    """Result of sequence alignment."""
    aligned_sequences: List[List[int]]
    consensus: List[int]
    scores: np.ndarray
    fixed_positions: List[int] = field(default_factory=list)
    variable_positions: List[int] = field(default_factory=list)
    conservation_scores: List[float] = field(default_factory=list)


class NeedlemanWunsch:
    """Needleman-Wunsch global alignment algorithm for byte sequences."""

    def __init__(self, match_score: int = 3, mismatch_score: int = -2,
                 gap_open: int = -5, gap_extend: int = -1):
        self.match_score = match_score
        self.mismatch_score = mismatch_score
        self.gap_open = gap_open
        self.gap_extend = gap_extend

    def align_pair(self, seq1: bytes, seq2: bytes) -> Tuple[List[int], List[int], int]:
        """Align two byte sequences using Needleman-Wunsch with affine gap penalty."""
        n, m = len(seq1), len(seq2)
        MINF = -10**9

        M = np.zeros((n + 1, m + 1), dtype=np.int64)
        Ix = np.zeros((n + 1, m + 1), dtype=np.int64)
        Iy = np.zeros((n + 1, m + 1), dtype=np.int64)

        for i in range(n + 1):
            Ix[i][0] = self.gap_open + (i - 1) * self.gap_extend if i > 0 else 0
            M[i][0] = self.gap_open + (i - 1) * self.gap_extend if i > 0 else 0
            Iy[i][0] = MINF

        for j in range(m + 1):
            Iy[0][j] = self.gap_open + (j - 1) * self.gap_extend if j > 0 else 0
            M[0][j] = self.gap_open + (j - 1) * self.gap_extend if j > 0 else 0
            Ix[0][j] = MINF

        Ix[0][0] = MINF
        Iy[0][0] = MINF

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                match_mismatch = self.match_score if seq1[i - 1] == seq2[j - 1] else self.mismatch_score
                M[i][j] = match_mismatch + max(M[i - 1][j - 1], Ix[i - 1][j - 1], Iy[i - 1][j - 1])

                Ix[i][j] = max(
                    self.gap_open + M[i - 1][j],
                    self.gap_extend + Ix[i - 1][j]
                )

                Iy[i][j] = max(
                    self.gap_open + M[i][j - 1],
                    self.gap_extend + Iy[i][j - 1]
                )

        score_matrix = np.maximum(np.maximum(M, Ix), Iy)

        align1: List[int] = []
        align2: List[int] = []
        i, j = n, m

        while i > 0 or j > 0:
            current_max = max(M[i][j], Ix[i][j], Iy[i][j])

            if i > 0 and j > 0 and current_max == M[i][j]:
                align1.append(seq1[i - 1])
                align2.append(seq2[j - 1])
                i -= 1
                j -= 1
            elif i > 0 and current_max == Ix[i][j]:
                align1.append(seq1[i - 1])
                align2.append(GAP_SYMBOL)
                i -= 1
            elif j > 0 and current_max == Iy[i][j]:
                align1.append(GAP_SYMBOL)
                align2.append(seq2[j - 1])
                j -= 1
            elif i > 0:
                align1.append(seq1[i - 1])
                align2.append(GAP_SYMBOL)
                i -= 1
            else:
                align1.append(GAP_SYMBOL)
                align2.append(seq2[j - 1])
                j -= 1

        align1.reverse()
        align2.reverse()

        final_score = int(max(M[n][m], Ix[n][m], Iy[n][m]))
        return align1, align2, final_score

    def calculate_conservation(self, aligned_sequences: List[List[int]]) -> List[float]:
        """Calculate conservation score for each position."""
        if not aligned_sequences:
            return []

        seq_len = len(aligned_sequences[0])
        conservation = []

        for pos in range(seq_len):
            values = [seq[pos] for seq in aligned_sequences if seq[pos] != GAP_SYMBOL]
            if not values:
                conservation.append(0.0)
                continue

            counter = Counter(values)
            most_common = counter.most_common(1)[0][1]
            conservation.append(most_common / len(values))

        return conservation

    def build_consensus(self, aligned_sequences: List[List[int]]) -> List[int]:
        """Build consensus sequence from aligned sequences."""
        if not aligned_sequences:
            return []

        seq_len = len(aligned_sequences[0])
        consensus = []

        for pos in range(seq_len):
            values = [seq[pos] for seq in aligned_sequences if seq[pos] != GAP_SYMBOL]
            if not values:
                consensus.append(GAP_SYMBOL)
            else:
                counter = Counter(values)
                consensus.append(counter.most_common(1)[0][0])

        return consensus

    def progressive_alignment(self, sequences: List[bytes], guide_order: Optional[List[int]] = None) -> AlignmentResult:
        """Perform progressive multiple sequence alignment."""
        if len(sequences) == 0:
            return AlignmentResult(
                aligned_sequences=[],
                consensus=[],
                scores=np.array([])
            )

        if len(sequences) == 1:
            aligned = [[b for b in sequences[0]]]
            conservation = [1.0] * len(sequences[0])
            return AlignmentResult(
                aligned_sequences=aligned,
                consensus=[b for b in sequences[0]],
                scores=np.array([[0]]),
                conservation_scores=conservation,
                fixed_positions=list(range(len(sequences[0]))),
                variable_positions=[]
            )

        if guide_order is None:
            guide_order = list(range(len(sequences)))

        pairwise_scores = np.zeros((len(sequences), len(sequences)))
        for i in range(len(sequences)):
            for j in range(i + 1, len(sequences)):
                _, _, score = self.align_pair(sequences[i], sequences[j])
                pairwise_scores[i][j] = score
                pairwise_scores[j][i] = score

        sorted_indices = np.argsort([pairwise_scores[i].sum() for i in range(len(sequences))])[::-1]
        order = sorted_indices.tolist()

        aligned = [[b for b in sequences[order[0]]]]

        for idx in order[1:]:
            seq = sequences[idx]

            best_aligned = None
            best_score = float('-inf')

            for ref in aligned:
                ref_bytes = bytes([b for b in ref if b != GAP_SYMBOL])
                a1, a2, score = self.align_pair(ref_bytes, seq)

                if score > best_score:
                    best_score = score
                    aligned_ref = a1
                    aligned_seq = a2

            if best_aligned is None:
                best_aligned = aligned[0]

            ref_bytes = bytes([b for b in aligned[0] if b != GAP_SYMBOL])
            aligned_ref, aligned_seq, _ = self.align_pair(ref_bytes, seq)

            pos_map = []
            ref_idx = 0
            for b in aligned[0]:
                if b != GAP_SYMBOL:
                    pos_map.append(ref_idx)
                    ref_idx += 1
                else:
                    pos_map.append(-1)

            new_aligned = []
            seq_idx = 0

            for pos in range(len(aligned[0])):
                ref_pos = pos_map[pos]
                if ref_pos == -1:
                    new_aligned.append(GAP_SYMBOL)
                else:
                    if seq_idx < len(aligned_seq):
                        val = aligned_seq[seq_idx]
                        new_aligned.append(val)
                        seq_idx += 1
                    else:
                        new_aligned.append(GAP_SYMBOL)

            while seq_idx < len(aligned_seq):
                for i in range(len(aligned)):
                    aligned[i].append(GAP_SYMBOL)
                new_aligned.append(aligned_seq[seq_idx])
                seq_idx += 1

            aligned.append(new_aligned)

        final_order = [0] * len(order)
        for i, orig_idx in enumerate(order):
            final_order[orig_idx] = aligned[i]

        conservation = self.calculate_conservation(final_order)
        consensus = self.build_consensus(final_order)

        fixed = [i for i, c in enumerate(conservation) if c >= 0.95]
        variable = [i for i, c in enumerate(conservation) if c < 0.95]

        return AlignmentResult(
            aligned_sequences=final_order,
            consensus=consensus,
            scores=pairwise_scores,
            fixed_positions=fixed,
            variable_positions=variable,
            conservation_scores=conservation
        )

    def extract_fields(self, alignment: AlignmentResult, min_field_len: int = 1) -> List[Field]:
        """Extract fields from alignment result."""
        fields = []
        conservation = alignment.conservation_scores

        current_type = None
        current_start = 0

        for i, score in enumerate(conservation):
            is_fixed = score >= 0.95

            if current_type is None:
                current_type = 'fixed' if is_fixed else 'variable'
                current_start = i
            elif (current_type == 'fixed' and not is_fixed) or (current_type == 'variable' and is_fixed):
                length = i - current_start
                if length >= min_field_len:
                    fields.append(self._create_field(
                        current_start, length, current_type, alignment
                    ))
                current_type = 'fixed' if is_fixed else 'variable'
                current_start = i

        if current_type is not None:
            length = len(conservation) - current_start
            if length >= min_field_len:
                fields.append(self._create_field(
                    current_start, length, current_type, alignment
                ))

        return fields

    def _create_field(self, offset: int, length: int, field_type: str,
                      alignment: AlignmentResult) -> Field:
        """Create a Field object from alignment data."""
        values = []
        for seq in alignment.aligned_sequences:
            field_bytes = bytes([b for b in seq[offset:offset + length] if b != GAP_SYMBOL])
            if field_bytes:
                values.append(field_bytes)

        unique_values = len(set(values))
        total_values = len(values)
        confidence = sum(alignment.conservation_scores[offset:offset + length]) / length

        if field_type == 'fixed':
            name = f"fixed_{offset:04x}"
            description = "Fixed field - value conserved across messages"
        else:
            name = f"variable_{offset:04x}"
            description = f"Variable field - {unique_values}/{total_values} unique values"

        return Field(
            name=name,
            offset=offset,
            length=length,
            field_type=field_type,
            is_fixed=(field_type == 'fixed'),
            values=values,
            confidence=confidence,
            description=description
        )

    def merge_fields(self, fields: List[Field], max_gap: int = 1) -> List[Field]:
        """Merge adjacent fields of the same type."""
        if len(fields) < 2:
            return fields

        merged = [fields[0]]
        for field in fields[1:]:
            last = merged[-1]
            if (last.field_type == field.field_type and
                    field.offset - (last.offset + last.length) <= max_gap):
                new_length = field.offset + field.length - last.offset
                merged[-1] = Field(
                    name=f"{last.field_type}_{last.offset:04x}",
                    offset=last.offset,
                    length=new_length,
                    field_type=last.field_type,
                    is_fixed=last.is_fixed,
                    values=last.values + field.values,
                    confidence=(last.confidence + field.confidence) / 2,
                    description=f"Merged {last.field_type} field"
                )
            else:
                merged.append(field)

        return merged
