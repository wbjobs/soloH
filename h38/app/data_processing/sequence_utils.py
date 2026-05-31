import re
from typing import Tuple, List, Optional
from app.constants import (
    VALID_BASES,
    SGRNA_LENGTH,
    PAM_LENGTH,
    TOTAL_SEQUENCE_LENGTH,
    PAM_SEQUENCES,
    STRAND_POSITIVE,
    STRAND_NEGATIVE,
)


def validate_sgrna(sequence: str) -> Tuple[bool, Optional[str]]:
    sequence = sequence.upper().strip()

    if len(sequence) != TOTAL_SEQUENCE_LENGTH:
        return False, f"Sequence length must be {TOTAL_SEQUENCE_LENGTH}nt (20nt sgRNA + 3nt PAM)"

    if not all(base in VALID_BASES for base in sequence):
        return False, f"Sequence contains invalid bases. Valid bases: {''.join(sorted(VALID_BASES))}"

    pam = sequence[-PAM_LENGTH:]
    if not is_valid_pam(pam):
        return False, f"Invalid PAM sequence: {pam}. Expected NGG, NAG, or NGA."

    return True, None


def is_valid_pam(pam: str) -> bool:
    pam = pam.upper()
    for pattern in PAM_SEQUENCES:
        if re.match(pattern.replace("N", "[ATCG]"), pam):
            return True
    return False


def extract_sgrna_and_pam(sequence: str) -> Tuple[str, str]:
    sequence = sequence.upper().strip()
    sgrna = sequence[:SGRNA_LENGTH]
    pam = sequence[SGRNA_LENGTH:]
    return sgrna, pam


def reverse_complement(sequence: str) -> str:
    complement = {"A": "T", "T": "A", "C": "G", "G": "C", "N": "N"}
    return "".join(complement[base] for base in reversed(sequence.upper()))


def calculate_gc_content(sequence: str) -> float:
    sequence = sequence.upper()
    gc_count = sequence.count("G") + sequence.count("C")
    return gc_count / len(sequence) if sequence else 0.0


def count_mismatches(seq1: str, seq2: str, ignore_pam: bool = True) -> int:
    if ignore_pam:
        seq1 = seq1[:SGRNA_LENGTH]
        seq2 = seq2[:SGRNA_LENGTH]

    min_len = min(len(seq1), len(seq2))
    mismatches = sum(1 for i in range(min_len) if seq1[i].upper() != seq2[i].upper())
    mismatches += abs(len(seq1) - len(seq2))
    return mismatches


def count_mismatches_with_indel(
    target: str, query: str, max_mismatches: int = 6, max_indel: int = 2
) -> Tuple[int, str, str]:
    target = target.upper()
    query = query.upper()

    m, n = len(target), len(query)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if target[i - 1] == query[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + 1)

    if dp[m][n] > max_mismatches + max_indel:
        return dp[m][n], target, query

    aligned_target, aligned_query = [], []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and target[i - 1] == query[j - 1]:
            aligned_target.append(target[i - 1])
            aligned_query.append(query[j - 1])
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or dp[i][j - 1] + 1 == dp[i][j]):
            aligned_target.append("-")
            aligned_query.append(query[j - 1])
            j -= 1
        elif i > 0 and (j == 0 or dp[i - 1][j] + 1 == dp[i][j]):
            aligned_target.append(target[i - 1])
            aligned_query.append("-")
            i -= 1
        else:
            aligned_target.append(target[i - 1])
            aligned_query.append(query[j - 1])
            i -= 1
            j -= 1

    return dp[m][n], "".join(reversed(aligned_target)), "".join(reversed(aligned_query))


def generate_pam_variants() -> List[str]:
    variants = []
    bases = ["A", "T", "C", "G"]
    for n in bases:
        for pam in ["GG", "AG", "GA"]:
            variants.append(n + pam)
    return variants


def classify_base_substitution(base1: str, base2: str) -> str:
    purines = {"A", "G"}
    pyrimidines = {"C", "T"}

    b1 = base1.upper()
    b2 = base2.upper()

    if b1 == b2 or b1 == "N" or b2 == "N" or b1 == "-" or b2 == "-":
        return "same"

    if (b1 in purines and b2 in purines) or (b1 in pyrimidines and b2 in pyrimidines):
        return "transition"
    else:
        return "transversion"


def count_mismatch_types(
    aligned_sgrna: str,
    aligned_target: str,
    ignore_pam: bool = True,
) -> Tuple[int, int, int, int]:
    from app.constants import SGRNA_LENGTH

    sgrna = aligned_sgrna
    target = aligned_target

    if ignore_pam and len(sgrna) > SGRNA_LENGTH:
        sgrna = sgrna[:SGRNA_LENGTH]
        target = target[:SGRNA_LENGTH]

    transitions = 0
    transversions = 0
    insertions = 0
    deletions = 0

    for s_base, t_base in zip(sgrna, target):
        if s_base == "-":
            insertions += 1
        elif t_base == "-":
            deletions += 1
        elif s_base.upper() != t_base.upper():
            mtype = classify_base_substitution(s_base, t_base)
            if mtype == "transition":
                transitions += 1
            elif mtype == "transversion":
                transversions += 1

    return transitions, transversions, insertions, deletions


def parse_genomic_coordinate(coord_str: str) -> Tuple[str, int, int, str]:
    pattern = r"(chr[\dXYM]+):(\d+)-(\d+)([+-])?"
    match = re.match(pattern, coord_str)
    if not match:
        raise ValueError(f"Invalid coordinate format: {coord_str}. Expected chrN:start-end[strand]")

    chromosome = match.group(1)
    start = int(match.group(2))
    end = int(match.group(3))
    strand = match.group(4) or STRAND_POSITIVE
    return chromosome, start, end, strand


def format_genomic_coordinate(chromosome: str, start: int, end: int, strand: str) -> str:
    return f"{chromosome}:{start}-{end}{strand}"
