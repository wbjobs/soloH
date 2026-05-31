import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.epigenomics.chromatin_accessibility import (
    ATACPeak,
    ChromatinAccessibility,
    calculate_accessibility_score,
    correct_offtarget_score,
)
from app.epigenomics.editing_efficiency import (
    EditingEfficiencyPredictor,
    calculate_sequence_features,
    calculate_melting_temperature,
    calculate_folding_energy,
    calculate_hairpin_score,
    predict_indel_frequency,
)
from app.epigenomics.repair_pathway import (
    RepairPathwayPredictor,
    RepairPathwayResult,
    calculate_microhomology_score,
    predict_repair_pathways,
)


class TestChromatinAccessibility:
    def test_atac_peak_dataclass(self):
        peak = ATACPeak(
            chromosome="chr1",
            start=1000,
            end=2000,
            name="peak_1",
            score=100,
            signal_value=50.0,
        )
        assert peak.chromosome == "chr1"
        assert peak.start == 1000
        assert peak.end == 2000
        assert peak.signal_value == 50.0

    def test_calculate_accessibility_score_in_peak(self):
        score = calculate_accessibility_score(
            accessibility=0.8,
            site_in_peak=True,
            distance_to_peak=0,
        )
        assert 0.5 <= score <= 1.0

    def test_calculate_accessibility_score_low_accessibility(self):
        score = calculate_accessibility_score(accessibility=0.0)
        assert score == 0.1

    def test_calculate_accessibility_score_distance_penalty(self):
        score_close = calculate_accessibility_score(
            accessibility=0.8,
            site_in_peak=False,
            distance_to_peak=100,
        )
        score_far = calculate_accessibility_score(
            accessibility=0.8,
            site_in_peak=False,
            distance_to_peak=4000,
        )
        assert score_close > score_far

    def test_correct_offtarget_score(self):
        corrected = correct_offtarget_score(
            original_score=0.8,
            accessibility_score=0.8,
            weight=0.3,
        )
        assert 0.0 <= corrected <= 1.0
        assert corrected <= 0.8 * 1.0

    def test_correct_offtarget_score_low_accessibility(self):
        corrected_high = correct_offtarget_score(
            original_score=0.8,
            accessibility_score=0.9,
            weight=0.3,
        )
        corrected_low = correct_offtarget_score(
            original_score=0.8,
            accessibility_score=0.1,
            weight=0.3,
        )
        assert corrected_high > corrected_low

    def test_correct_offtarget_score_bounds(self):
        corrected = correct_offtarget_score(
            original_score=1.0,
            accessibility_score=1.0,
            weight=1.0,
        )
        assert corrected <= 1.0

        corrected = correct_offtarget_score(
            original_score=0.0,
            accessibility_score=0.0,
            weight=1.0,
        )
        assert corrected >= 0.0


class TestEditingEfficiency:
    def test_calculate_melting_temperature_short(self):
        tm = calculate_melting_temperature("ATCGATCG")
        assert tm > 0

    def test_calculate_melting_temperature_long(self):
        seq = "ATCGATCGATCGATCGATCG"
        tm = calculate_melting_temperature(seq)
        assert tm > 50

    def test_calculate_folding_energy(self):
        energy = calculate_folding_energy("GCGCGCGC")
        assert energy < 0

    def test_calculate_hairpin_score(self):
        seq_with_hairpin = "ATCGATCGATCGATCG"
        score = calculate_hairpin_score(seq_with_hairpin)
        assert 0.0 <= score <= 1.0

    def test_calculate_sequence_features(self):
        sgrna = "GACCCCCTCCACCCCGCCTCGGG"
        target = "GACCCCCTCCACCCCGCCTCGGG"
        features = calculate_sequence_features(sgrna, target)
        assert 0.0 <= features.gc_content <= 1.0
        assert features.pam_strength > 0
        assert features.melting_temperature > 0

    def test_editing_efficiency_predictor(self):
        predictor = EditingEfficiencyPredictor()
        sgrna = "GACCCCCTCCACCCCGCCTCGGG"
        target = "GACCCCCTCCACCCCGCCTCGGG"

        efficiency, features = predictor.predict(sgrna, target)
        assert 0.0 <= efficiency <= 1.0
        assert features.gc_content > 0

    def test_predict_indel_frequency(self):
        sgrna = "GACCCCCTCCACCCCGCCTCGGG"
        target = "GACCCCCTCCACCCCGCCTCGGG"
        result = predict_indel_frequency(sgrna, target, mismatches=0)

        assert abs(result["indel_1bp"] + result["indel_small_2_10bp"] +
                   result["indel_large_gt10bp"] + result["no_edit"] - 1.0) < 0.01
        assert result["total_indel_frequency"] == pytest.approx(
            result["indel_1bp"] + result["indel_small_2_10bp"] + result["indel_large_gt10bp"], 0.01
        )

    def test_predict_indel_frequency_with_mismatches(self):
        sgrna = "GACCCCCTCCACCCCGCCTCGGG"
        target = "GACCCCCTCCACCCCGCCTAGGG"
        result_with_mm = predict_indel_frequency(sgrna, target, mismatches=1)
        result_no_mm = predict_indel_frequency(sgrna, sgrna, mismatches=0)

        assert result_with_mm["total_indel_frequency"] < result_no_mm["total_indel_frequency"]

    def test_mismatch_position_effect(self):
        predictor = EditingEfficiencyPredictor()
        sgrna = "ATCGATCGATCGATCGATCGGGG"

        from app.offtarget_search.offtarget_finder import MismatchDetail

        mm_seed = [MismatchDetail(position=5, sgrna_base="A", target_base="G", mismatch_type="mismatch")]
        mm_distal = [MismatchDetail(position=18, sgrna_base="A", target_base="G", mismatch_type="mismatch")]

        eff_seed, _ = predictor.predict(sgrna, sgrna, mismatches=1, mismatches_details=mm_seed)
        eff_distal, _ = predictor.predict(sgrna, sgrna, mismatches=1, mismatches_details=mm_distal)

        assert eff_seed < eff_distal


class TestRepairPathway:
    def test_repair_pathway_result(self):
        result = RepairPathwayResult(
            nhej_ratio=0.7,
            hdr_ratio=0.1,
            alt_nhej_ratio=0.15,
            ssa_ratio=0.03,
            mmej_ratio=0.02,
            microhomology_score=0.2,
            dsb_position=17,
            cell_type_effect=1.0,
            confidence=0.8,
        )
        assert abs(result.nhej_ratio + result.hdr_ratio + result.alt_nhej_ratio +
                   result.ssa_ratio + result.mmej_ratio - 1.0) < 0.01

    def test_calculate_microhomology_score(self):
        seq = "ATCGATCGATCGATCGATCG"
        score = calculate_microhomology_score(seq, cut_site=10)
        assert 0.0 <= score <= 1.0

    def test_calculate_microhomology_score_no_mh(self):
        seq = "ATCGATCGATCGATCGATCG"
        score = calculate_microhomology_score(seq, cut_site=2)
        assert score >= 0.0

    def test_predict_repair_pathways_default(self):
        seq = "GACCCCCTCCACCCCGCCTCGGG"
        result = predict_repair_pathways(seq, cut_site=17)

        assert abs(result.nhej_ratio + result.hdr_ratio + result.alt_nhej_ratio +
                   result.ssa_ratio + result.mmej_ratio - 1.0) < 0.01
        assert result.nhej_ratio > result.hdr_ratio
        assert 0.5 <= result.confidence <= 1.0

    def test_predict_repair_pathways_with_hdr_template(self):
        seq = "GACCCCCTCCACCCCGCCTCGGG"

        result_no_template = predict_repair_pathways(
            seq, cut_site=17, has_hdr_template=False
        )
        result_with_template = predict_repair_pathways(
            seq, cut_site=17, has_hdr_template=True
        )

        assert result_with_template.hdr_ratio > result_no_template.hdr_ratio

    def test_predict_repair_pathways_cell_type_effect(self):
        seq = "GACCCCCTCCACCCCGCCTCGGG"

        result_default = predict_repair_pathways(seq, cut_site=17, cell_type="default")
        result_ipsc = predict_repair_pathways(seq, cut_site=17, cell_type="iPSC")

        assert result_ipsc.hdr_ratio > result_default.hdr_ratio
        assert result_ipsc.nhej_ratio < result_default.nhej_ratio

    def test_predict_repair_pathways_cell_cycle_effect(self):
        seq = "GACCCCCTCCACCCCGCCTCGGG"

        result_g1 = predict_repair_pathways(
            seq, cut_site=17, has_hdr_template=True, cell_cycle_phase="G1"
        )
        result_sg2 = predict_repair_pathways(
            seq, cut_site=17, has_hdr_template=True, cell_cycle_phase="S/G2"
        )

        assert result_sg2.hdr_ratio > result_g1.hdr_ratio

    def test_mmej_with_microhomology(self):
        predictor = RepairPathwayPredictor()

        seq_no_mh = "ATCGATCGATCGATCGATCG"
        result_no_mh = predictor.predict(seq_no_mh, cut_site=10)

        seq_with_mh = "ATCGATCGATCGATCGATCG"
        result_with_mh = predictor.predict(seq_with_mh, cut_site=10)

        assert result_with_mh.mmej_ratio >= result_no_mh.mmej_ratio * 0.5

    def test_get_repair_products(self):
        predictor = RepairPathwayPredictor()
        result = RepairPathwayResult(
            nhej_ratio=0.7,
            hdr_ratio=0.1,
            alt_nhej_ratio=0.15,
            ssa_ratio=0.03,
            mmej_ratio=0.02,
            microhomology_score=0.2,
            dsb_position=17,
            cell_type_effect=1.0,
            confidence=0.8,
        )
        products = predictor.get_repair_products(result, total_events=1000)

        assert products["nhej_events"] == 700
        assert products["hdr_events"] == 100
        assert sum(products.values()) == 1000

    def test_suggest_optimization_low_hdr(self):
        predictor = RepairPathwayPredictor()
        result = RepairPathwayResult(
            nhej_ratio=0.8,
            hdr_ratio=0.05,
            alt_nhej_ratio=0.1,
            ssa_ratio=0.03,
            mmej_ratio=0.02,
            microhomology_score=0.1,
            dsb_position=17,
            cell_type_effect=1.0,
            confidence=0.8,
        )
        suggestions = predictor.suggest_optimization(result, target_hdr_ratio=0.3)

        assert "hdr_enhancement" in suggestions

    def test_suggest_optimization_high_hdr(self):
        predictor = RepairPathwayPredictor()
        result = RepairPathwayResult(
            nhej_ratio=0.5,
            hdr_ratio=0.35,
            alt_nhej_ratio=0.1,
            ssa_ratio=0.03,
            mmej_ratio=0.02,
            microhomology_score=0.1,
            dsb_position=17,
            cell_type_effect=1.0,
            confidence=0.8,
        )
        suggestions = predictor.suggest_optimization(result, target_hdr_ratio=0.3)

        assert "optimization_status" in suggestions
