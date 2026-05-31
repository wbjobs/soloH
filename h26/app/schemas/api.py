from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.db import TaskStatus
from app.utils.fasta_parser import AMINO_ACIDS


class FastaInput(BaseModel):
    fasta: str = Field(..., description="FASTA格式的氨基酸序列", examples=[">protein1\nMALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"])
    model_name: Optional[str] = Field(None, description="使用的模型名称，默认为配置的默认模型")

    @field_validator('fasta')
    @classmethod
    def check_fasta_format(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("FASTA序列不能为空")
        if not v.startswith(">"):
            raise ValueError("FASTA格式必须以'>'开头")
        lines = v.splitlines()
        if len(lines) < 2:
            raise ValueError("FASTA格式必须包含标题行和序列行")
        return v


class PredictionTaskResponse(BaseModel):
    task_id: str
    status: str
    model_name: str
    sequence_length: int
    submitted_at: datetime

    class Config:
        from_attributes = True


class PredictionTaskStatus(BaseModel):
    task_id: str
    status: str
    model_name: str
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    sequence_length: int
    sequence_header: Optional[str] = None

    class Config:
        from_attributes = True


class ContactResponse(BaseModel):
    i: int
    j: int
    probability: float
    distance: Optional[float] = None


class PrecisionMetrics(BaseModel):
    sequence_length: Optional[int] = None
    effective_L: Optional[int] = None
    top_1L_precision: Optional[float] = None
    top_1L_count: Optional[int] = None
    top_1L_avg_prob: Optional[float] = None
    top_1L_correct: Optional[int] = None
    top_1L_total: Optional[int] = None
    top_2L_precision: Optional[float] = None
    top_2L_count: Optional[int] = None
    top_2L_avg_prob: Optional[float] = None
    top_2L_correct: Optional[int] = None
    top_2L_total: Optional[int] = None
    top_5L_precision: Optional[float] = None
    top_5L_count: Optional[int] = None
    top_5L_avg_prob: Optional[float] = None
    top_5L_correct: Optional[int] = None
    top_5L_total: Optional[int] = None


class PredictionResultResponse(BaseModel):
    task_id: str
    status: str
    model_name: str
    sequence_length: int
    num_contacts: int
    threshold_angstrom: float
    contact_list: List[ContactResponse]
    precision_metrics: PrecisionMetrics
    coordinates_3d: List[List[float]]
    inference_time_ms: Optional[float] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModelInfoResponse(BaseModel):
    name: str
    description: str
    version: Optional[str] = None
    in_channels: int
    threshold_angstrom: float
    is_available: bool
    is_default: bool
    trained_on: Optional[str] = None
    training_samples: Optional[int] = None

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class MutationInput(BaseModel):
    position: int = Field(..., ge=0, description="突变位置（0-indexed）")
    mutant_aa: str = Field(..., description="突变后的氨基酸", min_length=1, max_length=1)
    model_name: Optional[str] = Field(None, description="使用的模型名称")

    @field_validator('mutant_aa')
    @classmethod
    def check_amino_acid(cls, v):
        v = v.upper()
        if v not in AMINO_ACIDS:
            raise ValueError(f"Invalid amino acid: {v}. Must be one of {''.join(sorted(AMINO_ACIDS))}")
        return v


class MutationScanInput(BaseModel):
    positions: Optional[List[int]] = Field(None, description="要扫描的位置列表，不提供则扫描所有位置")
    model_name: Optional[str] = Field(None, description="使用的模型名称")


class AttentionInput(BaseModel):
    task_id: str = Field(..., description="预测任务ID")
    residue_i: Optional[int] = Field(None, description="第一个残基位置（0-indexed）")
    residue_j: Optional[int] = Field(None, description="第二个残基位置（0-indexed）")
    top_k: int = Field(5, ge=1, le=20, description="分析Top-K个预测接触")


class StructureCompareInput(BaseModel):
    alphafold_pdb: str = Field(..., description="AlphaFold预测的PDB文件内容")
    threshold_angstrom: float = Field(8.0, description="接触图阈值（Å）")


class ContactExplanation(BaseModel):
    target_i: int
    target_j: int
    target_probability: float
    importance_map: List[List[float]]
    top_residues: List[List[Any]]
    attention_score: float


class AttentionResponse(BaseModel):
    attention_results: List[ContactExplanation]
    per_residue_importance: List[Dict[str, Any]]
    analyzed_contacts: int


class ResidueImportance(BaseModel):
    residue_index: int
    total_contact_probability: float
    high_prob_contact_count: int
    normalized_score: float


class MutationResponse(BaseModel):
    position: int
    wild_type: str
    mutant: str
    contact_map_change: float
    affected_contacts: List[Dict[str, Any]]
    structure_change_score: float
    functional_impact: str
    delta_probability: float


class MutationScanResponse(BaseModel):
    total_mutations: int
    impact_counts: Dict[str, int]
    impact_percentages: Dict[str, float]
    hotspot_positions: List[Dict[str, Any]]
    avg_contact_map_change: float
    max_contact_map_change: float
    most_damaging: Optional[MutationResponse] = None
    results: List[MutationResponse]


class StructureCompareResponse(BaseModel):
    tm_score: float
    gdt_ts: float
    gdt_ha: float
    rmsd: float
    aligned_length: int
    sequence_identity: float
    contact_map_similarity: float
    per_residue_errors: List[Dict[str, Any]]
    aligned_positions: List[int]
    transformation: Optional[Dict[str, Any]] = None


class PerResidueError(BaseModel):
    residue_index: int
    pdb_residue_number: int
    error_angstrom: float
    within_threshold: bool
