__all__ = ["IGVLinkGenerator", "generate_igv_link", "generate_batch_igv_links"]


def __getattr__(name):
    from . import igv_linker
    if hasattr(igv_linker, name):
        return getattr(igv_linker, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
