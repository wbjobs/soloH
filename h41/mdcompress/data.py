import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from torch_geometric.data import Data, Batch
import MDAnalysis as mda
from typing import List, Tuple, Optional
from tqdm import tqdm

from .utils import (
    normalize_coords,
    build_bond_list,
    atom_type_to_feature,
    get_element_from_mda,
    remove_pbc_wrapping,
    remove_translation_rotation,
    get_device,
)


class TrajectoryDataset(Dataset):
    def __init__(
        self,
        topology_file: str,
        trajectory_file: str,
        selection: str = "protein",
        stride: int = 1,
        cutoff: float = 2.0,
        frame_range: Optional[Tuple[int, int]] = None,
        remove_pbc: bool = True,
        remove_transform: bool = True,
        use_mda_elements: bool = True,
    ):
        self.topology_file = topology_file
        self.trajectory_file = trajectory_file
        self.selection = selection
        self.stride = stride
        self.cutoff = cutoff
        self.remove_pbc = remove_pbc
        self.remove_transform = remove_transform
        self.use_mda_elements = use_mda_elements

        self.universe = mda.Universe(topology_file, trajectory_file)
        self.atoms = self.universe.select_atoms(selection)
        self.n_atoms = len(self.atoms)

        if frame_range is None:
            self.frame_indices = list(range(0, len(self.universe.trajectory), stride))
        else:
            start, end = frame_range
            self.frame_indices = list(range(start, min(end, len(self.universe.trajectory)), stride))

        self.atom_types = [atom.name for atom in self.atoms]

        if use_mda_elements:
            self.elements = [get_element_from_mda(atom) for atom in self.atoms]
        else:
            from .utils import get_element_from_atom_name
            self.residue_names = [atom.resname for atom in self.atoms]
            self.elements = [
                get_element_from_atom_name(t, r)
                for t, r in zip(self.atom_types, self.residue_names)
            ]

        try:
            self.masses = [atom.mass for atom in self.atoms]
        except (AttributeError, ValueError):
            self.masses = [None] * len(self.atom_types)

        self.atom_features = np.vstack([
            atom_type_to_feature(t, elem, mass)
            for t, elem, mass in zip(self.atom_types, self.elements, self.masses)
        ])

        all_coords = []
        all_boxes = []
        for idx in tqdm(self.frame_indices, desc="Loading trajectory"):
            ts = self.universe.trajectory[idx]
            all_coords.append(self.atoms.positions.copy().astype(np.float32))
            if ts.dimensions is not None:
                all_boxes.append(ts.dimensions[:3].astype(np.float32))
            else:
                all_boxes.append(None)

        self.coords = np.array(all_coords, dtype=np.float32)
        self.boxes = all_boxes if any(b is not None for b in all_boxes) else None

        if remove_pbc and self.boxes is not None:
            print("Removing PBC wrapping artifacts...")
            self.coords = remove_pbc_wrapping(self.coords, self.boxes)

        if remove_transform:
            print("Removing translation and rotation...")
            self.coords, self.transforms = remove_translation_rotation(self.coords)
        else:
            self.transforms = None

        self.normalized_coords, self.mean, self.std = normalize_coords(self.coords)

        ref_coords = self.coords[0]
        self.edge_index, self.edge_attr = build_bond_list(
            self.atom_types, ref_coords, cutoff, self.elements
        )

    def __len__(self) -> int:
        return len(self.frame_indices)

    def __getitem__(self, idx: int) -> Data:
        coords = self.normalized_coords[idx]
        x = torch.tensor(self.atom_features, dtype=torch.float32)
        pos = torch.tensor(coords, dtype=torch.float32)
        edge_index = torch.tensor(self.edge_index, dtype=torch.long)
        edge_attr = torch.tensor(self.edge_attr, dtype=torch.float32)
        original_pos = torch.tensor(self.coords[idx], dtype=torch.float32)

        return Data(
            x=x,
            pos=pos,
            edge_index=edge_index,
            edge_attr=edge_attr,
            original_pos=original_pos,
            frame_idx=torch.tensor(idx, dtype=torch.long),
        )

    def get_stats(self) -> dict:
        return {
            "n_frames": len(self),
            "n_atoms": self.n_atoms,
            "mean": self.mean,
            "std": self.std,
            "atom_types": self.atom_types,
            "elements": self.elements,
            "remove_pbc": self.remove_pbc,
            "remove_transform": self.remove_transform,
        }


def collate_fn(batch: List[Data]) -> Batch:
    return Batch.from_data_list(batch)


def create_dataloader(
    dataset: TrajectoryDataset,
    batch_size: int = 4,
    shuffle: bool = True,
    num_workers: int = 0,
) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        collate_fn=collate_fn,
    )


def load_single_frame(
    topology_file: str,
    trajectory_file: str,
    frame_idx: int,
    selection: str = "protein",
    cutoff: float = 2.0,
    use_mda_elements: bool = True,
) -> Tuple[Data, np.ndarray, np.ndarray]:
    universe = mda.Universe(topology_file, trajectory_file)
    atoms = universe.select_atoms(selection)
    atom_types = [atom.name for atom in atoms]

    if use_mda_elements:
        elements = [get_element_from_mda(atom) for atom in atoms]
    else:
        from .utils import get_element_from_atom_name
        elements = [get_element_from_atom_name(t) for t in atom_types]

    try:
        masses = [atom.mass for atom in atoms]
    except (AttributeError, ValueError):
        masses = [None] * len(atom_types)

    atom_features = np.vstack([
        atom_type_to_feature(t, elem, mass)
        for t, elem, mass in zip(atom_types, elements, masses)
    ])

    ts = universe.trajectory[frame_idx]
    coords = atoms.positions.copy().astype(np.float32)

    if ts.dimensions is not None:
        box = ts.dimensions[:3]
        coords_f64 = coords.astype(np.float64)
        for i in range(1, len(coords_f64)):
            diff = coords_f64[i] - coords_f64[i-1]
            coords_f64[i] = coords_f64[i-1] + diff - box * np.round(diff / box)
        coords = coords_f64.astype(np.float32)

    mean = coords.mean(axis=0)
    std = coords.std(axis=0) + 1e-8
    normalized = (coords - mean) / std

    edge_index, edge_attr = build_bond_list(atom_types, coords, cutoff, elements)

    data = Data(
        x=torch.tensor(atom_features, dtype=torch.float32),
        pos=torch.tensor(normalized, dtype=torch.float32),
        edge_index=torch.tensor(edge_index, dtype=torch.long),
        edge_attr=torch.tensor(edge_attr, dtype=torch.float32),
        original_pos=torch.tensor(coords, dtype=torch.float32),
    )

    return data, mean, std
