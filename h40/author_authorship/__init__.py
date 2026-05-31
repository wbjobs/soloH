"""
小说作者归属分析系统
基于Python + scikit-learn + spaCy实现
"""

__version__ = "2.0.0"

__all__ = [
    "FeatureExtractor",
    "AuthorClassifier",
    "StyleDriftAnalyzer",
    "StyleVisualizer",
    "PrototypicalNetwork",
    "CrossLanguageClassifier",
    "DialogueSeparator",
    "CharacterStyleAnalyzer",
    "NarrativePerspectiveDetector",
    "CharacterUtterance",
    "CharacterProfile",
]


def __getattr__(name):
    """
    延迟导入 - 仅在实际使用时才导入模块
    避免在 spaCy 未安装时导入失败
    """
    if name == "FeatureExtractor":
        from .feature_extractor import FeatureExtractor
        return FeatureExtractor
    elif name == "AuthorClassifier":
        from .classifier import AuthorClassifier
        return AuthorClassifier
    elif name == "StyleDriftAnalyzer":
        from .style_drift import StyleDriftAnalyzer
        return StyleDriftAnalyzer
    elif name == "StyleVisualizer":
        from .visualization import StyleVisualizer
        return StyleVisualizer
    elif name == "PrototypicalNetwork":
        from .prototypical_network import PrototypicalNetwork
        return PrototypicalNetwork
    elif name == "CrossLanguageClassifier":
        from .cross_language import CrossLanguageClassifier
        return CrossLanguageClassifier
    elif name == "DialogueSeparator":
        from .character_analyzer import DialogueSeparator
        return DialogueSeparator
    elif name == "CharacterStyleAnalyzer":
        from .character_analyzer import CharacterStyleAnalyzer
        return CharacterStyleAnalyzer
    elif name == "NarrativePerspectiveDetector":
        from .character_analyzer import NarrativePerspectiveDetector
        return NarrativePerspectiveDetector
    elif name == "CharacterUtterance":
        from .character_analyzer import CharacterUtterance
        return CharacterUtterance
    elif name == "CharacterProfile":
        from .character_analyzer import CharacterProfile
        return CharacterProfile
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
