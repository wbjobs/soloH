from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from app.constants import SortField, SortOrder, CHROMOSOMES


@dataclass
class FilterParams:
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    min_mismatches: Optional[int] = None
    max_mismatches: Optional[int] = None
    max_insertions: Optional[int] = None
    max_deletions: Optional[int] = None
    chromosomes: Optional[List[str]] = None
    strand: Optional[str] = None
    off_target_types: Optional[List[str]] = None
    exclude_pam_mismatch: bool = False
    min_gc_content: Optional[float] = None
    max_gc_content: Optional[float] = None


@dataclass
class SortParams:
    field: SortField = SortField.SCORE
    order: SortOrder = SortOrder.DESCENDING


def filter_results(
    results: List[Dict],
    params: FilterParams,
) -> List[Dict]:
    filtered = []

    for site in results:
        if params.min_score is not None and site.get("score", 0) < params.min_score:
            continue

        if params.max_score is not None and site.get("score", 0) > params.max_score:
            continue

        if params.min_mismatches is not None and site.get("mismatches", 0) < params.min_mismatches:
            continue

        if params.max_mismatches is not None and site.get("mismatches", 0) > params.max_mismatches:
            continue

        if params.max_insertions is not None and site.get("insertions", 0) > params.max_insertions:
            continue

        if params.max_deletions is not None and site.get("deletions", 0) > params.max_deletions:
            continue

        if params.chromosomes and site.get("chromosome") not in params.chromosomes:
            continue

        if params.strand and site.get("strand") != params.strand:
            continue

        if params.off_target_types and site.get("off_target_type") not in params.off_target_types:
            continue

        if params.exclude_pam_mismatch:
            pam = site.get("pam_sequence", "")
            if len(pam) >= 2 and pam[1:] not in ["GG", "AG", "GA"]:
                continue

        if params.min_gc_content is not None and site.get("gc_content", 0) < params.min_gc_content:
            continue

        if params.max_gc_content is not None and site.get("gc_content", 0) > params.max_gc_content:
            continue

        filtered.append(site)

    return filtered


def sort_results(
    results: List[Dict],
    params: SortParams,
) -> List[Dict]:
    if not results:
        return results

    reverse = params.order == SortOrder.DESCENDING

    def sort_key(site: Dict) -> Any:
        if params.field == SortField.SCORE:
            return site.get("score", 0)
        elif params.field == SortField.MISMATCHES:
            return site.get("mismatches", 0)
        elif params.field == SortField.CHROMOSOME:
            chrom = site.get("chromosome", "")
            return _chromosome_order(chrom)
        elif params.field == SortField.POSITION:
            return (
                _chromosome_order(site.get("chromosome", "")),
                site.get("start", 0),
            )
        else:
            return site.get("score", 0)

    return sorted(results, key=sort_key, reverse=reverse)


def _chromosome_order(chrom: str) -> int:
    if chrom in CHROMOSOMES:
        return CHROMOSOMES.index(chrom)
    return len(CHROMOSOMES)


def paginate_results(
    results: List[Dict],
    page: int = 1,
    page_size: int = 100,
) -> Dict[str, Any]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 100

    total = len(results)
    total_pages = (total + page_size - 1) // page_size

    start = (page - 1) * page_size
    end = min(start + page_size, total)

    return {
        "items": results[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def aggregate_statistics(results: List[Dict]) -> Dict[str, Any]:
    if not results:
        return {
            "total_sites": 0,
            "avg_score": 0,
            "max_score": 0,
            "min_score": 0,
            "avg_mismatches": 0,
            "by_chromosome": {},
            "by_type": {},
            "by_mismatches": {},
        }

    scores = [r.get("score", 0) for r in results]
    mismatches = [r.get("mismatches", 0) for r in results]

    by_chromosome: Dict[str, int] = {}
    for r in results:
        chrom = r.get("chromosome", "unknown")
        by_chromosome[chrom] = by_chromosome.get(chrom, 0) + 1

    by_type: Dict[str, int] = {}
    for r in results:
        otype = r.get("off_target_type", "unknown")
        by_type[otype] = by_type.get(otype, 0) + 1

    by_mismatches: Dict[str, int] = {}
    for r in results:
        mm = str(r.get("mismatches", 0))
        by_mismatches[mm] = by_mismatches.get(mm, 0) + 1

    high_risk = sum(1 for r in results if r.get("score", 0) >= 0.7)
    medium_risk = sum(1 for r in results if 0.3 <= r.get("score", 0) < 0.7)
    low_risk = sum(1 for r in results if r.get("score", 0) < 0.3)

    return {
        "total_sites": len(results),
        "avg_score": sum(scores) / len(scores),
        "max_score": max(scores),
        "min_score": min(scores),
        "avg_mismatches": sum(mismatches) / len(mismatches),
        "median_mismatches": sorted(mismatches)[len(mismatches) // 2],
        "sites_with_indel": sum(1 for r in results if r.get("insertions", 0) + r.get("deletions", 0) > 0),
        "high_risk_sites": high_risk,
        "medium_risk_sites": medium_risk,
        "low_risk_sites": low_risk,
        "by_chromosome": dict(sorted(by_chromosome.items(), key=lambda x: -x[1])),
        "by_type": by_type,
        "by_mismatches": dict(sorted(by_mismatches.items(), key=lambda x: int(x[0]))),
    }


def process_results(
    results: List[Dict],
    filter_params: Optional[FilterParams] = None,
    sort_params: Optional[SortParams] = None,
    page: int = 1,
    page_size: int = 100,
) -> Dict[str, Any]:
    if filter_params:
        results = filter_results(results, filter_params)

    if sort_params:
        results = sort_results(results, sort_params)

    stats = aggregate_statistics(results)
    pagination = paginate_results(results, page, page_size)

    return {
        "statistics": stats,
        "pagination": pagination,
        "results": pagination["items"],
    }
