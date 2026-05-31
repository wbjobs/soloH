import os
import argparse
from typing import Optional


def parse_args():
    parser = argparse.ArgumentParser(
        description='LiDAR Point Cloud Tree Segmentation and Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single file
  python -m lidar_tree_tool.main --input input.ply --output output_dir --model model.pth

  # Batch process a directory
  python -m lidar_tree_tool.main --input ./data --output ./results --model model.pth --batch

  # Only preprocess
  python -m lidar_tree_tool.main --input input.ply --output output_dir --preprocess-only

  # Visualize results
  python -m lidar_tree_tool.main --input labeled.ply --visualize

  # Skip segmentation (if labels already exist)
  python -m lidar_tree_tool.main --input input_with_labels.ply --output output_dir --skip-segmentation
        """
    )

    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Input point cloud file or directory')
    parser.add_argument('--output', '-o', type=str, default='./output',
                        help='Output directory (default: ./output)')
    parser.add_argument('--model', '-m', type=str, default=None,
                        help='Path to trained PointNet++ model weights')

    parser.add_argument('--batch', action='store_true',
                        help='Batch process all files in input directory')
    parser.add_argument('--file-pattern', type=str, default='*.ply,*.las,*.laz',
                        help='File pattern for batch processing (default: *.ply,*.las,*.laz)')

    parser.add_argument('--preprocess-only', action='store_true',
                        help='Only run preprocessing, skip segmentation and extraction')
    parser.add_argument('--skip-segmentation', action='store_true',
                        help='Skip segmentation (use existing labels in input file)')
    parser.add_argument('--skip-extraction', action='store_true',
                        help='Skip individual tree extraction')

    parser.add_argument('--ground-filter', type=str, default='csf',
                        choices=['csf', 'simple', 'none'],
                        help='Ground filtering method (default: csf)')
    parser.add_argument('--cloth-resolution', type=float, default=0.5,
                        help='Cloth resolution for CSF (default: 0.5)')
    parser.add_argument('--rigidness', type=int, default=3,
                        help='Rigidness for CSF (default: 3)')
    parser.add_argument('--class-threshold', type=float, default=0.5,
                        help='Classification threshold for ground filtering (default: 0.5)')

    parser.add_argument('--downsample', type=float, default=0.05,
                        help='Voxel downsample size, 0 to disable (default: 0.05)')
    parser.add_argument('--normalize-height', action='store_true', default=True,
                        help='Normalize point height to ground (default: True)')

    parser.add_argument('--normalize-density', action='store_true', default=False,
                        help='Normalize point cloud density to fix near-dense/far-sparse issue (default: False)')
    parser.add_argument('--density-method', type=str, default='adaptive',
                        choices=['voxel', 'adaptive', 'distance'],
                        help='Density normalization method (default: adaptive)')
    parser.add_argument('--voxel-size-density', type=float, default=0.1,
                        help='Voxel size for voxel-based density normalization (default: 0.1)')
    parser.add_argument('--max-points-per-voxel', type=int, default=5,
                        help='Max points per voxel for density normalization (default: 5)')
    parser.add_argument('--target-avg-distance', type=float, default=0.05,
                        help='Target average point distance for adaptive density normalization (default: 0.05)')
    parser.add_argument('--density-k', type=int, default=10,
                        help='K neighbors for adaptive density normalization (default: 10)')

    parser.add_argument('--use-geometric-features', action='store_true', default=False,
                        help='Use multi-scale geometric features for better generalization across tree species (default: False)')
    parser.add_argument('--num-geometric-features', type=int, default=32,
                        help='Number of geometric features (4 scales * 8 features = 32) (default: 32)')

    parser.add_argument('--complete-trunk', action='store_true', default=False,
                        help='Complete hollow trunk geometry caused by occlusion (default: False)')
    parser.add_argument('--trunk-method', type=str, default='cylinder',
                        choices=['cylinder', 'morphological', 'hybrid'],
                        help='Trunk completion method (default: cylinder)')
    parser.add_argument('--min-trunk-height', type=float, default=1.3,
                        help='Minimum trunk height for completion (default: 1.3m)')
    parser.add_argument('--max-trunk-radius', type=float, default=0.5,
                        help='Maximum trunk radius for fitting (default: 0.5m)')
    parser.add_argument('--morph-kernel', type=int, default=3,
                        help='Kernel size for morphological trunk completion (default: 3)')
    parser.add_argument('--morph-iterations', type=int, default=2,
                        help='Iterations for morphological trunk completion (default: 2)')

    parser.add_argument('--model-arch', type=str, default='pointnet2',
                        choices=['pointnet2', 'gcn'],
                        help='Model architecture (default: pointnet2)')
    parser.add_argument('--num-classes', type=int, default=5,
                        help='Number of segmentation classes (default: 5)')
    parser.add_argument('--use-rgb', action='store_true', default=True,
                        help='Use RGB features (default: True)')
    parser.add_argument('--use-normal', action='store_true', default=False,
                        help='Use normal features (default: False)')
    parser.add_argument('--batch-size', type=int, default=4096,
                        help='Batch size for segmentation inference (default: 4096)')
    parser.add_argument('--vote-sampling', type=int, default=0,
                        help='Number of vote samples for full point cloud inference, 0 to disable (default: 0)')

    parser.add_argument('--cluster-method', type=str, default='dbscan',
                        choices=['dbscan', 'horizontal'],
                        help='Tree clustering method (default: dbscan)')
    parser.add_argument('--min-points', type=int, default=50,
                        help='Minimum points for DBSCAN clustering (default: 50)')
    parser.add_argument('--distance-threshold', type=float, default=0.5,
                        help='Distance threshold for DBSCAN (default: 0.5)')
    parser.add_argument('--min-tree-points', type=int, default=100,
                        help='Minimum points per tree (default: 100)')
    parser.add_argument('--leaf-area-per-point', type=float, default=0.01,
                        help='Leaf area per point estimate (default: 0.01)')

    parser.add_argument('--visualize', action='store_true',
                        help='Visualize segmentation results')
    parser.add_argument('--visualize-instances', action='store_true',
                        help='Visualize individual tree instances')
    parser.add_argument('--no-show-ground', action='store_true',
                        help='Hide ground points in visualization')
    parser.add_argument('--leaf-alpha', type=float, default=0.5,
                        help='Transparency of leaf points (default: 0.5)')
    parser.add_argument('--render-image', action='store_true',
                        help='Render visualization to image file')

    parser.add_argument('--save-intermediate', action='store_true',
                        help='Save intermediate processing results')
    parser.add_argument('--device', type=str, default='auto',
                        choices=['auto', 'cpu', 'cuda'],
                        help='Device for inference (default: auto)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    return parser.parse_args()


def get_device(device_str: str) -> str:
    import torch
    if device_str == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    return device_str


def load_trained_model(model_path: str, args):
    from .pointnet2 import PointNet2SemSeg
    import torch

    if model_path is None or not os.path.exists(model_path):
        print(f"Warning: Model file not found: {model_path}")
        return None

    device = get_device(args.device)
    print(f"Loading model from {model_path} to {device}...")

    if args.model_arch == 'pointnet2':
        model = PointNet2SemSeg(
            num_classes=args.num_classes,
            use_rgb=args.use_rgb,
            use_normal=args.use_normal,
            use_geometric=args.use_geometric_features,
            num_geometric_features=args.num_geometric_features
        )
    else:
        print("GCN model loading not implemented yet")
        return None

    try:
        state_dict = torch.load(model_path, map_location=device)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        print("Model loaded successfully")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None


def process_single_file(args):
    import numpy as np
    from .data_io import load_point_cloud
    from .preprocessing import preprocess_pipeline
    from .pointnet2 import predict_segmentation, predict_segmentation_full
    from .tree_extraction import extract_individual_trees, save_metrics_csv
    from .visualization import visualize_segmentation, visualize_instances

    print(f"\n{'='*60}")
    print(f"Processing: {args.input}")
    print(f"{'='*60}")

    os.makedirs(args.output, exist_ok=True)
    device = get_device(args.device)

    print(f"\n[1/4] Loading point cloud...")
    data = load_point_cloud(args.input)
    print(f"  Loaded {data.num_points} points")
    if data.colors is not None:
        print(f"  Color data available: {data.colors.shape}")
    if data.labels is not None:
        print(f"  Existing labels found: {np.bincount(data.labels, minlength=5)}")

    print(f"\n[2/4] Preprocessing...")
    ground_filter_method = None if args.ground_filter == 'none' else args.ground_filter
    preprocess_kwargs = {
        'downsample_voxel': args.downsample,
        'ground_filter_method': ground_filter_method,
        'normalize': args.normalize_height,
        'normalize_density': args.normalize_density,
        'density_method': args.density_method,
        'voxel_size': args.voxel_size_density,
        'max_points_per_voxel': args.max_points_per_voxel,
        'k': args.density_k,
        'target_avg_distance': args.target_avg_distance,
        'cloth_resolution': args.cloth_resolution,
        'rigidness': args.rigidness,
        'class_threshold': args.class_threshold,
    }
    processed_data = preprocess_pipeline(data, **preprocess_kwargs)
    print(f"  Preprocessed: {processed_data.num_points} points remaining")
    print(f"  Ground removed: {processed_data.ground_removed}")
    print(f"  Height normalized: {processed_data.height_normalized}")
    if args.normalize_density:
        print(f"  Density normalized: {args.density_method} method")

    if args.save_intermediate:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        preprocessed_path = os.path.join(args.output, f"{base_name}_preprocessed.ply")
        processed_data.save(preprocessed_path, save_labels=False)
        print(f"  Saved preprocessed data to: {preprocessed_path}")

    if args.preprocess_only:
        print("\nPreprocessing only mode - skipping segmentation and extraction")
        return

    if not args.skip_segmentation:
        print(f"\n[3/4] Running segmentation...")
        model = load_trained_model(args.model, args)

        if model is not None:
            if args.vote_sampling > 0:
                labels = predict_segmentation_full(
                    model,
                    processed_data.points,
                    processed_data.colors,
                    processed_data.normals,
                    num_samples=args.vote_sampling,
                    use_geometric_features=args.use_geometric_features,
                    device=device
                )
            else:
                labels = predict_segmentation(
                    model,
                    processed_data.points,
                    processed_data.colors,
                    processed_data.normals,
                    batch_size=args.batch_size,
                    use_geometric_features=args.use_geometric_features,
                    device=device
                )
            processed_data.labels = labels

            label_counts = np.bincount(labels, minlength=5)
            print(f"  Segmentation complete:")
            print(f"    Ground: {label_counts[0]} points")
            print(f"    Trunk: {label_counts[1]} points")
            print(f"    Large branch: {label_counts[2]} points")
            print(f"    Small branch: {label_counts[3]} points")
            print(f"    Leaf: {label_counts[4]} points")

        else:
            print("  Warning: No model available, skipping segmentation")
            if processed_data.labels is None:
                print("  No existing labels found, cannot continue")
                return
    else:
        print(f"\n[3/4] Skipping segmentation (using existing labels)")
        if processed_data.labels is None:
            print("  Error: No labels found in input file!")
            return

    if args.complete_trunk and processed_data.labels is not None:
        from .enhancement import complete_trunk_geometry
        print(f"\n[3.5/4] Completing trunk geometry...")
        trunk_kwargs = {
            'min_height': args.min_trunk_height,
            'max_radius': args.max_trunk_radius,
            'kernel_size': args.morph_kernel,
            'iterations': args.morph_iterations,
        }
        processed_data = complete_trunk_geometry(
            processed_data,
            method=args.trunk_method,
            **trunk_kwargs
        )
        label_counts = np.bincount(processed_data.labels, minlength=5)
        print(f"  After trunk completion:")
        print(f"    Trunk: {label_counts[1]} points")

    base_name = os.path.splitext(os.path.basename(args.input))[0]
    labeled_path = os.path.join(args.output, f"{base_name}_labeled.ply")
    processed_data.save(labeled_path, save_labels=True)
    print(f"  Saved labeled point cloud to: {labeled_path}")

    instance_labels = None
    if not args.skip_extraction and processed_data.labels is not None:
        print(f"\n[4/4] Extracting individual trees...")
        extraction_kwargs = {
            'method': args.cluster_method,
            'min_points': args.min_points,
            'distance_threshold': args.distance_threshold,
            'min_tree_points': args.min_tree_points,
            'leaf_area_per_point': args.leaf_area_per_point,
        }

        tree_metrics, tree_ids, instance_labels = extract_individual_trees(
            processed_data, **extraction_kwargs
        )
        print(f"  Found {len(tree_metrics)} trees")

        metrics_path = os.path.join(args.output, f"{base_name}_metrics.csv")
        save_metrics_csv(tree_metrics, metrics_path)
        print(f"  Saved tree metrics to: {metrics_path}")

        if len(tree_metrics) > 0:
            print("\n  Tree metrics summary:")
            print(f"    Average height: {np.mean([m.tree_height for m in tree_metrics]):.2f}m")
            print(f"    Average crown width: {np.mean([m.crown_width for m in tree_metrics]):.2f}m")
            print(f"    Average LAI: {np.mean([m.lai for m in tree_metrics]):.2f}")
            print(f"    Average DBH: {np.mean([m.dbh for m in tree_metrics]):.2f}m")

    if args.visualize and processed_data.labels is not None:
        print("\nVisualizing segmentation results...")
        show_ground = not args.no_show_ground
        visualize_segmentation(
            processed_data,
            leaf_alpha=args.leaf_alpha,
            use_original_colors=False,
            show_ground=show_ground
        )

    if args.visualize_instances and instance_labels is not None:
        print("\nVisualizing individual trees...")
        visualize_instances(processed_data, instance_labels)

    if args.render_image and processed_data.labels is not None:
        from .visualization import render_to_image
        img_path = os.path.join(args.output, f"{base_name}_render.png")
        show_ground = not args.no_show_ground
        try:
            render_to_image(
                processed_data,
                img_path,
                leaf_alpha=args.leaf_alpha,
                show_ground=show_ground
            )
            print(f"  Rendered image to: {img_path}")
        except Exception as e:
            print(f"  Warning: Could not render image: {e}")

    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"{'='*60}\n")


def process_batch(args):
    from .batch_processing import BatchProcessor
    from .tree_extraction import merge_metrics_csv

    print(f"\n{'='*60}")
    print(f"Batch Processing Mode")
    print(f"{'='*60}")
    print(f"Input directory: {args.input}")
    print(f"Output directory: {args.output}")

    os.makedirs(args.output, exist_ok=True)
    device = get_device(args.device)

    model = load_trained_model(args.model, args) if not args.skip_segmentation and not args.preprocess_only else None

    processor = BatchProcessor(
        input_dir=args.input,
        output_dir=args.output,
        model=model,
        file_pattern=args.file_pattern,
        device=device
    )

    preprocess_kwargs = {
        'downsample_voxel': args.downsample,
        'ground_filter_method': None if args.ground_filter == 'none' else args.ground_filter,
        'normalize': args.normalize_height,
        'normalize_density': args.normalize_density,
        'density_method': args.density_method,
        'voxel_size': args.voxel_size_density,
        'max_points_per_voxel': args.max_points_per_voxel,
        'k': args.density_k,
        'target_avg_distance': args.target_avg_distance,
        'cloth_resolution': args.cloth_resolution,
        'rigidness': args.rigidness,
        'class_threshold': args.class_threshold,
    }

    segmentation_kwargs = {
        'batch_size': args.batch_size,
        'normalize': True,
        'use_geometric_features': args.use_geometric_features,
    } if not args.skip_segmentation else None

    extraction_kwargs = {
        'method': args.cluster_method,
        'min_points': args.min_points,
        'distance_threshold': args.distance_threshold,
        'min_tree_points': args.min_tree_points,
        'leaf_area_per_point': args.leaf_area_per_point,
        'complete_trunk': args.complete_trunk,
        'trunk_method': args.trunk_method,
        'min_trunk_height': args.min_trunk_height,
        'max_trunk_radius': args.max_trunk_radius,
        'morph_kernel': args.morph_kernel,
        'morph_iterations': args.morph_iterations,
    } if not args.skip_extraction else None

    if args.preprocess_only:
        segmentation_kwargs = None
        extraction_kwargs = None

    if args.skip_extraction:
        extraction_kwargs = None

    summary_df = processor.process_all(
        preprocess_kwargs=preprocess_kwargs,
        segmentation_kwargs=segmentation_kwargs,
        extraction_kwargs=extraction_kwargs,
        save_intermediate=args.save_intermediate,
        generate_visualization=args.render_image
    )

    if not args.skip_extraction and not args.preprocess_only:
        merge_metrics_csv(args.output)

    print(f"\n{'='*60}")
    print("Batch processing complete!")
    print(f"{'='*60}\n")


def main():
    args = parse_args()

    if args.verbose:
        print(f"Arguments: {args}")

    if not os.path.exists(args.input):
        print(f"Error: Input path does not exist: {args.input}")
        return

    if args.batch or os.path.isdir(args.input):
        process_batch(args)
    else:
        process_single_file(args)


if __name__ == '__main__':
    main()
