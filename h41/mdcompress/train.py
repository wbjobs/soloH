import torch
import torch.optim as optim
from torch.utils.data import random_split
from tqdm import tqdm
import numpy as np
from typing import Tuple, Optional, Dict
import os

from .data import TrajectoryDataset, create_dataloader
from .model import (
    TrajectoryAutoencoder,
    TemporalTrajectoryAutoencoder,
    LossFunction,
    TemporalLossFunction,
)
from .utils import get_device, denormalize_coords, compute_rmsd


class Trainer:
    def __init__(
        self,
        model: TrajectoryAutoencoder,
        device: Optional[torch.device] = None,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        coord_weight: float = 1.0,
        bond_weight: float = 0.5,
        vdw_weight: float = 0.1,
        temporal_weight: float = 0.1,
        temporal_window: int = 10,
    ):
        self.device = device if device is not None else get_device()
        self.model = model.to(self.device)
        self.temporal_window = temporal_window

        if isinstance(model, TemporalTrajectoryAutoencoder):
            self.loss_fn = TemporalLossFunction(
                coord_weight=coord_weight,
                bond_weight=bond_weight,
                vdw_weight=vdw_weight,
                temporal_weight=temporal_weight,
                use_high_precision=True,
            )
        else:
            self.loss_fn = LossFunction(
                coord_weight=coord_weight,
                bond_weight=bond_weight,
                use_high_precision=True,
            )

        self.optimizer = optim.Adam(
            self.model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )
        self.train_losses = []
        self.val_losses = []

    def train_epoch(self, train_loader) -> Dict[str, float]:
        self.model.train()
        total_loss = 0.0
        total_coord_loss = 0.0
        total_bond_loss = 0.0
        total_vdw_loss = 0.0
        total_temporal_loss = 0.0
        n_batches = 0

        for batch in tqdm(train_loader, desc="Training"):
            batch = batch.to(self.device)
            self.optimizer.zero_grad()

            model_output = self.model(
                x=batch.x,
                pos=batch.pos,
                edge_index=batch.edge_index,
                batch=batch.batch,
            )

            if isinstance(self.loss_fn, TemporalLossFunction):
                losses = self.loss_fn(
                    model_output=model_output,
                    pos_true=batch.pos,
                    edge_index=batch.edge_index,
                    batch=batch.batch,
                )
            else:
                pos_recon = model_output["pos_recon"]
                losses = self.loss_fn(
                    pos_recon=pos_recon,
                    pos_true=batch.pos,
                    edge_index=batch.edge_index,
                    batch=batch.batch,
                )

            losses["total_loss"].backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += losses["total_loss"].item()
            total_coord_loss += losses["coord_loss"].item()
            total_bond_loss += losses["bond_loss"].item()
            total_vdw_loss += losses.get("vdw_loss", torch.tensor(0.0)).item()
            total_temporal_loss += losses.get("temporal_loss", torch.tensor(0.0)).item()
            n_batches += 1

        result = {
            "total_loss": total_loss / n_batches,
            "coord_loss": total_coord_loss / n_batches,
            "bond_loss": total_bond_loss / n_batches,
        }
        if total_vdw_loss > 0:
            result["vdw_loss"] = total_vdw_loss / n_batches
        if total_temporal_loss > 0:
            result["temporal_loss"] = total_temporal_loss / n_batches

        return result

    def validate(self, val_loader) -> Dict[str, float]:
        self.model.eval()
        total_loss = 0.0
        total_coord_loss = 0.0
        total_bond_loss = 0.0
        total_vdw_loss = 0.0
        total_temporal_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validating"):
                batch = batch.to(self.device)

                model_output = self.model(
                    x=batch.x,
                    pos=batch.pos,
                    edge_index=batch.edge_index,
                    batch=batch.batch,
                )

                if isinstance(self.loss_fn, TemporalLossFunction):
                    losses = self.loss_fn(
                        model_output=model_output,
                        pos_true=batch.pos,
                        edge_index=batch.edge_index,
                        batch=batch.batch,
                    )
                else:
                    pos_recon = model_output["pos_recon"]
                    losses = self.loss_fn(
                        pos_recon=pos_recon,
                        pos_true=batch.pos,
                        edge_index=batch.edge_index,
                        batch=batch.batch,
                    )

                total_loss += losses["total_loss"].item()
                total_coord_loss += losses["coord_loss"].item()
                total_bond_loss += losses["bond_loss"].item()
                total_vdw_loss += losses.get("vdw_loss", torch.tensor(0.0)).item()
                total_temporal_loss += losses.get("temporal_loss", torch.tensor(0.0)).item()
                n_batches += 1

        result = {
            "total_loss": total_loss / n_batches,
            "coord_loss": total_coord_loss / n_batches,
            "bond_loss": total_bond_loss / n_batches,
        }
        if total_vdw_loss > 0:
            result["vdw_loss"] = total_vdw_loss / n_batches
        if total_temporal_loss > 0:
            result["temporal_loss"] = total_temporal_loss / n_batches

        return result

    def train(
        self,
        dataset: TrajectoryDataset,
        num_epochs: int = 100,
        batch_size: int = 4,
        val_split: float = 0.1,
        save_path: Optional[str] = None,
        early_stopping_patience: int = 10,
    ) -> Dict[str, list]:
        val_size = int(len(dataset) * val_split)
        train_size = len(dataset) - val_size
        train_dataset, val_dataset = random_split(
            dataset, [train_size, val_size], generator=torch.Generator().manual_seed(42)
        )

        train_loader = create_dataloader(
            train_dataset, batch_size=batch_size, shuffle=True
        )
        val_loader = create_dataloader(
            val_dataset, batch_size=batch_size, shuffle=False
        )

        best_val_loss = float("inf")
        patience_counter = 0

        for epoch in range(num_epochs):
            print(f"\nEpoch {epoch + 1}/{num_epochs}")

            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.validate(val_loader)

            self.train_losses.append(train_metrics)
            self.val_losses.append(val_metrics)

            self.scheduler.step(val_metrics["total_loss"])

            train_msg = f"Train Loss: {train_metrics['total_loss']:.6f} "
            train_msg += f"(coord: {train_metrics['coord_loss']:.6f}, "
            train_msg += f"bond: {train_metrics['bond_loss']:.6f}"
            if 'vdw_loss' in train_metrics:
                train_msg += f", vdw: {train_metrics['vdw_loss']:.6f}"
            if 'temporal_loss' in train_metrics:
                train_msg += f", temporal: {train_metrics['temporal_loss']:.6f}"
            train_msg += ")"
            print(train_msg)

            val_msg = f"Val Loss: {val_metrics['total_loss']:.6f} "
            val_msg += f"(coord: {val_metrics['coord_loss']:.6f}, "
            val_msg += f"bond: {val_metrics['bond_loss']:.6f}"
            if 'vdw_loss' in val_metrics:
                val_msg += f", vdw: {val_metrics['vdw_loss']:.6f}"
            if 'temporal_loss' in val_metrics:
                val_msg += f", temporal: {val_metrics['temporal_loss']:.6f}"
            val_msg += ")"
            print(val_msg)

            if val_metrics["total_loss"] < best_val_loss:
                best_val_loss = val_metrics["total_loss"]
                patience_counter = 0
                if save_path is not None:
                    extra_info = {
                        "mean": dataset.mean,
                        "std": dataset.std,
                        "atom_types": dataset.atom_types,
                        "n_atoms": dataset.n_atoms,
                        "train_losses": self.train_losses,
                        "val_losses": self.val_losses,
                    }
                    self.model.save_model(save_path, extra_info=extra_info)
                    print(f"Saved best model to {save_path}")
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    print(f"Early stopping after {epoch + 1} epochs")
                    break

        return {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
        }

    def finetune(
        self,
        dataset: TrajectoryDataset,
        num_epochs: int = 50,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
        freeze_encoder: bool = False,
        save_path: Optional[str] = None,
    ) -> Dict[str, list]:
        if freeze_encoder:
            for param in self.model.encoder.parameters():
                param.requires_grad = False

        for param_group in self.optimizer.param_groups:
            param_group["lr"] = learning_rate

        return self.train(
            dataset=dataset,
            num_epochs=num_epochs,
            batch_size=batch_size,
            save_path=save_path,
        )


def train_model(
    topology_file: str,
    trajectory_file: str,
    output_model_path: str,
    latent_dim: int = 32,
    hidden_dim: int = 128,
    encoder_layers: int = 3,
    decoder_layers: int = 3,
    gnn_type: str = "gcn",
    num_epochs: int = 100,
    batch_size: int = 4,
    learning_rate: float = 1e-3,
    selection: str = "protein",
    stride: int = 1,
    cutoff: float = 2.0,
    remove_pbc: bool = True,
    remove_transform: bool = True,
    use_mda_elements: bool = True,
    pretrained_model: Optional[str] = None,
    finetune: bool = False,
    freeze_encoder: bool = False,
    use_temporal_encoding: bool = True,
    temporal_hidden_dim: int = 64,
    num_lstm_layers: int = 2,
    bidirectional_lstm: bool = False,
    temporal_window: int = 10,
    use_vdw_constraint: bool = True,
    vdw_scale_factor: float = 0.9,
    vdw_penalty: float = 1.0,
    coord_weight: float = 1.0,
    bond_weight: float = 0.5,
    vdw_weight: float = 0.1,
    temporal_weight: float = 0.1,
    device: Optional[torch.device] = None,
) -> Tuple[TrajectoryAutoencoder, Dict]:
    device = device if device is not None else get_device()

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

    print(f"Dataset loaded: {len(dataset)} frames, {dataset.n_atoms} atoms")
    print(f"Compression ratio target: {3 / latent_dim:.2f}x")

    if pretrained_model is not None and os.path.exists(pretrained_model):
        print(f"Loading pretrained model from {pretrained_model}")
        model, extra_info = TrajectoryAutoencoder.load_model(pretrained_model, device)
        if finetune:
            print("Fine-tuning mode enabled")
    else:
        if use_temporal_encoding or use_vdw_constraint:
            print(f"Creating TemporalTrajectoryAutoencoder (VDW constraint: {use_vdw_constraint}, Temporal encoding: {use_temporal_encoding})")
            model = TemporalTrajectoryAutoencoder(
                atom_feature_dim=20,
                coord_dim=3,
                hidden_dim=hidden_dim,
                latent_dim=latent_dim,
                encoder_layers=encoder_layers,
                decoder_layers=decoder_layers,
                gnn_type=gnn_type,
                dropout=0.1,
                n_atoms=dataset.n_atoms,
                use_temporal_encoding=use_temporal_encoding,
                temporal_hidden_dim=temporal_hidden_dim,
                num_lstm_layers=num_lstm_layers,
                bidirectional_lstm=bidirectional_lstm,
                use_vdw_constraint=use_vdw_constraint,
                vdw_scale_factor=vdw_scale_factor,
                vdw_penalty=vdw_penalty,
            )
        else:
            print("Creating TrajectoryAutoencoder")
            model = TrajectoryAutoencoder(
                atom_feature_dim=20,
                coord_dim=3,
                hidden_dim=hidden_dim,
                latent_dim=latent_dim,
                encoder_layers=encoder_layers,
                decoder_layers=decoder_layers,
                gnn_type=gnn_type,
                dropout=0.1,
            )

    trainer = Trainer(
        model=model,
        device=device,
        learning_rate=learning_rate,
        coord_weight=coord_weight,
        bond_weight=bond_weight,
        vdw_weight=vdw_weight,
        temporal_weight=temporal_weight,
        temporal_window=temporal_window,
    )

    if finetune and pretrained_model is not None:
        history = trainer.finetune(
            dataset=dataset,
            num_epochs=num_epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            freeze_encoder=freeze_encoder,
            save_path=output_model_path,
        )
    else:
        history = trainer.train(
            dataset=dataset,
            num_epochs=num_epochs,
            batch_size=batch_size,
            save_path=output_model_path,
        )

    return model, history
