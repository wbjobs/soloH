import os
from typing import Optional, List, Tuple
from pyfaidx import Fasta, Faidx
from app.constants import CHROMOSOMES, STRAND_POSITIVE, STRAND_NEGATIVE
from app.config import get_settings


class GenomeHandler:
    _instance: Optional["GenomeHandler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        settings = get_settings()
        self.genome_path = settings.GENOME_REFERENCE_PATH
        self.genome_build = settings.GENOME_BUILD
        self._fasta: Optional[Fasta] = None
        self._initialized = True

    def _load_genome(self):
        if self._fasta is None:
            if not os.path.exists(self.genome_path):
                raise FileNotFoundError(
                    f"Genome reference file not found: {self.genome_path}. "
                    f"Please download hg38 reference genome and place it at this path."
                )
            self._fasta = Fasta(self.genome_path)

    def get_sequence(
        self, chromosome: str, start: int, end: int, strand: str = STRAND_POSITIVE
    ) -> str:
        self._load_genome()

        if chromosome not in self._fasta:
            raise ValueError(f"Chromosome {chromosome} not found in reference genome")

        sequence = self._fasta[chromosome][start:end].seq

        if strand == STRAND_NEGATIVE:
            from app.data_processing.sequence_utils import reverse_complement
            sequence = reverse_complement(sequence)

        return sequence.upper()

    def get_chromosome_length(self, chromosome: str) -> int:
        self._load_genome()
        if chromosome not in self._fasta:
            raise ValueError(f"Chromosome {chromosome} not found in reference genome")
        return len(self._fasta[chromosome])

    def get_all_chromosomes(self) -> List[str]:
        return list(CHROMOSOMES)

    def scan_chromosome(
        self,
        chromosome: str,
        sgrna: str,
        pam_sequences: List[str],
        max_mismatches: int = 6,
        max_indel: int = 2,
    ) -> List[Tuple[str, int, int, str, int]]:
        from app.data_processing.sequence_utils import (
            count_mismatches_with_indel,
            reverse_complement,
        )

        self._load_genome()
        results = []

        chr_length = self.get_chromosome_length(chromosome)
        search_length = len(sgrna) + 3
        sgrna_rc = reverse_complement(sgrna)
        pam_rc_variants = [reverse_complement(p) for p in pam_sequences]

        for pos in range(chr_length - search_length):
            for strand in [STRAND_POSITIVE, STRAND_NEGATIVE]:
                try:
                    seq = self.get_sequence(chromosome, pos, pos + search_length, strand)
                except Exception:
                    continue

                if strand == STRAND_POSITIVE:
                    pam = seq[-3:]
                    target_seq = seq[: len(sgrna)]
                    query_sgrna = sgrna
                    pam_patterns = pam_sequences
                else:
                    pam = seq[:3]
                    target_seq = seq[3:]
                    query_sgrna = sgrna_rc
                    pam_patterns = pam_rc_variants

                if not any(
                    all(pb == "N" or sb == pb for pb, sb in zip(pam_pattern, pam))
                    for pam_pattern in pam_patterns
                ):
                    continue

                mismatches, _, _ = count_mismatches_with_indel(
                    query_sgrna, target_seq, max_mismatches, max_indel
                )

                if mismatches <= max_mismatches + max_indel:
                    results.append(
                        (chromosome, pos, pos + search_length, strand, mismatches)
                    )

        return results

    def extract_sequence_context(
        self,
        chromosome: str,
        position: int,
        strand: str,
        upstream: int = 50,
        downstream: int = 50,
    ) -> str:
        start = max(0, position - upstream)
        end = position + 23 + downstream
        return self.get_sequence(chromosome, start, end, strand)

    def build_index(self):
        fai_path = self.genome_path + ".fai"
        if not os.path.exists(fai_path):
            Faidx(self.genome_path)
