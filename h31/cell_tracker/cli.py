import click
import logging
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

from .pipeline import CellTrackingPipeline
from .utils import load_tiff_stack

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """Cell Tracking Analysis Pipeline
    
    A comprehensive tool for analyzing time-lapse fluorescence microscopy images.
    Features include U-Net segmentation, Hungarian algorithm tracking, 
    division detection, fluorescence quantification, and napari visualization.
    """
    pass


@cli.command()
@click.argument('input_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--weights', '-w', type=click.Path(exists=True, dir_okay=False),
              help='Path to pre-trained U-Net weights (.pth)')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False),
              default='./output', help='Output directory')
@click.option('--device', '-d', type=click.Choice(['auto', 'cpu', 'cuda']),
              default='auto', help='Computation device')
@click.option('--num-workers', '-j', type=int, default=4,
              help='Number of parallel workers')
@click.option('--no-parallel', is_flag=True, default=False,
              help='Disable parallel processing')
@click.option('--min-track-length', type=int, default=5,
              help='Minimum track length to keep')
@click.option('--max-distance', type=float, default=50.0,
              help='Maximum distance for tracking (pixels)')
@click.option('--max-lost-frames', type=int, default=3,
              help='Maximum number of lost frames for tracking recovery')
@click.option('--division-area-threshold', type=float, default=0.4,
              help='Area drop threshold for division detection (ratio)')
@click.option('--division-area-hysteresis', type=float, default=0.1,
              help='Hysteresis for area threshold (prevents oscillating detection)')
@click.option('--division-morphology-threshold', type=float, default=0.3,
              help='Morphology change threshold for division detection')
@click.option('--division-morphology-hysteresis', type=float, default=0.08,
              help='Hysteresis for morphology threshold')
@click.option('--division-require-both', is_flag=True, default=True,
              help='Require both area and morphology changes for division detection')
@click.option('--division-min-consecutive', type=int, default=1,
              help='Minimum consecutive frames above threshold for division')
@click.option('--no-bleach-correction', is_flag=True, default=False,
              help='Disable photobleaching correction')
@click.option('--bleach-method', type=click.Choice(['exponential']),
              default='exponential', help='Photobleaching correction method')
@click.option('--bleach-per-track', is_flag=True, default=False,
              help='Use per-track bleach correction instead of global')
@click.option('--no-background-correction', is_flag=True, default=False,
              help='Disable background subtraction')
@click.option('--weights-3d', type=click.Path(exists=True, dir_okay=False),
              help='Path to pre-trained 3D U-Net weights (.pth)')
@click.option('--no-3d-segmentation', is_flag=True, default=False,
              help='Disable 3D segmentation (use 2D+Z instead)')
@click.option('--no-z-consistency', is_flag=True, default=False,
              help='Disable Z-axis consistency filtering')
@click.option('--min-object-size-3d', type=int, default=500,
              help='Minimum object size for 3D segmentation (voxels)')
@click.option('--no-phenotype-clustering', is_flag=True, default=False,
              help='Disable phenotype clustering')
@click.option('--clustering-algorithm', type=click.Choice(['kmeans', 'hierarchical', 'dbscan']),
              default='kmeans', help='Clustering algorithm')
@click.option('--n-clusters', type=int, default=3,
              help='Number of phenotype clusters')
@click.option('--no-pca', is_flag=True, default=False,
              help='Disable PCA for clustering')
@click.option('--no-interaction-analysis', is_flag=True, default=False,
              help='Disable cell-cell interaction analysis')
@click.option('--interaction-distance-threshold', type=float, default=15.0,
              help='Maximum distance for interaction detection (pixels)')
@click.option('--contact-distance-threshold', type=float, default=5.0,
              help='Distance threshold for cell contact (pixels)')
@click.option('--min-contact-duration', type=int, default=3,
              help='Minimum consecutive frames for contact')
@click.option('--no-boundary-contact', is_flag=True, default=False,
              help='Disable boundary-based contact area calculation')
@click.option('--gt-masks', type=click.Path(exists=True, dir_okay=False),
              help='Path to ground truth segmentation masks (TIFF)')
@click.option('--gt-tracks', type=click.Path(exists=True, dir_okay=False),
              help='Path to ground truth tracks (CSV)')
@click.option('--gt-divisions', type=click.Path(exists=True, dir_okay=False),
              help='Path to ground truth divisions (CSV)')
@click.option('--show-napari', is_flag=True, default=False,
              help='Open napari viewer after processing')
def run(input_path, weights, output_dir, device, num_workers, no_parallel,
        min_track_length, max_distance, max_lost_frames,
        division_area_threshold, division_area_hysteresis,
        division_morphology_threshold, division_morphology_hysteresis,
        division_require_both, division_min_consecutive,
        no_bleach_correction, bleach_method, bleach_per_track,
        no_background_correction,
        weights_3d, no_3d_segmentation, no_z_consistency, min_object_size_3d,
        no_phenotype_clustering, clustering_algorithm, n_clusters, no_pca,
        no_interaction_analysis, interaction_distance_threshold,
        contact_distance_threshold, min_contact_duration, no_boundary_contact,
        gt_masks, gt_tracks, gt_divisions,
        show_napari):
    """Run the complete cell tracking pipeline.
    
    INPUT_PATH: Path to TIFF stack image sequence
    """
    click.echo("=" * 60)
    click.echo("Cell Tracking Analysis Pipeline")
    click.echo("=" * 60)
    
    click.echo("\nTracking options:")
    click.echo(f"  Motion prediction: Kalman filter (adaptive distance)")
    click.echo(f"  Max distance: {max_distance} px")
    click.echo(f"  Max lost frames: {max_lost_frames}")
    
    click.echo("\nDivision detection options:")
    click.echo(f"  Area threshold: {division_area_threshold} (hysteresis: {division_area_hysteresis})")
    click.echo(f"  Morphology threshold: {division_morphology_threshold} (hysteresis: {division_morphology_hysteresis})")
    click.echo(f"  Require both metrics: {division_require_both}")
    click.echo(f"  Min consecutive frames: {division_min_consecutive}")
    
    click.echo("\nPhotobleaching correction:")
    click.echo(f"  Enabled: {not no_bleach_correction}")
    click.echo(f"  Method: {bleach_method}")
    click.echo(f"  Mode: {'per-track' if bleach_per_track else 'global'}")
    click.echo(f"  Background subtraction: {not no_background_correction}")
    
    click.echo("")
    
    pipeline = CellTrackingPipeline(
        weights_path=weights,
        weights_path_3d=weights_3d,
        device=device,
        num_workers=num_workers,
        use_parallel=not no_parallel,
        output_dir=output_dir,
        tracking_max_distance=max_distance,
        tracking_max_lost_frames=max_lost_frames,
        division_area_drop_threshold=division_area_threshold,
        division_area_hysteresis=division_area_hysteresis,
        division_morphology_threshold=division_morphology_threshold,
        division_morphology_hysteresis=division_morphology_hysteresis,
        division_require_both_metrics=division_require_both,
        division_min_consecutive_frames=division_min_consecutive,
        photobleach_correction=not no_bleach_correction,
        photobleach_method=bleach_method,
        photobleach_global=not bleach_per_track,
        background_correction=not no_background_correction,
        use_3d_segmentation=not no_3d_segmentation,
        use_z_consistency=not no_z_consistency,
        min_object_size_3d=min_object_size_3d,
        enable_phenotype_clustering=not no_phenotype_clustering,
        clustering_algorithm=clustering_algorithm,
        n_clusters=n_clusters,
        use_pca_for_clustering=not no_pca,
        enable_interaction_analysis=not no_interaction_analysis,
        interaction_distance_threshold=interaction_distance_threshold,
        contact_distance_threshold=contact_distance_threshold,
        min_contact_duration=min_contact_duration,
        use_boundary_contact=not no_boundary_contact
    )
    
    pipeline.tracker.min_track_length = min_track_length
    
    try:
        results = pipeline.run_full_pipeline(
            input_path=input_path,
            gt_masks_path=gt_masks,
            gt_tracks_path=gt_tracks,
            gt_divisions_path=gt_divisions,
            show_napari=show_napari
        )
        
        click.echo("\n" + "=" * 60)
        click.echo("RESULTS SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Frames analyzed:    {results['n_frames']}")
        click.echo(f"Tracks found:       {results['n_tracks']}")
        click.echo(f"Divisions detected: {results['n_divisions']}")
        if results.get('is_3d_data'):
            click.echo(f"Data type:          3D volumetric")
        if results.get('n_phenotype_clusters', 0) > 0:
            click.echo(f"Phenotype clusters: {results['n_phenotype_clusters']}")
        if results.get('n_cell_contacts', 0) > 0:
            click.echo(f"Cell contacts:      {results['n_cell_contacts']}")
        click.echo(f"Output directory:   {results['output_dir']}")
        
        if results.get('evaluation'):
            click.echo("\nEvaluation Metrics:")
            if 'segmentation' in results['evaluation']:
                seg = results['evaluation']['segmentation']
                click.echo(f"  Segmentation IoU: {seg['mean_iou']:.4f}")
                click.echo(f"  Segmentation F1:  {seg['mean_f1']:.4f}")
            if 'tracking' in results['evaluation']:
                track = results['evaluation']['tracking']
                click.echo(f"  Track accuracy:   {track['track_accuracy']:.4f}")
                click.echo(f"  Track switches:   {track['total_switches']}")
            if 'division' in results['evaluation']:
                div = results['evaluation']['division']
                click.echo(f"  Division F1:      {div['f1']:.4f}")
        
        click.echo("\nPipeline completed successfully!")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--weights', '-w', type=click.Path(exists=True, dir_okay=False),
              help='Path to pre-trained U-Net weights (.pth)')
@click.option('--output', '-o', type=click.Path(dir_okay=False),
              default='segmentation.tiff', help='Output segmentation file')
@click.option('--device', '-d', type=click.Choice(['auto', 'cpu', 'cuda']),
              default='auto', help='Computation device')
@click.option('--num-workers', '-j', type=int, default=4,
              help='Number of parallel workers')
@click.option('--no-parallel', is_flag=True, default=False,
              help='Disable parallel processing')
@click.option('--threshold', type=float, default=0.5,
              help='Segmentation probability threshold')
@click.option('--min-size', type=int, default=100,
              help='Minimum object size (pixels)')
def segment(input_path, weights, output, device, num_workers, no_parallel,
            threshold, min_size):
    """Run U-Net segmentation only.
    
    INPUT_PATH: Path to TIFF stack image sequence
    """
    click.echo("Running U-Net segmentation...")
    
    from .segmentation import UNetSegmenter
    from .parallel import parallel_segmentation
    from .utils import save_tiff_stack
    
    images = load_tiff_stack(input_path)
    
    segmenter = UNetSegmenter(
        weights_path=weights,
        device=device,
        threshold=threshold,
        min_object_size=min_size
    )
    
    if not no_parallel and num_workers > 1:
        masks = parallel_segmentation(
            segmenter=segmenter,
            frames=images,
            num_workers=num_workers,
            use_threads=True
        )
    else:
        masks = segmenter.segment_stack(images, parallel=False)
    
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_tiff_stack(masks.astype(np.uint16), str(output_path))
    
    click.echo(f"Segmentation complete. Output saved to: {output_path}")
    click.echo(f"Segmented {masks.shape[0]} frames.")


@cli.command()
@click.argument('masks_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--image-path', '-i', type=click.Path(exists=True, dir_okay=False),
              help='Path to raw image for fluorescence extraction')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False),
              default='./tracking_output', help='Output directory')
@click.option('--max-distance', type=float, default=50.0,
              help='Maximum distance for tracking (pixels)')
@click.option('--min-track-length', type=int, default=5,
              help='Minimum track length to keep')
@click.option('--detect-divisions', is_flag=True, default=True,
              help='Detect division events')
@click.option('--show-napari', is_flag=True, default=False,
              help='Open napari viewer after processing')
def track(masks_path, image_path, output_dir, max_distance, min_track_length,
          detect_divisions, show_napari):
    """Run cell tracking from segmentation masks.
    
    MASKS_PATH: Path to segmentation masks (TIFF stack)
    """
    click.echo("Running cell tracking...")
    
    from .tracking import CellTracker
    from .division_detection import DivisionDetector
    from .features import FeatureExtractor
    from .visualization import NapariVisualizer
    from .utils import load_tiff_stack, save_tiff_stack
    
    masks = load_tiff_stack(masks_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tracker = CellTracker(
        max_distance=max_distance,
        min_track_length=min_track_length
    )
    
    image_stack = None
    feature_extractor = None
    fluo_df = None
    
    if image_path:
        image_stack = load_tiff_stack(image_path)
        feature_extractor = FeatureExtractor()
        feature_extractor.extract_fluorescence(image_stack, masks)
        feature_extractor.get_fluorescence_for_tracker(tracker)
        fluo_df = feature_extractor.get_fluorescence_timeseries(tracker)
        fluo_df.to_csv(output_dir / "fluorescence_timeseries.csv", index=False)
    
    n_frames = masks.shape[0]
    from tqdm import tqdm
    
    for frame in tqdm(range(n_frames), desc="Tracking"):
        fluo_values = None
        if feature_extractor:
            fluo_values = {
                label: fluo['mean']
                for label, fluo in feature_extractor.fluorescence_data.get(frame, {}).items()
            }
        tracker.update(frame, masks[frame], fluo_values)
    
    tracker.filter_short_tracks()
    
    tracks_df = tracker.get_tracks_dataframe()
    tracks_df.to_csv(output_dir / "tracks.csv", index=False)
    
    track_masks = tracker.get_tracks_overlay(masks)
    save_tiff_stack(track_masks.astype(np.uint16), output_dir / "track_masks.tiff")
    
    division_events = None
    if detect_divisions:
        division_detector = DivisionDetector()
        division_events = division_detector.detect_divisions(tracker, masks)
        division_df = division_detector.get_division_dataframe()
        if not division_df.empty:
            division_df.to_csv(output_dir / "division_events.csv", index=False)
    
    click.echo(f"Tracking complete. Found {len(tracker.tracks)} tracks.")
    if division_events:
        click.echo(f"Detected {len(division_events)} division events.")
    
    if show_napari and image_stack is not None:
        visualizer = NapariVisualizer()
        visualizer.visualize_all(
            image_stack=image_stack,
            masks=masks,
            tracker=tracker,
            division_events=division_events,
            fluo_timeseries=fluo_df
        )
        visualizer.show()


@cli.command()
@click.argument('pred_path', type=click.Path(exists=True, dir_okay=False))
@click.argument('gt_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--mode', '-m', type=click.Choice(['segmentation', 'tracking', 'all']),
              default='all', help='Evaluation mode')
@click.option('--pred-tracks', type=click.Path(exists=True, dir_okay=False),
              help='Predicted tracks CSV (for tracking evaluation)')
@click.option('--gt-tracks', type=click.Path(exists=True, dir_okay=False),
              help='Ground truth tracks CSV (for tracking evaluation)')
@click.option('--output', '-o', type=click.Path(file_okay=False),
              default='evaluation_results.csv', help='Output file')
@click.option('--iou-threshold', type=float, default=0.5,
              help='IoU threshold for segmentation evaluation')
def evaluate(pred_path, gt_path, mode, pred_tracks, gt_tracks, output, iou_threshold):
    """Evaluate results against ground truth.
    
    PRED_PATH: Path to predicted segmentation masks (TIFF)
    GT_PATH: Path to ground truth segmentation masks (TIFF)
    """
    click.echo("Running evaluation...")
    
    from .evaluation import Evaluator
    from .utils import load_tiff_stack
    
    pred_masks = load_tiff_stack(pred_path)
    gt_masks = load_tiff_stack(gt_path)
    
    evaluator = Evaluator(iou_threshold=iou_threshold)
    
    results = {}
    
    if mode in ['segmentation', 'all']:
        results['segmentation'] = evaluator.evaluate_segmentation(pred_masks, gt_masks)
    
    if mode in ['tracking', 'all']:
        if pred_tracks and gt_tracks:
            from .tracking import CellTracker
            
            pred_tracks_df = pd.read_csv(pred_tracks)
            gt_tracks_df = pd.read_csv(gt_tracks)
            
            tracker = CellTracker()
            for track_id in pred_tracks_df['track_id'].unique():
                track_data = pred_tracks_df[pred_tracks_df['track_id'] == track_id]
                for _, row in track_data.iterrows():
                    tracker.tracks[track_id] = tracker.tracks.get(track_id, __import__('cell_tracker.tracking', fromlist=['CellTrack']).CellTrack(track_id))
                    tracker.tracks[track_id].add_detection(
                        frame=int(row['frame']),
                        label=int(row.get('label', track_id)),
                        centroid=(row['y'], row['x']),
                        area=row.get('area', 0),
                        properties={},
                        fluorescence=row.get('fluorescence', 0)
                    )
            
            results['tracking'] = evaluator.evaluate_tracking(tracker, gt_tracks_df)
        else:
            click.echo("Warning: Provide --pred-tracks and --gt-tracks for tracking evaluation")
    
    report = evaluator.generate_report(results)
    click.echo("\n" + report)
    
    metrics_df = evaluator.get_metrics_dataframe()
    metrics_df.to_csv(output, index=False)
    click.echo(f"\nEvaluation metrics saved to: {output}")


@cli.command()
@click.argument('image-path', type=click.Path(exists=True, dir_okay=False))
@click.option('--masks-path', '-m', type=click.Path(exists=True, dir_okay=False),
              help='Path to segmentation masks')
@click.option('--tracks-path', '-t', type=click.Path(exists=True, dir_okay=False),
              help='Path to tracks CSV')
@click.option('--track-masks', type=click.Path(exists=True, dir_okay=False),
              help='Path to track masks')
@click.option('--division-events', type=click.Path(exists=True, dir_okay=False),
              help='Path to division events CSV')
@click.option('--fluorescence-path', '-f', type=click.Path(exists=True, dir_okay=False),
              help='Path to fluorescence timeseries CSV')
def visualize(image_path, masks_path, tracks_path, track_masks, division_events,
              fluorescence_path):
    """Visualize results with napari.
    
    IMAGE_PATH: Path to raw image TIFF stack
    """
    click.echo("Opening napari viewer...")
    
    from .visualization import NapariVisualizer
    from .utils import load_tiff_stack
    
    image_stack = load_tiff_stack(image_path)
    visualizer = NapariVisualizer()
    
    visualizer.add_image(image_stack, name="Raw Image")
    
    if masks_path:
        masks = load_tiff_stack(masks_path)
        visualizer.add_segmentation(masks, name="Segmentation")
    
    if tracks_path and masks_path:
        from .tracking import CellTracker
        
        masks = load_tiff_stack(masks_path)
        tracks_df = pd.read_csv(tracks_path)
        
        tracker = CellTracker()
        for track_id in tracks_df['track_id'].unique():
            track_data = tracks_df[tracks_df['track_id'] == track_id]
            for _, row in track_data.iterrows():
                from .tracking import CellTrack
                tracker.tracks[track_id] = tracker.tracks.get(track_id, CellTrack(track_id))
                tracker.tracks[track_id].add_detection(
                    frame=int(row['frame']),
                    label=int(row.get('label', track_id)),
                    centroid=(row['y'], row['x']),
                    area=row.get('area', 0),
                    properties={},
                    fluorescence=row.get('fluorescence', 0)
                )
        
        visualizer.add_tracks(tracker, masks, name="Tracks")
    
    if track_masks:
        track_masks_data = load_tiff_stack(track_masks)
        visualizer.add_segmentation(track_masks_data, name="Track Masks", opacity=0.7)
    
    if division_events and tracks_path and masks_path:
        from .division_detection import DivisionDetector
        
        divisions_df = pd.read_csv(division_events)
        div_events = []
        for _, row in divisions_df.iterrows():
            div_events.append({
                'parent_id': int(row['parent_id']),
                'children_ids': list(map(int, row['children_ids'].split(','))),
                'frame': int(row['frame']),
                'next_frame': int(row['frame']) + 1,
                'parent_centroid': (row['parent_y'], row['parent_x']),
                'parent_area': row['parent_area'],
                'children_areas': [row.get('child1_area', 0), row.get('child2_area', 0)],
                'children_centroids': [(row.get('child1_y', 0), row.get('child1_x', 0)),
                                       (row.get('child2_y', 0), row.get('child2_x', 0))],
            })
        
        masks = load_tiff_stack(masks_path)
        visualizer.add_division_events(div_events, tracker, masks)
    
    if fluorescence_path and masks_path and tracks_path:
        fluo_df = pd.read_csv(fluorescence_path)
        masks = load_tiff_stack(masks_path)
        visualizer.add_fluorescence_overlay(fluo_df, masks, tracker)
    
    visualizer.show()


@cli.command()
@click.option('--output-path', '-o', type=click.Path(dir_okay=False),
              default='test_data.tiff', help='Output test data path')
@click.option('--n-frames', type=int, default=50,
              help='Number of frames to generate')
@click.option('--n-cells', type=int, default=10,
              help='Number of simulated cells')
@click.option('--image-size', type=int, default=256,
              help='Image size (pixels)')
@click.option('--add-noise', is_flag=True, default=True,
              help='Add noise to simulated images')
def generate_test_data(output_path, n_frames, n_cells, image_size, add_noise):
    """Generate synthetic test data for validation.
    
    Creates a simulated TIFF stack with moving/dividing cells.
    """
    click.echo(f"Generating test data: {n_frames} frames, {n_cells} cells, {image_size}x{image_size}...")
    
    from .utils import save_tiff_stack
    
    np.random.seed(42)
    
    images = np.zeros((n_frames, image_size, image_size), dtype=np.float32)
    masks = np.zeros((n_frames, image_size, image_size), dtype=np.int32)
    
    cells = []
    for i in range(n_cells):
        cell = {
            'id': i + 1,
            'x': np.random.randint(30, image_size - 30),
            'y': np.random.randint(30, image_size - 30),
            'vx': np.random.randn() * 2,
            'vy': np.random.randn() * 2,
            'radius': np.random.randint(10, 20),
            'fluorescence': np.random.uniform(100, 500),
            'alive': True,
            'division_frame': np.random.choice([-1, np.random.randint(10, max(n_frames - 5, 11))]) if n_frames > 15 else -1,
            'children': [],
        }
        cells.append(cell)
    
    for frame in range(n_frames):
        for cell in cells:
            if not cell['alive']:
                continue
            
            if cell['division_frame'] == frame and not cell['children']:
                cell['alive'] = False
                
                for j in range(2):
                    child = {
                        'id': len(cells) + 1,
                        'x': cell['x'] + np.random.randn() * 5,
                        'y': cell['y'] + np.random.randn() * 5,
                        'vx': np.random.randn() * 2 + cell['vx'],
                        'vy': np.random.randn() * 2 + cell['vy'],
                        'radius': cell['radius'] * 0.6,
                        'fluorescence': cell['fluorescence'] * 0.5,
                        'alive': True,
                        'division_frame': -1,
                        'children': [],
                    }
                    cells.append(child)
                    cell['children'].append(child['id'])
                continue
            
            cell['x'] += cell['vx']
            cell['y'] += cell['vy']
            
            if cell['x'] < cell['radius']:
                cell['x'] = cell['radius']
                cell['vx'] *= -0.8
            if cell['x'] > image_size - cell['radius']:
                cell['x'] = image_size - cell['radius']
                cell['vx'] *= -0.8
            if cell['y'] < cell['radius']:
                cell['y'] = cell['radius']
                cell['vy'] *= -0.8
            if cell['y'] > image_size - cell['radius']:
                cell['y'] = image_size - cell['radius']
                cell['vy'] *= -0.8
            
            y, x = np.ogrid[:image_size, :image_size]
            dist_from_center = np.sqrt((x - cell['x']) ** 2 + (y - cell['y']) ** 2)
            
            cell_image = np.exp(-dist_from_center ** 2 / (2 * cell['radius'] ** 2))
            cell_image *= cell['fluorescence']
            images[frame] += cell_image
            
            cell_mask = dist_from_center < cell['radius']
            masks[frame][cell_mask] = cell['id']
    
    if add_noise:
        noise = np.random.normal(0, 10, images.shape)
        images += noise
    
    images = np.clip(images, 0, None).astype(np.uint16)
    
    save_tiff_stack(images, output_path)
    
    masks_path = Path(output_path).parent / "test_masks.tiff"
    save_tiff_stack(masks.astype(np.uint16), str(masks_path))
    
    tracks_data = []
    for cell in cells:
        if cell['alive']:
            frames = list(range(n_frames))
        else:
            frames = list(range(cell['division_frame']))
        
        for f in frames:
            tracks_data.append({
                'track_id': cell['id'],
                'frame': f,
                'y': cell['y'] + cell['vy'] * (f - frames[0]),
                'x': cell['x'] + cell['vx'] * (f - frames[0]),
                'area': np.pi * cell['radius'] ** 2,
                'fluorescence': cell['fluorescence'],
                'parent_id': None if cell['division_frame'] == -1 else None,
            })
    
    tracks_df = pd.DataFrame(tracks_data)
    tracks_path = Path(output_path).parent / "test_tracks.csv"
    tracks_df.to_csv(tracks_path, index=False)
    
    click.echo(f"Test data saved to: {output_path}")
    click.echo(f"Ground truth masks: {masks_path}")
    click.echo(f"Ground truth tracks: {tracks_path}")


@cli.command()
@click.argument('masks_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--image-path', '-i', type=click.Path(exists=True, dir_okay=False),
              help='Path to raw image for feature extraction')
@click.option('--division-events', type=click.Path(exists=True, dir_okay=False),
              help='Path to division events CSV')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False),
              default='./clustering_output', help='Output directory')
@click.option('--algorithm', '-a', type=click.Choice(['kmeans', 'hierarchical', 'dbscan']),
              default='kmeans', help='Clustering algorithm')
@click.option('--n-clusters', '-k', type=int, default=3,
              help='Number of clusters')
@click.option('--no-pca', is_flag=True, default=False,
              help='Disable PCA dimensionality reduction')
@click.option('--include-motion/--no-motion', default=True,
              help='Include motion features')
@click.option('--include-division/--no-division', default=True,
              help='Include division features')
@click.option('--include-morphology/--no-morphology', default=True,
              help='Include morphology features')
@click.option('--include-fluorescence/--no-fluorescence', default=True,
              help='Include fluorescence features')
def cluster_phenotypes(masks_path, image_path, division_events, output_dir,
                       algorithm, n_clusters, no_pca,
                       include_motion, include_division, include_morphology, include_fluorescence):
    """Cluster cells by phenotype based on tracking features.
    
    MASKS_PATH: Path to track masks (TIFF stack)
    """
    from .tracking import CellTracker
    from .phenotype_clustering import (
        TrackFeatureExtractor, PhenotypeClusterer, assign_phenotype_names
    )
    from .utils import load_tiff_stack
    
    click.echo("Running phenotype clustering...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    masks = load_tiff_stack(masks_path)
    
    tracker = CellTracker()
    tracker.tracks = {}
    unique_labels = np.unique(masks)
    unique_labels = unique_labels[unique_labels != 0]
    
    for label in unique_labels:
        from .tracking import CellTrack
        track = CellTrack(int(label))
        for frame in range(len(masks)):
            mask = masks[frame] == label
            if np.any(mask):
                y, x = np.where(mask)
                centroid = (float(np.mean(y)), float(np.mean(x)))
                track.add_detection(
                    frame=frame,
                    label=int(label),
                    centroid=centroid,
                    area=int(np.sum(mask)),
                    properties={}
                )
        if len(track.frames) >= 3:
            tracker.tracks[int(label)] = track
    
    division_df = None
    if division_events and Path(division_events).exists():
        division_df = pd.read_csv(division_events)
    
    feature_data = None
    if image_path and Path(image_path).exists():
        from .features import FeatureExtractor
        images = load_tiff_stack(image_path)
        extractor = FeatureExtractor()
        extractor.extract_all_features(images, masks)
        
        feature_rows = []
        for frame, frame_data in extractor.features_data.items():
            for label, feats in frame_data.items():
                row = {'frame': frame, 'label': label, 'track_id': int(label)}
                row.update(feats)
                feature_rows.append(row)
        if feature_rows:
            feature_data = pd.DataFrame(feature_rows)
    
    feat_extractor = TrackFeatureExtractor(
        include_motion=include_motion,
        include_division=include_division,
        include_morphology=include_morphology,
        include_fluorescence=include_fluorescence
    )
    
    features_df = feat_extractor.extract_features(
        tracker=tracker,
        feature_data=feature_data,
        division_data=division_df,
        masks=masks
    )
    
    if len(features_df) < n_clusters:
        click.echo(f"Warning: Only {len(features_df)} tracks, need at least {n_clusters} for clustering")
        return
    
    clusterer = PhenotypeClusterer(
        algorithm=algorithm,
        n_clusters=n_clusters,
        use_pca=not no_pca
    )
    
    result = clusterer.cluster(features_df)
    result.clusters = assign_phenotype_names(result.clusters)
    
    labels_df = pd.DataFrame([
        {'track_id': tid, 'phenotype_cluster': cid, 'cluster_name': result.clusters[cid].name}
        for tid, cid in result.labels.items()
    ])
    labels_df.to_csv(output_dir / "phenotype_labels.csv", index=False)
    
    features_df['phenotype_cluster'] = features_df['track_id'].map(result.labels)
    features_df.to_csv(output_dir / "phenotype_features.csv", index=False)
    
    cluster_summary = []
    for cid, cluster in result.clusters.items():
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
        output_dir / "phenotype_cluster_summary.csv", index=False
    )
    
    if result.pca_coordinates is not None:
        pca_df = pd.DataFrame([
            {'track_id': tid, 'pc1': pc[0], 'pc2': pc[1],
             'phenotype_cluster': result.labels[tid],
             'cluster_name': result.clusters[result.labels[tid]].name}
            for tid, pc in result.pca_coordinates.items()
        ])
        pca_df.to_csv(output_dir / "phenotype_pca_coordinates.csv", index=False)
    
    click.echo(f"\nPhenotype clustering complete.")
    click.echo(f"  Tracks: {len(features_df)}")
    click.echo(f"  Clusters: {len(result.clusters)}")
    for cid, cluster in result.clusters.items():
        click.echo(f"    Cluster {cid} ({cluster.name}): {len(cluster.member_track_ids)} cells")
    
    if 'silhouette_score' in result.cluster_metrics:
        click.echo(f"\nClustering metrics:")
        click.echo(f"  Silhouette score: {result.cluster_metrics['silhouette_score']:.4f}")
        click.echo(f"  Calinski-Harabasz: {result.cluster_metrics['calinski_harabasz']:.4f}")
    
    click.echo(f"\nResults saved to: {output_dir}")


@cli.command()
@click.argument('masks_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--image-path', '-i', type=click.Path(exists=True, dir_okay=False),
              help='Path to raw image (for fluorescence features)')
@click.option('--tracks-path', '-t', type=click.Path(exists=True, dir_okay=False),
              help='Path to tracks CSV')
@click.option('--phenotype-labels', type=click.Path(exists=True, dir_okay=False),
              help='Path to phenotype labels CSV')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False),
              default='./interaction_output', help='Output directory')
@click.option('--distance-threshold', type=float, default=15.0,
              help='Maximum distance for interaction detection (pixels)')
@click.option('--contact-distance', type=float, default=5.0,
              help='Distance threshold for cell contact (pixels)')
@click.option('--min-contact-duration', type=int, default=3,
              help='Minimum consecutive frames for contact')
@click.option('--no-boundary-contact', is_flag=True, default=False,
              help='Disable boundary-based contact area calculation')
@click.option('--dilation-radius', type=int, default=2,
              help='Boundary dilation radius for contact area')
def analyze_interactions(masks_path, image_path, tracks_path, phenotype_labels,
                         output_dir, distance_threshold, contact_distance,
                         min_contact_duration, no_boundary_contact, dilation_radius):
    """Analyze cell-cell interactions and contacts.
    
    MASKS_PATH: Path to segmentation/track masks (TIFF stack)
    """
    from .tracking import CellTracker, CellTrack
    from .interaction_analysis import (
        InteractionAnalyzer, compute_interaction_statistics,
        analyze_temporal_interaction_patterns, identify_leader_follower_pairs
    )
    from .utils import load_tiff_stack
    
    click.echo("Running cell-cell interaction analysis...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    masks = load_tiff_stack(masks_path)
    
    tracker = CellTracker()
    tracker.tracks = {}
    
    if tracks_path and Path(tracks_path).exists():
        tracks_df = pd.read_csv(tracks_path)
        for track_id in tracks_df['track_id'].unique():
            track_data = tracks_df[tracks_df['track_id'] == track_id]
            track = CellTrack(int(track_id))
            for _, row in track_data.iterrows():
                track.add_detection(
                    frame=int(row['frame']),
                    label=int(row.get('label', track_id)),
                    centroid=(float(row['y']), float(row['x'])),
                    area=float(row.get('area', 0)),
                    properties={}
                )
            if len(track.frames) >= 3:
                tracker.tracks[int(track_id)] = track
    else:
        unique_labels = np.unique(masks)
        unique_labels = unique_labels[unique_labels != 0]
        
        for label in unique_labels:
            track = CellTrack(int(label))
            for frame in range(len(masks)):
                mask = masks[frame] == label
                if np.any(mask):
                    y, x = np.where(mask)
                    centroid = (float(np.mean(y)), float(np.mean(x)))
                    track.add_detection(
                        frame=frame,
                        label=int(label),
                        centroid=centroid,
                        area=int(np.sum(mask)),
                        properties={}
                    )
            if len(track.frames) >= 3:
                tracker.tracks[int(label)] = track
    
    phenotype_label_dict = None
    phenotype_name_dict = None
    if phenotype_labels and Path(phenotype_labels).exists():
        pheno_df = pd.read_csv(phenotype_labels)
        phenotype_label_dict = dict(zip(pheno_df['track_id'], pheno_df['phenotype_cluster']))
        if 'cluster_name' in pheno_df.columns:
            phenotype_name_dict = dict(zip(pheno_df['phenotype_cluster'], pheno_df['cluster_name']))
    
    feature_data = None
    if image_path and Path(image_path).exists():
        from .features import FeatureExtractor
        images = load_tiff_stack(image_path)
        extractor = FeatureExtractor()
        extractor.extract_all_features(images, masks)
        
        feature_rows = []
        for frame, frame_data in extractor.features_data.items():
            for label, feats in frame_data.items():
                row = {'frame': frame, 'label': label}
                row.update(feats)
                feature_rows.append(row)
        if feature_rows:
            feature_data = pd.DataFrame(feature_rows)
    
    analyzer = InteractionAnalyzer(
        distance_threshold=distance_threshold,
        contact_distance_threshold=contact_distance,
        min_contact_duration=min_contact_duration,
        use_boundary_contact=not no_boundary_contact,
        boundary_dilation_radius=dilation_radius
    )
    
    result = analyzer.analyze_interactions(
        tracker=tracker,
        masks=masks,
        feature_data=feature_data,
        phenotype_labels=phenotype_label_dict,
        phenotype_names=phenotype_name_dict
    )
    
    result.contact_summary.to_csv(output_dir / "cell_contacts.csv", index=False)
    result.frame_by_frame.to_csv(output_dir / "interactions_frame_by_frame.csv", index=False)
    result.interaction_matrix.to_csv(output_dir / "interaction_matrix.csv")
    
    stats = compute_interaction_statistics(
        result, phenotype_labels=phenotype_label_dict
    )
    with open(output_dir / "interaction_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    
    temporal_stats = analyze_temporal_interaction_patterns(result)
    if len(temporal_stats) > 0:
        temporal_stats.to_csv(output_dir / "interaction_temporal_patterns.csv", index=False)
    
    leader_follower = identify_leader_follower_pairs(result, tracker)
    if leader_follower:
        pd.DataFrame(leader_follower).to_csv(
            output_dir / "leader_follower_pairs.csv", index=False
        )
    
    click.echo(f"\nInteraction analysis complete.")
    click.echo(f"  Cells analyzed: {len(tracker.tracks)}")
    click.echo(f"  Total contacts: {stats['total_contacts']}")
    click.echo(f"  Mean duration: {stats.get('mean_duration', 0):.1f} frames")
    
    if 'contact_types' in stats:
        click.echo("\nContact types:")
        for ctype, count in stats['contact_types'].items():
            click.echo(f"  {ctype}: {count}")
    
    if 'homotypic_contacts' in stats:
        click.echo(f"\nPhenotype interactions:")
        click.echo(f"  Homotypic: {stats['homotypic_contacts']}")
        click.echo(f"  Heterotypic: {stats['heterotypic_contacts']}")
        click.echo(f"  Homotypic ratio: {stats['homotypic_ratio']:.2%}")
    
    if leader_follower:
        click.echo(f"\nLeader-follower pairs: {len(leader_follower)}")
    
    click.echo(f"\nResults saved to: {output_dir}")


if __name__ == '__main__':
    cli()
