"""
Quickstart example for MDCompress.

This example demonstrates the full workflow using synthetic data:
1. Generate synthetic molecular dynamics trajectory
2. Train a GNN autoencoder model
3. Compress the trajectory
4. Decompress and reconstruct
5. Evaluate the reconstruction quality

Note: This is a demonstration using synthetic data. For real MD data,
use actual PDB/XTC/DCD files as input.
"""

import numpy as np
import torch
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mdcompress.model import TrajectoryAutoencoder, LossFunction
from mdcompress.utils import (
    normalize_coords,
    denormalize_coords,
    build_bond_list,
    atom_type_to_feature,
    compute_rmsd,
)
from mdcompress.compress import compress_trajectory, decompress_trajectory
from mdcompress.evaluate import evaluate_trajectories
from mdcompress.train import Trainer
from torch_geometric.data import Data, Batch


def generate_synthetic_trajectory(
    n_frames: int = 50,
    n_atoms: int = 20,
    noise_level: float = 0.1,
) -> tuple:
    """Generate a synthetic MD-like trajectory for testing."""
    print(f"Generating synthetic trajectory: {n_frames} frames, {n_atoms} atoms...")

    atom_types = []
    elements = ["C", "N", "O", "H"]
    for i in range(n_atoms):
        atom_types.append(elements[i % len(elements)] + str(i))

    base_structure = np.random.randn(n_atoms, 3).astype(np.float32) * 5

    coords = []
    for frame in range(n_frames):
        displacement = np.sin(frame * 0.1) * 0.5
        frame_coords = base_structure + displacement * np.random.randn(n_atoms, 3).astype(np.float32) * noise_level
        coords.append(frame_coords)

    coords = np.array(coords, dtype=np.float32)

    return coords, atom_types


def create_graph_dataset(coords: np.ndarray, atom_types: list):
    """Create a list of PyG Data objects from coordinates."""
    normalized, mean, std = normalize_coords(coords)

    atom_features = np.vstack([atom_type_to_feature(t) for t in atom_types])
    edge_index, edge_attr = build_bond_list(atom_types, coords[0], cutoff=3.0)

    data_list = []
    for i in range(len(coords)):
        data = Data(
            x=torch.tensor(atom_features, dtype=torch.float32),
            pos=torch.tensor(normalized[i], dtype=torch.float32),
            edge_index=torch.tensor(edge_index, dtype=torch.long),
            edge_attr=torch.tensor(edge_attr, dtype=torch.float32),
            original_pos=torch.tensor(coords[i], dtype=torch.float32),
        )
        data_list.append(data)

    return data_list, mean, std


def train_synthetic_model():
    """Train a model on synthetic data."""
    print("\n" + "=" * 60)
    print("1. Training Model on Synthetic Data")
    print("=" * 60)

    n_frames = 50
    n_atoms = 20
    latent_dim = 8

    coords, atom_types = generate_synthetic_trajectory(n_frames, n_atoms)
    data_list, mean, std = create_graph_dataset(coords, atom_types)

    model = TrajectoryAutoencoder(
        atom_feature_dim=8,
        coord_dim=3,
        hidden_dim=64,
        latent_dim=latent_dim,
        encoder_layers=2,
        decoder_layers=2,
        gnn_type="gcn",
        dropout=0.1,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    model.to(device)

    trainer = Trainer(model, device=device, learning_rate=1e-3)

    from torch.utils.data import random_split
    train_size = int(0.8 * len(data_list))
    val_size = len(data_list) - train_size
    train_dataset, val_dataset = random_split(
        data_list, [train_size, val_size], generator=torch.Generator().manual_seed(42)
    )

    from torch.utils.data import DataLoader

    def collate_fn(batch):
        return Batch.from_data_list(batch)

    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=4, shuffle=False, collate_fn=collate_fn)

    print(f"\nTraining for 20 epochs...")
    print(f"Compression ratio target: {3 / latent_dim:.2f}x")

    for epoch in range(20):
        train_metrics = trainer.train_epoch(train_loader)
        val_metrics = trainer.validate(val_loader)

        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch + 1:3d} | "
                  f"Train Loss: {train_metrics['total_loss']:.6f} | "
                  f"Val Loss: {val_metrics['total_loss']:.6f}")

    return model, coords, atom_types, mean, std


def compress_and_decompress(model, coords, atom_types, mean, std):
    """Test compression and decompression with synthetic data."""
    print("\n" + "=" * 60)
    print("2. Testing Compression/Decompression")
    print("=" * 60)

    device = next(model.parameters()).device

    atom_features = np.vstack([atom_type_to_feature(t) for t in atom_types])
    edge_index, _ = build_bond_list(atom_types, coords[0], cutoff=3.0)

    normalized = (coords - mean) / std

    x = torch.tensor(atom_features, dtype=torch.float32, device=device)
    pos = torch.tensor(normalized.reshape(-1, 3), dtype=torch.float32, device=device)
    edge_index = torch.tensor(edge_index, dtype=torch.long, device=device)

    batch = torch.repeat_interleave(torch.arange(len(coords), device=device), len(atom_types))

    edge_index_full = edge_index.clone()
    for b in range(1, len(coords)):
        offset = b * len(atom_types)
        edge_index_full = torch.cat([edge_index_full, edge_index + offset], dim=1)

    print("Encoding...")
    model.eval()
    with torch.no_grad():
        z = model.encode(x.repeat(len(coords), 1), pos, edge_index_full, batch)
        pos_recon = model.decode(z, x.repeat(len(coords), 1), batch)

    pos_recon_np = pos_recon.cpu().numpy().reshape(len(coords), len(atom_types), 3)
    recon_coords = denormalize_coords(pos_recon_np, mean, std)

    print("Computing reconstruction error...")
    rmsds = []
    for i in range(len(coords)):
        rmsd = compute_rmsd(coords[i], recon_coords[i])
        rmsds.append(rmsd)

    print(f"\nReconstruction RMSD:")
    print(f"  Mean:   {np.mean(rmsds):.4f} Angstrom")
    print(f"  Std:    {np.std(rmsds):.4f} Angstrom")
    print(f"  Median: {np.median(rmsds):.4f} Angstrom")

    return recon_coords


def save_synthetic_files(coords, recon_coords, atom_types):
    """Save synthetic data as PDB files for testing."""
    print("\n" + "=" * 60)
    print("3. Saving Synthetic PDB Files")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        orig_pdb = os.path.join(tmpdir, "original.pdb")
        recon_pdb = os.path.join(tmpdir, "reconstructed.pdb")

        def write_pdb(filename, coords, atom_types):
            with open(filename, "w") as f:
                for i, (coord, atype) in enumerate(zip(coords[0], atom_types)):
                    elem = atype[0] if atype[0] in "CHNOSP" else "C"
                    f.write(f"ATOM  {i+1:5d}  {atype:4s} MOL     1    "
                            f"{coord[0]:8.3f}{coord[1]:8.3f}{coord[2]:8.3f}"
                            f"  1.00  0.00          {elem:2s}\n")
                f.write("END\n")

        write_pdb(orig_pdb, coords, atom_types)
        write_pdb(recon_pdb, recon_coords, atom_types)

        print(f"Original PDB: {orig_pdb}")
        print(f"Reconstructed PDB: {recon_pdb}")

        return orig_pdb, recon_pdb


def main():
    print("=" * 60)
    print("MDCompress Quickstart Example")
    print("=" * 60)
    print("\nThis example demonstrates the full MDCompress workflow")
    print("using synthetic molecular dynamics data.\n")

    try:
        model, coords, atom_types, mean, std = train_synthetic_model()

        recon_coords = compress_and_decompress(model, coords, atom_types, mean, std)

        orig_pdb, recon_pdb = save_synthetic_files(coords, recon_coords, atom_types)

        print("\n" + "=" * 60)
        print("Example completed successfully!")
        print("=" * 60)
        print("\nTo use with real data:")
        print("  mdcompress train --topology protein.pdb --trajectory traj.xtc --latent-dim 32 --output model.pt")
        print("  mdcompress compress --topology protein.pdb --trajectory traj.xtc --model model.pt --output compressed.bin")
        print("  mdcompress decompress --topology protein.pdb --input compressed.bin --model model.pt --output recon.xtc")
        print("  mdcompress evaluate --topology protein.pdb --original traj.xtc --reconstructed recon.xtc")

    except ImportError as e:
        print(f"\nMissing dependencies: {e}")
        print("Please install required packages: pip install torch torch-geometric mdanalysis")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
