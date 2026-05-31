import numpy as np
import torch
import struct
import os
from typing import Tuple, Optional, Dict
from tqdm import tqdm
import MDAnalysis as mda

from .data import TrajectoryDataset, create_dataloader
from .model import TrajectoryAutoencoder
from .utils import get_device, denormalize_coords, atom_type_to_feature, build_bond_list


MAGIC_NUMBER = b"MDCOMP01"


class CompressedData:
    def __init__(
        self,
        latent_vectors: np.ndarray,
        mean: np.ndarray,
        std: np.ndarray,
        atom_types: list,
        n_atoms: int,
        n_frames: int,
        latent_dim: int,
        extra_info: Optional[Dict] = None,
    ):
        self.latent_vectors = latent_vectors
        self.mean = mean
        self.std = std
        self.atom_types = atom_types
        self.n_atoms = n_atoms
        self.n_frames = n_frames
        self.latent_dim = latent_dim
        self.extra_info = extra_info or {}

    def get_compression_stats(self) -> Dict:
        original_size = self.n_frames * self.n_atoms * 3 * 4
        compressed_size = len(MAGIC_NUMBER) + 4 + 4 + 4 + 4 + 3 * 8 + 3 * 8 + 4
        compressed_size += sum(len(t.encode("utf-8")) + 1 for t in self.atom_types)
        compressed_size += self.latent_vectors.nbytes
        ratio = original_size / compressed_size
        return {
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
            "compression_ratio": ratio,
            "n_frames": self.n_frames,
            "n_atoms": self.n_atoms,
            "latent_dim": self.latent_dim,
        }


def compress_trajectory(
    topology_file: str,
    trajectory_file: str,
    model: TrajectoryAutoencoder,
    output_file: str,
    selection: str = "protein",
    stride: int = 1,
    cutoff: float = 2.0,
    remove_pbc: bool = True,
    remove_transform: bool = True,
    use_mda_elements: bool = True,
    batch_size: int = 8,
    device: Optional[torch.device] = None,
    model_extra_info: Optional[Dict] = None,
) -> CompressedData:
    device = device if device is not None else get_device()
    model.eval()
    model.to(device)

    dataset = TrajectoryDataset(
        topology_file=topology_file,
        trajectory_file=trajectory_file,
        selection=selection,
        stride=stride,
        cutoff=cutoff,
        remove_pbc=remove_pbc,
        remove_transform=remove_transform,
        use_mda_elements=use_mda_elements,
    )

    dataloader = create_dataloader(
        dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )

    all_latents = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Compressing"):
            batch = batch.to(device)
            z = model.encode(
                x=batch.x,
                pos=batch.pos,
                edge_index=batch.edge_index,
                batch=batch.batch,
            )
            all_latents.append(z.cpu().numpy())

    latent_vectors = np.vstack(all_latents)
    latent_vectors = latent_vectors.reshape(len(dataset), dataset.n_atoms, model.latent_dim)

    compressed_data = CompressedData(
        latent_vectors=latent_vectors.astype(np.float32),
        mean=dataset.mean,
        std=dataset.std,
        atom_types=dataset.atom_types,
        n_atoms=dataset.n_atoms,
        n_frames=len(dataset),
        latent_dim=model.latent_dim,
        extra_info=model_extra_info,
    )

    save_compressed(compressed_data, output_file)
    return compressed_data


def decompress_trajectory(
    input_file: str,
    model: TrajectoryAutoencoder,
    topology_file: str,
    output_trajectory: str,
    selection: str = "protein",
    cutoff: float = 2.0,
    batch_size: int = 8,
    device: Optional[torch.device] = None,
) -> np.ndarray:
    device = device if device is not None else get_device()
    model.eval()
    model.to(device)

    compressed_data = load_compressed(input_file)

    universe = mda.Universe(topology_file)
    atoms = universe.select_atoms(selection)

    atom_features_list = []
    for i, atom_name in enumerate(compressed_data.atom_types):
        if i < len(atoms):
            try:
                from .utils import get_element_from_mda
                element = get_element_from_mda(atoms[i])
            except Exception:
                element = None
            try:
                mass = atoms[i].mass
            except Exception:
                mass = None
            atom_features_list.append(atom_type_to_feature(atom_name, element, mass))
        else:
            atom_features_list.append(atom_type_to_feature(atom_name))

    atom_features = np.vstack(atom_features_list)
    atom_features_tensor = torch.tensor(atom_features, dtype=torch.float32, device=device)

    ref_coords = atoms.positions.copy()
    edge_index, _ = build_bond_list(compressed_data.atom_types, ref_coords, cutoff)
    edge_index_tensor = torch.tensor(edge_index, dtype=torch.long, device=device)

    all_recon_coords = []
    latents = compressed_data.latent_vectors

    for i in tqdm(range(0, len(latents), batch_size), desc="Decompressing"):
        batch_slice = slice(i, min(i + batch_size, len(latents)))
        batch_latents = latents[batch_slice].reshape(-1, compressed_data.latent_dim)
        batch_latents_tensor = torch.tensor(
            batch_latents, dtype=torch.float32, device=device
        )

        batch_size_actual = batch_latents.shape[0] // compressed_data.n_atoms
        batch_atom_features = atom_features_tensor.repeat(batch_size_actual, 1)
        batch_edge_index = edge_index_tensor.clone()
        batch = torch.repeat_interleave(
            torch.arange(batch_size_actual, device=device), compressed_data.n_atoms
        )

        for b in range(1, batch_size_actual):
            offset = b * compressed_data.n_atoms
            batch_edge_index = torch.cat(
                [batch_edge_index, edge_index_tensor + offset], dim=1
            )

        with torch.no_grad():
            pos_recon = model.decode(
                z=batch_latents_tensor,
                atom_features=batch_atom_features,
                batch=batch,
            )

        pos_recon_np = pos_recon.cpu().numpy()
        pos_recon_np = pos_recon_np.reshape(batch_size_actual, compressed_data.n_atoms, 3)

        for frame_coords in pos_recon_np:
            denorm_coords = denormalize_coords(
                frame_coords, compressed_data.mean, compressed_data.std
            )
            all_recon_coords.append(denorm_coords)

    recon_coords = np.array(all_recon_coords, dtype=np.float32)
    write_trajectory(topology_file, output_trajectory, recon_coords, selection)

    return recon_coords


def save_compressed(data: CompressedData, filepath: str):
    with open(filepath, "wb") as f:
        f.write(MAGIC_NUMBER)

        f.write(struct.pack("<I", data.n_frames))
        f.write(struct.pack("<I", data.n_atoms))
        f.write(struct.pack("<I", data.latent_dim))

        f.write(struct.pack("<d", data.mean[0]))
        f.write(struct.pack("<d", data.mean[1]))
        f.write(struct.pack("<d", data.mean[2]))

        f.write(struct.pack("<d", data.std[0]))
        f.write(struct.pack("<d", data.std[1]))
        f.write(struct.pack("<d", data.std[2]))

        f.write(struct.pack("<I", len(data.atom_types)))
        for atom_type in data.atom_types:
            encoded = atom_type.encode("utf-8")
            f.write(struct.pack("<B", len(encoded)))
            f.write(encoded)

        f.write(data.latent_vectors.astype(np.float32).tobytes())


def load_compressed(filepath: str) -> CompressedData:
    with open(filepath, "rb") as f:
        magic = f.read(len(MAGIC_NUMBER))
        if magic != MAGIC_NUMBER:
            raise ValueError(f"Invalid magic number. Expected {MAGIC_NUMBER}, got {magic}")

        n_frames = struct.unpack("<I", f.read(4))[0]
        n_atoms = struct.unpack("<I", f.read(4))[0]
        latent_dim = struct.unpack("<I", f.read(4))[0]

        mean = np.array(
            [
                struct.unpack("<d", f.read(8))[0],
                struct.unpack("<d", f.read(8))[0],
                struct.unpack("<d", f.read(8))[0],
            ],
            dtype=np.float64,
        )

        std = np.array(
            [
                struct.unpack("<d", f.read(8))[0],
                struct.unpack("<d", f.read(8))[0],
                struct.unpack("<d", f.read(8))[0],
            ],
            dtype=np.float64,
        )

        n_atom_types = struct.unpack("<I", f.read(4))[0]
        atom_types = []
        for _ in range(n_atom_types):
            name_len = struct.unpack("<B", f.read(1))[0]
            atom_type = f.read(name_len).decode("utf-8")
            atom_types.append(atom_type)

        expected_latent_size = n_frames * n_atoms * latent_dim * 4
        latent_data = f.read(expected_latent_size)
        latent_vectors = np.frombuffer(latent_data, dtype=np.float32).reshape(
            n_frames, n_atoms, latent_dim
        )

    return CompressedData(
        latent_vectors=latent_vectors,
        mean=mean,
        std=std,
        atom_types=atom_types,
        n_atoms=n_atoms,
        n_frames=n_frames,
        latent_dim=latent_dim,
    )


def write_trajectory(
    topology_file: str,
    output_file: str,
    coords: np.ndarray,
    selection: str = "protein",
):
    universe = mda.Universe(topology_file)
    atoms = universe.select_atoms(selection)

    if coords.shape[1] != len(atoms):
        raise ValueError(
            f"Coordinate shape mismatch: coords have {coords.shape[1]} atoms, "
            f"but selection has {len(atoms)} atoms"
        )

    output_ext = os.path.splitext(output_file)[1].lower()

    if output_ext == ".xtc":
        with mda.Writer(output_file, n_atoms=len(atoms)) as W:
            for frame_coords in coords:
                atoms.positions = frame_coords
                W.write(atoms)
    elif output_ext == ".dcd":
        with mda.Writer(output_file, n_atoms=len(atoms), format="DCD") as W:
            for frame_coords in coords:
                atoms.positions = frame_coords
                W.write(atoms)
    elif output_ext == ".pdb":
        if len(coords) > 1:
            with mda.Writer(output_file, n_atoms=len(atoms), multiframe=True) as W:
                for frame_coords in coords:
                    atoms.positions = frame_coords
                    W.write(atoms)
        else:
            atoms.positions = coords[0]
            atoms.write(output_file)
    else:
        raise ValueError(f"Unsupported output format: {output_ext}")

    print(f"Written {len(coords)} frames to {output_file}")
