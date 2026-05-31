import itertools
from typing import List, Tuple, Optional, Dict
from app.constants import SGRNA_LENGTH, PAM_LENGTH, VALID_BASES
from app.data_processing.sequence_utils import count_mismatches_with_indel


def generate_candidate_sites(
    sgrna: str,
    max_mismatches: int = 6,
    max_indel: int = 2,
    include_pam: bool = True,
) -> List[str]:
    sgrna_only = sgrna[:SGRNA_LENGTH]
    pam = sgrna[SGRNA_LENGTH:] if include_pam else ""

    candidates = set()
    candidates.add(sgrna_only)

    for num_mismatches in range(1, max_mismatches + 1):
        positions = itertools.combinations(range(SGRNA_LENGTH), num_mismatches)
        for pos_tuple in positions:
            bases_to_replace = [sgrna_only[p] for p in pos_tuple]
            for replacements in itertools.product(
                *[
                    [b for b in VALID_BASES if b != original and b != "N"]
                    for original in bases_to_replace
                ]
            ):
                candidate = list(sgrna_only)
                for i, pos in enumerate(pos_tuple):
                    candidate[pos] = replacements[i]
                candidates.add("".join(candidate))

    if max_indel > 0:
        indel_candidates = set()
        for candidate in candidates:
            for ins_count in range(1, max_indel + 1):
                for ins_pos in range(SGRNA_LENGTH):
                    for ins_base in [b for b in VALID_BASES if b != "N"]:
                        new_cand = (
                            candidate[:ins_pos]
                            + ins_base
                            + candidate[ins_pos : SGRNA_LENGTH - 1]
                        )
                        if len(new_cand) == SGRNA_LENGTH:
                            indel_candidates.add(new_cand)

            for del_count in range(1, max_indel + 1):
                for del_pos in range(SGRNA_LENGTH - del_count):
                    new_cand = (
                        candidate[:del_pos]
                        + candidate[del_pos + del_count :]
                        + "N" * del_count
                    )
                    if len(new_cand) == SGRNA_LENGTH:
                        indel_candidates.add(new_cand)

        candidates.update(indel_candidates)

    if include_pam and pam:
        pam_variants = _generate_pam_variants(pam)
        final_candidates = [
            candidate + pam_var for candidate in candidates for pam_var in pam_variants
        ]
    else:
        final_candidates = list(candidates)

    return final_candidates


def _generate_pam_variants(pam: str) -> List[str]:
    variants = []
    bases = ["A", "T", "C", "G"]

    if len(pam) == 3:
        variants.append(pam)
        for n in bases:
            for pam_end in ["GG", "AG", "GA"]:
                variant = n + pam_end
                if variant != pam:
                    variants.append(variant)

    return list(set(variants))


def search_genome_offtargets(
    sgrna: str,
    genome_sequences: Dict[str, str],
    max_mismatches: int = 6,
    max_indel: int = 2,
) -> List[Tuple[str, int, str, int, str, str]]:
    sgrna_only = sgrna[:SGRNA_LENGTH]
    search_len = SGRNA_LENGTH + PAM_LENGTH

    results = []

    for chrom, seq in genome_sequences.items():
        seq_len = len(seq)
        if seq_len < search_len:
            continue

        for pos in range(seq_len - search_len + 1):
            for strand in ["+", "-"]:
                if strand == "+":
                    target = seq[pos : pos + search_len]
                else:
                    from app.data_processing.sequence_utils import reverse_complement
                    target = reverse_complement(seq[pos : pos + search_len])

                target_sgrna = target[:SGRNA_LENGTH]
                pam = target[SGRNA_LENGTH:]

                if not _is_valid_pam(pam):
                    continue

                mismatches, aligned_sgrna, aligned_target = count_mismatches_with_indel(
                    sgrna_only, target_sgrna, max_mismatches, max_indel
                )

                if mismatches <= max_mismatches + max_indel:
                    results.append(
                        (
                            chrom,
                            pos,
                            strand,
                            mismatches,
                            aligned_sgrna,
                            aligned_target,
                        )
                    )

    return results


def _is_valid_pam(pam: str) -> bool:
    if len(pam) != 3:
        return False
    return pam[1:3] in ["GG", "AG", "GA"] or pam[0] == "N"


def filter_candidates(
    candidates: List[Dict],
    min_score: float = 0.0,
    max_mismatches: Optional[int] = None,
    max_insertions: Optional[int] = None,
    max_deletions: Optional[int] = None,
    chromosomes: Optional[List[str]] = None,
    exclude_pam: bool = False,
) -> List[Dict]:
    filtered = []

    for cand in candidates:
        if cand.get("score", 0) < min_score:
            continue

        if max_mismatches is not None and cand.get("mismatches", 0) > max_mismatches:
            continue

        if max_insertions is not None and cand.get("insertions", 0) > max_insertions:
            continue

        if max_deletions is not None and cand.get("deletions", 0) > max_deletions:
            continue

        if chromosomes is not None and cand.get("chromosome") not in chromosomes:
            continue

        filtered.append(cand)

    return filtered


def prioritize_sites(
    sites: List[Dict],
    weight_mismatches: float = 0.4,
    weight_indel: float = 0.3,
    weight_score: float = 0.3,
) -> List[Dict]:
    for site in sites:
        mismatches = site.get("mismatches", 0)
        insertions = site.get("insertions", 0)
        deletions = site.get("deletions", 0)
        score = site.get("score", 0.0)

        mismatch_score = 1.0 - (mismatches / 10.0)
        indel_score = 1.0 - ((insertions + deletions) / 5.0)
        model_score = score

        priority = (
            weight_mismatches * mismatch_score
            + weight_indel * indel_score
            + weight_score * model_score
        )

        site["priority"] = max(0.0, min(1.0, priority))

    return sorted(sites, key=lambda x: x.get("priority", 0), reverse=True)


def build_offtarget_index(
    sequences: List[str],
    kmer_size: int = 10,
) -> Dict[str, List[Tuple[int, int]]]:
    index = {}

    for seq_idx, sequence in enumerate(sequences):
        for i in range(len(sequence) - kmer_size + 1):
            kmer = sequence[i : i + kmer_size]
            if kmer not in index:
                index[kmer] = []
            index[kmer].append((seq_idx, i))

    return index


def fast_search_with_index(
    sgrna: str,
    index: Dict[str, List[Tuple[int, int]]],
    sequences: List[str],
    max_mismatches: int = 6,
    kmer_size: int = 10,
) -> List[Tuple[int, int, int]]:
    sgrna_only = sgrna[:SGRNA_LENGTH]
    candidate_positions = set()

    for i in range(SGRNA_LENGTH - kmer_size + 1):
        kmer = sgrna_only[i : i + kmer_size]
        if kmer in index:
            for seq_idx, pos in index[kmer]:
                candidate_positions.add((seq_idx, pos - i))

    results = []
    for seq_idx, pos in candidate_positions:
        if pos < 0 or pos + SGRNA_LENGTH > len(sequences[seq_idx]):
            continue

        target = sequences[seq_idx][pos : pos + SGRNA_LENGTH]
        mismatches, _, _ = count_mismatches_with_indel(
            sgrna_only, target, max_mismatches, 0
        )

        if mismatches <= max_mismatches:
            results.append((seq_idx, pos, mismatches))

    return results
