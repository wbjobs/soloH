#!/usr/bin/env python
"""
Download hg38 reference genome from UCSC
"""
import os
import sys
import argparse
import urllib.request
import subprocess
from pathlib import Path


def download_hg38(output_dir: str = "./data"):
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "hg38.fa")

    if os.path.exists(output_file):
        print(f"Genome file already exists: {output_file}")
        return True

    url = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz"
    gz_file = output_file + ".gz"

    print(f"Downloading hg38 from {url}...")
    try:
        urllib.request.urlretrieve(url, gz_file)
    except Exception as e:
        print(f"Download failed: {e}")
        print("Alternative: download manually from UCSC Genome Browser")
        return False

    print("Decompressing...")
    try:
        import gzip
        with gzip.open(gz_file, "rb") as f_in:
            with open(output_file, "wb") as f_out:
                f_out.write(f_in.read())
        os.remove(gz_file)
    except Exception as e:
        print(f"Decompression failed: {e}")
        return False

    print("Building index...")
    try:
        from pyfaidx import Faidx
        Faidx(output_file)
    except Exception as e:
        print(f"Indexing failed: {e}")
        return False

    print(f"Successfully downloaded hg38 to {output_file}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download hg38 reference genome")
    parser.add_argument(
        "--output-dir",
        default="./data",
        help="Output directory for genome file",
    )
    args = parser.parse_args()

    success = download_hg38(args.output_dir)
    sys.exit(0 if success else 1)
