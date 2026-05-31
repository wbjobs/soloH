from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Dict, Any
from enum import Enum


class JunctionType(str, Enum):
    T = "T"
    FLOW_FOCUSING = "flow-focusing"
    CO_FLOW = "co-flow"


class ContinuousPhase(BaseModel):
    flowRate: float = Field(20.0, ge=0.1, le=1000, description="连续相流速 μL/min")
    viscosity: float = Field(1.0, ge=0.1, le=1000, description="连续相粘度 mPa·s")
    density: float = Field(1000.0, ge=500, le=3000, description="连续相密度 kg/m³")


class DispersedPhase(BaseModel):
    flowRate: float = Field(5.0, ge=0.1, le=500, description="离散相流速 μL/min")
    viscosity: float = Field(5.0, ge=0.1, le=1000, description="离散相粘度 mPa·s")
    density: float = Field(800.0, ge=500, le=3000, description="离散相密度 kg/m³")


class ChannelGeometry(BaseModel):
    width: float = Field(100.0, ge=10, le=1000, description="通道宽度 μm")
    height: float = Field(50.0, ge=5, le=500, description="通道高度 μm")
    length: float = Field(1000.0, ge=100, le=10000, description="通道长度 μm")
    junctionType: JunctionType = Field(JunctionType.T, description="通道交汇类型")


class SimulationParameters(BaseModel):
    continuousPhase: ContinuousPhase = Field(default_factory=ContinuousPhase)
    dispersedPhase: DispersedPhase = Field(default_factory=DispersedPhase)
    interfacialTension: float = Field(30.0, ge=1, le=100, description="界面张力 mN/m")
    channel: ChannelGeometry = Field(default_factory=ChannelGeometry)


class SimulationResult(BaseModel):
    timestamp: float
    dropletSize: float
    generationFrequency: float
    flowRateRatio: float
    capillaryNumber: float
    continuousFlowRate: float
    dispersedFlowRate: float
    polydispersity: Optional[float] = None


class PIDParameters(BaseModel):
    enabled: bool = False
    targetDropletSize: float = Field(80.0, ge=10, le=500, description="目标液滴尺寸 μm")
    Kp: float = Field(0.5, ge=0, le=10, description="比例系数")
    Ki: float = Field(0.1, ge=0, le=5, description="积分系数")
    Kd: float = Field(0.01, ge=0, le=2, description="微分系数")
    outputMin: float = Field(0.5, ge=0.1, description="最小输出流速 μL/min")
    outputMax: float = Field(50.0, le=500, description="最大输出流速 μL/min")


class PIDStatus(BaseModel):
    enabled: bool
    targetSize: float
    currentSize: float
    error: float
    controlOutput: float
    integralTerm: float
    derivativeTerm: float


class OptimizationConfig(BaseModel):
    targetSize: float = Field(80.0, ge=10, le=500, description="目标液滴尺寸 μm")
    continuousFlowRateRange: List[float] = Field([5.0, 50.0], description="连续相流速范围 [min, max]")
    dispersedFlowRateRange: List[float] = Field([1.0, 20.0], description="离散相流速范围 [min, max]")
    resolution: int = Field(10, ge=3, le=30, description="每维采样点数")
    objective: Literal['minimize_error', 'maximize_frequency', 'minimize_polydispersity'] = 'minimize_error'


class OptimizationResult(BaseModel):
    continuousFlowRate: float
    dispersedFlowRate: float
    dropletSize: float
    frequency: float
    error: float


class OptimizationStatus(BaseModel):
    running: bool
    progress: float
    totalIterations: int
    completedIterations: int
    bestResult: Optional[OptimizationResult] = None
    results: List[OptimizationResult] = []


class PerturbationType(str, Enum):
    SINUSOIDAL = "sinusoidal"
    STEP = "step"
    RANDOM = "random"


class PerturbationPhase(str, Enum):
    CONTINUOUS = "continuous"
    DISPERSED = "dispersed"
    BOTH = "both"


class PerturbationConfig(BaseModel):
    enabled: bool = False
    type: PerturbationType = PerturbationType.SINUSOIDAL
    phase: PerturbationPhase = PerturbationPhase.DISPERSED
    amplitude: float = Field(10.0, ge=0, le=100, description="扰动幅值 %")
    frequency: float = Field(0.5, ge=0.01, le=10, description="扰动频率 Hz")


class SimulationStatus(BaseModel):
    running: bool
    time: float
    parameters: SimulationParameters
    latestResult: Optional[SimulationResult] = None
    pidStatus: Optional[PIDStatus] = None
    perturbation: PerturbationConfig


class SimulationControl(BaseModel):
    action: Literal['start', 'pause', 'reset']


class SimulationTimeSeries(BaseModel):
    timestamps: List[float]
    dropletSizes: List[float]
    frequencies: List[float]
    continuousFlowRates: List[float]
    dispersedFlowRates: List[float]


class NeuralSurrogateConfig(BaseModel):
    hiddenLayers: List[int] = Field([64, 32, 16], description="隐藏层神经元数量")
    trainingSamples: int = Field(10000, ge=1000, le=50000, description="训练样本数")
    epochs: int = Field(2000, ge=100, le=10000, description="训练轮数")
    learningRate: float = Field(0.001, ge=1e-5, le=0.1, description="学习率")
    batchSize: int = Field(64, ge=16, le=256, description="批次大小")


class NeuralSurrogateStatus(BaseModel):
    trained: bool
    architecture: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None
    trainingProgress: float = 0.0


class ChannelResult(BaseModel):
    channelId: int
    enabled: bool
    blocked: bool
    blockageSeverity: Optional[float] = None
    dropletSize: float
    generationFrequency: float
    continuousFlowRate: float
    dispersedFlowRate: float
    baseContinuousFlowRate: Optional[float] = None
    baseDispersedFlowRate: Optional[float] = None
    flowRateRatio: float
    capillaryNumber: float
    polydispersity: Optional[float] = None
    crosstalkDeltaQc: Optional[float] = None
    crosstalkDeltaQd: Optional[float] = None


class MultichannelConfig(BaseModel):
    nChannels: int = Field(4, ge=1, le=16, description="通道数量")
    channelSpacing: float = Field(200.0, ge=50, le=1000, description="通道间距 μm")
    crosstalkStrength: float = Field(0.15, ge=0, le=1, description="串扰强度")
    crosstalkDecay: float = Field(2.0, ge=0.1, le=10, description="串扰衰减长度")
    pressureCoupling: float = Field(0.1, ge=0, le=1, description="压力耦合系数")


class MultichannelStatus(BaseModel):
    nChannels: int
    channelConfigs: List[Dict[str, Any]]
    crosstalkInfo: Dict[str, Any]
    summaryStats: Optional[Dict[str, Any]] = None
    lastResults: List[ChannelResult] = []


class FaultTypeEnum(str, Enum):
    NORMAL = "normal"
    PARTIAL_BLOCKAGE = "partial_blockage"
    FULL_BLOCKAGE = "full_blockage"
    FLOW_INSTABILITY = "flow_instability"
    PRESSURE_ANOMALY = "pressure_anomaly"
    LEAKAGE = "leakage"


class ChannelFaultStatus(BaseModel):
    channelId: int
    faultType: FaultTypeEnum
    confidence: float
    blockageSeverity: float
    anomalyScore: float


class FaultDetectionStatus(BaseModel):
    enabled: bool
    overallStatus: Literal['normal', 'warning', 'critical']
    channelStatuses: List[ChannelFaultStatus]
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]


class SimulationMode(str, Enum):
    SINGLE_CHANNEL = "single_channel"
    MULTICHANNEL = "multichannel"
    NEURAL_SURROGATE = "neural_surrogate"


class SimulationConfig(BaseModel):
    mode: SimulationMode = SimulationMode.SINGLE_CHANNEL
    multichannel: Optional[MultichannelConfig] = None
    neuralSurrogate: Optional[NeuralSurrogateConfig] = None
    faultDetectionEnabled: bool = True


class ExtendedSimulationStatus(SimulationStatus):
    mode: SimulationMode = SimulationMode.SINGLE_CHANNEL
    multichannel: Optional[MultichannelStatus] = None
    faultDetection: Optional[FaultDetectionStatus] = None
    neuralSurrogate: Optional[NeuralSurrogateStatus] = None
