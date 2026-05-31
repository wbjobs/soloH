__all__ = [
    "CRISPRModel",
    "CRISPRPredictor",
    "load_model",
    "predict_batch",
    "calculate_offtarget_score",
    "save_model",
]


def __getattr__(name):
    if name in ("CRISPRModel", "CRISPRPredictor"):
        from . import crispr_model
        return getattr(crispr_model, name)
    elif name in ("load_model", "predict_batch", "calculate_offtarget_score", "save_model"):
        from . import model_utils
        return getattr(model_utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
