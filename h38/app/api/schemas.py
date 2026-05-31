from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.constants import TOTAL_SEQUENCE_LENGTH, SGRNA_LENGTH, SortField, SortOrder
from app.data_processing.sequence_utils import validate_sgrna


class SGRNARequest(BaseModel):
    sgrna: str = Field(
        ...,
        description="sgRNA序列 (20nt + 3nt PAM = 23nt)",
        min_length=TOTAL_SEQUENCE_LENGTH,
        max_length=TOTAL_SEQUENCE_LENGTH,
        examples=["GACCCCCTCCACCCCGCCTCCGGG"],
    )
    max_mismatches: Optional[int] = Field(
        6, ge=0, le=10, description="最大允许错配数"
    )
    max_indel: Optional[int] = Field(
        2, ge=0, le=5, description="最大允许插入缺失数"
    )
    chromosomes: Optional[List[str]] = Field(
        None, description="限制搜索的染色体列表，None表示搜索全部"
    )
    use_cache: Optional[bool] = Field(True, description="是否使用缓存")
    include_igv_links: Optional[bool] = Field(True, description="是否包含IGV链接")

    @field_validator("sgrna")
    @classmethod
    def validate_sgrna_sequence(cls, v: str) -> str:
        v = v.upper().strip()
        is_valid, error_msg = validate_sgrna(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class BatchSGRNARequest(BaseModel):
    sgrnas: List[SGRNARequest] = Field(
        ..., description="sgRNA请求列表", min_length=1, max_length=100
    )
    max_mismatches: Optional[int] = Field(
        None, ge=0, le=10, description="全局最大允许错配数，覆盖单个请求设置"
    )
    max_indel: Optional[int] = Field(
        None, ge=0, le=5, description="全局最大允许插入缺失数，覆盖单个请求设置"
    )
    use_cache: Optional[bool] = Field(True, description="是否使用缓存")
    include_igv_links: Optional[bool] = Field(True, description="是否包含IGV链接")


class FilterRequest(BaseModel):
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="最小评分")
    max_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="最大评分")
    min_mismatches: Optional[int] = Field(None, ge=0, description="最小区分配数")
    max_mismatches: Optional[int] = Field(None, ge=0, description="最大区分配数")
    max_insertions: Optional[int] = Field(None, ge=0, description="最大插入数")
    max_deletions: Optional[int] = Field(None, ge=0, description="最大缺失数")
    chromosomes: Optional[List[str]] = Field(None, description="染色体筛选")
    strand: Optional[str] = Field(None, description="链筛选 (+/-)")
    off_target_types: Optional[List[str]] = Field(None, description="脱靶类型筛选")
    exclude_pam_mismatch: Optional[bool] = Field(False, description="排除PAM区错配")
    min_gc_content: Optional[float] = Field(None, ge=0.0, le=1.0, description="最小GC含量")
    max_gc_content: Optional[float] = Field(None, ge=0.0, le=1.0, description="最大GC含量")


class SortRequest(BaseModel):
    field: SortField = Field(SortField.SCORE, description="排序字段")
    order: SortOrder = Field(SortOrder.DESCENDING, description="排序方向")


class PaginationRequest(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(100, ge=1, le=1000, description="每页大小")


class MismatchDetail(BaseModel):
    position: int
    sgrna_base: str
    target_base: str
    mismatch_type: str


class OffTargetSiteResponse(BaseModel):
    sgrna: str
    target_sequence: str
    chromosome: str
    start: int
    end: int
    strand: str
    mismatches: int
    insertions: int
    deletions: int
    score: float
    raw_score: float
    mismatch_details: List[MismatchDetail]
    aligned_sgrna: Optional[str]
    aligned_target: Optional[str]
    off_target_type: str
    context_sequence: Optional[str]
    gc_content: float
    igv_link: Optional[str]
    pam_sequence: Optional[str]
    genomic_coordinate: str
    chromatin_accessibility: float
    chromatin_corrected_score: float
    in_atac_peak: bool
    nearest_peak_distance: Optional[float]
    editing_efficiency: float
    indel_1bp: float
    indel_small_2_10bp: float
    indel_large_gt10bp: float
    no_edit: float
    total_indel_frequency: float
    nhej_ratio: float
    hdr_ratio: float
    alt_nhej_ratio: float
    ssa_ratio: float
    mmej_ratio: float
    microhomology_score: float
    repair_confidence: float
    melting_temperature: float
    sequence_features: Optional[dict] = None


class StatisticsResponse(BaseModel):
    total_sites: int
    avg_score: float
    max_score: float
    min_score: float
    avg_mismatches: float
    median_mismatches: Optional[int]
    sites_with_indel: int
    high_risk_sites: int
    medium_risk_sites: int
    low_risk_sites: int
    by_chromosome: Dict[str, int]
    by_type: Dict[str, int]
    by_mismatches: Dict[str, int]


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class OffTargetResponse(BaseModel):
    sgrna: str
    sgrna_sequence: str
    pam_sequence: str
    statistics: StatisticsResponse
    pagination: PaginationResponse
    results: List[OffTargetSiteResponse]
    from_cache: bool
    processing_time_ms: float


class BatchOffTargetResponse(BaseModel):
    results: List[OffTargetResponse]
    total_processed: int
    total_sites_found: int
    processing_time_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    genome_build: str
    model_loaded: bool
    redis_connected: bool
    genome_loaded: bool


class CacheStatsResponse(BaseModel):
    enabled: bool
    connected_clients: Optional[int] = None
    used_memory_human: Optional[str] = None
    total_commands_processed: Optional[int] = None
    keyspace_hits: Optional[int] = None
    keyspace_misses: Optional[int] = None
    error: Optional[str] = None


class ValidationResponse(BaseModel):
    valid: bool
    sgrna: str
    pam: str
    gc_content: float
    errors: List[str]


class IGVLinkRequest(BaseModel):
    chromosome: str
    start: int
    end: int
    strand: Optional[str] = None
    expand: int = Field(50, ge=0, le=10000)


class IGVLinkResponse(BaseModel):
    igv_link: str
    locus: str
    expand: int
