from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    IMPORT_CSV = "import_csv"
    IMPORT_API = "import_api"
    SYNC_BLOCKCHAIN = "sync_blockchain"
    ANALYZE_ADDRESS = "analyze_address"
    ANALYZE_TRANSACTION = "analyze_transaction"
    CLUSTER_ADDRESSES = "cluster_addresses"
    BUILD_GRAPH = "build_graph"
    EXPORT_DATA = "export_data"


class TaskCreate(BaseModel):
    type: TaskType = Field(description="任务类型")
    name: Optional[str] = Field(default=None, description="任务名称")
    description: Optional[str] = Field(default=None, description="任务描述")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="任务参数")


class TaskResponse(BaseModel):
    id: str = Field(description="任务ID")
    type: TaskType = Field(description="任务类型")
    name: Optional[str] = Field(default=None, description="任务名称")
    description: Optional[str] = Field(default=None, description="任务描述")
    status: TaskStatus = Field(description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    message: Optional[str] = Field(default=None, description="状态消息")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="任务参数")
    result: Optional[Dict[str, Any]] = Field(default=None, description="任务结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    createdAt: datetime = Field(description="创建时间")
    startedAt: Optional[datetime] = Field(default=None, description="开始时间")
    completedAt: Optional[datetime] = Field(default=None, description="完成时间")

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    id: str = Field(description="任务ID")
    type: TaskType = Field(description="任务类型")
    name: Optional[str] = Field(default=None, description="任务名称")
    status: TaskStatus = Field(description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    message: Optional[str] = Field(default=None, description="状态消息")
    createdAt: datetime = Field(description="创建时间")
    startedAt: Optional[datetime] = Field(default=None, description="开始时间")
    completedAt: Optional[datetime] = Field(default=None, description="完成时间")

    class Config:
        from_attributes = True


class TaskLogResponse(BaseModel):
    id: int = Field(description="日志ID")
    taskId: str = Field(description="任务ID")
    level: str = Field(description="日志级别")
    message: str = Field(description="日志消息")
    timestamp: datetime = Field(description="时间戳")

    class Config:
        from_attributes = True


class ImportCSVRequest(BaseModel):
    filePath: str = Field(description="CSV文件路径")
    type: str = Field(description="数据类型（transactions, addresses, blocks）")
    delimiter: str = Field(default=",", description="分隔符")
    hasHeader: bool = Field(default=True, description="是否有表头")
    encoding: str = Field(default="utf-8", description="编码")
    mapping: Optional[Dict[str, str]] = Field(default=None, description="字段映射")


class ImportAPIRequest(BaseModel):
    source: str = Field(description="数据源名称")
    type: str = Field(description="数据类型（transactions, addresses, blocks）")
    apiUrl: str = Field(description="API地址")
    apiKey: Optional[str] = Field(default=None, description="API密钥")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="请求参数")
    startBlock: Optional[int] = Field(default=None, description="起始区块")
    endBlock: Optional[int] = Field(default=None, description="结束区块")
    addresses: Optional[List[str]] = Field(default=None, description="地址列表")
