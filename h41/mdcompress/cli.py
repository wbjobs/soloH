import argparse
import sys
import os
import json
from typing import Optional

from .utils import get_device
from .model import TrajectoryAutoencoder
from .train import train_model
from .compress import (
    compress_trajectory,
    decompress_trajectory,
    load_compressed,
)
from .evaluate import evaluate_trajectories, print_evaluation_report


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdcompress",
        description="Molecular Dynamics trajectory compression using Graph Neural Networks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train a new model
  mdcompress train --topology protein.pdb --trajectory traj.xtc --latent-dim 32 --output model.pt

  # Compress a trajectory
  mdcompress compress --topology protein.pdb --trajectory traj.xtc --model model.pt --output compressed.bin

  # Decompress a trajectory
  mdcompress decompress --topology protein.pdb --input compressed.bin --model model.pt --output recon.xtc

  # Evaluate compression quality
  mdcompress evaluate --topology protein.pdb --original traj.xtc --reconstructed recon.xtc

  # Incremental training (fine-tuning)
  mdcompress train --topology new_protein.pdb --trajectory new_traj.xtc --pretrained-model existing.pt --output fine_tuned.pt --finetune
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    train_parser = subparsers.add_parser("train", help="Train a new model or fine-tune an existing one")
    _add_train_arguments(train_parser)

    compress_parser = subparsers.add_parser("compress", help="Compress a trajectory using a trained model")
    _add_compress_arguments(compress_parser)

    decompress_parser = subparsers.add_parser("decompress", help="Decompress a trajectory")
    _add_decompress_arguments(decompress_parser)

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate compression quality")
    _add_evaluate_arguments(evaluate_parser)

    info_parser = subparsers.add_parser("info", help="Get information about compressed file or model")
    _add_info_arguments(info_parser)

    return parser


def _add_train_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--topology", "-t", required=True, help="Topology file (PDB, PRMTOP, etc.)")
    parser.add_argument("--trajectory", "-T", required=True, help="Trajectory file (XTC, DCD)")
    parser.add_argument("--output", "-o", required=True, help="Output model file (.pt)")

    model_group = parser.add_argument_group("Model configuration")
    model_group.add_argument("--latent-dim", type=int, default=32, help="Latent space dimension (controls compression ratio)")
    model_group.add_argument("--hidden-dim", type=int, default=128, help="Hidden layer dimension")
    model_group.add_argument("--encoder-layers", type=int, default=3, help="Number of GNN encoder layers")
    model_group.add_argument("--decoder-layers", type=int, default=3, help="Number of decoder layers")
    model_group.add_argument("--gnn-type", choices=["gcn", "gat"], default="gcn", help="GNN convolution type")

    constraint_group = parser.add_argument_group("Chemical constraints")
    constraint_group.add_argument("--no-vdw-constraint", action="store_true", help="Disable VDW conflict avoidance layer")
    constraint_group.add_argument("--vdw-scale-factor", type=float, default=0.9, help="VDW radius scale factor for conflict detection")
    constraint_group.add_argument("--vdw-penalty", type=float, default=1.0, help="Weight for VDW conflict loss")

    temporal_group = parser.add_argument_group("Temporal compression")
    temporal_group.add_argument("--no-temporal-encoding", action="store_true", help="Disable LSTM temporal encoding")
    temporal_group.add_argument("--temporal-hidden-dim", type=int, default=64, help="LSTM hidden dimension for temporal encoding")
    temporal_group.add_argument("--num-lstm-layers", type=int, default=2, help="Number of LSTM layers")
    temporal_group.add_argument("--bidirectional-lstm", action="store_true", help="Use bidirectional LSTM")
    temporal_group.add_argument("--temporal-window", type=int, default=10, help="Number of frames in temporal window for LSTM")

    train_group = parser.add_argument_group("Training configuration")
    train_group.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    train_group.add_argument("--batch-size", type=int, default=4, help="Batch size")
    train_group.add_argument("--learning-rate", type=float, default=1e-3, help="Learning rate")
    train_group.add_argument("--selection", default="protein", help="Atom selection string (MDAnalysis format)")
    train_group.add_argument("--stride", type=int, default=1, help="Trajectory frame stride")
    train_group.add_argument("--cutoff", type=float, default=2.0, help="Graph construction cutoff (Angstrom)")

    preprocess_group = parser.add_argument_group("Preprocessing options")
    preprocess_group.add_argument("--no-remove-pbc", action="store_true", help="Disable PBC wrapping removal")
    preprocess_group.add_argument("--no-remove-transform", action="store_true", help="Disable translation/rotation removal")
    preprocess_group.add_argument("--no-use-mda-elements", action="store_true", help="Do not use MDAnalysis element detection")

    finetune_group = parser.add_argument_group("Fine-tuning / Incremental training")
    finetune_group.add_argument("--pretrained-model", help="Path to pretrained model for fine-tuning")
    finetune_group.add_argument("--finetune", action="store_true", help="Enable fine-tuning mode")
    finetune_group.add_argument("--freeze-encoder", action="store_true", help="Freeze encoder weights during fine-tuning")

    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Device to use (auto-detect if not specified)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def _add_compress_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--topology", "-t", required=True, help="Topology file (PDB, PRMTOP, etc.)")
    parser.add_argument("--trajectory", "-T", required=True, help="Input trajectory file (XTC, DCD)")
    parser.add_argument("--model", "-m", required=True, help="Trained model file (.pt)")
    parser.add_argument("--output", "-o", required=True, help="Output compressed binary file (.bin)")

    parser.add_argument("--selection", default="protein", help="Atom selection string")
    parser.add_argument("--stride", type=int, default=1, help="Trajectory frame stride")
    parser.add_argument("--cutoff", type=float, default=2.0, help="Graph construction cutoff (Angstrom)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for compression")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Device to use")
    parser.add_argument("--no-remove-pbc", action="store_true", help="Disable PBC wrapping removal")
    parser.add_argument("--no-remove-transform", action="store_true", help="Disable translation/rotation removal")
    parser.add_argument("--no-use-mda-elements", action="store_true", help="Do not use MDAnalysis element detection")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def _add_decompress_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--topology", "-t", required=True, help="Topology file (PDB, PRMTOP, etc.)")
    parser.add_argument("--input", "-i", required=True, help="Input compressed binary file (.bin)")
    parser.add_argument("--model", "-m", required=True, help="Trained model file (.pt)")
    parser.add_argument("--output", "-o", required=True, help="Output trajectory file (.xtc, .dcd, .pdb)")

    parser.add_argument("--selection", default="protein", help="Atom selection string")
    parser.add_argument("--cutoff", type=float, default=2.0, help="Graph construction cutoff (Angstrom)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for decompression")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Device to use")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def _add_evaluate_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--topology", "-t", required=True, help="Topology file (PDB, PRMTOP, etc.)")
    parser.add_argument("--original", "-O", required=True, help="Original trajectory file")
    parser.add_argument("--reconstructed", "-r", required=True, help="Reconstructed trajectory file")

    parser.add_argument("--selection", default="protein", help="Atom selection string")
    parser.add_argument("--stride", type=int, default=1, help="Trajectory frame stride")
    parser.add_argument("--no-ss", action="store_true", help="Skip secondary structure analysis")
    parser.add_argument("--no-rmsf", action="store_true", help="Skip RMSF preservation analysis")
    parser.add_argument("--no-remove-pbc", action="store_true", help="Disable PBC wrapping removal")
    parser.add_argument("--no-remove-transform", action="store_true", help="Disable translation/rotation removal")
    parser.add_argument("--use-relative-dev", action="store_true", help="Use relative bond deviation (%)")
    parser.add_argument("--output-json", help="Save evaluation results to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")


def _add_info_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("--input", "-i", required=True, help="Input file (compressed .bin or model .pt)")
    parser.add_argument("--output-json", help="Save info to JSON file")


def _get_device(device_arg: Optional[str] = None):
    if device_arg:
        import torch
        return torch.device(device_arg)
    return get_device()


def cmd_train(args: argparse.Namespace):
    device = _get_device(args.device)
    print(f"Using device: {device}")

    use_temporal = not args.no_temporal_encoding
    use_vdw = not args.no_vdw_constraint

    print(f"Temporal encoding: {'Enabled' if use_temporal else 'Disabled'}")
    print(f"VDW constraint: {'Enabled' if use_vdw else 'Disabled'}")

    model, history = train_model(
        topology_file=args.topology,
        trajectory_file=args.trajectory,
        output_model_path=args.output,
        latent_dim=args.latent_dim,
        hidden_dim=args.hidden_dim,
        encoder_layers=args.encoder_layers,
        decoder_layers=args.decoder_layers,
        gnn_type=args.gnn_type,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        selection=args.selection,
        stride=args.stride,
        cutoff=args.cutoff,
        remove_pbc=not args.no_remove_pbc,
        remove_transform=not args.no_remove_transform,
        use_mda_elements=not args.no_use_mda_elements,
        pretrained_model=args.pretrained_model,
        finetune=args.finetune,
        freeze_encoder=args.freeze_encoder,
        use_temporal_encoding=use_temporal,
        temporal_hidden_dim=args.temporal_hidden_dim,
        num_lstm_layers=args.num_lstm_layers,
        bidirectional_lstm=args.bidirectional_lstm,
        temporal_window=args.temporal_window,
        use_vdw_constraint=use_vdw,
        vdw_scale_factor=args.vdw_scale_factor,
        vdw_penalty=args.vdw_penalty,
        device=device,
    )

    print(f"\nTraining complete. Model saved to {args.output}")
    return 0


def cmd_compress(args: argparse.Namespace):
    device = _get_device(args.device)
    print(f"Using device: {device}")

    print(f"Loading model from {args.model}")
    model, extra_info = TrajectoryAutoencoder.load_model(args.model, device)

    print(f"Compressing trajectory {args.trajectory}")
    compressed_data = compress_trajectory(
        topology_file=args.topology,
        trajectory_file=args.trajectory,
        model=model,
        output_file=args.output,
        selection=args.selection,
        stride=args.stride,
        cutoff=args.cutoff,
        remove_pbc=not args.no_remove_pbc,
        remove_transform=not args.no_remove_transform,
        use_mda_elements=not args.no_use_mda_elements,
        batch_size=args.batch_size,
        device=device,
        model_extra_info=extra_info,
    )

    stats = compressed_data.get_compression_stats()
    print("\n=== Compression Statistics ===")
    print(f"Frames: {stats['n_frames']}")
    print(f"Atoms: {stats['n_atoms']}")
    print(f"Latent dim: {stats['latent_dim']}")
    print(f"Original size: {stats['original_size_bytes'] / 1024 / 1024:.2f} MB")
    print(f"Compressed size: {stats['compressed_size_bytes'] / 1024 / 1024:.2f} MB")
    print(f"Compression ratio: {stats['compression_ratio']:.2f}x")
    print(f"\nCompressed data saved to {args.output}")

    return 0


def cmd_decompress(args: argparse.Namespace):
    device = _get_device(args.device)
    print(f"Using device: {device}")

    print(f"Loading model from {args.model}")
    model, _ = TrajectoryAutoencoder.load_model(args.model, device)

    print(f"Decompressing {args.input} to {args.output}")
    recon_coords = decompress_trajectory(
        input_file=args.input,
        model=model,
        topology_file=args.topology,
        output_trajectory=args.output,
        selection=args.selection,
        cutoff=args.cutoff,
        batch_size=args.batch_size,
        device=device,
    )

    print(f"Decompression complete. Output saved to {args.output}")
    return 0


def cmd_evaluate(args: argparse.Namespace):
    print(f"Evaluating: {args.original} vs {args.reconstructed}")

    result = evaluate_trajectories(
        topology_file=args.topology,
        original_trajectory=args.original,
        reconstructed_trajectory=args.reconstructed,
        selection=args.selection,
        stride=args.stride,
        compute_ss=not args.no_ss,
        compute_rmsf=not args.no_rmsf,
        remove_pbc=not args.no_remove_pbc,
        remove_transform=not args.no_remove_transform,
        use_relative_dev=args.use_relative_dev,
    )

    print_evaluation_report(result)

    if args.output_json:
        import json
        serializable_result = {
            "n_frames": result["n_frames"],
            "n_atoms": result["n_atoms"],
            "rmsd": {
                "mean": result["rmsd"]["mean"],
                "std": result["rmsd"]["std"],
                "median": result["rmsd"]["median"],
                "min": result["rmsd"]["min"],
                "max": result["rmsd"]["max"],
                "per_frame": result["rmsd"]["per_frame"],
            },
            "bond_deviation": {
                "mean_bond_deviation": result["bond_deviation"]["mean_bond_deviation"],
                "std_bond_deviation": result["bond_deviation"]["std_bond_deviation"],
                "max_bond_deviation": result["bond_deviation"]["max_bond_deviation"],
                "median_bond_deviation": result["bond_deviation"]["median_bond_deviation"],
                "n_bonds": result["bond_deviation"]["n_bonds"],
            },
        }
        if "secondary_structure" in result and "overall_ss_retention" in result["secondary_structure"]:
            serializable_result["secondary_structure"] = {
                "overall_ss_retention": result["secondary_structure"]["overall_ss_retention"],
                "class_retention": result["secondary_structure"]["class_retention"],
            }
        with open(args.output_json, "w") as f:
            json.dump(serializable_result, f, indent=2)
        print(f"\nResults saved to {args.output_json}")

    return 0


def cmd_info(args: argparse.Namespace):
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return 1

    ext = os.path.splitext(input_path)[1].lower()

    info = {}

    if ext == ".bin":
        print(f"Analyzing compressed file: {input_path}")
        try:
            compressed_data = load_compressed(input_path)
            stats = compressed_data.get_compression_stats()
            info = {
                "type": "compressed_trajectory",
                "n_frames": stats["n_frames"],
                "n_atoms": stats["n_atoms"],
                "latent_dim": stats["latent_dim"],
                "original_size_mb": stats["original_size_bytes"] / 1024 / 1024,
                "compressed_size_mb": stats["compressed_size_bytes"] / 1024 / 1024,
                "compression_ratio": stats["compression_ratio"],
                "mean": compressed_data.mean.tolist(),
                "std": compressed_data.std.tolist(),
                "atom_types": compressed_data.atom_types,
            }
        except Exception as e:
            print(f"Error reading compressed file: {e}")
            return 1

    elif ext == ".pt":
        print(f"Analyzing model file: {input_path}")
        try:
            import torch
            checkpoint = torch.load(input_path, map_location="cpu")
            config = checkpoint["config"]
            extra = checkpoint.get("extra_info", {})

            info = {
                "type": "model",
                "config": config,
                "n_atoms": extra.get("n_atoms", "N/A"),
                "atom_types": extra.get("atom_types", "N/A"),
            }
        except Exception as e:
            print(f"Error reading model file: {e}")
            return 1
    else:
        print(f"Unsupported file type: {ext}")
        return 1

    print("\n=== File Information ===")
    for key, value in info.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        elif isinstance(value, list) and len(value) > 20:
            print(f"{key}: {value[:5]}... (total {len(value)} items)")
        else:
            print(f"{key}: {value}")

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(info, f, indent=2)
        print(f"\nInfo saved to {args.output_json}")

    return 0


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

    commands = {
        "train": cmd_train,
        "compress": cmd_compress,
        "decompress": cmd_decompress,
        "evaluate": cmd_evaluate,
        "info": cmd_info,
    }

    try:
        return commands[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
