__all__ = [
    "filter_results",
    "sort_results",
    "paginate_results",
    "aggregate_statistics",
    "FilterParams",
    "SortParams",
]


def __getattr__(name):
    from . import results_filter
    if hasattr(results_filter, name):
        return getattr(results_filter, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
