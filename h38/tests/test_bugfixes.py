import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.data_processing.sequence_utils import (
    classify_base_substitution,
    count_mismatch_types,
    reverse_complement,
)
from app.models.model_utils import calculate_offtarget_score
from app.cache.redis_cache import cache_key


class TestBaseSubstitutionClassification:
    def test_transition_purine(self):
        assert classify_base_substitution("A", "G") == "transition"
        assert classify_base_substitution("G", "A") == "transition"

    def test_transition_pyrimidine(self):
        assert classify_base_substitution("C", "T") == "transition"
        assert classify_base_substitution("T", "C") == "transition"

    def test_transversion_purine_to_pyrimidine(self):
        assert classify_base_substitution("A", "C") == "transversion"
        assert classify_base_substitution("A", "T") == "transversion"
        assert classify_base_substitution("G", "C") == "transversion"
        assert classify_base_substitution("G", "T") == "transversion"

    def test_transversion_pyrimidine_to_purine(self):
        assert classify_base_substitution("C", "A") == "transversion"
        assert classify_base_substitution("C", "G") == "transversion"
        assert classify_base_substitution("T", "A") == "transversion"
        assert classify_base_substitution("T", "G") == "transversion"

    def test_same_base(self):
        assert classify_base_substitution("A", "A") == "same"
        assert classify_base_substitution("G", "G") == "same"

    def test_n_base(self):
        assert classify_base_substitution("A", "N") == "same"
        assert classify_base_substitution("N", "G") == "same"

    def test_case_insensitive(self):
        assert classify_base_substitution("a", "g") == "transition"
        assert classify_base_substitution("A", "g") == "transition"
        assert classify_base_substitution("a", "T") == "transversion"


class TestCountMismatchTypes:
    def test_no_mismatches(self):
        sgrna = "ATCGATCGATCGATCGATCG"
        target = "ATCGATCGATCGATCGATCG"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert transitions == 0
        assert transversions == 0
        assert insertions == 0
        assert deletions == 0

    def test_only_transitions(self):
        sgrna = "AGTCAGTCAGTCAGTCAGTC"
        target = "GATCAGTCAGTCAGTCAGTC"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert transitions == 2
        assert transversions == 0

    def test_only_transversions(self):
        sgrna = "AGTCAGTCAGTCAGTCAGTC"
        target = "CTTCAGTCAGTCAGTCAGTC"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert transitions == 0
        assert transversions == 2

    def test_mixed_mismatches(self):
        sgrna = "AGTCAGTCAGTCAGTCAGTC"
        target = "GGTCAGTCTGTCCGTCAGTC"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert transitions == 1
        assert transversions == 2

    def test_insertions(self):
        sgrna = "A-CGATCGATCGATCGATCG"
        target = "ATCGATCGATCGATCGATCG"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert insertions == 1
        assert deletions == 0

    def test_deletions(self):
        sgrna = "ATCGATCGATCGATCGATCG"
        target = "A-CGATCGATCGATCGATCG"
        transitions, transversions, insertions, deletions = count_mismatch_types(
            sgrna, target
        )
        assert insertions == 0
        assert deletions == 1


class TestCalculateOffTargetScore:
    def test_perfect_match(self):
        score = calculate_offtarget_score(
            raw_score=0.85,
            transitions=0,
            transversions=0,
            insertions=0,
            deletions=0,
        )
        assert score == pytest.approx(0.85 * 1.1, 0.01)

    def test_transition_penalty(self):
        score_transition = calculate_offtarget_score(
            raw_score=0.9,
            transitions=1,
            transversions=0,
        )
        score_transversion = calculate_offtarget_score(
            raw_score=0.9,
            transitions=0,
            transversions=1,
        )
        assert score_transition > score_transversion

    def test_indel_penalty(self):
        score_insertion = calculate_offtarget_score(
            raw_score=0.9,
            insertions=1,
        )
        score_deletion = calculate_offtarget_score(
            raw_score=0.9,
            deletions=1,
        )
        assert score_insertion > score_deletion

    def test_score_bounds(self):
        score_low = calculate_offtarget_score(
            raw_score=0.5,
            transitions=10,
            transversions=10,
            insertions=5,
            deletions=5,
        )
        assert score_low >= 0.0
        assert score_low <= 1.0

        score_high = calculate_offtarget_score(
            raw_score=0.99,
            transitions=0,
            transversions=0,
        )
        assert score_high >= 0.0
        assert score_high <= 1.0

    def test_mismatch_bonus(self):
        score_1mm = calculate_offtarget_score(
            raw_score=0.8,
            transitions=1,
            transversions=0,
        )
        score_4mm = calculate_offtarget_score(
            raw_score=0.8,
            transitions=4,
            transversions=0,
        )
        assert score_1mm > score_4mm


class TestCacheKey:
    def test_cache_key_uniqueness(self):
        key1 = cache_key("ATCGATCGATCGATCGATCGGGG")
        key2 = cache_key("ATCGATCGATCGATCGATCGAGGG")
        assert key1 != key2

    def test_cache_key_case_insensitive(self):
        key1 = cache_key("ATCGATCGATCGATCGATCGGGG")
        key2 = cache_key("atcgatcgatcgatcgatcgggg")
        assert key1 == key2

    def test_cache_key_with_params(self):
        key1 = cache_key(
            "ATCGATCGATCGATCGATCGGGG",
            max_mismatches=6,
            max_indel=2,
        )
        key2 = cache_key(
            "ATCGATCGATCGATCGATCGGGG",
            max_mismatches=4,
            max_indel=2,
        )
        assert key1 != key2

    def test_cache_key_with_list_params_order_independent(self):
        key1 = cache_key(
            "ATCGATCGATCGATCGATCGGGG",
            chromosomes=["chr1", "chr2", "chr3"],
        )
        key2 = cache_key(
            "ATCGATCGATCGATCGATCGGGG",
            chromosomes=["chr3", "chr1", "chr2"],
        )
        assert key1 == key2

    def test_cache_key_structure(self):
        key = cache_key("ATCGATCGATCGATCGATCGGGG")
        assert key.startswith("crispr:offtarget:")
        parts = key.split(":")
        assert len(parts) == 4
        assert len(parts[2]) == 32
        assert len(parts[3]) == 16


class TestStrandSpecificity:
    def test_reverse_complement_sgrna(self):
        sgrna = "ATCGATCGATCGATCGATCG"
        rc_sgrna = reverse_complement(sgrna)
        assert rc_sgrna == "CGATCGATCGATCGATCGAT"
        assert reverse_complement(rc_sgrna) == sgrna

    def test_reverse_complement_pam(self):
        pam = "NGG"
        rc_pam = reverse_complement(pam)
        assert rc_pam == "CCN"
