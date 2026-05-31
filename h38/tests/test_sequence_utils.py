import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.data_processing.sequence_utils import (
    validate_sgrna,
    extract_sgrna_and_pam,
    reverse_complement,
    calculate_gc_content,
    count_mismatches,
    count_mismatches_with_indel,
    generate_pam_variants,
)


def test_validate_sgrna_valid():
    sgrna = "GACCCCCTCCACCCCGCCTCGGG"
    is_valid, error = validate_sgrna(sgrna)
    assert is_valid
    assert error is None


def test_validate_sgrna_too_short():
    sgrna = "GACCCCCTCCACCCCGCCTC"
    is_valid, error = validate_sgrna(sgrna)
    assert not is_valid
    assert "length" in error.lower()


def test_validate_sgrna_invalid_base():
    sgrna = "GACCCCCTCCACCCCGCCTXGGG"
    is_valid, error = validate_sgrna(sgrna)
    assert not is_valid
    assert "invalid bases" in error.lower()


def test_validate_sgrna_invalid_pam():
    sgrna = "GACCCCCTCCACCCCGCCTCAAA"
    is_valid, error = validate_sgrna(sgrna)
    assert not is_valid
    assert "PAM" in error


def test_extract_sgrna_and_pam():
    sgrna = "GACCCCCTCCACCCCGCCTCGGG"
    sgrna_part, pam_part = extract_sgrna_and_pam(sgrna)
    assert len(sgrna_part) == 20
    assert len(pam_part) == 3
    assert sgrna_part == "GACCCCCTCCACCCCGCCTC"
    assert pam_part == "GGG"


def test_reverse_complement():
    seq = "ATCG"
    rc = reverse_complement(seq)
    assert rc == "CGAT"


def test_reverse_complement_with_n():
    seq = "ATCNG"
    rc = reverse_complement(seq)
    assert rc == "CNGAT"


def test_calculate_gc_content():
    seq = "GGCC"
    gc = calculate_gc_content(seq)
    assert gc == 1.0

    seq = "AATT"
    gc = calculate_gc_content(seq)
    assert gc == 0.0

    seq = "AGCT"
    gc = calculate_gc_content(seq)
    assert gc == 0.5


def test_count_mismatches():
    seq1 = "ATCGATCG"
    seq2 = "ATCGATCG"
    assert count_mismatches(seq1, seq2) == 0

    seq2 = "ATCGATCA"
    assert count_mismatches(seq1, seq2) == 1

    seq2 = "ATCGXXXX"
    assert count_mismatches(seq1, seq2) == 4


def test_count_mismatches_with_indel():
    target = "ATCGATCGAT"
    query = "ATCGATCGAT"
    mismatches, al_target, al_query = count_mismatches_with_indel(target, query)
    assert mismatches == 0
    assert al_target == target
    assert al_query == query


def test_count_mismatches_with_deletion():
    target = "ATCGATCGAT"
    query = "ATCGATGAT"
    mismatches, al_target, al_query = count_mismatches_with_indel(target, query)
    assert mismatches == 1


def test_count_mismatches_with_insertion():
    target = "ATCGATCGAT"
    query = "ATCGATXCGAT"
    mismatches, al_target, al_query = count_mismatches_with_indel(target, query)
    assert mismatches == 1


def test_generate_pam_variants():
    variants = generate_pam_variants()
    assert len(variants) == 12
    assert all(len(v) == 3 for v in variants)
    assert "NGG" not in variants
    assert "AGG" in variants
    assert "TGG" in variants
    assert "GGG" in variants
    assert "CGG" in variants
