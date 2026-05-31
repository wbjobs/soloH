import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from tqdm import tqdm

from .segmentation import UNetSegmenter
from .segmentation_3d import Segmentation3D, check_3d_data
from .tracking import CellTracker
from .division_detection import DivisionDetector
from .features import FeatureExtractor
from .phenotype_clustering import (
    TrackFeatureExtractor,
    PhenotypeClusterer,
    assign_phenotype_names,
    ClusteringResult
)
from .interaction_analysis import (
    InteractionAnalyzer,
    InteractionResult,
    compute_interaction_statistics,
    analyze_temporal_interaction_patterns,
    identify_leader_follower_pairs
)
from .evaluation import Evaluator
from .visualization import (
    NapariVisualizer,
    plot_trajectories,
    plot_fluorescence_timeseries,
    plot_division_timeline,
    plot_evaluation_metrics,
)
from .parallel import ParallelProcessor
from .utils import load_tiff_stack, save_tiff_stack, normalize_stack

logger = logging.getLogger(__name__)


class CellTrackingPipeline:
    def __init__(self,
                 weights_path: Optional[str] = None,
                 weights_path_3d: Optional[str] = None,
                 device: str = 'auto',
                 num_workers: int = 4,
                 use_parallel: bool = True,
                 output_dir: str = "./output",
                 tracking_max_distance: float = 50.0,
                 tracking_max_lost_frames: int = 3,
                 division_area_drop_threshold: float = 0.4,
                 division_area_hysteresis: float = 0.1,
                 division_morphology_threshold: float = 0.3,
                 division_morphology_hysteresis: float = 0.08,
                 division_require_both_metrics: bool = True,
                 division_min_consecutive_frames: int = 1,
                 photobleach_correction: bool = True,
                 photobleach_method: str = 'exponential',
                 photobleach_global: bool = True,
                 background_correction: bool = True,
                 use_3d_segmentation: bool = True,
                 use_3d_network: bool = True,
                 use_z_consistency: bool = True,
                 min_object_size_3d: int = 500,
                 enable_phenotype_clustering: bool = True,
                 clustering_algorithm: str = 'kmeans',
                 n_clusters: int = 3,
                 use_pca_for_clustering: bool = True,
                 enable_interaction_analysis: bool = True,
                 interaction_distance_threshold: float = 15.0,
                 contact_distance_threshold: float = 5.0,
                 min_contact_duration: int = 3,
                 use_boundary_contact: bool = True):
        self.weights_path = weights_path
        self.device = device
        self.num_workers = num_workers
        self.use_parallel = use_parallel
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.tracking_max_distance = tracking_max_distance
        self.tracking_max_lost_frames = tracking_max_lost_frames
        self.division_area_drop_threshold = division_area_drop_threshold
        self.division_area_hysteresis = division_area_hysteresis
        self.division_morphology_threshold = division_morphology_threshold
        self.division_morphology_hysteresis = division_morphology_hysteresis
        self.division_require_both_metrics = division_require_both_metrics
        self.division_min_consecutive_frames = division_min_consecutive_frames
        self.photobleach_correction = photobleach_correction
        self.photobleach_method = photobleach_method
        self.photobleach_global = photobleach_global
        self.background_correction = background_correction
        
        self.weights_path_3d = weights_path_3d
        self.use_3d_segmentation = use_3d_segmentation
        self.use_3d_network = use_3d_network
        self.use_z_consistency = use_z_consistency
        self.min_object_size_3d = min_object_size_3d
        self.is_3d_data = False
        self.z_slices = 1
        
        self.enable_phenotype_clustering = enable_phenotype_clustering
        self.clustering_algorithm = clustering_algorithm
        self.n_clusters = n_clusters
        self.use_pca_for_clustering = use_pca_for_clustering
        
        self.enable_interaction_analysis = enable_interaction_analysis
        self.interaction_distance_threshold = interaction_distance_threshold
        self.contact_distance_threshold = contact_distance_threshold
        self.min_contact_duration = min_contact_duration
        self.use_boundary_contact = use_boundary_contact
        
        self.segmenter = None
        self.segmenter_3d = None
        self.tracker = None
        self.division_detector = None
        self.feature_extractor = None
        self.phenotype_extractor = None
        self.phenotype_clusterer = None
        self.interaction_analyzer = None
        self.evaluator = None
        self.visualizer = None
        
        self.image_stack = None
        self.segmentation_masks = None
        self.tracks_df = None
        self.fluorescence_df = None
        self.division_events = None
        self.phenotype_features = None
        self.clustering_result = None
        self.interaction_result = None
        self.evaluation_results = None
        
        self._init_components()
    
    def _init_components(self):
        logger.info("Initializing pipeline components...")
        
        self.segmenter = UNetSegmenter(
            weights_path=self.weights_path,
            device=self.device,
            threshold=0.5,
            use_watershed=True,
            min_object_size=100
        )
        
        self.tracker = CellTracker(
            max_distance=self.tracking_max_distance,
            distance_weight=1.0,
            iou_weight=1.0,
            area_weight=0.5,
            max_lost_frames=self.tracking_max_lost_frames,
            min_track_length=5
        )
        
        self.division_detector = DivisionDetector(
            area_drop_threshold=self.division_area_drop_threshold,
            area_increase_threshold=1.0 / self.division_area_drop_threshold,
            morphology_change_threshold=self.division_morphology_threshold,
            area_drop_hysteresis=self.division_area_hysteresis,
            area_increase_hysteresis=self.division_area_hysteresis * 1.5,
            morphology_hysteresis=self.division_morphology_hysteresis,
            min_consecutive_frames=self.division_min_consecutive_frames,
            require_both_metrics=self.division_require_both_metrics,
            min_cell_area=100,
            max_cell_area=10000,
            min_tracks_for_division=2,
            max_distance_for_children=40.0
        )
        
        self.feature_extractor = FeatureExtractor(
            use_parallel=self.use_parallel,
            num_workers=self.num_workers,
            perform_photobleach_correction=self.photobleach_correction,
            bleaching_correction_method=self.photobleach_method,
            background_correction=self.background_correction,
            use_global_bleach=self.photobleach_global
        )
        
        self.evaluator = Evaluator(
            iou_threshold=0.5,
            min_track_length=5
        )
        
        self.visualizer = NapariVisualizer()
        
        if self.use_3d_segmentation:
            self.segmenter_3d = Segmentation3D(
                weights_path_3d=self.weights_path_3d,
                weights_path_2d=self.weights_path,
                device=self.device,
                threshold=0.5,
                use_3d_network=self.use_3d_network,
                use_z_consistency=self.use_z_consistency,
                min_object_size=self.min_object_size_3d
            )
            logger.info("3D segmentation component initialized")
        
        if self.enable_phenotype_clustering:
            self.phenotype_extractor = TrackFeatureExtractor(
                include_motion=True,
                include_division=True,
                include_morphology=True,
                include_fluorescence=True
            )
            self.phenotype_clusterer = PhenotypeClusterer(
                algorithm=self.clustering_algorithm,
                n_clusters=self.n_clusters,
                use_pca=self.use_pca_for_clustering
            )
            logger.info("Phenotype clustering components initialized")
        
        if self.enable_interaction_analysis:
            self.interaction_analyzer = InteractionAnalyzer(
                distance_threshold=self.interaction_distance_threshold,
                contact_distance_threshold=self.contact_distance_threshold,
                min_contact_duration=self.min_contact_duration,
                use_boundary_contact=self.use_boundary_contact
            )
            logger.info("Interaction analysis component initialized")
        
        if self.use_parallel:
            self.parallel_processor = ParallelProcessor(
                num_workers=self.num_workers,
                use_threads=True,
                show_progress=True
            )
        else:
            self.parallel_processor = None
        
        logger.info("Pipeline components initialized")
    
    def load_data(self, input_path: str) -> np.ndarray:
        logger.info(f"Loading data from {input_path}")
        self.image_stack = load_tiff_stack(input_path)
        
        self.is_3d_data, self.z_slices = check_3d_data(self.image_stack)
        if self.is_3d_data:
            logger.info(f"3D data detected: {self.image_stack.shape} (Z-slices: {self.z_slices})")
        else:
            logger.info(f"2D data loaded: {self.image_stack.shape}")
        
        return self.image_stack
    
    def preprocess(self, 
                   lower_percentile: float = 0.5,
                   upper_percentile: float = 99.5,
                   by_frame: bool = True) -> np.ndarray:
        if self.image_stack is None:
            raise RuntimeError("No data loaded. Call load_data() first.")
        
        logger.info("Preprocessing image stack...")
        self.image_stack = normalize_stack(
            self.image_stack,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
            by_frame=by_frame
        )
        logger.info("Preprocessing complete")
        return self.image_stack
    
    def run_segmentation(self, 
                          parallel: Optional[bool] = None,
                          num_workers: Optional[int] = None) -> np.ndarray:
        if self.image_stack is None:
            raise RuntimeError("No data loaded. Call load_data() first.")
        
        if self.is_3d_data and self.use_3d_segmentation and self.segmenter_3d is not None:
            return self.run_3d_segmentation(parallel, num_workers)
        
        parallel = parallel if parallel is not None else self.use_parallel
        num_workers = num_workers if num_workers is not None else self.num_workers
        
        logger.info(f"Running 2D segmentation (parallel={parallel}, workers={num_workers})")
        
        if parallel and self.parallel_processor is not None:
            self.segmentation_masks = self.parallel_processor.segment_frames_parallel(
                segmenter=self.segmenter,
                frames=self.image_stack
            )
        else:
            self.segmentation_masks = self.segmenter.segment_stack(
                stack=self.image_stack,
                parallel=False
            )
        
        save_tiff_stack(
            self.segmentation_masks.astype(np.uint16),
            self.output_dir / "segmentation_masks.tiff"
        )
        logger.info(f"Segmentation complete. Output shape: {self.segmentation_masks.shape}")
        
        return self.segmentation_masks
    
    def run_3d_segmentation(self,
                            parallel: Optional[bool] = None,
                            num_workers: Optional[int] = None) -> np.ndarray:
        if self.image_stack is None:
            raise RuntimeError("No data loaded. Call load_data() first.")
        
        if self.segmenter_3d is None:
            raise RuntimeError("3D segmenter not initialized. Set use_3d_segmentation=True.")
        
        parallel = parallel if parallel is not None else self.use_parallel
        num_workers = num_workers if num_workers is not None else self.num_workers
        
        logger.info(f"Running 3D segmentation (parallel={parallel}, workers={num_workers})")
        
        self.segmentation_masks = self.segmenter_3d.segment_3d(
            image_stack=self.image_stack,
            parallel=parallel,
            num_workers=num_workers
        )
        
        save_tiff_stack(
            self.segmentation_masks.astype(np.uint16),
            self.output_dir / "segmentation_masks_3d.tiff"
        )
        
        if self.is_3d_data and self.segmentation_masks.ndim == 4:
            max_projection = np.max(self.segmentation_masks, axis=1)
            save_tiff_stack(
                max_projection.astype(np.uint16),
                self.output_dir / "segmentation_masks_z_projection.tiff"
            )
            logger.info(f"Saved Z-projection for 2D visualization")
        
        logger.info(f"3D segmentation complete. Output shape: {self.segmentation_masks.shape}")
        
        return self.segmentation_masks
    
    def run_phenotype_clustering(self) -> ClusteringResult:
        if self.tracker is None or not self.tracker.tracks:
            raise RuntimeError("No tracks available. Run tracking first.")
        
        if not self.enable_phenotype_clustering or self.phenotype_extractor is None:
            logger.warning("Phenotype clustering not enabled")
            return None
        
        logger.info("Running phenotype clustering...")
        
        division_df = None
        if self.division_events:
            division_df = self.division_detector.get_division_dataframe()
        
        feature_data = None
        if self.feature_extractor.features_data:
            feature_rows = []
            for frame, frame_data in self.feature_extractor.features_data.items():
                for label, feats in frame_data.items():
                    row = {'frame': frame, 'label': label}
                    row.update(feats)
                    feature_rows.append(row)
            if feature_rows:
                feature_data = pd.DataFrame(feature_rows)
        
        phenotype_df = None
        if feature_data is not None and len(feature_data) > 0:
            track_label_map = {}
            for track_id, track in self.tracker.tracks.items():
                for i, frame in enumerate(track.frames):
                    if hasattr(track, 'labels') and i < len(track.labels):
                        track_label_map[(frame, track.labels[i])] = track_id
            
            feature_data['track_id'] = feature_data.apply(
                lambda row: track_label_map.get((int(row['frame']), int(row['label'])), -1),
                axis=1
            )
            feature_data = feature_data[feature_data['track_id'] != -1]
            
            if len(feature_data) > 0:
                phenotype_df = feature_data
        
        self.phenotype_features = self.phenotype_extractor.extract_features(
            tracker=self.tracker,
            feature_data=phenotype_df,
            division_data=division_df,
            masks=self.segmentation_masks
        )
        
        if len(self.phenotype_features) < self.n_clusters:
            logger.warning(f"Not enough tracks ({len(self.phenotype_features)}) for {self.n_clusters} clusters")
            return None
        
        self.clustering_result = self.phenotype_clusterer.cluster(
            features_df=self.phenotype_features
        )
        
        self.clustering_result.clusters = assign_phenotype_names(self.clustering_result.clusters)
        
        self._save_clustering_results()
        
        logger.info(f"Phenotype clustering complete. Found {len(self.clustering_result.clusters)} clusters")
        
        return self.clustering_result
    
    def _save_clustering_results(self):
        if self.clustering_result is None:
            return
        
        labels_df = pd.DataFrame([
            {'track_id': tid, 'phenotype_cluster': cid}
            for tid, cid in self.clustering_result.labels.items()
        ])
        labels_df.to_csv(self.output_dir / "phenotype_labels.csv", index=False)
        
        self.phenotype_features['phenotype_cluster'] = self.phenotype_features['track_id'].map(
            self.clustering_result.labels
        )
        self.phenotype_features.to_csv(self.output_dir / "phenotype_features.csv", index=False)
        
        cluster_summary = []
        for cid, cluster in self.clustering_result.clusters.items():
            summary_row = {
                'cluster_id': cid,
                'name': cluster.name,
                'description': cluster.description,
                'n_tracks': len(cluster.member_track_ids),
            }
            for feat_name, feat_mean in cluster.feature_means.items():
                summary_row[f'mean_{feat_name}'] = feat_mean
            cluster_summary.append(summary_row)
        
        pd.DataFrame(cluster_summary).to_csv(
            self.output_dir / "phenotype_cluster_summary.csv", index=False
        )
        
        importance_df = pd.DataFrame([
            {'feature': feat, 'importance': imp}
            for feat, imp in sorted(
                self.clustering_result.feature_importance.items(),
                key=lambda x: x[1], reverse=True
            )
        ])
        importance_df.to_csv(self.output_dir / "phenotype_feature_importance.csv", index=False)
        
        if self.clustering_result.pca_coordinates is not None:
            pca_df = pd.DataFrame([
                {'track_id': tid, 'pc1': pc[0], 'pc2': pc[1],
                 'phenotype_cluster': self.clustering_result.labels[tid]}
                for tid, pc in self.clustering_result.pca_coordinates.items()
            ])
            pca_df.to_csv(self.output_dir / "phenotype_pca_coordinates.csv", index=False)
        
        metrics_df = pd.DataFrame([self.clustering_result.cluster_metrics])
        metrics_df.to_csv(self.output_dir / "phenotype_clustering_metrics.csv", index=False)
        
        logger.info("Phenotype clustering results saved")
    
    def run_interaction_analysis(self) -> InteractionResult:
        if self.tracker is None or not self.tracker.tracks:
            raise RuntimeError("No tracks available. Run tracking first.")
        
        if self.segmentation_masks is None:
            raise RuntimeError("No segmentation masks available. Run segmentation first.")
        
        if not self.enable_interaction_analysis or self.interaction_analyzer is None:
            logger.warning("Interaction analysis not enabled")
            return None
        
        logger.info("Running cell-cell interaction analysis...")
        
        phenotype_labels = None
        phenotype_names = None
        if self.clustering_result is not None:
            phenotype_labels = self.clustering_result.labels
            phenotype_names = {
                cid: cluster.name 
                for cid, cluster in self.clustering_result.clusters.items()
            }
        
        feature_data = None
        if self.feature_extractor.features_data:
            feature_rows = []
            for frame, frame_data in self.feature_extractor.features_data.items():
                for label, feats in frame_data.items():
                    row = {'frame': frame, 'label': label}
                    row.update(feats)
                    feature_rows.append(row)
            if feature_rows:
                feature_data = pd.DataFrame(feature_rows)
        
        masks_for_analysis = self.segmentation_masks
        if self.is_3d_data and self.segmentation_masks.ndim == 4:
            masks_for_analysis = np.max(self.segmentation_masks, axis=1)
        
        self.interaction_result = self.interaction_analyzer.analyze_interactions(
            tracker=self.tracker,
            masks=masks_for_analysis,
            feature_data=feature_data,
            phenotype_labels=phenotype_labels,
            phenotype_names=phenotype_names
        )
        
        self._save_interaction_results()
        
        interaction_stats = compute_interaction_statistics(
            self.interaction_result,
            phenotype_labels=phenotype_labels
        )
        logger.info(f"Interaction analysis complete. {interaction_stats['total_contacts']} contacts detected")
        
        return self.interaction_result
    
    def _save_interaction_results(self):
        if self.interaction_result is None:
            return
        
        self.interaction_result.contact_summary.to_csv(
            self.output_dir / "cell_contacts.csv", index=False
        )
        
        self.interaction_result.frame_by_frame.to_csv(
            self.output_dir / "interactions_frame_by_frame.csv", index=False
        )
        
        self.interaction_result.interaction_matrix.to_csv(
            self.output_dir / "interaction_matrix.csv"
        )
        
        stats = compute_interaction_statistics(self.interaction_result)
        with open(self.output_dir / "interaction_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
        temporal_stats = analyze_temporal_interaction_patterns(self.interaction_result)
        if len(temporal_stats) > 0:
            temporal_stats.to_csv(
                self.output_dir / "interaction_temporal_patterns.csv", index=False
            )
        
        leader_follower = identify_leader_follower_pairs(
            self.interaction_result, self.tracker
        )
        if leader_follower:
            pd.DataFrame(leader_follower).to_csv(
                self.output_dir / "leader_follower_pairs.csv", index=False
            )
            logger.info(f"Identified {len(leader_follower)} leader-follower pairs")
        
        logger.info("Interaction analysis results saved")
    
    def run_tracking(self, 
                      min_track_length: Optional[int] = None) -> pd.DataFrame:
        if self.segmentation_masks is None:
            raise RuntimeError("No segmentation masks available. Run segmentation first.")
        
        if min_track_length is not None:
            self.tracker.min_track_length = min_track_length
        
        logger.info("Running cell tracking...")
        
        n_frames = self.segmentation_masks.shape[0]
        
        for frame in tqdm(range(n_frames), desc="Tracking cells"):
            mask = self.segmentation_masks[frame]
            
            fluo_values = None
            if self.feature_extractor.fluorescence_data:
                fluo_values = {
                    label: fluo['mean']
                    for label, fluo in self.feature_extractor.fluorescence_data.get(frame, {}).items()
                }
            
            self.tracker.update(
                frame=frame,
                mask=mask,
                fluorescence_values=fluo_values
            )
        
        self.tracker.filter_short_tracks()
        
        self.tracks_df = self.tracker.get_tracks_dataframe()
        self.tracks_df.to_csv(self.output_dir / "tracks.csv", index=False)
        
        track_masks = self.tracker.get_tracks_overlay(self.segmentation_masks)
        save_tiff_stack(
            track_masks.astype(np.uint16),
            self.output_dir / "track_masks.tiff"
        )
        
        logger.info(f"Tracking complete. Found {len(self.tracker.tracks)} tracks")
        
        return self.tracks_df
    
    def run_division_detection(self) -> pd.DataFrame:
        if self.tracker is None or not self.tracker.tracks:
            raise RuntimeError("No tracks available. Run tracking first.")
        
        logger.info("Detecting division events...")
        
        self.division_events = self.division_detector.detect_divisions(
            tracker=self.tracker,
            masks=self.segmentation_masks
        )
        
        division_df = self.division_detector.get_division_dataframe()
        if not division_df.empty:
            division_df.to_csv(self.output_dir / "division_events.csv", index=False)
            
            division_mask = self.division_detector.get_division_mask(
                self.segmentation_masks,
                self.tracker
            )
            save_tiff_stack(
                division_mask.astype(np.uint8),
                self.output_dir / "division_masks.tiff"
            )
        
        logger.info(f"Division detection complete. Found {len(self.division_events)} events")
        
        return division_df
    
    def run_feature_extraction(self, 
                                channel: int = 0,
                                extract_all: bool = True) -> pd.DataFrame:
        if self.image_stack is None or self.segmentation_masks is None:
            raise RuntimeError("Image data and masks required for feature extraction")
        
        logger.info("Extracting features...")
        
        if extract_all:
            if self.use_parallel and self.parallel_processor is not None:
                features = self.parallel_processor.extract_features_parallel(
                    extractor=self.feature_extractor,
                    image_stack=self.image_stack,
                    masks=self.segmentation_masks,
                    channel=channel
                )
                self.feature_extractor.features_data = features
                
                for frame, frame_features in features.items():
                    self.feature_extractor.fluorescence_data[frame] = {
                        label: feat['fluorescence'] 
                        for label, feat in frame_features.items()
                    }
            else:
                self.feature_extractor.extract_all_features(
                    image_stack=self.image_stack,
                    masks=self.segmentation_masks,
                    channel=channel
                )
        else:
            self.feature_extractor.extract_fluorescence(
                image_stack=self.image_stack,
                masks=self.segmentation_masks,
                channel=channel
            )
        
        self.feature_extractor.get_fluorescence_for_tracker(self.tracker)
        
        self.fluorescence_df = self.feature_extractor.get_fluorescence_timeseries(self.tracker)
        self.fluorescence_df.to_csv(self.output_dir / "fluorescence_timeseries.csv", index=False)
        
        summary_df = self.feature_extractor.get_summary_statistics(self.tracker)
        summary_df.to_csv(self.output_dir / "track_summary.csv", index=False)
        
        logger.info(f"Feature extraction complete. {len(self.fluorescence_df)} rows of data")
        
        return self.fluorescence_df
    
    def run_evaluation(self,
                        gt_masks: Optional[np.ndarray] = None,
                        gt_tracks: Optional[pd.DataFrame] = None,
                        gt_divisions: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        if self.segmentation_masks is None or self.tracker is None:
            raise RuntimeError("Segmentation and tracking results required for evaluation")
        
        logger.info("Running evaluation...")
        
        pred_division_events = self.division_events if self.division_events else []
        
        self.evaluation_results = self.evaluator.evaluate_all(
            pred_masks=self.segmentation_masks,
            gt_masks=gt_masks,
            pred_tracker=self.tracker,
            gt_tracks_df=gt_tracks,
            pred_division_events=pred_division_events,
            gt_divisions_df=gt_divisions
        )
        
        report = self.evaluator.generate_report(self.evaluation_results)
        
        with open(self.output_dir / "evaluation_report.txt", 'w') as f:
            f.write(report)
        
        with open(self.output_dir / "evaluation_results.json", 'w') as f:
            json.dump(
                {k: v for k, v in self.evaluation_results.items() 
                 if not isinstance(v, dict) or 'per_frame' not in v},
                f, 
                indent=2
            )
        
        metrics_df = self.evaluator.get_metrics_dataframe()
        metrics_df.to_csv(self.output_dir / "evaluation_metrics.csv", index=False)
        
        logger.info("Evaluation complete")
        logger.info(f"\n{report}")
        
        return self.evaluation_results
    
    def run_visualization(self,
                           show_napari: bool = False,
                           save_plots: bool = True,
                           show_fluorescence: bool = True,
                           show_division: bool = True):
        if self.image_stack is None or self.segmentation_masks is None:
            raise RuntimeError("Data required for visualization")
        
        logger.info("Generating visualizations...")
        
        if save_plots:
            plots_dir = self.output_dir / "plots"
            plots_dir.mkdir(exist_ok=True)
            
            plot_trajectories(
                self.tracker,
                output_file=plots_dir / "trajectories.png",
                min_length=self.tracker.min_track_length
            )
            
            if self.fluorescence_df is not None and not self.fluorescence_df.empty:
                plot_fluorescence_timeseries(
                    self.fluorescence_df,
                    output_file=plots_dir / "fluorescence_timeseries.png",
                    max_tracks=10
                )
            
            if self.division_events is not None and len(self.division_events) > 0:
                plot_division_timeline(
                    self.division_events,
                    output_file=plots_dir / "division_timeline.png",
                    max_frame=self.image_stack.shape[0]
                )
            
            if self.evaluation_results and 'segmentation' in self.evaluation_results:
                plot_evaluation_metrics(
                    self.evaluation_results['segmentation'],
                    output_file=plots_dir / "segmentation_metrics.png"
                )
        
        if show_napari:
            logger.info("Opening napari viewer...")
            
            fluo_df = self.fluorescence_df if show_fluorescence else None
            division_events = self.division_events if show_division else None
            
            self.visualizer.visualize_all(
                image_stack=self.image_stack,
                masks=self.segmentation_masks,
                tracker=self.tracker,
                division_events=division_events,
                fluo_timeseries=fluo_df
            )
            
            self.visualizer.show()
    
    def run_full_pipeline(self,
                           input_path: str,
                           gt_masks_path: Optional[str] = None,
                           gt_tracks_path: Optional[str] = None,
                           gt_divisions_path: Optional[str] = None,
                           show_napari: bool = False) -> Dict[str, Any]:
        logger.info("=" * 60)
        logger.info("STARTING FULL CELL TRACKING PIPELINE")
        logger.info("=" * 60)
        
        self.load_data(input_path)
        self.preprocess()
        self.run_feature_extraction(extract_all=True)
        self.run_segmentation()
        self.run_tracking()
        self.run_division_detection()
        
        n_clusters = 0
        n_contacts = 0
        
        if self.enable_phenotype_clustering and len(self.tracker.tracks) >= 2:
            self.run_phenotype_clustering()
            if self.clustering_result is not None:
                n_clusters = len(self.clustering_result.clusters)
        
        if self.enable_interaction_analysis and len(self.tracker.tracks) >= 2:
            self.run_interaction_analysis()
            if self.interaction_result is not None:
                n_contacts = len(self.interaction_result.contacts)
        
        gt_masks = None
        gt_tracks = None
        gt_divisions = None
        
        if gt_masks_path and Path(gt_masks_path).exists():
            gt_masks = load_tiff_stack(gt_masks_path)
        
        if gt_tracks_path and Path(gt_tracks_path).exists():
            gt_tracks = pd.read_csv(gt_tracks_path)
        
        if gt_divisions_path and Path(gt_divisions_path).exists():
            gt_divisions = pd.read_csv(gt_divisions_path)
        
        if gt_masks is not None or gt_tracks is not None:
            self.run_evaluation(gt_masks, gt_tracks, gt_divisions)
        
        self.run_visualization(show_napari=show_napari)
        
        self._save_metadata()
        
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"Results saved to: {self.output_dir}")
        logger.info("=" * 60)
        
        return {
            'n_frames': self.image_stack.shape[0],
            'n_tracks': len(self.tracker.tracks),
            'n_divisions': len(self.division_events) if self.division_events else 0,
            'n_phenotype_clusters': n_clusters,
            'n_cell_contacts': n_contacts,
            'is_3d_data': self.is_3d_data,
            'output_dir': str(self.output_dir),
            'evaluation': self.evaluation_results,
        }
    
    def _save_metadata(self):
        metadata = {
            'pipeline_config': {
                'weights_path': self.weights_path,
                'device': self.device,
                'num_workers': self.num_workers,
                'use_parallel': self.use_parallel,
                'tracking': {
                    'max_distance': self.tracking_max_distance,
                    'max_lost_frames': self.tracking_max_lost_frames,
                    'motion_prediction': 'Kalman filter enabled',
                },
                'division_detection': {
                    'area_drop_threshold': self.division_area_drop_threshold,
                    'area_hysteresis': self.division_area_hysteresis,
                    'morphology_threshold': self.division_morphology_threshold,
                    'morphology_hysteresis': self.division_morphology_hysteresis,
                    'require_both_metrics': self.division_require_both_metrics,
                    'min_consecutive_frames': self.division_min_consecutive_frames,
                },
                'photobleach_correction': {
                    'enabled': self.photobleach_correction,
                    'method': self.photobleach_method,
                    'global_correction': self.photobleach_global,
                    'background_correction': self.background_correction,
                },
                'segmentation_3d': {
                    'enabled': self.use_3d_segmentation,
                    'use_3d_network': self.use_3d_network,
                    'use_z_consistency': self.use_z_consistency,
                    'is_3d_data': self.is_3d_data,
                    'z_slices': self.z_slices,
                },
                'phenotype_clustering': {
                    'enabled': self.enable_phenotype_clustering,
                    'algorithm': self.clustering_algorithm,
                    'n_clusters': self.n_clusters,
                    'use_pca': self.use_pca_for_clustering,
                },
                'interaction_analysis': {
                    'enabled': self.enable_interaction_analysis,
                    'distance_threshold': self.interaction_distance_threshold,
                    'contact_distance_threshold': self.contact_distance_threshold,
                    'min_contact_duration': self.min_contact_duration,
                    'use_boundary_contact': self.use_boundary_contact,
                }
            },
            'results': {
                'n_frames': self.image_stack.shape[0] if self.image_stack is not None else 0,
                'image_shape': list(self.image_stack.shape) if self.image_stack is not None else [],
                'n_tracks': len(self.tracker.tracks),
                'n_divisions': len(self.division_events) if self.division_events else 0,
                'n_phenotype_clusters': len(self.clustering_result.clusters) if self.clustering_result else 0,
                'n_cell_contacts': len(self.interaction_result.contacts) if self.interaction_result else 0,
                'is_3d_data': self.is_3d_data,
            }
        }
        
        if self.feature_extractor.bleach_correction_params is not None:
            metadata['results']['bleach_correction'] = self.feature_extractor.bleach_correction_params
        
        with open(self.output_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        if self.feature_extractor.bleach_correction_params is not None:
            import csv
            with open(self.output_dir / "bleach_correction_factors.csv", 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'correction_factor', 'background'])
                
                n_frames = self.segmentation_masks.shape[0] if self.segmentation_masks is not None else 0
                for frame in range(n_frames):
                    fluo_data = self.feature_extractor.corrected_fluorescence_data.get(frame, {})
                    factor = 1.0
                    bg = 0.0
                    if fluo_data:
                        first_key = next(iter(fluo_data.keys()))
                        factor = fluo_data[first_key].get('correction_factor', 1.0)
                        bg = fluo_data[first_key].get('background', 0.0)
                    writer.writerow([frame, factor, bg])
            
            logger.info("Bleach correction factors saved to bleach_correction_factors.csv")
