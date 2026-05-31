import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, global_mean_pool, global_add_pool
from torch_geometric.data import Data, Batch
from typing import Tuple, Optional, List

ELEMENT_LIST = ["H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "Na", "K", "Mg", "Ca", "Zn", "Fe"]

VDW_RADIUS_TORCH = torch.tensor([
    1.20, 1.70, 1.55, 1.52, 1.80, 1.80, 1.47, 1.75,
    1.85, 1.98, 2.27, 2.75, 1.73, 2.31, 1.39, 1.63,
], dtype=torch.float64)


class GNNEncoder(nn.Module):
    def __init__(
        self,
        atom_feature_dim: int = 20,
        coord_dim: int = 3,
        hidden_dim: int = 128,
        latent_dim: int = 32,
        num_layers: int = 3,
        gnn_type: str = "gcn",
        dropout: float = 0.1,
    ):
        super().__init__()
        self.atom_feature_dim = atom_feature_dim
        self.coord_dim = coord_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.num_layers = num_layers
        self.gnn_type = gnn_type
        self.dropout = dropout

        input_dim = atom_feature_dim + coord_dim

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()

        for i in range(num_layers):
            in_dim = input_dim if i == 0 else hidden_dim
            if gnn_type == "gcn":
                self.convs.append(GCNConv(in_dim, hidden_dim))
            elif gnn_type == "gat":
                heads = 4 if i < num_layers - 1 else 1
                self.convs.append(GATConv(in_dim, hidden_dim // heads, heads=heads))
            else:
                raise ValueError(f"Unknown GNN type: {gnn_type}")
            self.norms.append(nn.LayerNorm(hidden_dim))

        self.latent_proj = nn.Linear(hidden_dim, latent_dim)
        self.dropout_layer = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        h = torch.cat([x, pos], dim=-1)

        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            h = conv(h, edge_index)
            h = norm(h)
            h = F.relu(h)
            h = self.dropout_layer(h)

        z = self.latent_proj(h)
        return z


class GraphDecoder(nn.Module):
    def __init__(
        self,
        latent_dim: int = 32,
        atom_feature_dim: int = 20,
        hidden_dim: int = 128,
        coord_dim: int = 3,
        num_layers: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.atom_feature_dim = atom_feature_dim
        self.hidden_dim = hidden_dim
        self.coord_dim = coord_dim
        self.num_layers = num_layers
        self.dropout = dropout

        input_dim = latent_dim + atom_feature_dim

        self.layers = nn.ModuleList()
        self.norms = nn.ModuleList()

        for i in range(num_layers):
            in_dim = input_dim if i == 0 else hidden_dim
            out_dim = hidden_dim if i < num_layers - 1 else coord_dim
            self.layers.append(nn.Linear(in_dim, out_dim))
            if i < num_layers - 1:
                self.norms.append(nn.LayerNorm(out_dim))

        self.dropout_layer = nn.Dropout(dropout)

    def forward(
        self,
        z: torch.Tensor,
        atom_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        h = torch.cat([z, atom_features], dim=-1)

        for i, layer in enumerate(self.layers):
            h = layer(h)
            if i < len(self.norms):
                h = self.norms[i](h)
                h = F.relu(h)
                h = self.dropout_layer(h)

        return h


class TrajectoryAutoencoder(nn.Module):
    def __init__(
        self,
        atom_feature_dim: int = 20,
        coord_dim: int = 3,
        hidden_dim: int = 128,
        latent_dim: int = 32,
        encoder_layers: int = 3,
        decoder_layers: int = 3,
        gnn_type: str = "gcn",
        dropout: float = 0.1,
    ):
        super().__init__()
        self.atom_feature_dim = atom_feature_dim
        self.coord_dim = coord_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.encoder_layers = encoder_layers
        self.decoder_layers = decoder_layers
        self.gnn_type = gnn_type
        self.dropout = dropout

        self.encoder = GNNEncoder(
            atom_feature_dim=atom_feature_dim,
            coord_dim=coord_dim,
            hidden_dim=hidden_dim,
            latent_dim=latent_dim,
            num_layers=encoder_layers,
            gnn_type=gnn_type,
            dropout=dropout,
        )

        self.decoder = GraphDecoder(
            latent_dim=latent_dim,
            atom_feature_dim=atom_feature_dim,
            hidden_dim=hidden_dim,
            coord_dim=coord_dim,
            num_layers=decoder_layers,
            dropout=dropout,
        )

    def encode(
        self,
        x: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        return self.encoder(x, pos, edge_index, batch)

    def decode(
        self,
        z: torch.Tensor,
        atom_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        return self.decoder(z, atom_features, batch)

    def forward(
        self,
        x: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x, pos, edge_index, batch)
        pos_recon = self.decode(z, x, batch)
        return pos_recon, z

    def get_compression_ratio(self, n_atoms: int) -> float:
        original_size = n_atoms * 3
        compressed_size = n_atoms * self.latent_dim
        return original_size / compressed_size

    def save_model(self, path: str, extra_info: Optional[dict] = None):
        state = {
            "model_state_dict": self.state_dict(),
            "config": {
                "atom_feature_dim": self.atom_feature_dim,
                "coord_dim": self.coord_dim,
                "hidden_dim": self.hidden_dim,
                "latent_dim": self.latent_dim,
                "encoder_layers": self.encoder_layers,
                "decoder_layers": self.decoder_layers,
                "gnn_type": self.gnn_type,
                "dropout": self.dropout,
            },
        }
        if extra_info is not None:
            state["extra_info"] = extra_info
        torch.save(state, path)

    @classmethod
    def load_model(cls, path: str, device: torch.device = torch.device("cpu")):
        checkpoint = torch.load(path, map_location=device)
        config = checkpoint["config"]
        model = cls(**config)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        extra_info = checkpoint.get("extra_info", {})
        return model, extra_info


class LossFunction(nn.Module):
    def __init__(
        self,
        coord_weight: float = 1.0,
        bond_weight: float = 0.5,
        use_high_precision: bool = True,
    ):
        super().__init__()
        self.coord_weight = coord_weight
        self.bond_weight = bond_weight
        self.use_high_precision = use_high_precision

    def forward(
        self,
        pos_recon: torch.Tensor,
        pos_true: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> dict:
        if self.use_high_precision:
            pos_recon_f64 = pos_recon.double()
            pos_true_f64 = pos_true.double()

            coord_diff = pos_recon_f64 - pos_true_f64
            coord_loss = torch.mean(coord_diff * coord_diff)
            coord_loss = coord_loss.float()

            if edge_index.size(1) > 0:
                src, dst = edge_index
                vec_recon = pos_recon_f64[src] - pos_recon_f64[dst]
                vec_true = pos_true_f64[src] - pos_true_f64[dst]

                bond_dist_recon = torch.sqrt(torch.sum(vec_recon * vec_recon, dim=-1) + 1e-12)
                bond_dist_true = torch.sqrt(torch.sum(vec_true * vec_true, dim=-1) + 1e-12)

                bond_diff = bond_dist_recon - bond_dist_true
                bond_loss = torch.mean(bond_diff * bond_diff)
                bond_loss = bond_loss.float()
            else:
                bond_loss = torch.tensor(0.0, device=pos_recon.device)
        else:
            coord_loss = F.mse_loss(pos_recon, pos_true)

            if edge_index.size(1) > 0:
                src, dst = edge_index
                bond_dist_recon = torch.norm(pos_recon[src] - pos_recon[dst], dim=-1)
                bond_dist_true = torch.norm(pos_true[src] - pos_true[dst], dim=-1)
                bond_loss = F.mse_loss(bond_dist_recon, bond_dist_true)
            else:
                bond_loss = torch.tensor(0.0, device=pos_recon.device)

        total_loss = self.coord_weight * coord_loss + self.bond_weight * bond_loss

        return {
            "total_loss": total_loss,
            "coord_loss": coord_loss,
            "bond_loss": bond_loss,
        }


class VDWConstraintLayer(nn.Module):
    def __init__(
        self,
        scale_factor: float = 0.9,
        conflict_penalty: float = 1.0,
        min_distance: float = 0.4,
        use_high_precision: bool = True,
    ):
        super().__init__()
        self.scale_factor = scale_factor
        self.conflict_penalty = conflict_penalty
        self.min_distance = min_distance
        self.use_high_precision = use_high_precision

    def get_vdw_radii(self, atom_features: torch.Tensor) -> torch.Tensor:
        n_atoms = atom_features.shape[0]
        elem_onehot = atom_features[:, :len(ELEMENT_LIST)]
        elem_indices = torch.argmax(elem_onehot, dim=-1)

        vdw_radii = VDW_RADIUS_TORCH.to(atom_features.device)
        radii = vdw_radii[elem_indices]
        return radii

    def forward(
        self,
        pos: torch.Tensor,
        atom_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.use_high_precision:
            pos_f64 = pos.double()
            radii = self.get_vdw_radii(atom_features).double()
        else:
            pos_f64 = pos.float()
            radii = self.get_vdw_radii(atom_features).float()

        n_atoms = pos_f64.shape[0]

        if batch is not None:
            unique_batches = torch.unique(batch)
            total_vdw_loss = torch.tensor(0.0, device=pos.device, dtype=torch.float32)
            corrected_pos = pos.clone()

            for b in unique_batches:
                mask = batch == b
                pos_b = pos_f64[mask]
                radii_b = radii[mask]
                n_atoms_b = pos_b.shape[0]

                if n_atoms_b < 2:
                    continue

                diff = pos_b.unsqueeze(1) - pos_b.unsqueeze(0)
                dist_sq = torch.sum(diff * diff, dim=-1)
                dist = torch.sqrt(dist_sq + 1e-12)

                sum_radii = radii_b.unsqueeze(1) + radii_b.unsqueeze(0)
                threshold = sum_radii * self.scale_factor

                eye_mask = ~torch.eye(n_atoms_b, dtype=torch.bool, device=pos.device)
                conflict_mask = (dist < threshold) & eye_mask

                if conflict_mask.any():
                    conflict_dist = torch.where(conflict_mask, dist, torch.zeros_like(dist))
                    target_dist = torch.where(conflict_mask, threshold, torch.zeros_like(dist))
                    vdw_loss = torch.sum(torch.square(conflict_dist - target_dist)) / 2.0
                    total_vdw_loss = total_vdw_loss + vdw_loss.float()

                    correction = torch.zeros_like(pos_b)
                    for i in range(n_atoms_b):
                        for j in range(i + 1, n_atoms_b):
                            if conflict_mask[i, j]:
                                vec = pos_b[j] - pos_b[i]
                                current_dist = dist[i, j]
                                if current_dist < self.min_distance:
                                    current_dist = self.min_distance
                                push_dir = vec / current_dist
                                push_amount = (threshold[i, j] - current_dist) / 2.0
                                correction[i] = correction[i] - push_dir * push_amount
                                correction[j] = correction[j] + push_dir * push_amount

                    corrected_pos[mask] = (pos_b + correction).float()

            return corrected_pos, total_vdw_loss * self.conflict_penalty

        else:
            if n_atoms < 2:
                return pos, torch.tensor(0.0, device=pos.device, dtype=torch.float32)

            diff = pos_f64.unsqueeze(1) - pos_f64.unsqueeze(0)
            dist_sq = torch.sum(diff * diff, dim=-1)
            dist = torch.sqrt(dist_sq + 1e-12)

            sum_radii = radii.unsqueeze(1) + radii.unsqueeze(0)
            threshold = sum_radii * self.scale_factor

            eye_mask = ~torch.eye(n_atoms, dtype=torch.bool, device=pos.device)
            conflict_mask = (dist < threshold) & eye_mask

            if not conflict_mask.any():
                return pos, torch.tensor(0.0, device=pos.device, dtype=torch.float32)

            conflict_dist = torch.where(conflict_mask, dist, torch.zeros_like(dist))
            target_dist = torch.where(conflict_mask, threshold, torch.zeros_like(dist))
            vdw_loss = torch.sum(torch.square(conflict_dist - target_dist)) / 2.0

            correction = torch.zeros_like(pos_f64)
            for i in range(n_atoms):
                for j in range(i + 1, n_atoms):
                    if conflict_mask[i, j]:
                        vec = pos_f64[j] - pos_f64[i]
                        current_dist = dist[i, j]
                        if current_dist < self.min_distance:
                            current_dist = self.min_distance
                        push_dir = vec / current_dist
                        push_amount = (threshold[i, j] - current_dist) / 2.0
                        correction[i] = correction[i] - push_dir * push_amount
                        correction[j] = correction[j] + push_dir * push_amount

            corrected_pos = (pos_f64 + correction).float()
            return corrected_pos, vdw_loss.float() * self.conflict_penalty


class LSTMTemporalEncoder(nn.Module):
    def __init__(
        self,
        latent_dim: int = 32,
        n_atoms: int = 100,
        temporal_hidden_dim: int = 64,
        num_lstm_layers: int = 2,
        bidirectional: bool = False,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.n_atoms = n_atoms
        self.temporal_hidden_dim = temporal_hidden_dim
        self.num_lstm_layers = num_lstm_layers
        self.bidirectional = bidirectional
        self.dropout = dropout

        self.per_atom_latent_dim = latent_dim
        self.frame_latent_dim = n_atoms * latent_dim

        self.lstm = nn.LSTM(
            input_size=self.frame_latent_dim,
            hidden_size=temporal_hidden_dim,
            num_layers=num_lstm_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_lstm_layers > 1 else 0.0,
        )

        self.direction_factor = 2 if bidirectional else 1
        self.temporal_compressed_dim = temporal_hidden_dim * self.direction_factor

        self.output_proj = nn.Linear(
            self.temporal_compressed_dim,
            self.frame_latent_dim,
        )

        self.dropout_layer = nn.Dropout(dropout)

    def forward(
        self,
        z_sequence: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, seq_len, n_atoms, latent_dim = z_sequence.shape

        z_flat = z_sequence.reshape(batch_size, seq_len, -1)

        lstm_out, (h_n, c_n) = self.lstm(z_flat)

        if self.bidirectional:
            h_forward = h_n[-2]
            h_backward = h_n[-1]
            h_combined = torch.cat([h_forward, h_backward], dim=-1)
        else:
            h_combined = h_n[-1]

        temporal_summary = self.dropout_layer(h_combined)
        z_reconstructed_flat = self.output_proj(lstm_out)
        z_reconstructed = z_reconstructed_flat.reshape(batch_size, seq_len, n_atoms, latent_dim)

        return z_reconstructed, temporal_summary

    def encode_sequence(
        self,
        z_sequence: torch.Tensor,
    ) -> torch.Tensor:
        batch_size, seq_len, n_atoms, latent_dim = z_sequence.shape
        z_flat = z_sequence.reshape(batch_size, seq_len, -1)
        _, (h_n, _) = self.lstm(z_flat)

        if self.bidirectional:
            h_forward = h_n[-2]
            h_backward = h_n[-1]
            h_combined = torch.cat([h_forward, h_backward], dim=-1)
        else:
            h_combined = h_n[-1]

        return h_combined


class TemporalTrajectoryAutoencoder(TrajectoryAutoencoder):
    def __init__(
        self,
        atom_feature_dim: int = 20,
        coord_dim: int = 3,
        hidden_dim: int = 128,
        latent_dim: int = 32,
        encoder_layers: int = 3,
        decoder_layers: int = 3,
        gnn_type: str = "gcn",
        dropout: float = 0.1,
        n_atoms: int = 100,
        use_temporal_encoding: bool = True,
        temporal_hidden_dim: int = 64,
        num_lstm_layers: int = 2,
        bidirectional_lstm: bool = False,
        use_vdw_constraint: bool = True,
        vdw_scale_factor: float = 0.9,
        vdw_penalty: float = 1.0,
    ):
        super().__init__(
            atom_feature_dim=atom_feature_dim,
            coord_dim=coord_dim,
            hidden_dim=hidden_dim,
            latent_dim=latent_dim,
            encoder_layers=encoder_layers,
            decoder_layers=decoder_layers,
            gnn_type=gnn_type,
            dropout=dropout,
        )

        self.n_atoms = n_atoms
        self.use_temporal_encoding = use_temporal_encoding
        self.use_vdw_constraint = use_vdw_constraint

        if use_temporal_encoding:
            self.temporal_encoder = LSTMTemporalEncoder(
                latent_dim=latent_dim,
                n_atoms=n_atoms,
                temporal_hidden_dim=temporal_hidden_dim,
                num_lstm_layers=num_lstm_layers,
                bidirectional=bidirectional_lstm,
                dropout=dropout,
            )

        if use_vdw_constraint:
            self.vdw_layer = VDWConstraintLayer(
                scale_factor=vdw_scale_factor,
                conflict_penalty=vdw_penalty,
                use_high_precision=True,
            )

    def decode(
        self,
        z: torch.Tensor,
        atom_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        pos_recon = self.decoder(z, atom_features, batch)
        vdw_loss = torch.tensor(0.0, device=pos_recon.device)

        if self.use_vdw_constraint:
            pos_recon, vdw_loss = self.vdw_layer(pos_recon, atom_features, batch)

        return pos_recon, vdw_loss

    def forward(
        self,
        x: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
        z_sequence: Optional[torch.Tensor] = None,
    ) -> dict:
        if self.use_temporal_encoding and z_sequence is not None:
            z_refined, temporal_summary = self.temporal_encoder(z_sequence)
            batch_size, seq_len, n_atoms, latent_dim = z_refined.shape
            z_refined_flat = z_refined.reshape(batch_size * seq_len * n_atoms, latent_dim)

            x_expanded = x.unsqueeze(0).unsqueeze(0).expand(batch_size, seq_len, -1, -1)
            x_flat = x_expanded.reshape(batch_size * seq_len * n_atoms, -1)

            pos_recon, vdw_loss = self.decode(z_refined_flat, x_flat, batch)
            pos_recon = pos_recon.reshape(batch_size, seq_len, n_atoms, 3)

            return {
                "pos_recon": pos_recon,
                "z_refined": z_refined,
                "temporal_summary": temporal_summary,
                "vdw_loss": vdw_loss,
            }
        else:
            z = self.encode(x, pos, edge_index, batch)
            pos_recon, vdw_loss = self.decode(z, x, batch)

            return {
                "pos_recon": pos_recon,
                "z": z,
                "vdw_loss": vdw_loss,
            }

    def save_model(self, path: str, extra_info: Optional[dict] = None):
        state = {
            "model_state_dict": self.state_dict(),
            "config": {
                "atom_feature_dim": self.atom_feature_dim,
                "coord_dim": self.coord_dim,
                "hidden_dim": self.hidden_dim,
                "latent_dim": self.latent_dim,
                "encoder_layers": self.encoder_layers,
                "decoder_layers": self.decoder_layers,
                "gnn_type": self.gnn_type,
                "dropout": self.dropout,
                "n_atoms": self.n_atoms,
                "use_temporal_encoding": self.use_temporal_encoding,
                "temporal_hidden_dim": getattr(self, 'temporal_encoder', None) and self.temporal_encoder.temporal_hidden_dim,
                "num_lstm_layers": getattr(self, 'temporal_encoder', None) and self.temporal_encoder.num_lstm_layers,
                "bidirectional_lstm": getattr(self, 'temporal_encoder', None) and self.temporal_encoder.bidirectional,
                "use_vdw_constraint": self.use_vdw_constraint,
                "vdw_scale_factor": getattr(self, 'vdw_layer', None) and self.vdw_layer.scale_factor,
                "vdw_penalty": getattr(self, 'vdw_layer', None) and self.vdw_layer.conflict_penalty,
            },
        }
        if extra_info is not None:
            state["extra_info"] = extra_info
        torch.save(state, path)

    @classmethod
    def load_model(cls, path: str, device: torch.device = torch.device("cpu")):
        checkpoint = torch.load(path, map_location=device)
        config = checkpoint["config"]
        if config.get("use_temporal_encoding") or config.get("use_vdw_constraint"):
            model = cls(**config)
        else:
            model = TrajectoryAutoencoder(
                atom_feature_dim=config["atom_feature_dim"],
                coord_dim=config["coord_dim"],
                hidden_dim=config["hidden_dim"],
                latent_dim=config["latent_dim"],
                encoder_layers=config["encoder_layers"],
                decoder_layers=config["decoder_layers"],
                gnn_type=config["gnn_type"],
                dropout=config["dropout"],
            )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        extra_info = checkpoint.get("extra_info", {})
        return model, extra_info


class TemporalLossFunction(LossFunction):
    def __init__(
        self,
        coord_weight: float = 1.0,
        bond_weight: float = 0.5,
        vdw_weight: float = 0.1,
        temporal_weight: float = 0.1,
        use_high_precision: bool = True,
    ):
        super().__init__(
            coord_weight=coord_weight,
            bond_weight=bond_weight,
            use_high_precision=use_high_precision,
        )
        self.vdw_weight = vdw_weight
        self.temporal_weight = temporal_weight

    def forward(
        self,
        model_output: dict,
        pos_true: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> dict:
        pos_recon = model_output["pos_recon"]
        vdw_loss = model_output.get("vdw_loss", torch.tensor(0.0, device=pos_recon.device))

        if len(pos_recon.shape) == 4:
            batch_size, seq_len, n_atoms, _ = pos_recon.shape
            pos_recon_flat = pos_recon.reshape(batch_size * seq_len * n_atoms, 3)
            pos_true_flat = pos_true.reshape(batch_size * seq_len * n_atoms, 3)
        else:
            pos_recon_flat = pos_recon
            pos_true_flat = pos_true

        base_losses = super().forward(
            pos_recon_flat, pos_true_flat, edge_index, batch
        )

        temporal_loss = torch.tensor(0.0, device=pos_recon.device)
        if len(pos_recon.shape) == 4 and seq_len > 1:
            pos_true_f64 = pos_true.double()
            pos_recon_f64 = pos_recon.double()
            vel_true = pos_true_f64[:, 1:] - pos_true_f64[:, :-1]
            vel_recon = pos_recon_f64[:, 1:] - pos_recon_f64[:, :-1]
            temporal_loss = torch.mean((vel_true - vel_recon) ** 2).float()

        total_loss = (
            base_losses["total_loss"]
            + self.vdw_weight * vdw_loss
            + self.temporal_weight * temporal_loss
        )

        return {
            "total_loss": total_loss,
            "coord_loss": base_losses["coord_loss"],
            "bond_loss": base_losses["bond_loss"],
            "vdw_loss": vdw_loss,
            "temporal_loss": temporal_loss,
        }
