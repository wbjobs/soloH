import os
import glob
import numpy as np
import pandas as pd
from tqdm import tqdm
from typing import List, Dict, Tuple, Optional, Callable
from .data_io import PointCloudData, load_point_cloud, save_ply, save_las
from .preprocessing import preprocess_pipeline
from .pointnet2 import PointNet2SemSeg, predict_segmentation
from .tree_extraction import extract_individual_trees, save_metrics_csv, TreeMetrics
from .visualization import save_visualization, render_to_image


class BatchProcessor:
    def __init__(self,
                 input_dir: str,
                 output_dir: str,
                 model: Optional[PointNet2SemSeg] = None,
                 file_pattern: str = "*.ply,*.las,*.laz",
                 device: str = 'cpu'):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.model = model
        self.device = device
        self.file_patterns = file_pattern.split(',')

        self.results_summary = []

    def find_files(self) -> List[str]:
        all_files = []
        for pattern in self.file_patterns:
            pattern = pattern.strip()
            search_path = os.path.join(self.input_dir, '**', pattern)
            files = glob.glob(search_path, recursive=True)
            all_files.extend(files)
        return sorted(all_files)

    def process_single_file(self, filepath: str,
                            preprocess_kwargs: Optional[Dict] = None,
                            segmentation_kwargs: Optional[Dict] = None,
                            extraction_kwargs: Optional[Dict] = None,
                            save_intermediate: bool = False,
                            generate_visualization: bool = True) -> Dict:
        result = {
            'filename': os.path.basename(filepath),
            'filepath': filepath,
            'success': False,
            'error': None,
            'num_points': 0,
            'num_trees': 0,
            'processing_time': 0.0
        }

        try:
            import time
            start_time = time.time()

            print(f"\nProcessing: {filepath}")
            data = load_point_cloud(filepath)
            result['num_points'] = data.num_points
            print(f"  Loaded {data.num_points} points")

            if preprocess_kwargs is None:
                preprocess_kwargs = {}

            processed_data = preprocess_pipeline(data, **preprocess_kwargs)
            print(f"  Preprocessed: {processed_data.num_points} points remaining")

            if save_intermediate:
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                preprocessed_path = os.path.join(
                    self.output_dir, f"{base_name}_preprocessed.ply"
                )
                processed_data.save(preprocessed_path, save_labels=False)

            if self.model is not None:
                if segmentation_kwargs is None:
                    segmentation_kwargs = {}

                print("  Running segmentation...")
                labels = predict_segmentation(
                    self.model,
                    processed_data.points,
                    processed_data.colors,
                    processed_data.normals,
                    device=self.device,
                    **segmentation_kwargs
                )
                processed_data.labels = labels

                label_counts = np.bincount(labels, minlength=5)
                print(f"  Segmentation complete:")
                print(f"    Ground: {label_counts[0]} points")
                print(f"    Trunk: {label_counts[1]} points")
                print(f"    Large branch: {label_counts[2]} points")
                print(f"    Small branch: {label_counts[3]} points")
                print(f"    Leaf: {label_counts[4]} points")

            if processed_data.labels is not None and extraction_kwargs is not None:
                if extraction_kwargs.pop('complete_trunk', False):
                    from .enhancement import complete_trunk_geometry
                    print("  Completing trunk geometry...")
                    trunk_kwargs = {
                        'min_height': extraction_kwargs.pop('min_trunk_height', 1.3),
                        'max_radius': extraction_kwargs.pop('max_trunk_radius', 0.5),
                        'kernel_size': extraction_kwargs.pop('morph_kernel', 3),
                        'iterations': extraction_kwargs.pop('morph_iterations', 2),
                    }
                    trunk_method = extraction_kwargs.pop('trunk_method', 'cylinder')
                    processed_data = complete_trunk_geometry(
                        processed_data,
                        method=trunk_method,
                        **trunk_kwargs
                    )
                    label_counts = np.bincount(processed_data.labels, minlength=5)
                    print(f"  After trunk completion:")
                    print(f"    Trunk: {label_counts[1]} points")

            if processed_data.labels is not None and extraction_kwargs is not None:
                if extraction_kwargs is None:
                    extraction_kwargs = {}

                print("  Extracting individual trees...")
                tree_metrics, tree_ids, instance_labels = extract_individual_trees(
                    processed_data, **extraction_kwargs
                )
                result['num_trees'] = len(tree_metrics)
                print(f"  Found {len(tree_metrics)} trees")

                base_name = os.path.splitext(os.path.basename(filepath))[0]

                metrics_path = os.path.join(self.output_dir, f"{base_name}_metrics.csv")
                save_metrics_csv(tree_metrics, metrics_path)
                print(f"  Saved metrics to: {metrics_path}")

                labeled_path = os.path.join(self.output_dir, f"{base_name}_labeled.ply")
                processed_data.save(labeled_path, save_labels=True)
                print(f"  Saved labeled point cloud to: {labeled_path}")

                if generate_visualization:
                    vis_path = os.path.join(self.output_dir, f"{base_name}_visualization.ply")
                    save_visualization(processed_data, vis_path, leaf_alpha=0.5)

                    img_path = os.path.join(self.output_dir, f"{base_name}_render.png")
                    try:
                        render_to_image(processed_data, img_path, leaf_alpha=0.5)
                        print(f"  Saved visualization to: {img_path}")
                    except Exception as e:
                        print(f"  Warning: Could not render image: {e}")

            result['success'] = True
            result['processing_time'] = time.time() - start_time
            print(f"  Completed in {result['processing_time']:.2f} seconds")

        except Exception as e:
            result['error'] = str(e)
            print(f"  Error processing {filepath}: {e}")

        self.results_summary.append(result)
        return result

    def process_all(self,
                    preprocess_kwargs: Optional[Dict] = None,
                    segmentation_kwargs: Optional[Dict] = None,
                    extraction_kwargs: Optional[Dict] = None,
                    save_intermediate: bool = False,
                    generate_visualization: bool = True) -> pd.DataFrame:
        os.makedirs(self.output_dir, exist_ok=True)

        files = self.find_files()
        print(f"\nFound {len(files)} files to process")

        for filepath in tqdm(files, desc="Processing files", unit="file"):
            self.process_single_file(
                filepath,
                preprocess_kwargs=preprocess_kwargs,
                segmentation_kwargs=segmentation_kwargs,
                extraction_kwargs=extraction_kwargs,
                save_intermediate=save_intermediate,
                generate_visualization=generate_visualization
            )

        summary_df = self.save_summary()
        return summary_df

    def save_summary(self, filename: str = "processing_summary.csv") -> pd.DataFrame:
        summary_path = os.path.join(self.output_dir, filename)

        if not self.results_summary:
            print("No results to save")
            return pd.DataFrame()

        df = pd.DataFrame(self.results_summary)

        summary_stats = {
            'total_files': len(self.results_summary),
            'successful_files': sum(1 for r in self.results_summary if r['success']),
            'failed_files': sum(1 for r in self.results_summary if not r['success']),
            'total_points': sum(r['num_points'] for r in self.results_summary if r['success']),
            'total_trees': sum(r['num_trees'] for r in self.results_summary if r['success']),
            'total_time': sum(r['processing_time'] for r in self.results_summary if r['success']),
        }

        stats_df = pd.DataFrame([summary_stats])
        stats_path = os.path.join(self.output_dir, "overall_statistics.csv")
        stats_df.to_csv(stats_path, index=False, encoding='utf-8-sig')

        df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        print(f"\nProcessing summary saved to: {summary_path}")
        print(f"Overall statistics saved to: {stats_path}")
        print(f"\nStatistics:")
        print(f"  Total files: {summary_stats['total_files']}")
        print(f"  Successful: {summary_stats['successful_files']}")
        print(f"  Failed: {summary_stats['failed_files']}")
        print(f"  Total points: {summary_stats['total_points']:,}")
        print(f"  Total trees: {summary_stats['total_trees']}")
        print(f"  Total time: {summary_stats['total_time']:.2f}s")

        return df


def merge_metrics_csv(output_dir: str, output_filename: str = "all_tree_metrics.csv") -> pd.DataFrame:
    csv_files = glob.glob(os.path.join(output_dir, "*_metrics.csv"))
    all_dfs = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            source_file = os.path.basename(csv_file).replace('_metrics.csv', '')
            df.insert(0, 'source_file', source_file)
            all_dfs.append(df)
        except Exception as e:
            print(f"Warning: Could not read {csv_file}: {e}")

    if all_dfs:
        merged_df = pd.concat(all_dfs, ignore_index=True)
        output_path = os.path.join(output_dir, output_filename)
        merged_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\nMerged metrics saved to: {output_path}")
        print(f"Total trees across all files: {len(merged_df)}")
        return merged_df
    else:
        print("No metric files found to merge")
        return pd.DataFrame()
