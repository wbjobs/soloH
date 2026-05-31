__all__ = [
    "OffTargetFinder",
    "OffTargetSite",
    "generate_candidate_sites",
    "search_genome_offtargets",
    "filter_candidates",
    "prioritize_sites",
]


def __getattr__(name):
    if name in ("OffTargetFinder", "OffTargetSite"):
        from . import offtarget_finder
        return getattr(offtarget_finder, name)
    elif name in ("generate_candidate_sites", "search_genome_offtargets", "filter_candidates", "prioritize_sites"):
        from . import search_algorithm
        return getattr(search_algorithm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
