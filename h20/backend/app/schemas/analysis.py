from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class SuspiciousScoreResponse(BaseModel):
    address: str = Field(description="地址")
    overallScore: float = Field(ge=0, le=100, description="总体可疑分数")
    riskLevel: str = Field(description="风险等级（low, medium, high, critical）")
    factors: List[Dict[str, Any]] = Field(description="风险因素列表")
    relatedPatterns: List[str] = Field(default_factory=list, description="相关可疑模式")
    lastUpdated: datetime = Field(description="最后更新时间")

    class Config:
        from_attributes = True


class SuspiciousPatternResponse(BaseModel):
    id: int = Field(description="模式ID")
    patternType: str = Field(description="模式类型")
    name: str = Field(description="模式名称")
    description: str = Field(description="模式描述")
    severity: str = Field(description="严重程度（low, medium, high, critical）")
    confidence: float = Field(ge=0, le=1, description="置信度")
    addresses: List[str] = Field(default_factory=list, description="涉及的地址列表")
    transactions: List[str] = Field(default_factory=list, description="涉及的交易列表")
    firstSeen: Optional[datetime] = Field(default=None, description="首次发现时间")
    lastSeen: Optional[datetime] = Field(default=None, description="最后发现时间")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")

    class Config:
        from_attributes = True


class AddressClusterResponse(BaseModel):
    clusterId: str = Field(description="聚类ID")
    name: Optional[str] = Field(default=None, description="聚类名称")
    size: int = Field(description="聚类大小（地址数量）")
    addresses: List[str] = Field(description="地址列表")
    totalReceived: float = Field(default=0, description="总接收金额")
    totalSent: float = Field(default=0, description="总发送金额")
    balance: float = Field(default=0, description="总余额")
    txCount: int = Field(default=0, description="交易总数")
    avgSuspiciousScore: Optional[float] = Field(default=None, description="平均可疑分数")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    firstSeen: Optional[datetime] = Field(default=None, description="首次出现时间")
    lastSeen: Optional[datetime] = Field(default=None, description="最后出现时间")

    class Config:
        from_attributes = True


class ClusteringResult(BaseModel):
    id: int = Field(description="结果ID")
    algorithm: str = Field(description="聚类算法")
    parameters: Dict[str, Any] = Field(description="聚类参数")
    clusterCount: int = Field(description="聚类数量")
    addressCount: int = Field(description="地址总数")
    clusters: List[AddressClusterResponse] = Field(description="聚类列表")
    createdAt: datetime = Field(description="创建时间")

    class Config:
        from_attributes = True


class GNNAnomalyScoreRequest(BaseModel):
    address: str = Field(description="要分析的比特币地址")
    depth: int = Field(default=3, ge=1, le=5, description="图分析深度")


class GNNAnomalyScoreResponse(BaseModel):
    address: str = Field(description="分析的地址")
    anomalyScore: float = Field(ge=0, le=100, description="GNN异常评分")
    riskLevel: str = Field(description="风险等级")
    features: Dict[str, float] = Field(description="提取的特征向量")
    featureImportance: Dict[str, float] = Field(description="特征重要性")
    subgraphSize: Dict[str, int] = Field(description="子图大小")
    analysisDepth: int = Field(description="分析深度")
    explanations: List[Dict[str, Any]] = Field(default_factory=list, description="异常解释")

    class Config:
        from_attributes = True


class PrivacyCoinAnalysisRequest(BaseModel):
    address: str = Field(description="要分析的比特币地址")
    depth: int = Field(default=2, ge=1, le=4, description="分析深度")


class PrivacyCoinAnalysisResponse(BaseModel):
    address: str = Field(description="分析的地址")
    overallRiskScore: float = Field(ge=0, le=100, description="总体隐私风险评分")
    riskLevel: str = Field(description="风险等级")
    detectedPrivacyCoins: Dict[str, List[Dict[str, Any]]] = Field(description="检测到的隐私币类型")
    privacyCoinCount: int = Field(description="检测到的隐私币类型数量")
    associatedAddressCount: int = Field(description="关联地址数量")
    suspiciousTransactions: List[Dict[str, Any]] = Field(description="可疑交易列表")
    totalPrivacyRelatedValue: float = Field(description="隐私相关交易总金额")
    mixingPatterns: List[Dict[str, Any]] = Field(description="检测到的混币模式")
    crossChainLinks: List[Dict[str, Any]] = Field(description="跨链关联")
    analysisDepth: int = Field(description="分析深度")
    analysisTimestamp: str = Field(description="分析时间戳")
    threatIntelligence: Optional[Dict[str, Any]] = Field(default=None, description="威胁情报")

    class Config:
        from_attributes = True


class ComplianceReportRequest(BaseModel):
    address: str = Field(description="要生成报告的比特币地址")
    format: str = Field(default="pdf", description="报告格式（pdf/json）")
    includeVisualizations: bool = Field(default=True, description="是否包含可视化图表")


class ComplianceReportResponse(BaseModel):
    address: str = Field(description="分析的地址")
    reportType: str = Field(description="报告类型")
    format: str = Field(description="报告格式")
    generatedAt: str = Field(description="生成时间")
    fileSize: Optional[int] = Field(default=None, description="文件大小（字节）")
    filename: Optional[str] = Field(default=None, description="文件名")
    downloadUrl: Optional[str] = Field(default=None, description="下载链接")
    summary: Optional[Dict[str, Any]] = Field(default=None, description="报告摘要")

    class Config:
        from_attributes = True


class BatchReportRequest(BaseModel):
    addresses: List[str] = Field(description="要生成报告的地址列表")
    format: str = Field(default="pdf", description="报告格式")
