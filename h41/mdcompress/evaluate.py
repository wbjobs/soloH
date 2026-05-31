import numpy as np
import MDAnalysis as mda
from MDAnalysis.analysis import dssp
from typing import Dict, List, Tuple, Optional
from tqdm import tqdm
import warnings

from .utils import (
    compute_rmsd,
    center_coords,
    compute_bond_lengths_batch,
    remove_pbc_wrapping,
    remove_translation_rotation,
    compute_rmsf,
    compute_rmsf_preservation,
)

warnings.filterwarnings("ignore", category=UserWarning)


def load_trajectory_coords(
    topology_file: str,
    trajectory_file: str,
    selection: str = "protein",
    stride: int = 1,
    remove_pbc: bool = True,
    remove_transform: bool = True,
) -> Tuple[np.ndarray, mda.AtomGroup]:
    universe = mda.Universe(topology_file, trajectory_file)
    atoms = universe.select_atoms(selection)

    coords = []
    boxes = []
    for i, ts in enumerate(universe.trajectory):
        if i % stride == 0:
            coords.append(atoms.positions.copy().astype(np.float32))
            if ts.dimensions is not None:
                boxes.append(ts.dimensions[:3].astype(np.float32))
            else:
                boxes.append(None)

    coords = np.array(coords, dtype=np.float32)
    has_box = any(b is not None for b in boxes)

    if remove_pbc and has_box:
        coords = remove_pbc_wrapping(coords, boxes)

    if remove_transform:
        coords, _ = remove_translation_rotation(coords)

    return coords, atoms


def compute_frame_rmsd(
    coords1: np.ndarray, coords2: np.ndarray
) -> np.ndarray:
    n_frames = coords1.shape[0]
    rmsds = np.zeros(n_frames)
    for i in range(n_frames):
        rmsds[i] = compute_rmsd(coords1[i], coords2[i])
    return rmsds


def compute_bond_deviations(
    coords1: np.ndarray,
    coords2: np.ndarray,
    atoms: mda.AtomGroup,
    bond_pairs: Optional[List[Tuple[int, int]]] = None,
    boxes: Optional[List] = None,
    use_relative_deviation: bool = False,
) -> Dict[str, float]:
    if bond_pairs is None:
        bond_pairs = []
        for bond in atoms.bonds:
            bond_pairs.append((bond.atoms[0].ix, bond.atoms[1].ix))

    if len(bond_pairs) == 0:
        print("Warning: No bonds found in topology, using distance-based bond detection")
        n_atoms = coords1.shape[1]
        ref_coords = coords1[0].astype(np.float64)
        diff = ref_coords[:, None, :] - ref_coords[None, :, :]
        dist_matrix = np.sqrt(np.sum(diff**2, axis=-1))
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                if dist_matrix[i, j] < 2.0:
                    bond_pairs.append((i, j))

    n_frames = coords1.shape[0]
    n_bonds = len(bond_pairs)

    bond_lengths1 = compute_bond_lengths_batch(coords1, bond_pairs, boxes)
    bond_lengths2 = compute_bond_lengths_batch(coords2, bond_pairs, boxes)

    abs_deviations = np.abs(bond_lengths1 - bond_lengths2)

    if use_relative_deviation:
        mean_bond_lengths = (bond_lengths1 + bond_lengths2) / 2.0
        with np.errstate(divide='ignore', invalid='ignore'):
            deviations = np.where(
                mean_bond_lengths > 1e-8,
                abs_deviations / mean_bond_lengths * 100.0,
                0.0
            )
        unit = "%"
    else:
        deviations = abs_deviations
        unit = "Angstrom"

    deviations_flat = deviations.flatten()
    abs_deviations_flat = abs_deviations.flatten()

    return {
        "mean_bond_deviation": float(np.mean(abs_deviations_flat)),
        "std_bond_deviation": float(np.std(abs_deviations_flat)),
        "max_bond_deviation": float(np.max(abs_deviations_flat)),
        "median_bond_deviation": float(np.median(abs_deviations_flat)),
        "mean_relative_deviation": float(np.mean(deviations_flat)),
        "std_relative_deviation": float(np.std(deviations_flat)),
        "unit": unit,
        "n_bonds": n_bonds,
        "n_frames": n_frames,
        "bond_deviations": abs_deviations_flat,
        "per_bond_mean_deviation": np.mean(abs_deviations, axis=0),
        "per_frame_mean_deviation": np.mean(abs_deviations, axis=1),
    }


def compute_secondary_structure(
    coords: np.ndarray,
    atoms: mda.AtomGroup,
    topology_file: str,
) -> List[List[str]]:
    universe = mda.Universe(topology_file)
    protein_atoms = universe.select_atoms("protein")

    all_ss = []
    for frame_idx in range(coords.shape[0]):
        protein_atoms.positions = coords[frame_idx][: len(protein_atoms)]
        try:
            ss = dssp.DSSP(universe, "protein").results["dssp"]
            ss_codes = []
            for i, s in enumerate(ss):
                if i < len(protein_atoms.residues):
                    ss_codes.append(s)
            all_ss.append(ss_codes)
        except Exception as e:
            print(f"Warning: DSSP failed for frame {frame_idx}: {e}")
            all_ss.append([""] * len(protein_atoms.residues))

    return all_ss


def compute_secondary_structure_retention(
    original_ss: List[List[str]],
    reconstructed_ss: List[List[str]],
) -> Dict[str, float]:
    if len(original_ss) != len(reconstructed_ss):
        raise ValueError(
            f"Frame count mismatch: original has {len(original_ss)} frames, "
            f"reconstructed has {len(reconstructed_ss)} frames"
        )

    per_frame_retention = []
    per_residue_matches = []

    for frame_idx in range(len(original_ss)):
        orig = original_ss[frame_idx]
        recon = reconstructed_ss[frame_idx]

        n_res = min(len(orig), len(recon))
        matches = 0
        for res_idx in range(n_res):
            if orig[res_idx] == recon[res_idx]:
                matches += 1
                per_residue_matches.append(True)
            else:
                per_residue_matches.append(False)

        if n_res > 0:
            per_frame_retention.append(matches / n_res)

    ss_class_mapping = {
        "H": "Helix",
        "G": "Helix",
        "I": "Helix",
        "E": "Sheet",
        "B": "Sheet",
        "T": "Coil",
        "S": "Coil",
        "C": "Coil",
        "": "Other",
    }

    class_stats = {}
    for frame_idx in range(len(original_ss)):
        orig = original_ss[frame_idx]
        recon = reconstructed_ss[frame_idx]
        n_res = min(len(orig), len(recon))

        for res_idx in range(n_res):
            orig_class = ss_class_mapping.get(orig[res_idx], "Other")
            recon_class = ss_class_mapping.get(recon[res_idx], "Other")

            if orig_class not in class_stats:
                class_stats[orig_class] = {"total": 0, "correct": 0}
            class_stats[orig_class]["total"] += 1
            if orig_class == recon_class:
                class_stats[orig_class]["correct"] += 1

    overall_retention = np.mean(per_frame_retention) if per_frame_retention else 0.0

    result = {
        "overall_ss_retention": float(overall_retention),
        "mean_per_frame_retention": float(np.mean(per_frame_retention)) if per_frame_retention else 0.0,
        "std_per_frame_retention": float(np.std(per_frame_retention)) if per_frame_retention else 0.0,
        "per_frame_retention": per_frame_retention,
        "class_retention": {},
    }

    for ss_class, stats in class_stats.items():
        if stats["total"] > 0:
            result["class_retention"][ss_class] = stats["correct"] / stats["total"]

    return result


def evaluate_trajectories(
    topology_file: str,
    original_trajectory: str,
    reconstructed_trajectory: str,
    selection: str = "protein",
    stride: int = 1,
    compute_ss: bool = True,
    compute_rmsf: bool = True,
    remove_pbc: bool = True,
    remove_transform: bool = True,
    use_relative_dev: bool = False,
) -> Dict:
    print("Loading trajectories...")
    orig_coords, orig_atoms = load_trajectory_coords(
        topology_file, original_trajectory, selection, stride,
        remove_pbc=remove_pbc, remove_transform=remove_transform
    )
    recon_coords, recon_atoms = load_trajectory_coords(
        topology_file, reconstructed_trajectory, selection, stride,
        remove_pbc=remove_pbc, remove_transform=remove_transform
    )

    if orig_coords.shape != recon_coords.shape:
        min_frames = min(orig_coords.shape[0], recon_coords.shape[0])
        min_atoms = min(orig_coords.shape[1], recon_coords.shape[1])
        print(
            f"Warning: Shape mismatch. Original: {orig_coords.shape}, "
            f"Reconstructed: {recon_coords.shape}. Using first {min_frames} frames "
            f"and {min_atoms} atoms."
        )
        orig_coords = orig_coords[:min_frames, :min_atoms]
        recon_coords = recon_coords[:min_frames, :min_atoms]

    n_frames = orig_coords.shape[0]
    n_atoms = orig_coords.shape[1]
    print(f"Evaluating {n_frames} frames, {n_atoms} atoms...")

    print("Computing RMSD...")
    rmsds = compute_frame_rmsd(orig_coords, recon_coords)

    print("Computing bond deviations...")
    bond_deviations = compute_bond_deviations(
        orig_coords, recon_coords, orig_atoms,
        use_relative_deviation=use_relative_dev
    )

    result = {
        "n_frames": n_frames,
        "n_atoms": n_atoms,
        "rmsd": {
            "mean": float(np.mean(rmsds)),
            "std": float(np.std(rmsds)),
            "median": float(np.median(rmsds)),
            "min": float(np.min(rmsds)),
            "max": float(np.max(rmsds)),
            "per_frame": rmsds.tolist(),
        },
        "bond_deviation": bond_deviations,
    }

    if compute_rmsf:
        print("Computing RMSF preservation...")
        try:
            rmsf_orig = compute_rmsf(orig_coords)
            rmsf_recon = compute_rmsf(recon_coords)
            rmsf_result = compute_rmsf_preservation(rmsf_orig, rmsf_recon)
            result["rmsf"] = rmsf_result
        except Exception as e:
            print(f"Warning: RMSF analysis failed: {e}")
            result["rmsf"] = {"error": str(e)}

    if compute_ss:
        print("Computing secondary structure retention...")
        try:
            orig_ss = compute_secondary_structure(orig_coords, orig_atoms, topology_file)
            recon_ss = compute_secondary_structure(
                recon_coords, recon_atoms, topology_file
            )
            ss_retention = compute_secondary_structure_retention(orig_ss, recon_ss)
            result["secondary_structure"] = ss_retention
        except Exception as e:
            print(f"Warning: Secondary structure analysis failed: {e}")
            result["secondary_structure"] = {"error": str(e)}

    print("\n=== Evaluation Results ===")
    print(f"Frames: {n_frames}, Atoms: {n_atoms}")
    print(f"\nRMSD (Angstrom):")
    print(f"  Mean:   {result['rmsd']['mean']:.4f} ± {result['rmsd']['std']:.4f}")
    print(f"  Median: {result['rmsd']['median']:.4f}")
    print(f"  Range:  [{result['rmsd']['min']:.4f}, {result['rmsd']['max']:.4f}]")

    print(f"\nBond Deviation (Angstrom):")
    print(f"  Mean:   {bond_deviations['mean_bond_deviation']:.6f} ± {bond_deviations['std_bond_deviation']:.6f}")
    print(f"  Median: {bond_deviations['median_bond_deviation']:.6f}")
    print(f"  Max:    {bond_deviations['max_bond_deviation']:.6f}")
    print(f"  Mean Rel: {bond_deviations['mean_relative_deviation']:.4f}%")

    if compute_rmsf and "rmsf" in result and "correlation" in result["rmsf"]:
        print(f"\nRMSF Preservation:")
        print(f"  Correlation:       {result['rmsf']['correlation']:.4f}")
        print(f"  MAE (Angstrom):    {result['rmsf']['mae']:.6f}")
        print(f"  Mean Ratio:        {result['rmsf']['mean_ratio']:.4f}")
        print(f"  Mean Rel Error:    {result['rmsf']['mean_relative_error_percent']:.2f}%")

    if compute_ss and "secondary_structure" in result and "overall_ss_retention" in result["secondary_structure"]:
        print(f"\nSecondary Structure Retention:")
        print(f"  Overall: {result['secondary_structure']['overall_ss_retention']:.4f}")
        if "class_retention" in result["secondary_structure"]:
            for ss_class, retention in result["secondary_structure"]["class_retention"].items():
                print(f"  {ss_class}: {retention:.4f}")

    return result


def print_evaluation_report(result: Dict):
    print("\n" + "=" * 60)
    print("MDCompress Evaluation Report")
    print("=" * 60)
    print(f"Frames analyzed: {result['n_frames']}")
    print(f"Atoms per frame: {result['n_atoms']}")
    print("-" * 60)

    print("\nRMSD Statistics (Angstrom):")
    print(f"  Mean RMSD:     {result['rmsd']['mean']:.4f}")
    print(f"  Std Dev:       {result['rmsd']['std']:.4f}")
    print(f"  Median RMSD:   {result['rmsd']['median']:.4f}")
    print(f"  Min RMSD:      {result['rmsd']['min']:.4f}")
    print(f"  Max RMSD:      {result['rmsd']['max']:.4f}")

    print("\nBond Length Deviation (Angstrom):")
    print(f"  Mean Dev:      {result['bond_deviation']['mean_bond_deviation']:.4f}")
    print(f"  Std Dev:       {result['bond_deviation']['std_bond_deviation']:.4f}")
    print(f"  Median Dev:    {result['bond_deviation']['median_bond_deviation']:.4f}")
    print(f"  Max Dev:       {result['bond_deviation']['max_bond_deviation']:.4f}")
    print(f"  Bonds analyzed:{result['bond_deviation']['n_bonds']}")

    if "rmsf" in result and "correlation" in result["rmsf"]:
        print("\nRMSF Preservation:")
        print(f"  Correlation:   {result['rmsf']['correlation']:.4f}")
        print(f"  MAE:           {result['rmsf']['mae']:.6f} Angstrom")
        print(f"  Mean Ratio:    {result['rmsf']['mean_ratio']:.4f}")
        print(f"  Mean Rel Err:  {result['rmsf']['mean_relative_error_percent']:.2f}%")

    if "secondary_structure" in result and "overall_ss_retention" in result["secondary_structure"]:
        print("\nSecondary Structure Retention:")
        print(f"  Overall:       {result['secondary_structure']['overall_ss_retention']:.2%}")
        if "class_retention" in result["secondary_structure"]:
            for ss_class, retention in result["secondary_structure"]["class_retention"].items():
                print(f"  {ss_class:12s}: {retention:.2%}")

    print("\n" + "=" * 60)
