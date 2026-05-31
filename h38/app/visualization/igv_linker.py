import urllib.parse
from typing import Optional, List, Dict, Tuple
from app.config import get_settings
from app.constants import CHROMOSOMES


class IGVLinkGenerator:
    def __init__(
        self,
        base_url: Optional[str] = None,
        genome: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.IGV_BASE_URL
        self.genome = genome or settings.IGV_GENOME

    def generate_link(
        self,
        chromosome: str,
        start: int,
        end: int,
        strand: Optional[str] = None,
        expand: int = 50,
        tracks: Optional[List[str]] = None,
        highlight: bool = True,
    ) -> str:
        if chromosome not in CHROMOSOMES:
            raise ValueError(f"Invalid chromosome: {chromosome}")

        view_start = max(0, start - expand)
        view_end = end + expand

        params = {
            "genome": self.genome,
            "locus": f"{chromosome}:{view_start}-{view_end}",
        }

        if highlight:
            highlight_region = f"{chromosome}:{start}-{end}"
            params["highlight"] = highlight_region

        if tracks:
            params["tracks"] = ",".join(tracks)

        if strand:
            params["strand"] = strand

        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/goto?{query_string}"

    def generate_link_from_site(
        self,
        site_dict: Dict,
        expand: int = 50,
        tracks: Optional[List[str]] = None,
    ) -> str:
        return self.generate_link(
            chromosome=site_dict["chromosome"],
            start=site_dict["start"],
            end=site_dict["end"],
            strand=site_dict.get("strand"),
            expand=expand,
            tracks=tracks,
        )

    def generate_batch_link(
        self,
        regions: List[Tuple[str, int, int, Optional[str]]],
        expand: int = 50,
        tracks: Optional[List[str]] = None,
    ) -> str:
        if not regions:
            raise ValueError("No regions provided")

        loci = []
        highlights = []
        for chrom, start, end, strand in regions:
            view_start = max(0, start - expand)
            view_end = end + expand
            loci.append(f"{chrom}:{view_start}-{view_end}")
            highlights.append(f"{chrom}:{start}-{end}")

        params = {
            "genome": self.genome,
            "locus": " ".join(loci),
            "highlight": " ".join(highlights),
        }

        if tracks:
            params["tracks"] = ",".join(tracks)

        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/goto?{query_string}"

    def generate_session_link(
        self,
        session_file_url: str,
        locus: Optional[str] = None,
    ) -> str:
        params = {
            "genome": self.genome,
            "sessionURL": session_file_url,
        }

        if locus:
            params["locus"] = locus

        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/load?{query_string}"

    def generate_track_link(
        self,
        track_url: str,
        track_name: Optional[str] = None,
        format: str = "bed",
        locus: Optional[str] = None,
    ) -> str:
        params = {
            "genome": self.genome,
            "file": track_url,
            "name": track_name or track_url.split("/")[-1],
            "format": format,
        }

        if locus:
            params["locus"] = locus

        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/load?{query_string}"

    def generate_bed_track(
        self,
        sites: List[Dict],
        track_name: str = "CRISPR_OffTargets",
    ) -> str:
        bed_lines = [
            'track name="%s" description="CRISPR Off-Target Sites" useScore=1'
            % track_name
        ]

        for site in sites:
            score = int(min(1000, max(0, site.get("score", 0) * 1000)))
            strand = site.get("strand", "+")
            line = (
                f"{site['chromosome']}\t"
                f"{site['start']}\t"
                f"{site['end']}\t"
                f"{site.get('target_sequence', 'offtarget')}\t"
                f"{score}\t"
                f"{strand}"
            )
            bed_lines.append(line)

        return "\n".join(bed_lines)

    def generate_vcf_track(
        self,
        sites: List[Dict],
        track_name: str = "CRISPR_OffTargets",
    ) -> str:
        vcf_lines = [
            "##fileformat=VCFv4.2",
            f'##INFO=<ID=OFFTARGET,Number=1,Type=Float,Description="Off-target score">',
            f'##INFO=<ID=MISMATCHES,Number=1,Type=Integer,Description="Number of mismatches">',
            f'##INFO=<ID=SGRNA,Number=1,Type=String,Description="sgRNA sequence">',
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
        ]

        for site in sites:
            chrom = site["chromosome"].replace("chr", "")
            pos = site["start"] + 1
            sgrna = site.get("sgrna", "")
            target = site.get("target_sequence", "")
            ref = target[0] if target else "N"
            alt = "<DEL>" if site.get("deletions", 0) > 0 else "<INS>" if site.get("insertions", 0) > 0 else "<MISMATCH>"
            score = int(min(100, max(0, site.get("score", 0) * 100)))
            mismatches = site.get("mismatches", 0)

            info = f"OFFTARGET={site.get('score', 0):.6f};MISMATCHES={mismatches};SGRNA={sgrna}"

            line = f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t{score}\tPASS\t{info}"
            vcf_lines.append(line)

        return "\n".join(vcf_lines)


def generate_igv_link(
    chromosome: str,
    start: int,
    end: int,
    strand: Optional[str] = None,
    expand: int = 50,
) -> str:
    generator = IGVLinkGenerator()
    return generator.generate_link(
        chromosome=chromosome,
        start=start,
        end=end,
        strand=strand,
        expand=expand,
    )


def generate_batch_igv_links(
    sites: List[Dict],
    expand: int = 50,
) -> List[Dict]:
    generator = IGVLinkGenerator()
    for site in sites:
        if "igv_link" not in site or not site["igv_link"]:
            site["igv_link"] = generator.generate_link_from_site(site, expand=expand)
    return sites
