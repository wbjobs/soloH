from typing import Tuple, Optional
from dataclasses import dataclass
import re

AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
AMINO_ACID_ORDER = "ACDEFGHIKLMNPQRSTVWY"
AMINO_ACID_TO_IDX = {aa: idx for idx, aa in enumerate(AMINO_ACID_ORDER)}


@dataclass
class FastaRecord:
    header: str
    sequence: str
    description: str = ""


def parse_fasta(fasta_text: str) -> FastaRecord:
    lines = fasta_text.strip().splitlines()

    if not lines:
        raise ValueError("Empty FASTA input")

    if not lines[0].startswith(">"):
        raise ValueError("Invalid FASTA format: missing header line starting with '>'")

    header_line = lines[0][1:].strip()
    header_parts = header_line.split(maxsplit=1)
    header = header_parts[0]
    description = header_parts[1] if len(header_parts) > 1 else ""

    sequence_lines = []
    for line in lines[1:]:
        line = line.strip()
        if line and not line.startswith(">"):
            sequence_lines.append(line)

    sequence = "".join(sequence_lines).upper()

    if not sequence:
        raise ValueError("Empty sequence in FASTA")

    return FastaRecord(header=header, sequence=sequence, description=description)


def validate_sequence(sequence: str, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
    if len(sequence) > max_length:
        return False, f"Sequence length ({len(sequence)}) exceeds maximum allowed ({max_length})"

    if len(sequence) < 5:
        return False, "Sequence too short (minimum 5 amino acids)"

    invalid_chars = set(sequence) - AMINO_ACIDS
    if invalid_chars:
        return False, f"Invalid amino acid characters: {', '.join(sorted(invalid_chars))}"

    return True, None


def clean_sequence(sequence: str) -> str:
    sequence = sequence.upper()
    sequence = re.sub(r'[^A-Z]', '', sequence)
    sequence = re.sub(r'[BZJUO]', 'X', sequence)
    return sequence
