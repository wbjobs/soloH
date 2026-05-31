import unittest
import numpy as np
import torch
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mdcompress.utils import (
    normalize_coords,
    denormalize_coords,
    compute_rmsd,
    kabsch_alignment,
    build_bond_list,
    atom_type_to_feature,
    center_coords,
    remove_pbc_wrapping,
    remove_translation_rotation,
    get_element_from_atom_name,
    compute_bond_length,
    compute_bond_lengths_batch,
    get_atom_feature_dim,
    ELEMENT_LIST,
)
from mdcompress.model import (
    TrajectoryAutoencoder,
    TemporalTrajectoryAutoencoder,
    VDWConstraintLayer,
    LSTMTemporalEncoder,
    LossFunction,
    TemporalLossFunction,
)
from mdcompress.utils import compute_rmsf, compute_rmsf_preservation, get_vdw_radius
from mdcompress.compress import CompressedData, save_compressed, load_compressed


class TestUtils(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_normalize_denormalize(self):
        coords = np.random.rand(10, 5, 3).astype(np.float32) * 10
        normalized, mean, std = normalize_coords(coords)
        denormalized = denormalize_coords(normalized, mean, std)
        np.testing.assert_allclose(coords, denormalized, rtol=1e-5)

    def test_center_coords(self):
        coords = np.random.rand(5, 3).astype(np.float32) * 10
        centered, center = center_coords(coords)
        np.testing.assert_allclose(centered.mean(axis=0), [0, 0, 0], atol=1e-6)

    def test_kabsch_alignment(self):
        coords = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
        ], dtype=np.float32)
        theta = np.pi / 4
        R = np.array([
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ], dtype=np.float32)
        rotated = coords @ R.T
        R_recovered, _, _ = kabsch_alignment(rotated, coords)
        rotated_centered, _ = center_coords(rotated)
        coords_centered, _ = center_coords(coords)
        aligned = rotated_centered @ R_recovered
        diff = aligned - coords_centered
        rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
        self.assertLess(rmsd, 1e-5)

    def test_compute_rmsd(self):
        coords1 = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
        ], dtype=np.float32)
        coords2 = coords1 + np.array([0.1, 0.0, 0.0], dtype=np.float32)
        rmsd = compute_rmsd(coords1, coords2)
        self.assertAlmostEqual(rmsd, 0.0, places=5)

        coords2_permuted = np.array([
            [0.1, 0, 0],
            [1.1, 0, 0],
            [0.1, 1, 0.1],
        ], dtype=np.float32)
        rmsd = compute_rmsd(coords1, coords2_permuted)
        self.assertLess(rmsd, 0.1)

    def test_build_bond_list(self):
        coords = np.array([
            [0, 0, 0],
            [1.5, 0, 0],
            [3, 0, 0],
        ], dtype=np.float32)
        atom_types = ["C", "C", "C"]
        edges, edge_attr = build_bond_list(atom_types, coords, cutoff=2.0)
        self.assertEqual(edges.shape[0], 2)
        self.assertEqual(edges.shape[1], 4)

    def test_atom_type_to_feature_new_dimension(self):
        feat_dim = get_atom_feature_dim()
        self.assertEqual(feat_dim, 20)

        feat_C = atom_type_to_feature("CA")
        self.assertEqual(feat_C.shape, (20,))
        self.assertEqual(feat_C[ELEMENT_LIST.index("C")], 1)

        feat_N = atom_type_to_feature("N")
        self.assertEqual(feat_N[ELEMENT_LIST.index("N")], 1)

        feat_H = atom_type_to_feature("H")
        self.assertEqual(feat_H[ELEMENT_LIST.index("H")], 1)

        self.assertAlmostEqual(feat_C[16], 12.011 / 100.0, places=6)
        self.assertAlmostEqual(feat_C[17], 0.0, places=6)
        self.assertAlmostEqual(feat_C[18], 1.0, places=6)
        self.assertAlmostEqual(feat_C[19], 1.0, places=6)

    def test_get_element_from_atom_name_forcefields(self):
        test_cases = [
            ("CA", "C", "AMBER alpha carbon", None),
            ("CB", "C", "AMBER beta carbon", None),
            ("CG", "C", "AMBER gamma carbon", None),
            ("N", "N", "Backbone nitrogen", None),
            ("H", "H", "Hydrogen", None),
            ("HA", "H", "Alpha hydrogen", None),
            ("OW", "O", "TIP3P water oxygen", None),
            ("HW", "H", "TIP3P water hydrogen", None),
            ("SG", "S", "Cysteine sulfur", None),
            ("P", "P", "Phosphate", None),
            ("NA", "Na", "Sodium ion", "NA"),
            ("K", "K", "Potassium ion", "K"),
            ("MG", "Mg", "Magnesium", "MG"),
            ("CAL", "Ca", "Calcium ion (CAL)", None),
            ("CA2", "Ca", "Calcium ion (CA2)", None),
            ("CL", "Cl", "Chloride", "CL"),
            ("ZN", "Zn", "Zinc", "ZN"),
            ("FE", "Fe", "Iron", "FE"),
            ("BR", "Br", "Bromine", "BR"),
            ("I", "I", "Iodine", None),
            ("F", "F", "Fluorine", None),
            ("1H", "H", "GROMOS hydrogen", None),
            ("C12", "C", "CHARMM carbon", None),
            ("NH1", "N", "AMBER arginine nitrogen", None),
            ("OD1", "O", "AMBER aspartate oxygen", None),
            ("OG", "O", "AMBER serine oxygen", None),
            ("CA", "C", "Alpha carbon in ALA", "ALA"),
            ("CA", "C", "Alpha carbon in GLY", "GLY"),
            ("NA", "Na", "Sodium ion (non-protein residue)", "NA"),
        ]

        for atom_name, expected_element, description, residue_name in test_cases:
            detected = get_element_from_atom_name(atom_name, residue_name)
            self.assertEqual(
                detected, expected_element,
                f"Failed for {description}: {atom_name} (res={residue_name}) -> {detected}, expected {expected_element}"
            )

    def test_atom_type_to_feature_with_element(self):
        feat1 = atom_type_to_feature("CA", element="C", mass=12.011)
        feat2 = atom_type_to_feature("1H", element="H", mass=1.008)
        self.assertEqual(feat1[ELEMENT_LIST.index("C")], 1)
        self.assertEqual(feat2[ELEMENT_LIST.index("H")], 1)

    def test_remove_pbc_wrapping(self):
        n_frames = 10
        n_atoms = 3
        box_size = 10.0

        coords = np.zeros((n_frames, n_atoms, 3), dtype=np.float32)
        coords[0] = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3]], dtype=np.float32)

        for i in range(1, n_frames):
            coords[i] = coords[i-1] + 0.5

        wrapped = coords.copy()
        for i in range(n_frames):
            for atom_idx in range(n_atoms):
                for dim in range(3):
                    if wrapped[i, atom_idx, dim] > box_size:
                        wrapped[i, atom_idx, dim] -= box_size

        boxes = [np.array([box_size, box_size, box_size], dtype=np.float32)] * n_frames

        unwrapped = remove_pbc_wrapping(wrapped, boxes)

        diff = unwrapped[-1] - unwrapped[0]
        expected_diff = np.array([[4.5, 4.5, 4.5]] * n_atoms, dtype=np.float32)

        np.testing.assert_allclose(diff, expected_diff, atol=0.1)

    def test_remove_translation_rotation(self):
        n_frames = 5
        n_atoms = 3

        base_coords = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
        ], dtype=np.float32)

        coords = np.tile(base_coords, (n_frames, 1, 1)).reshape(n_frames, n_atoms, 3)

        for i in range(1, n_frames):
            coords[i] += np.array([i * 0.5, 0, 0], dtype=np.float32)
            theta = i * 0.1
            R = np.array([
                [np.cos(theta), -np.sin(theta), 0],
                [np.sin(theta), np.cos(theta), 0],
                [0, 0, 1],
            ], dtype=np.float32)
            coords[i] = (coords[i] - coords[i].mean(axis=0)) @ R + coords[i].mean(axis=0)

        aligned, transforms = remove_translation_rotation(coords)

        for i in range(n_frames):
            rmsd = compute_rmsd(aligned[i], aligned[0])
            self.assertLess(rmsd, 0.01)

    def test_high_precision_bond_length(self):
        coords = np.array([
            [0, 0, 0],
            [1.23456789, 0, 0],
        ], dtype=np.float32)

        length_low = np.float32(np.linalg.norm(coords[1] - coords[0]))
        length_high = compute_bond_length(coords, 0, 1)

        self.assertIsInstance(length_high, float)
        self.assertAlmostEqual(length_high, 1.23456789, places=6)

    def test_compute_bond_lengths_batch(self):
        n_frames = 5
        coords = np.zeros((n_frames, 4, 3), dtype=np.float32)
        for i in range(n_frames):
            coords[i] = np.array([
                [i * 0.1, 0, 0],
                [1 + i * 0.1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
            ])

        bond_pairs = [(0, 1), (1, 2), (0, 2)]
        lengths = compute_bond_lengths_batch(coords, bond_pairs)

        self.assertEqual(lengths.shape, (n_frames, 3))

        expected_bond0 = np.array([1.0] * n_frames, dtype=np.float64)
        np.testing.assert_allclose(lengths[:, 0], expected_bond0, atol=1e-6)

    def test_get_vdw_radius(self):
        self.assertAlmostEqual(get_vdw_radius("H"), 1.20, places=2)
        self.assertAlmostEqual(get_vdw_radius("C"), 1.70, places=2)
        self.assertAlmostEqual(get_vdw_radius("O"), 1.52, places=2)
        self.assertAlmostEqual(get_vdw_radius("N"), 1.55, places=2)

    def test_compute_rmsf(self):
        n_frames = 10
        n_atoms = 3
        coords = np.zeros((n_frames, n_atoms, 3), dtype=np.float64)

        mean_pos = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]], dtype=np.float64)
        for i in range(n_frames):
            coords[i] = mean_pos + np.random.randn(3, 3) * 0.1

        rmsf = compute_rmsf(coords)
        self.assertEqual(rmsf.shape, (n_atoms,))
        self.assertTrue(np.all(rmsf >= 0))
        self.assertAlmostEqual(rmsf[0], 0.1 * np.sqrt(3), delta=0.05)

    def test_compute_rmsf_preservation(self):
        n_atoms = 10
        rmsf_true = np.random.rand(n_atoms) * 0.5 + 0.1
        rmsf_pred = rmsf_true + np.random.randn(n_atoms) * 0.01

        result = compute_rmsf_preservation(rmsf_true, rmsf_pred)
        self.assertIn("correlation", result)
        self.assertIn("mae", result)
        self.assertIn("mean_relative_error_percent", result)
        self.assertIn("mean_ratio", result)

        self.assertGreater(result["correlation"], 0.9)
        self.assertLess(result["mae"], 0.1)
        self.assertGreater(result["mean_ratio"], 0.8)
        self.assertLess(result["mean_ratio"], 1.2)


class TestModel(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.model = TrajectoryAutoencoder(
            atom_feature_dim=20,
            coord_dim=3,
            hidden_dim=64,
            latent_dim=16,
            encoder_layers=2,
            decoder_layers=2,
            gnn_type="gcn",
            dropout=0.0,
        )

    def test_forward_pass(self):
        batch_size = 2
        n_atoms = 5
        x = torch.randn(batch_size * n_atoms, 20)
        pos = torch.randn(batch_size * n_atoms, 3)
        edge_index = torch.tensor([
            [0, 1, 1, 0, 2, 3, 3, 2, 5, 6, 6, 5, 7, 8, 8, 7],
            [1, 0, 2, 2, 3, 2, 4, 4, 6, 5, 7, 7, 8, 7, 9, 9],
        ], dtype=torch.long)
        batch = torch.repeat_interleave(torch.arange(batch_size), n_atoms)

        pos_recon, z = self.model(x, pos, edge_index, batch)
        self.assertEqual(pos_recon.shape, (batch_size * n_atoms, 3))
        self.assertEqual(z.shape, (batch_size * n_atoms, 16))

    def test_loss_function_high_precision(self):
        loss_fn = LossFunction(use_high_precision=True)
        pos_recon = torch.randn(10, 3)
        pos_true = torch.randn(10, 3)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)

        losses = loss_fn(pos_recon, pos_true, edge_index)
        self.assertIn("total_loss", losses)
        self.assertIn("coord_loss", losses)
        self.assertIn("bond_loss", losses)
        self.assertGreater(losses["total_loss"].item(), 0)

    def test_loss_function_low_precision(self):
        loss_fn = LossFunction(use_high_precision=False)
        pos_recon = torch.randn(10, 3)
        pos_true = torch.randn(10, 3)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)

        losses = loss_fn(pos_recon, pos_true, edge_index)
        self.assertIn("total_loss", losses)
        self.assertIn("coord_loss", losses)
        self.assertIn("bond_loss", losses)
        self.assertGreater(losses["total_loss"].item(), 0)

    def test_model_default_feature_dim(self):
        model_default = TrajectoryAutoencoder()
        self.assertEqual(model_default.atom_feature_dim, 20)

    def test_save_load_model(self):
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            temp_path = f.name
        try:
            self.model.save_model(temp_path, extra_info={"test": "value"})
            loaded_model, extra_info = TrajectoryAutoencoder.load_model(temp_path)
            self.assertEqual(extra_info["test"], "value")
            self.assertEqual(loaded_model.latent_dim, self.model.latent_dim)

            for p1, p2 in zip(self.model.parameters(), loaded_model.parameters()):
                self.assertTrue(torch.allclose(p1, p2))
        finally:
            os.unlink(temp_path)

    def test_compression_ratio(self):
        n_atoms = 100
        ratio = self.model.get_compression_ratio(n_atoms)
        expected = 3 / 16
        self.assertAlmostEqual(ratio, expected, places=5)


class TestCompressedData(unittest.TestCase):
    def test_save_load_compressed(self):
        n_frames = 5
        n_atoms = 10
        latent_dim = 16

        latent_vectors = np.random.randn(n_frames, n_atoms, latent_dim).astype(np.float32)
        mean = np.array([1.0, 2.0, 3.0])
        std = np.array([0.5, 0.5, 0.5])
        atom_types = ["C", "N", "O", "H", "C", "C", "N", "O", "H", "C"]

        data = CompressedData(
            latent_vectors=latent_vectors,
            mean=mean,
            std=std,
            atom_types=atom_types,
            n_atoms=n_atoms,
            n_frames=n_frames,
            latent_dim=latent_dim,
        )

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            temp_path = f.name
        try:
            save_compressed(data, temp_path)
            loaded = load_compressed(temp_path)

            self.assertEqual(loaded.n_frames, n_frames)
            self.assertEqual(loaded.n_atoms, n_atoms)
            self.assertEqual(loaded.latent_dim, latent_dim)
            np.testing.assert_allclose(loaded.mean, mean)
            np.testing.assert_allclose(loaded.std, std)
            self.assertEqual(loaded.atom_types, atom_types)
            np.testing.assert_allclose(loaded.latent_vectors, latent_vectors)
        finally:
            os.unlink(temp_path)

    def test_compression_stats(self):
        n_frames = 100
        n_atoms = 50
        latent_dim = 8

        latent_vectors = np.random.randn(n_frames, n_atoms, latent_dim).astype(np.float32)
        mean = np.zeros(3)
        std = np.ones(3)
        atom_types = ["C"] * n_atoms

        data = CompressedData(
            latent_vectors=latent_vectors,
            mean=mean,
            std=std,
            atom_types=atom_types,
            n_atoms=n_atoms,
            n_frames=n_frames,
            latent_dim=latent_dim,
        )

        stats = data.get_compression_stats()
        self.assertEqual(stats["n_frames"], n_frames)
        self.assertEqual(stats["n_atoms"], n_atoms)
        self.assertEqual(stats["latent_dim"], latent_dim)
        self.assertGreater(stats["compression_ratio"], 0)


class TestVDWConstraintLayer(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.vdw_layer = VDWConstraintLayer(
            scale_factor=0.9,
            conflict_penalty=1.0,
            use_high_precision=True,
        )

    def test_vdw_radii_extraction(self):
        n_atoms = 4
        features = torch.zeros(n_atoms, 20)
        features[0, 0] = 1
        features[1, 1] = 1
        features[2, 3] = 1
        features[3, 2] = 1

        radii = self.vdw_layer.get_vdw_radii(features)
        self.assertEqual(radii.shape, (n_atoms,))
        self.assertAlmostEqual(radii[0].item(), 1.20, places=2)
        self.assertAlmostEqual(radii[1].item(), 1.70, places=2)
        self.assertAlmostEqual(radii[2].item(), 1.52, places=2)
        self.assertAlmostEqual(radii[3].item(), 1.55, places=2)

    def test_vdw_conflict_detection_and_correction(self):
        n_atoms = 2
        features = torch.zeros(n_atoms, 20)
        features[0, 1] = 1
        features[1, 1] = 1

        pos = torch.tensor([
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
        ], dtype=torch.float32)

        corrected_pos, vdw_loss = self.vdw_layer(pos, features)

        self.assertGreater(vdw_loss.item(), 0)

        dist_before = torch.norm(pos[0] - pos[1]).item()
        dist_after = torch.norm(corrected_pos[0] - corrected_pos[1]).item()
        self.assertGreater(dist_after, dist_before)

        expected_min_dist = (1.70 + 1.70) * 0.9
        self.assertGreaterEqual(dist_after, expected_min_dist * 0.95)

    def test_vdw_no_conflict(self):
        n_atoms = 2
        features = torch.zeros(n_atoms, 20)
        features[0, 1] = 1
        features[1, 1] = 1

        pos = torch.tensor([
            [0.0, 0.0, 0.0],
            [5.0, 0.0, 0.0],
        ], dtype=torch.float32)

        corrected_pos, vdw_loss = self.vdw_layer(pos, features)

        self.assertEqual(vdw_loss.item(), 0.0)
        torch.testing.assert_close(corrected_pos, pos)


class TestLSTMTemporalEncoder(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.n_atoms = 10
        self.latent_dim = 16
        self.temporal_encoder = LSTMTemporalEncoder(
            latent_dim=self.latent_dim,
            n_atoms=self.n_atoms,
            temporal_hidden_dim=32,
            num_lstm_layers=2,
            bidirectional=False,
            dropout=0.0,
        )

    def test_forward_pass(self):
        batch_size = 2
        seq_len = 5

        z_sequence = torch.randn(
            batch_size, seq_len, self.n_atoms, self.latent_dim
        )

        z_refined, temporal_summary = self.temporal_encoder(z_sequence)

        self.assertEqual(z_refined.shape, (batch_size, seq_len, self.n_atoms, self.latent_dim))
        self.assertEqual(temporal_summary.shape, (batch_size, 32))

    def test_encode_sequence(self):
        batch_size = 2
        seq_len = 5

        z_sequence = torch.randn(
            batch_size, seq_len, self.n_atoms, self.latent_dim
        )

        summary = self.temporal_encoder.encode_sequence(z_sequence)
        self.assertEqual(summary.shape, (batch_size, 32))

    def test_bidirectional(self):
        bi_encoder = LSTMTemporalEncoder(
            latent_dim=self.latent_dim,
            n_atoms=self.n_atoms,
            temporal_hidden_dim=32,
            num_lstm_layers=2,
            bidirectional=True,
            dropout=0.0,
        )

        batch_size = 2
        seq_len = 5
        z_sequence = torch.randn(
            batch_size, seq_len, self.n_atoms, self.latent_dim
        )

        z_refined, temporal_summary = bi_encoder(z_sequence)
        self.assertEqual(temporal_summary.shape, (batch_size, 64))


class TestTemporalTrajectoryAutoencoder(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.n_atoms = 5
        self.model = TemporalTrajectoryAutoencoder(
            atom_feature_dim=20,
            coord_dim=3,
            hidden_dim=64,
            latent_dim=8,
            encoder_layers=2,
            decoder_layers=2,
            gnn_type="gcn",
            dropout=0.0,
            n_atoms=self.n_atoms,
            use_temporal_encoding=True,
            temporal_hidden_dim=32,
            num_lstm_layers=1,
            bidirectional_lstm=False,
            use_vdw_constraint=True,
            vdw_scale_factor=0.9,
            vdw_penalty=1.0,
        )

    def test_forward_single_frame(self):
        n_atoms = 5
        x = torch.randn(n_atoms, 20)
        pos = torch.randn(n_atoms, 3)
        edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long)

        output = self.model(x, pos, edge_index)

        self.assertIn("pos_recon", output)
        self.assertIn("z", output)
        self.assertIn("vdw_loss", output)
        self.assertEqual(output["pos_recon"].shape, (n_atoms, 3))
        self.assertEqual(output["z"].shape, (n_atoms, 8))

    def test_forward_temporal(self):
        batch_size = 1
        seq_len = 3
        n_atoms = 5

        x = torch.randn(n_atoms, 20)
        pos = torch.randn(n_atoms, 3)
        edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long)

        z_single = self.model.encode(x, pos, edge_index)
        z_sequence = z_single.unsqueeze(0).unsqueeze(0).expand(batch_size, seq_len, -1, -1)

        output = self.model(x, pos, edge_index, z_sequence=z_sequence)

        self.assertIn("pos_recon", output)
        self.assertIn("z_refined", output)
        self.assertIn("temporal_summary", output)
        self.assertIn("vdw_loss", output)
        self.assertEqual(output["pos_recon"].shape, (batch_size, seq_len, n_atoms, 3))
        self.assertEqual(output["z_refined"].shape, (batch_size, seq_len, n_atoms, 8))

    def test_save_load_temporal_model(self):
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            temp_path = f.name
        try:
            self.model.save_model(temp_path, extra_info={"test": "temporal"})
            loaded_model, extra_info = TemporalTrajectoryAutoencoder.load_model(temp_path)

            self.assertEqual(extra_info["test"], "temporal")
            self.assertTrue(hasattr(loaded_model, 'use_vdw_constraint'))
            self.assertTrue(hasattr(loaded_model, 'use_temporal_encoding'))

            for p1, p2 in zip(self.model.parameters(), loaded_model.parameters()):
                self.assertTrue(torch.allclose(p1, p2, atol=1e-5))
        finally:
            os.unlink(temp_path)


class TestTemporalLossFunction(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.loss_fn = TemporalLossFunction(
            coord_weight=1.0,
            bond_weight=0.5,
            vdw_weight=0.1,
            temporal_weight=0.1,
            use_high_precision=True,
        )

    def test_loss_with_vdw(self):
        n_atoms = 4
        pos_recon = torch.randn(n_atoms, 3)
        pos_true = torch.randn(n_atoms, 3)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)

        model_output = {
            "pos_recon": pos_recon,
            "vdw_loss": torch.tensor(0.5),
        }

        losses = self.loss_fn(model_output, pos_true, edge_index)

        self.assertIn("total_loss", losses)
        self.assertIn("coord_loss", losses)
        self.assertIn("bond_loss", losses)
        self.assertIn("vdw_loss", losses)
        self.assertIn("temporal_loss", losses)

        self.assertGreater(losses["total_loss"].item(), 0)
        self.assertAlmostEqual(losses["vdw_loss"].item(), 0.5, places=5)
        self.assertAlmostEqual(losses["temporal_loss"].item(), 0.0, places=5)

    def test_loss_with_temporal(self):
        batch_size = 1
        seq_len = 4
        n_atoms = 3

        pos_true = torch.randn(batch_size, seq_len, n_atoms, 3)
        pos_recon = pos_true + torch.randn_like(pos_true) * 0.1
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)

        model_output = {
            "pos_recon": pos_recon,
            "vdw_loss": torch.tensor(0.0),
        }

        losses = self.loss_fn(model_output, pos_true, edge_index)

        self.assertIn("temporal_loss", losses)
        self.assertGreater(losses["temporal_loss"].item(), 0)

        weighted_temporal = 0.1 * losses["temporal_loss"].item()
        self.assertGreater(losses["total_loss"].item(), weighted_temporal)
        self.assertGreater(losses["total_loss"].item(), losses["coord_loss"].item())


if __name__ == "__main__":
    unittest.main()
