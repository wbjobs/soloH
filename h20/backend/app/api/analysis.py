from typing import Annotated, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from app.api.dependencies import (
    get_clustering_service,
    get_pattern_service,
    get_task_service,
    get_gnn_service,
    get_privacy_coin_service,
    get_compliance_report_service,
)
from app.services import ClusteringService, PatternService, TaskService, GNNAnomalyService, PrivacyCoinAnalysisService, ComplianceReportService
from app.schemas import (
    AddressClusterResponse,
    ClusteringResult,
    PaginatedResponse,
    PaginationParams,
    SuspiciousPatternResponse,
    GNNAnomalyScoreRequest,
    GNNAnomalyScoreResponse,
    PrivacyCoinAnalysisRequest,
    PrivacyCoinAnalysisResponse,
    ComplianceReportRequest,
    ComplianceReportResponse,
    BatchReportRequest,
)

router = APIRouter()


class RunClusteringRequest(BaseModel):
    heuristicType: str = "multi_input"
    minClusterSize: Optional[int] = 2
    transactionLimit: Optional[int] = 10000


class AnalyzePatternsRequest(BaseModel):
    address: Optional[str] = None
    patternTypes: Optional[List[str]] = None


class RunClusteringResponse(BaseModel):
    taskId: str
    message: str


class AnalyzePatternsResponse(BaseModel):
    taskId: str
    message: str


@router.get("/clustering/results", response_model=PaginatedResponse[AddressClusterResponse])
async def get_clustering_results(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[ClusteringService, Depends(get_clustering_service)],
    heuristicType: Optional[str] = Query(None, description="启发式类型"),
    minSize: Optional[int] = Query(None, ge=1, description="最小聚类大小"),
    minSuspiciousScore: Optional[float] = Query(None, ge=0, le=100, description="最小可疑分数"),
):
    """获取聚类结果"""
    return await service.get_clustering_results(
        page=pagination.page,
        page_size=pagination.pageSize,
        heuristic_type=heuristicType,
        min_size=minSize,
        min_suspicious_score=minSuspiciousScore,
    )


@router.post("/clustering/run", response_model=RunClusteringResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_clustering(
    request: RunClusteringRequest,
    clustering_service: Annotated[ClusteringService, Depends(get_clustering_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
):
    """运行聚类分析"""
    valid_heuristics = ["multi_input", "common_spend", "shadow"]
    if request.heuristicType not in valid_heuristics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid heuristic type. Must be one of: {', '.join(valid_heuristics)}",
        )

    task = await task_service.create_task(
        task_type="cluster_addresses",
        name=f"Clustering: {request.heuristicType}",
        description=f"Run {request.heuristicType} clustering analysis",
        parameters={
            "heuristic_type": request.heuristicType,
            "params": {
                "min_cluster_size": request.minClusterSize,
                "transaction_limit": request.transactionLimit,
            },
        },
    )

    try:
        from app.tasks.analysis_tasks import run_clustering_task

        run_clustering_task.apply_async(
            task_id=task.id,
            kwargs={
                "heuristic_type": request.heuristicType,
                "params": {
                    "min_cluster_size": request.minClusterSize,
                    "transaction_limit": request.transactionLimit,
                },
            },
        )
    except Exception as e:
        await task_service.fail_task(task.id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start clustering task: {str(e)}",
        )

    return RunClusteringResponse(
        taskId=task.id,
        message="Clustering task started",
    )


@router.get("/patterns/suspicious", response_model=PaginatedResponse[SuspiciousPatternResponse])
async def get_suspicious_patterns(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[PatternService, Depends(get_pattern_service)],
    patternType: Optional[str] = Query(None, description="模式类型"),
    minSeverity: Optional[str] = Query(None, description="最小严重程度"),
    minConfidence: Optional[float] = Query(None, ge=0, le=1, description="最小置信度"),
):
    """获取可疑模式列表"""
    return await service.get_suspicious_patterns(
        page=pagination.page,
        page_size=pagination.pageSize,
        pattern_type=patternType,
        min_severity=minSeverity,
        min_confidence=minConfidence,
    )


@router.post("/patterns/analyze", response_model=AnalyzePatternsResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_patterns(
    request: AnalyzePatternsRequest,
    pattern_service: Annotated[PatternService, Depends(get_pattern_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
):
    """分析指定地址的可疑模式"""
    valid_patterns = [
        "tornado_cash",
        "peel_chain",
        "mixing",
        "ransomware",
        "dark_market",
    ]
    if request.patternTypes:
        invalid = [p for p in request.patternTypes if p not in valid_patterns]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pattern types: {', '.join(invalid)}. Valid types: {', '.join(valid_patterns)}",
            )

    task_name = f"Pattern Analysis"
    if request.address:
        task_name += f": {request.address[:16]}..."

    task = await task_service.create_task(
        task_type="detect_patterns",
        name=task_name,
        description="Detect suspicious patterns for address",
        parameters={
            "address": request.address,
            "pattern_types": request.patternTypes,
        },
    )

    try:
        from app.tasks.analysis_tasks import detect_patterns_task

        detect_patterns_task.apply_async(
            task_id=task.id,
            kwargs={
                "address": request.address,
                "pattern_types": request.patternTypes,
            },
        )
    except Exception as e:
        await task_service.fail_task(task.id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start pattern analysis task: {str(e)}",
        )

    return AnalyzePatternsResponse(
        taskId=task.id,
        message="Pattern analysis task started",
    )


@router.get("/patterns/{pattern_id}", response_model=SuspiciousPatternResponse)
async def get_pattern_detail(
    pattern_id: int,
    service: Annotated[PatternService, Depends(get_pattern_service)],
):
    """获取模式详情"""
    pattern = await service.get_pattern_detail(pattern_id)
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with id {pattern_id} not found",
        )
    return pattern


@router.post("/gnn/anomaly-score", response_model=GNNAnomalyScoreResponse)
async def calculate_gnn_anomaly_score(
    request: GNNAnomalyScoreRequest,
    service: Annotated[GNNAnomalyService, Depends(get_gnn_service)],
):
    """计算指定地址的GNN异常评分"""
    result = await service.calculate_gnn_anomaly_score(
        address=request.address,
        depth=request.depth
    )

    explanations = await service.explain_anomaly_score(request.address, result)

    return GNNAnomalyScoreResponse(
        address=result["address"],
        anomalyScore=result["anomaly_score"],
        riskLevel=result["risk_level"],
        features=result["features"],
        featureImportance=result["feature_importance"],
        subgraphSize=result["subgraph_size"],
        analysisDepth=result["analysis_depth"],
        explanations=explanations
    )


@router.post("/gnn/batch-score", response_model=List[GNNAnomalyScoreResponse])
async def batch_calculate_gnn_scores(
    addresses: List[str],
    service: Annotated[GNNAnomalyService, Depends(get_gnn_service)],
    depth: int = Query(default=2, ge=1, le=4, description="分析深度"),
):
    """批量计算多个地址的GNN异常评分"""
    results = await service.batch_calculate_gnn_scores(addresses, depth)

    responses = []
    for result in results:
        explanations = await service.explain_anomaly_score(result["address"], result)
        responses.append(GNNAnomalyScoreResponse(
            address=result["address"],
            anomalyScore=result["anomaly_score"],
            riskLevel=result["risk_level"],
            features=result["features"],
            featureImportance=result["feature_importance"],
            subgraphSize=result["subgraph_size"],
            analysisDepth=result["analysis_depth"],
            explanations=explanations
        ))
    return responses


@router.post("/privacy/analyze", response_model=PrivacyCoinAnalysisResponse)
async def analyze_privacy_coin_associations(
    request: PrivacyCoinAnalysisRequest,
    service: Annotated[PrivacyCoinAnalysisService, Depends(get_privacy_coin_service)],
):
    """分析指定地址的隐私币关联"""
    result = await service.analyze_privacy_coin_associations(
        address=request.address,
        depth=request.depth
    )

    threat_intel = await service.generate_privacy_threat_intel(result)

    return PrivacyCoinAnalysisResponse(
        address=result["address"],
        overallRiskScore=result["overall_risk_score"],
        riskLevel=result["risk_level"],
        detectedPrivacyCoins=result["detected_privacy_coins"],
        privacyCoinCount=result["privacy_coin_count"],
        associatedAddressCount=result["associated_address_count"],
        suspiciousTransactions=result["suspicious_transactions"],
        totalPrivacyRelatedValue=result["total_privacy_related_value"],
        mixingPatterns=result["mixing_patterns"],
        crossChainLinks=result["cross_chain_links"],
        analysisDepth=result["analysis_depth"],
        analysisTimestamp=result["analysis_timestamp"],
        threatIntelligence=threat_intel
    )


@router.post("/privacy/batch-analyze", response_model=List[PrivacyCoinAnalysisResponse])
async def batch_analyze_privacy_associations(
    addresses: List[str],
    service: Annotated[PrivacyCoinAnalysisService, Depends(get_privacy_coin_service)],
    depth: int = Query(default=2, ge=1, le=3, description="分析深度"),
):
    """批量分析多个地址的隐私币关联"""
    results = await service.batch_analyze_privacy_associations(addresses, depth)

    responses = []
    for result in results:
        threat_intel = await service.generate_privacy_threat_intel(result)
        responses.append(PrivacyCoinAnalysisResponse(
            address=result["address"],
            overallRiskScore=result["overall_risk_score"],
            riskLevel=result["risk_level"],
            detectedPrivacyCoins=result["detected_privacy_coins"],
            privacyCoinCount=result["privacy_coin_count"],
            associatedAddressCount=result["associated_address_count"],
            suspiciousTransactions=result["suspicious_transactions"],
            totalPrivacyRelatedValue=result["total_privacy_related_value"],
            mixingPatterns=result["mixing_patterns"],
            crossChainLinks=result["cross_chain_links"],
            analysisDepth=result["analysis_depth"],
            analysisTimestamp=result["analysis_timestamp"],
            threatIntelligence=threat_intel
        ))
    return responses


@router.post("/report/generate")
async def generate_compliance_report(
    request: ComplianceReportRequest,
    service: Annotated[ComplianceReportService, Depends(get_compliance_report_service)],
):
    """生成合规调查报告（支持PDF和JSON格式）"""
    result = await service.generate_address_compliance_report(
        address=request.address,
        report_format=request.format,
        include_visualizations=request.includeVisualizations
    )

    if request.format == "pdf":
        pdf_content = result["content"]
        filename = result["filename"]

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_content))
            }
        )
    else:
        return result["data"]


@router.post("/report/generate/info", response_model=ComplianceReportResponse)
async def generate_report_info(
    request: ComplianceReportRequest,
    service: Annotated[ComplianceReportService, Depends(get_compliance_report_service)],
):
    """生成合规报告并返回报告信息（不直接下载）"""
    result = await service.generate_address_compliance_report(
        address=request.address,
        report_format=request.format,
        include_visualizations=request.includeVisualizations
    )

    return ComplianceReportResponse(
        address=result["address"],
        reportType=result["report_type"],
        format=result["format"],
        generatedAt=result["generated_at"],
        fileSize=result.get("file_size"),
        filename=result.get("filename"),
        downloadUrl=f"/api/v1/analysis/report/download/{result['address']}",
        summary=result.get("summary")
    )


@router.post("/report/batch-generate")
async def batch_generate_reports(
    request: BatchReportRequest,
    service: Annotated[ComplianceReportService, Depends(get_compliance_report_service)],
):
    """批量生成多个地址的合规报告"""
    result = await service.generate_batch_compliance_report(
        addresses=request.addresses,
        report_format=request.format
    )
    return result
