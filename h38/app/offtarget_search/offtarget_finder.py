from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum
from app.constants import SGRNA_LENGTH


class OffTargetType(str, Enum):
    EXACT = "exact"
    MISMATCH = "mismatch"
    INSERTION = "insertion"
    DELETION = "deletion"
    MIXED = "mixed"


@dataclass
class MismatchDetail:
    position: int
    sgrna_base: str
    target_base: str
    mismatch_type: str


@dataclass
class OffTargetSite:
    sgrna: str
    target_sequence: str
    chromosome: str
    start: int
    end: int
    strand: str
    mismatches: int
    insertions: int = 0
    deletions: int = 0
    score: float = 0.0
    raw_score: float = 0.0
    mismatch_details: List[MismatchDetail] = field(default_factory=list)
    aligned_sgrna: Optional[str] = None
    aligned_target: Optional[str] = None
    off_target_type: OffTargetType = OffTargetType.MISMATCH
    context_sequence: Optional[str] = None
    gc_content: float = 0.0
    igv_link: Optional[str] = None
    pam_sequence: Optional[str] = None
    chromatin_accessibility: float = 0.5
    chromatin_corrected_score: float = 0.0
    in_atac_peak: bool = False
    nearest_peak_distance: Optional[float] = None
    editing_efficiency: float = 0.0
    indel_1bp: float = 0.0
    indel_small_2_10bp: float = 0.0
    indel_large_gt10bp: float = 0.0
    no_edit: float = 0.0
    total_indel_frequency: float = 0.0
    nhej_ratio: float = 0.0
    hdr_ratio: float = 0.0
    alt_nhej_ratio: float = 0.0
    ssa_ratio: float = 0.0
    mmej_ratio: float = 0.0
    microhomology_score: float = 0.0
    repair_confidence: float = 0.0
    melting_temperature: float = 0.0
    sequence_features: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "sgrna": self.sgrna,
            "target_sequence": self.target_sequence,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "strand": self.strand,
            "mismatches": self.mismatches,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "score": round(float(self.score), 6),
            "raw_score": round(float(self.raw_score), 6),
            "mismatch_details": [
                {
                    "position": d.position,
                    "sgrna_base": d.sgrna_base,
                    "target_base": d.target_base,
                    "mismatch_type": d.mismatch_type,
                }
                for d in self.mismatch_details
            ],
            "aligned_sgrna": self.aligned_sgrna,
            "aligned_target": self.aligned_target,
            "off_target_type": self.off_target_type.value,
            "context_sequence": self.context_sequence,
            "gc_content": round(float(self.gc_content), 4),
            "igv_link": self.igv_link,
            "pam_sequence": self.pam_sequence,
            "genomic_coordinate": f"{self.chromosome}:{self.start}-{self.end}{self.strand}",
            "chromatin_accessibility": round(float(self.chromatin_accessibility), 6),
            "chromatin_corrected_score": round(float(self.chromatin_corrected_score), 6),
            "in_atac_peak": self.in_atac_peak,
            "nearest_peak_distance": round(float(self.nearest_peak_distance), 2)
            if self.nearest_peak_distance is not None
            else None,
            "editing_efficiency": round(float(self.editing_efficiency), 6),
            "indel_1bp": round(float(self.indel_1bp), 6),
            "indel_small_2_10bp": round(float(self.indel_small_2_10bp), 6),
            "indel_large_gt10bp": round(float(self.indel_large_gt10bp), 6),
            "no_edit": round(float(self.no_edit), 6),
            "total_indel_frequency": round(float(self.total_indel_frequency), 6),
            "nhej_ratio": round(float(self.nhej_ratio), 6),
            "hdr_ratio": round(float(self.hdr_ratio), 6),
            "alt_nhej_ratio": round(float(self.alt_nhej_ratio), 6),
            "ssa_ratio": round(float(self.ssa_ratio), 6),
            "mmej_ratio": round(float(self.mmej_ratio), 6),
            "microhomology_score": round(float(self.microhomology_score), 6),
            "repair_confidence": round(float(self.repair_confidence), 6),
            "melting_temperature": round(float(self.melting_temperature), 2),
            "sequence_features": self.sequence_features,
        }


class OffTargetFinder:
    def __init__(
        self,
        genome_handler,
        predictor,
        max_mismatches: int = 6,
        max_indel: int = 2,
        batch_size: int = 32,
    ):
        self.genome_handler = genome_handler
        self.predictor = predictor
        self.max_mismatches = max_mismatches
        self.max_indel = max_indel
        self.batch_size = batch_size

    def find_offtargets(
        self,
        sgrna: str,
        chromosomes: Optional[List[str]] = None,
        max_mismatches: Optional[int] = None,
        max_indel: Optional[int] = None,
    ) -> List[OffTargetSite]:
        from app.data_processing.sequence_utils import (
            extract_sgrna_and_pam,
            generate_pam_variants,
        )

        max_mismatches = max_mismatches or self.max_mismatches
        max_indel = max_indel or self.max_indel

        sgrna_only, pam = extract_sgrna_and_pam(sgrna)
        pam_variants = generate_pam_variants()

        if chromosomes is None:
            chromosomes = self.genome_handler.get_all_chromosomes()

        all_candidates = []

        for chromosome in chromosomes:
            candidates = self.genome_handler.scan_chromosome(
                chromosome=chromosome,
                sgrna=sgrna_only,
                pam_sequences=pam_variants,
                max_mismatches=max_mismatches,
                max_indel=max_indel,
            )
            all_candidates.extend(candidates)

        return self._process_candidates(sgrna, all_candidates)

    def find_offtargets_fast(
        self,
        sgrna: str,
        candidate_sites: List[Tuple[str, int, int, str, str]],
    ) -> List[OffTargetSite]:
        from app.data_processing.sequence_utils import count_mismatches_with_indel

        sgrna_only = sgrna[:SGRNA_LENGTH]

        candidates = []
        for chromosome, start, end, strand, target_seq in candidate_sites:
            mismatches, aligned_sgrna, aligned_target = count_mismatches_with_indel(
                sgrna_only, target_seq[:SGRNA_LENGTH], self.max_mismatches, self.max_indel
            )

            if mismatches <= self.max_mismatches + self.max_indel:
                candidates.append(
                    (chromosome, start, end, strand, mismatches, aligned_sgrna, aligned_target, target_seq)
                )

        return self._process_candidates(sgrna, candidates)

    def _process_candidates(
        self,
        sgrna: str,
        candidates: List,
    ) -> List[OffTargetSite]:
        from app.models.model_utils import predict_batch, calculate_offtarget_score
        from app.data_processing.sequence_utils import (
            count_mismatches_with_indel,
            calculate_gc_content,
        )

        if not candidates:
            return []

        sgrna_only = sgrna[:SGRNA_LENGTH]

        pairs = []
        candidate_data = []

        for cand in candidates:
            if len(cand) == 5:
                chromosome, start, end, strand, mismatches = cand
                target_seq = self.genome_handler.get_sequence(
                    chromosome, start, end, strand
                )
                _, aligned_sgrna, aligned_target = count_mismatches_with_indel(
                    sgrna_only, target_seq[:SGRNA_LENGTH], self.max_mismatches, self.max_indel
                )
            else:
                chromosome, start, end, strand, mismatches, aligned_sgrna, aligned_target, target_seq = cand

            pam_seq = target_seq[SGRNA_LENGTH:SGRNA_LENGTH + 3]
            pairs.append((sgrna, target_seq))

            insertions = aligned_sgrna.count("-")
            deletions = aligned_target.count("-")
            pure_mismatches = mismatches - insertions - deletions

            candidate_data.append(
                {
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "strand": strand,
                    "mismatches": pure_mismatches,
                    "insertions": insertions,
                    "deletions": deletions,
                    "total_mismatches": mismatches,
                    "target_sequence": target_seq,
                    "aligned_sgrna": aligned_sgrna,
                    "aligned_target": aligned_target,
                    "pam_sequence": pam_seq,
                }
            )

        raw_scores = predict_batch(
            self.predictor, pairs, batch_size=self.batch_size
        )

        from app.epigenomics.chromatin_accessibility import (
            get_chromatin_accessibility,
            calculate_accessibility_score,
            correct_offtarget_score,
        )
        from app.epigenomics.editing_efficiency import (
            EditingEfficiencyPredictor,
            calculate_sequence_features,
        )
        from app.epigenomics.repair_pathway import RepairPathwayPredictor
        from app.config import get_settings

        settings = get_settings()
        chromatin = get_chromatin_accessibility()
        efficiency_predictor = EditingEfficiencyPredictor()
        repair_predictor = RepairPathwayPredictor()

        off_target_sites = []
        for i, raw_score in enumerate(raw_scores):
            data = candidate_data[i]

            from app.data_processing.sequence_utils import count_mismatch_types
            transitions, transversions, _, _ = count_mismatch_types(
                data["aligned_sgrna"],
                data["aligned_target"],
            )

            final_score = calculate_offtarget_score(
                raw_score=float(raw_score),
                transitions=transitions,
                transversions=transversions,
                insertions=data["insertions"],
                deletions=data["deletions"],
            )

            mismatch_details = self._extract_mismatch_details(
                data["aligned_sgrna"], data["aligned_target"]
            )

            if data["insertions"] == 0 and data["deletions"] == 0:
                if data["mismatches"] == 0:
                    off_type = OffTargetType.EXACT
                else:
                    off_type = OffTargetType.MISMATCH
            elif data["insertions"] > 0 and data["deletions"] > 0:
                off_type = OffTargetType.MIXED
            elif data["insertions"] > 0:
                off_type = OffTargetType.INSERTION
            else:
                off_type = OffTargetType.DELETION

            try:
                context = self.genome_handler.extract_sequence_context(
                    chromosome=data["chromosome"],
                    position=data["start"],
                    strand=data["strand"],
                )
            except Exception:
                context = None

            chromatin_accessibility = 0.5
            chromatin_corrected_score = final_score
            in_atac_peak = False
            nearest_peak_distance = None

            if settings.ENABLE_CHROMATIN_CORRECTION and chromatin.is_loaded():
                try:
                    cut_position = data["start"] + 17 if data["strand"] == "+" else data["end"] - 17
                    accessibility, nearest_peak = chromatin.get_accessibility(
                        data["chromosome"], cut_position
                    )
                    chromatin_accessibility = float(accessibility)

                    if nearest_peak:
                        peak_center = (nearest_peak.start + nearest_peak.end) // 2
                        nearest_peak_distance = abs(cut_position - peak_center)
                        in_atac_peak = (
                            nearest_peak.start <= cut_position <= nearest_peak.end
                        )

                    acc_score = calculate_accessibility_score(
                        chromatin_accessibility,
                        site_in_peak=in_atac_peak,
                        distance_to_peak=nearest_peak_distance or 0,
                    )
                    chromatin_corrected_score = correct_offtarget_score(
                        final_score,
                        acc_score,
                        weight=settings.CHROMATIN_CORRECTION_WEIGHT,
                    )
                except Exception as e:
                    print(f"Warning: Chromatin accessibility calculation failed: {e}")

            editing_efficiency = 0.0
            indel_1bp = 0.0
            indel_small = 0.0
            indel_large = 0.0
            no_edit = 0.0
            total_indel = 0.0
            seq_features_dict = None
            melting_temp = 0.0

            if settings.ENABLE_EFFICIENCY_PREDICTION:
                try:
                    efficiency, features = efficiency_predictor.predict(
                        sgrna,
                        data["target_sequence"],
                        mismatches=data["mismatches"],
                        mismatches_details=mismatch_details,
                    )
                    editing_efficiency = float(efficiency)
                    melting_temp = float(features.melting_temperature)

                    indel_freq = efficiency_predictor.predict_indel_frequency(
                        sgrna,
                        data["target_sequence"],
                        editing_efficiency,
                        cell_type=settings.DEFAULT_CELL_TYPE,
                    )
                    indel_1bp = indel_freq["indel_1bp"]
                    indel_small = indel_freq["indel_small_2_10bp"]
                    indel_large = indel_freq["indel_large_gt10bp"]
                    no_edit = indel_freq["no_edit"]
                    total_indel = indel_freq["total_indel_frequency"]

                    seq_features_dict = {
                        "gc_content": features.gc_content,
                        "pam_strength": features.pam_strength,
                        "melting_temperature": features.melting_temperature,
                        "has_poly_t": features.has_poly_t,
                        "has_poly_g": features.has_poly_g,
                        "seed_region_mismatches": features.seed_region_mismatches,
                        "distal_region_mismatches": features.distal_region_mismatches,
                        "overall_energy": features.overall_energy,
                        "hairpin_score": features.hairpin_score,
                    }
                except Exception as e:
                    print(f"Warning: Editing efficiency prediction failed: {e}")

            nhej_ratio = 0.0
            hdr_ratio = 0.0
            alt_nhej_ratio = 0.0
            ssa_ratio = 0.0
            mmej_ratio = 0.0
            microhomology_score = 0.0
            repair_confidence = 0.0

            if settings.ENABLE_REPAIR_PREDICTION:
                try:
                    cut_site = 17
                    repair_result = repair_predictor.predict(
                        data["target_sequence"],
                        cut_site=cut_site,
                        cell_type=settings.DEFAULT_CELL_TYPE,
                        has_hdr_template=False,
                        chromatin_accessibility=chromatin_accessibility,
                    )
                    nhej_ratio = repair_result.nhej_ratio
                    hdr_ratio = repair_result.hdr_ratio
                    alt_nhej_ratio = repair_result.alt_nhej_ratio
                    ssa_ratio = repair_result.ssa_ratio
                    mmej_ratio = repair_result.mmej_ratio
                    microhomology_score = repair_result.microhomology_score
                    repair_confidence = repair_result.confidence
                except Exception as e:
                    print(f"Warning: Repair pathway prediction failed: {e}")

            site = OffTargetSite(
                sgrna=sgrna,
                target_sequence=data["target_sequence"],
                chromosome=data["chromosome"],
                start=data["start"],
                end=data["end"],
                strand=data["strand"],
                mismatches=data["mismatches"],
                insertions=data["insertions"],
                deletions=data["deletions"],
                score=final_score,
                raw_score=float(raw_score),
                mismatch_details=mismatch_details,
                aligned_sgrna=data["aligned_sgrna"],
                aligned_target=data["aligned_target"],
                off_target_type=off_type,
                context_sequence=context,
                gc_content=calculate_gc_content(data["target_sequence"]),
                pam_sequence=data["pam_sequence"],
                chromatin_accessibility=chromatin_accessibility,
                chromatin_corrected_score=chromatin_corrected_score,
                in_atac_peak=in_atac_peak,
                nearest_peak_distance=nearest_peak_distance,
                editing_efficiency=editing_efficiency,
                indel_1bp=indel_1bp,
                indel_small_2_10bp=indel_small,
                indel_large_gt10bp=indel_large,
                no_edit=no_edit,
                total_indel_frequency=total_indel,
                nhej_ratio=nhej_ratio,
                hdr_ratio=hdr_ratio,
                alt_nhej_ratio=alt_nhej_ratio,
                ssa_ratio=ssa_ratio,
                mmej_ratio=mmej_ratio,
                microhomology_score=microhomology_score,
                repair_confidence=repair_confidence,
                melting_temperature=melting_temp,
                sequence_features=seq_features_dict,
            )
            off_target_sites.append(site)

        return off_target_sites

    def _extract_mismatch_details(
        self, aligned_sgrna: str, aligned_target: str
    ) -> List[MismatchDetail]:
        details = []

        for i, (s_base, t_base) in enumerate(zip(aligned_sgrna, aligned_target)):
            if s_base != t_base:
                if s_base == "-":
                    mtype = "insertion"
                elif t_base == "-":
                    mtype = "deletion"
                else:
                    mtype = "mismatch"

                details.append(
                    MismatchDetail(
                        position=i,
                        sgrna_base=s_base,
                        target_base=t_base,
                        mismatch_type=mtype,
                    )
                )

        return details
