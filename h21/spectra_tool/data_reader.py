import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import os


@dataclass
class SpectrumData:
    filename: str
    wavelength: np.ndarray
    intensity: np.ndarray
    header: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @property
    def n_points(self) -> int:
        return len(self.wavelength)

    @property
    def wavelength_range(self) -> Tuple[float, float]:
        return (float(np.min(self.wavelength)), float(np.max(self.wavelength)))

    @property
    def intensity_stats(self) -> Tuple[float, float, float]:
        return (
            float(np.min(self.intensity)),
            float(np.max(self.intensity)),
            float(np.mean(self.intensity)),
        )

    def crop(self, wl_min: float, wl_max: float) -> "SpectrumData":
        mask = (self.wavelength >= wl_min) & (self.wavelength <= wl_max)
        return SpectrumData(
            filename=self.filename,
            wavelength=self.wavelength[mask].copy(),
            intensity=self.intensity[mask].copy(),
            header=self.header.copy(),
            metadata=self.metadata.copy(),
        )

    def normalize(self) -> "SpectrumData":
        max_int = np.max(self.intensity)
        if max_int > 0:
            normalized = self.intensity / max_int
        else:
            normalized = self.intensity
        return SpectrumData(
            filename=self.filename,
            wavelength=self.wavelength.copy(),
            intensity=normalized,
            header=self.header.copy(),
            metadata=self.metadata.copy(),
        )

    def remove_baseline(self, method: str = "poly", degree: int = 3) -> "SpectrumData":
        if method == "poly":
            x = self.wavelength
            y = self.intensity
            coeffs = np.polyfit(x, y, degree)
            baseline = np.polyval(coeffs, x)
            corrected = y - baseline
            corrected = corrected - np.min(corrected)
        elif method == "als":
            corrected = self._als_baseline(self.intensity)
        else:
            corrected = self.intensity

        return SpectrumData(
            filename=self.filename,
            wavelength=self.wavelength.copy(),
            intensity=corrected,
            header=self.header.copy(),
            metadata=self.metadata.copy(),
        )

    def _als_baseline(self, y: np.ndarray, lam: float = 1e5, p: float = 0.01, niter: int = 10) -> np.ndarray:
        L = len(y)
        D = np.diag([1, -2, 1] + [0] * (L - 3), 0) + \
            np.diag([-2, 1] + [0] * (L - 3), 1) + \
            np.diag([1] + [0] * (L - 3), 2)
        D = D[:-2, :]
        w = np.ones(L)
        for _ in range(niter):
            W = np.diag(w)
            Z = W + lam * D.T @ D
            z = np.linalg.solve(Z, w * y)
            w = p * (y > z) + (1 - p) * (y < z)
        return y - z


def read_spectrum_file(
    filepath: str,
    delimiter: Optional[str] = None,
    skiprows: int = 0,
    encoding: str = "utf-8",
    wl_column: int = 0,
    int_column: int = 1,
) -> SpectrumData:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    header = {}
    metadata = {}

    with open(filepath, "r", encoding=encoding, errors="ignore") as f:
        lines = f.readlines()

    data_start = skiprows
    for i, line in enumerate(lines[:skiprows + 50]):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "!", ";", "%")):
            parts = stripped[1:].split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                header[key] = value
            data_start = max(data_start, i + 1)
        elif any(c.isalpha() for c in stripped.split()[0] if c.strip()):
            data_start = max(data_start, i + 1)

    if delimiter is None:
        delimiter = _detect_delimiter(lines[data_start] if data_start < len(lines) else "")

    try:
        with open(filepath, "r", encoding=encoding, errors="ignore") as f:
            data = np.loadtxt(
                f,
                delimiter=delimiter,
                skiprows=data_start,
                usecols=(wl_column, int_column),
                unpack=True,
            )
    except Exception as e:
        try:
            data = []
            for line in lines[data_start:]:
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split(delimiter) if delimiter else stripped.split()
                if len(parts) >= 2:
                    try:
                        wl = float(parts[wl_column])
                        inten = float(parts[int_column])
                        data.append([wl, inten])
                    except ValueError:
                        continue
            if not data:
                raise ValueError(f"No valid data found in file: {filepath}")
            data = np.array(data).T
        except Exception as e2:
            raise ValueError(f"Failed to parse file {filepath}: {str(e2)}") from e

    original_line_count = len(lines)
    del lines

    wavelength = data[0]
    intensity = data[1]

    sort_idx = np.argsort(wavelength)
    wavelength = wavelength[sort_idx]
    intensity = intensity[sort_idx]

    metadata["original_rows"] = original_line_count
    metadata["data_points"] = len(wavelength)
    metadata["delimiter"] = delimiter
    metadata["encoding"] = encoding

    return SpectrumData(
        filename=os.path.basename(filepath),
        wavelength=wavelength,
        intensity=intensity,
        header=header,
        metadata=metadata,
    )


def _detect_delimiter(line: str) -> str:
    if not line.strip():
        return None

    explicit_candidates = [",", "\t", ";", "|"]
    counts = {}
    for delim in explicit_candidates:
        count = line.count(delim)
        if count > 0:
            counts[delim] = count

    if counts:
        return max(counts.items(), key=lambda x: x[1])[0]

    parts = line.split()
    if len(parts) >= 2:
        return " "

    return None


def read_batch_files(
    filepaths: List[str],
    **kwargs,
) -> List[SpectrumData]:
    spectra = []
    for fp in filepaths:
        try:
            spec = read_spectrum_file(fp, **kwargs)
            spectra.append(spec)
        except Exception as e:
            print(f"Warning: Could not read {fp}: {e}")
    return spectra
