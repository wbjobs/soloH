from enum import Enum

PAM_SEQUENCES = ["NGG", "NAG", "NGA"]
VALID_BASES = {"A", "T", "C", "G", "N"}
SGRNA_LENGTH = 20
PAM_LENGTH = 3
TOTAL_SEQUENCE_LENGTH = SGRNA_LENGTH + PAM_LENGTH

BASE_TO_INDEX = {"A": 0, "T": 1, "C": 2, "G": 3, "N": 4}
INDEX_TO_BASE = {v: k for k, v in BASE_TO_INDEX.items()}

STRAND_POSITIVE = "+"
STRAND_NEGATIVE = "-"

CHROMOSOMES = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY", "chrM"]


class SortField(str, Enum):
    SCORE = "score"
    MISMATCHES = "mismatches"
    CHROMOSOME = "chromosome"
    POSITION = "position"


class SortOrder(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"
