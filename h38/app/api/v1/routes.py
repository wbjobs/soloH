import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import get_settings, Settings
from app.api.schemas import (
    SGRNARequest,
    BatchSGRNARequest,
    FilterRequest,
    SortRequest,
    PaginationRequest,
    OffTargetResponse,
    BatchOffTargetResponse,
    OffTargetSiteResponse,
    StatisticsResponse,
    PaginationResponse,
    ValidationResponse,
    IGVLinkRequest,
    IGVLinkResponse,
    MismatchDetail,
)
from app.api.dependencies import (
    get_predictor,
    get_genome_handler,
    get_cache,
    get_offtarget_finder,
)
from app.models.crispr_model import CRISPRPredictor
from app.data_processing.genome_handler import GenomeHandler
from app.data_processing.sequence_utils import (
    validate_sgrna,
    extract_sgrna_and_pam,
    calculate_gc_content,
)
from app.cache.redis_cache import RedisCache, cache_key
from app.offtarget_search.offtarget_finder import OffTargetFinder, OffTargetSite
from app.filtering.results_filter import (
    FilterParams,
    SortParams,
    process_results,
    aggregate_statistics,
)
from app.visualization.igv_linker import IGVLinkGenerator, generate_batch_igv_links
from app.constants import SortField, SortOrder

router = APIRouter()


@router.post("/predict", response_model=OffTargetResponse)
async def predict_offtargets(
    request: SGRNARequest,
    filter_params: Optional[FilterRequest] = None,
    sort_params: Optional[SortRequest] = None,
    pagination: Optional[PaginationRequest] = None,
    offtarget_finder: OffTargetFinder = Depends(get_offtarget_finder),
    cache: RedisCache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
):
    start_time = time.time()
    sgrna = request.sgrna
    sgrna_only, pam = extract_sgrna_and_pam(sgrna)

    cache_params = {
        "max_mismatches": request.max_mismatches,
        "max_indel": request.max_indel,
        "chromosomes": request.chromosomes,
    }

    from_cache = False
    results_dicts: List[Dict] = []

    if request.use_cache:
        cached = cache.get_offtarget_results(sgrna, cache_params)
        if cached is not None:
            results_dicts = cached
            from_cache = True

    if not results_dicts:
        try:
            results: List[OffTargetSite] = offtarget_finder.find_offtargets(
                sgrna=sgrna,
                chromosomes=request.chromosomes,
                max_mismatches=request.max_mismatches,
                max_indel=request.max_indel,
            )

            results_dicts = [r.to_dict() for r in results]

            if request.include_igv_links:
                igv_gen = IGVLinkGenerator()
                for r_dict in results_dicts:
                    r_dict["igv_link"] = igv_gen.generate_link_from_site(r_dict)

            if request.use_cache:
                cache.cache_offtarget_results(sgrna, results, cache_params)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error searching for off-target sites: {str(e)}",
            )

    validated_results = []
    for r in results_dicts:
        if r.get("sgrna", "").upper() == sgrna.upper():
            validated_results.append(r)
        else:
            print(
                f"Warning: Result sgrna mismatch! "
                f"Expected: {sgrna.upper()}, Found: {r.get('sgrna', '').upper()}. "
                f"Skipping invalid result."
            )
    results_dicts = validated_results

    f_params = None
    if filter_params:
        f_params = FilterParams(
            min_score=filter_params.min_score,
            max_score=filter_params.max_score,
            min_mismatches=filter_params.min_mismatches,
            max_mismatches=filter_params.max_mismatches,
            max_insertions=filter_params.max_insertions,
            max_deletions=filter_params.max_deletions,
            chromosomes=filter_params.chromosomes,
            strand=filter_params.strand,
            off_target_types=filter_params.off_target_types,
            exclude_pam_mismatch=filter_params.exclude_pam_mismatch,
            min_gc_content=filter_params.min_gc_content,
            max_gc_content=filter_params.max_gc_content,
        )

    s_params = None
    if sort_params:
        s_params = SortParams(
            field=SortField(sort_params.field),
            order=SortOrder(sort_params.order),
        )

    page = pagination.page if pagination else 1
    page_size = pagination.page_size if pagination else 100

    processed = process_results(
        results=results_dicts,
        filter_params=f_params,
        sort_params=s_params,
        page=page,
        page_size=page_size,
    )

    processing_time = (time.time() - start_time) * 1000

    return OffTargetResponse(
        sgrna=sgrna,
        sgrna_sequence=sgrna_only,
        pam_sequence=pam,
        statistics=StatisticsResponse(**processed["statistics"]),
        pagination=PaginationResponse(**processed["pagination"]),
        results=[OffTargetSiteResponse(**r) for r in processed["results"]],
        from_cache=from_cache,
        processing_time_ms=round(processing_time, 2),
    )


@router.post("/batch", response_model=BatchOffTargetResponse)
async def predict_batch_offtargets(
    request: BatchSGRNARequest,
    offtarget_finder: OffTargetFinder = Depends(get_offtarget_finder),
    cache: RedisCache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
):
    start_time = time.time()
    all_results: List[OffTargetResponse] = []
    total_sites = 0

    max_mismatches = request.max_mismatches or settings.MAX_MISMATCHES
    max_indel = request.max_indel or settings.MAX_INDEL

    for sgrna_req in request.sgrnas:
        sgrna = sgrna_req.sgrna
        sgrna_only, pam = extract_sgrna_and_pam(sgrna)

        req_max_mm = sgrna_req.max_mismatches or max_mismatches
        req_max_indel = sgrna_req.max_indel or max_indel

        cache_params = {
            "max_mismatches": req_max_mm,
            "max_indel": req_max_indel,
            "chromosomes": sgrna_req.chromosomes,
        }

        from_cache = False
        results_dicts: List[Dict] = []

        if request.use_cache:
            cached = cache.get_offtarget_results(sgrna, cache_params)
            if cached is not None:
                results_dicts = cached
                from_cache = True

        if not results_dicts:
            try:
                results: List[OffTargetSite] = offtarget_finder.find_offtargets(
                    sgrna=sgrna,
                    chromosomes=sgrna_req.chromosomes,
                    max_mismatches=req_max_mm,
                    max_indel=req_max_indel,
                )

                results_dicts = [r.to_dict() for r in results]

                if request.include_igv_links:
                    igv_gen = IGVLinkGenerator()
                    for r_dict in results_dicts:
                        r_dict["igv_link"] = igv_gen.generate_link_from_site(r_dict)

                if request.use_cache:
                    cache.cache_offtarget_results(sgrna, results, cache_params)

            except Exception as e:
                results_dicts = []

        validated_results = []
        for r in results_dicts:
            if r.get("sgrna", "").upper() == sgrna.upper():
                validated_results.append(r)
            else:
                print(
                    f"Warning: Result sgrna mismatch! "
                    f"Expected: {sgrna.upper()}, Found: {r.get('sgrna', '').upper()}. "
                    f"Skipping invalid result."
                )
        results_dicts = validated_results

        stats = aggregate_statistics(results_dicts)
        total_sites += len(results_dicts)

        all_results.append(
            OffTargetResponse(
                sgrna=sgrna,
                sgrna_sequence=sgrna_only,
                pam_sequence=pam,
                statistics=StatisticsResponse(**stats),
                pagination=PaginationResponse(
                    page=1,
                    page_size=len(results_dicts),
                    total=len(results_dicts),
                    total_pages=1,
                    has_next=False,
                    has_prev=False,
                ),
                results=[OffTargetSiteResponse(**r) for r in results_dicts],
                from_cache=from_cache,
                processing_time_ms=0,
            )
        )

    processing_time = (time.time() - start_time) * 1000

    return BatchOffTargetResponse(
        results=all_results,
        total_processed=len(request.sgrnas),
        total_sites_found=total_sites,
        processing_time_ms=round(processing_time, 2),
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_sgrna_sequence(
    sgrna: str = Query(
        ...,
        description="sgRNA序列 (20nt + 3nt PAM)",
        min_length=23,
        max_length=23,
    ),
):
    sgrna = sgrna.upper().strip()
    is_valid, error_msg = validate_sgrna(sgrna)
    sgrna_only, pam = extract_sgrna_and_pam(sgrna)
    gc_content = calculate_gc_content(sgrna_only)

    errors = []
    if not is_valid and error_msg:
        errors.append(error_msg)

    return ValidationResponse(
        valid=is_valid,
        sgrna=sgrna_only,
        pam=pam,
        gc_content=round(gc_content, 4),
        errors=errors,
    )


@router.post("/igv-link", response_model=IGVLinkResponse)
async def generate_igv_link_endpoint(
    request: IGVLinkRequest,
    settings: Settings = Depends(get_settings),
):
    igv_gen = IGVLinkGenerator()

    try:
        link = igv_gen.generate_link(
            chromosome=request.chromosome,
            start=request.start,
            end=request.end,
            strand=request.strand,
            expand=request.expand,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    locus = f"{request.chromosome}:{max(0, request.start - request.expand)}-{request.end + request.expand}"

    return IGVLinkResponse(
        igv_link=link,
        locus=locus,
        expand=request.expand,
    )


@router.get("/cache/clear")
async def clear_cache(
    pattern: str = "crispr:offtarget:*",
    cache: RedisCache = Depends(get_cache),
):
    deleted = cache.clear_pattern(pattern)
    return {"deleted_keys": deleted, "pattern": pattern}
