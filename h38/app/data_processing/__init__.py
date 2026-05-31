from .sequence_utils import (
    validate_sgrna,
    extract_sgrna_and_pam,
    reverse_complement,
    calculate_gc_content,
    count_mismatches,
    generate_pam_variants,
)

__all__ = [
    "encode_sequence",
    "one_hot_encode",
    "encode_sgrna_pair",
    "GenomeHandler",
    "validate_sgrna",
    "extract_sgrna_and_pam",
    "reverse_complement",
    "calculate_gc_content",
    "count_mismatches",
    "generate_pam_variants",
]


def __getattr__(name):
    if name in ("encode_sequence", "one_hot_encode", "encode_sgrna_pair"):
        from . import sequence_encoder
        return getattr(sequence_encoder, name)
    elif name == "GenomeHandler":
        from . import genome_handler
        return genome_handler.GenomeHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
