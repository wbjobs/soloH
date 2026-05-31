# MDCompress: Molecular Dynamics Trajectory Compression with GNNs

A command-line tool for compressing molecular dynamics (MD) trajectories using Graph Neural Networks (GNNs).

## Features

- **GNN-based Encoder-Decoder**: Uses graph neural networks to encode atomic coordinates into latent variables
- **Adjustable Compression Ratio**: Control compression via latent space dimension
- **Multiple Trajectory Formats**: Support for XTC and DCD formats
- **Comprehensive Evaluation**: RMSD, bond length deviation, and DSSP secondary structure retention
- **Batch Processing**: Multi-frame batch processing for efficiency
- **Incremental Training**: Fine-tune pre-trained models on new proteins

## Installation

```bash
pip install -e .
```

## Usage

### Train a model
```bash
mdcompress train --topology protein.pdb --trajectory traj.xtc --latent-dim 32 --output model.pt
```

### Compress a trajectory
```bash
mdcompress compress --topology protein.pdb --trajectory traj.xtc --model model.pt --output compressed.bin
```

### Decompress a trajectory
```bash
mdcompress decompress --topology protein.pdb --input compressed.bin --model model.pt --output reconstructed.xtc
```

### Evaluate compression quality
```bash
mdcompress evaluate --topology protein.pdb --original traj.xtc --reconstructed recon.xtc
```

### Incremental training (fine-tuning)
```bash
mdcompress train --topology new_protein.pdb --trajectory new_traj.xtc --pretrained-model existing_model.pt --output fine_tuned.pt --finetune
```
