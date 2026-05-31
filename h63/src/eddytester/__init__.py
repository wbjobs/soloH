__version__ = "1.0.0"
from .config import Config
from .data_io import EddyCurrentData, DataLoader, DataVisualizer
from .preprocessing import (
    WaveletDenoiser,
    SavGolDenoiser,
    LiftOffCompensator,
    MaterialNormalizer,
    SpatialResampler,
    Preprocessor
)
from .features import FeatureExtractor, MultiFrequencyFusion
from .identification import (
    SVMClassifier,
    SVMRegressor,
    CNNModel,
    CrackIdentifier
)
from .annotation import Annotation, AnnotatedDataset, AnnotationTool
from .simulation import EddyCurrentSimulator
from .array_probe import (
    ArrayProbeConfig,
    ArrayScanData,
    ArrayDataLoader,
    ArrayDataFusion,
    CScanImaging,
    ArrayPreprocessor,
    ArraySimulator
)
from .streaming import (
    StreamConfig,
    StreamDataChunk,
    AlarmEvent,
    DataSource,
    SimulatedDataSource,
    FileDataSource,
    AlarmHandler,
    ConsoleAlarmHandler,
    FileAlarmHandler,
    CallbackAlarmHandler,
    StreamProcessor,
    RealTimeMonitor
)

try:
    from .pinn_inversion import (
        PINNConfig,
        HelmholtzPDE,
        PINNNetwork,
        CrackReconstructorPINN,
        PINNInverter
    )
    PINN_AVAILABLE = True
except ImportError:
    PINN_AVAILABLE = False
