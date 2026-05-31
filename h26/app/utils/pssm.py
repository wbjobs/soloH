import numpy as np
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.fasta_parser import AMINO_ACID_ORDER, AMINO_ACID_TO_IDX


def create_dummy_pssm(sequence: str) -> np.ndarray:
    seq_len = len(sequence)
    pssm = np.zeros((seq_len, 20), dtype=np.float32)

    for i, aa in enumerate(sequence):
        if aa in AMINO_ACID_TO_IDX:
            pssm[i, AMINO_ACID_TO_IDX[aa]] = 2.0
            for j in range(20):
                if j != AMINO_ACID_TO_IDX[aa]:
                    pssm[i, j] = np.random.uniform(-1.0, 0.5)

    return pssm


def run_psiblast(sequence: str) -> Optional[np.ndarray]:
    if not settings.PSIBLAST_PATH or not settings.BLAST_DB_PATH:
        return None

    psiblast_path = Path(settings.PSIBLAST_PATH)
    blast_db = Path(settings.BLAST_DB_PATH)

    if not psiblast_path.exists() or not blast_db.with_suffix(".pin").exists():
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        query_file = tmpdir / "query.fasta"
        with open(query_file, "w") as f:
            f.write(f">query\n{sequence}\n")

        pssm_file = tmpdir / "pssm.asn"
        output_file = tmpdir / "blast.out"

        try:
            cmd = [
                str(psiblast_path),
                "-query", str(query_file),
                "-db", str(blast_db),
                "-out_ascii_pssm", str(pssm_file),
                "-out", str(output_file),
                "-num_iterations", "3",
                "-evalue", "0.001",
                "-num_threads", "4"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return None

            if not pssm_file.exists():
                return None

            return parse_pssm_file(str(pssm_file), len(sequence))

        except Exception:
            return None


def parse_pssm_file(pssm_path: str, seq_len: int) -> np.ndarray:
    pssm = np.zeros((seq_len, 20), dtype=np.float32)

    with open(pssm_path, "r") as f:
        lines = f.readlines()

    header_found = False
    row_idx = 0

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("Last position-specific scoring matrix"):
            header_found = True
            continue

        if header_found and line and line[0].isdigit():
            parts = line.split()

            if len(parts) < 22:
                continue

            scores = []
            for i in range(2, 22):
                try:
                    scores.append(float(parts[i]))
                except ValueError:
                    scores.append(0.0)

            if row_idx < seq_len:
                pssm[row_idx] = np.array(scores, dtype=np.float32)
                row_idx += 1

            if row_idx >= seq_len:
                break

    return pssm


def generate_pssm(sequence: str) -> np.ndarray:
    pssm = run_psiblast(sequence)

    if pssm is None:
        pssm = create_dummy_pssm(sequence)

    return normalize_pssm(pssm)


def normalize_pssm(pssm: np.ndarray) -> np.ndarray:
    pssm = np.clip(pssm, -10, 10)
    pssm = (pssm + 10) / 20.0
    return pssm.astype(np.float32)
