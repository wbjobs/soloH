from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(description="节点ID")
    label: str = Field(description="节点标签")
    type: str = Field(description="节点类型（address, transaction）")
    data: Optional[Dict[str, Any]] = Field(default=None, description="附加数据")
    x: Optional[float] = Field(default=None, description="X坐标")
    y: Optional[float] = Field(default=None, description="Y坐标")
    size: Optional[float] = Field(default=None, description="节点大小")
    color: Optional[str] = Field(default=None, description="节点颜色")
    suspiciousScore: Optional[float] = Field(default=None, description="可疑分数")


class GraphEdge(BaseModel):
    id: str = Field(description="边ID")
    source: str = Field(description="源节点ID")
    target: str = Field(description="目标节点ID")
    label: Optional[str] = Field(default=None, description="边标签")
    value: Optional[float] = Field(default=None, description="边权重")
    data: Optional[Dict[str, Any]] = Field(default=None, description="附加数据")
    type: Optional[str] = Field(default=None, description="边类型")
    color: Optional[str] = Field(default=None, description="边颜色")
    timestamp: Optional[int] = Field(default=None, description="时间戳")


class GraphData(BaseModel):
    nodes: List[GraphNode] = Field(description="节点列表")
    edges: List[GraphEdge] = Field(description="边列表")
    directed: bool = Field(default=True, description="是否有向图")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class SubgraphRequest(BaseModel):
    startAddress: Optional[str] = Field(default=None, description="起始地址")
    startTxId: Optional[str] = Field(default=None, description="起始交易ID")
    maxDepth: int = Field(default=3, ge=1, le=10, description="最大深度")
    minValue: Optional[float] = Field(default=None, description="最小金额")
    maxEdges: int = Field(default=1000, ge=1, description="最大边数")
    includeAddresses: Optional[List[str]] = Field(default=None, description="包含的地址列表")
    excludeAddresses: Optional[List[str]] = Field(default=None, description="排除的地址列表")
    startBlock: Optional[int] = Field(default=None, description="起始区块")
    endBlock: Optional[int] = Field(default=None, description="结束区块")


class SubgraphResponse(BaseModel):
    graph: GraphData = Field(description="子图数据")
    stats: Dict[str, Any] = Field(description="统计信息")
    warnings: Optional[List[str]] = Field(default=None, description="警告信息")
