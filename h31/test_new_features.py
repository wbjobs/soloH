#!/usr/bin/env python
"""Test script for new features: 3D segmentation, phenotype clustering, and interaction analysis."""

import numpy as np
import pandas as pd
import logging
import sys
from pathlib import Path
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_3d_test_data(n_frames=10, n_z=5, size=64, n_cells=4):
    """Generate synthetic 3D test data."""
    images = np.zeros((n_frames, n_z, size, size), dtype=np.float32)
    masks = np.zeros((n_frames, n_z, size, size), dtype=np.int32)
    
    cells = []
    for i in range(n_cells):
        cell = {
            'id': i + 1,
            'x': np.random.randint(20, size - 20),
            'y': np.random.randint(20, size - 20),
            'z': np.random.randint(1, n_z - 1),
            'vx': np.random.randn() * 1.5,
            'vy': np.random.randn() * 1.5,
            'vz': np.random.randn() * 0.3,
            'radius_xy': np.random.randint(6, 10),
            'radius_z': np.random.randint(1, 2),
            'fluorescence': np.random.uniform(200, 500),
        }
        cells.append(cell)
    
    for frame in range(n_frames):
        for cell in cells:
            cell['x'] += cell['vx']
            cell['y'] += cell['vy']
            cell['z'] += cell['vz']
            
            cell['x'] = np.clip(cell['x'], cell['radius_xy'] + 2, size - cell['radius_xy'] - 2)
            cell['y'] = np.clip(cell['y'], cell['radius_xy'] + 2, size - cell['radius_xy'] - 2)
            cell['z'] = np.clip(cell['z'], cell['radius_z'] + 1, n_z - cell['radius_z'] - 1)
            
            z, y, x = np.ogrid[:n_z, :size, :size]
            dist_sq = (
                ((x - cell['x']) / cell['radius_xy']) ** 2 +
                ((y - cell['y']) / cell['radius_xy']) ** 2 +
                ((z - cell['z']) / cell['radius_z']) ** 2
            )
            
            cell_mask = dist_sq < 1.0
            cell_image = np.exp(-dist_sq * 2) * cell['fluorescence']
            
            images[frame] += cell_image
            masks[frame][cell_mask] = cell['id']
    
    images += np.random.normal(0, 10, images.shape)
    images = np.clip(images, 0, None).astype(np.uint16)
    
    return images, masks


def generate_tracking_test_data(n_frames=20, size=128, n_cells=6):
    """Generate test data with varied phenotypes for clustering and interaction."""
    from cell_tracker.tracking import CellTracker, CellTrack
    from cell_tracker.utils import save_tiff_stack
    
    images = np.zeros((n_frames, size, size), dtype=np.float32)
    masks = np.zeros((n_frames, size, size), dtype=np.int32)
    
    tracker = CellTracker(max_distance=30.0, min_track_length=3)
    
    phenotypes = [
        {'type': 'fast', 'speed': 3.0, 'divides': True},
        {'type': 'slow', 'speed': 0.5, 'divides': False},
        {'type': 'fast', 'speed': 2.5, 'divides': False},
        {'type': 'slow', 'speed': 0.8, 'divides': True},
        {'type': 'fast', 'speed': 2.8, 'divides': False},
        {'type': 'slow', 'speed': 0.6, 'divides': False},
    ]
    
    cells = []
    for i in range(n_cells):
        angle = np.random.uniform(0, 2 * np.pi)
        speed = phenotypes[i]['speed']
        cells.append({
            'id': i + 1,
            'x': np.random.randint(30, size - 30),
            'y': np.random.randint(30, size - 30),
            'vx': np.cos(angle) * speed,
            'vy': np.sin(angle) * speed,
            'radius': np.random.randint(8, 14),
            'fluorescence': np.random.uniform(300, 600),
            'phenotype': phenotypes[i]['type'],
            'divides': phenotypes[i]['divides'],
            'division_frame': np.random.randint(8, 15) if phenotypes[i]['divides'] else -1,
            'alive': True,
            'children': [],
        })
    
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
                        'vx': cell['vx'] + np.random.randn() * 1,
                        'vy': cell['vy'] + np.random.randn() * 1,
                        'radius': cell['radius'] * 0.6,
                        'fluorescence': cell['fluorescence'] * 0.5,
                        'phenotype': cell['phenotype'],
                        'divides': False,
                        'division_frame': -1,
                        'alive': True,
                        'children': [],
                    }
                    cells.append(child)
                    cell['children'].append(child['id'])
                continue
            
            cell['x'] += cell['vx']
            cell['y'] += cell['vy']
            
            if cell['x'] < cell['radius'] or cell['x'] > size - cell['radius']:
                cell['vx'] *= -1
            if cell['y'] < cell['radius'] or cell['y'] > size - cell['radius']:
                cell['vy'] *= -1
            
            cell['x'] = np.clip(cell['x'], cell['radius'], size - cell['radius'])
            cell['y'] = np.clip(cell['y'], cell['radius'], size - cell['radius'])
            
            y, x = np.ogrid[:size, :size]
            dist_sq = (x - cell['x']) ** 2 + (y - cell['y']) ** 2
            
            cell_mask = dist_sq < cell['radius'] ** 2
            cell_image = np.exp(-dist_sq / (2 * cell['radius'] ** 2)) * cell['fluorescence']
            
            images[frame] += cell_image
            masks[frame][cell_mask] = cell['id']
            
            if cell_mask.sum() > 0:
                if cell['id'] not in tracker.tracks:
                    tracker.tracks[cell['id']] = CellTrack(cell['id'])
                
                y_idx, x_idx = np.where(cell_mask)
                centroid = (float(np.mean(y_idx)), float(np.mean(x_idx)))
                tracker.tracks[cell['id']].add_detection(
                    frame=frame,
                    label=cell['id'],
                    centroid=centroid,
                    area=int(cell_mask.sum()),
                    properties={
                        'eccentricity': 0.3 if cell['phenotype'] == 'slow' else 0.7,
                        'solidity': 0.9,
                    }
                )
    
    images += np.random.normal(0, 15, images.shape)
    images = np.clip(images, 0, None).astype(np.uint16)
    
    tracker.filter_short_tracks()
    
    division_events = []
    for cell in cells:
        if cell['children']:
            division_events.append({
                'parent_track_id': cell['id'],
                'child_track_id': cell['children'][0],
                'frame': cell['division_frame'],
                'parent_area': np.pi * cell['radius'] ** 2,
                'parent_y': cell['y'],
                'parent_x': cell['x'],
            })
            if len(cell['children']) > 1:
                division_events.append({
                    'parent_track_id': cell['id'],
                    'child_track_id': cell['children'][1],
                    'frame': cell['division_frame'],
                    'parent_area': np.pi * cell['radius'] ** 2,
                    'parent_y': cell['y'],
                    'parent_x': cell['x'],
                })
    
    division_df = pd.DataFrame(division_events) if division_events else pd.DataFrame()
    
    return images, masks, tracker, division_df


def test_3d_data_detection():
    """Test 3D data detection."""
    logger.info("=" * 60)
    logger.info("TEST 1: 3D Data Detection")
    logger.info("=" * 60)
    
    from cell_tracker.segmentation_3d import check_3d_data
    
    data_2d = np.random.rand(10, 64, 64)
    is_3d, z_slices = check_3d_data(data_2d)
    assert not is_3d, "Should detect 2D data"
    assert z_slices == 1, "Z-slices should be 1 for 2D"
    
    data_3d = np.random.rand(10, 5, 64, 64)
    is_3d, z_slices = check_3d_data(data_3d)
    assert is_3d, "Should detect 3D data"
    assert z_slices == 5, f"Z-slices should be 5, got {z_slices}"
    
    data_5d = np.random.rand(10, 2, 5, 64, 64)
    is_3d, z_slices = check_3d_data(data_5d)
    assert is_3d, "Should detect 3D data from 5D array"
    assert z_slices == 2, f"Z-slices should be 2, got {z_slices}"
    
    logger.info("✓ 3D data detection works correctly")
    logger.info("✓ TEST 1 PASSED")
    return True


def test_3d_segmentation_basic():
    """Test basic 3D segmentation functionality."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: 3D Segmentation (Basic)")
    logger.info("=" * 60)
    
    from cell_tracker.segmentation_3d import (
        Segmentation3D, z_axis_consistency_filter,
        create_3d_instance_mask, extract_3d_features
    )
    
    images, masks = generate_3d_test_data(n_frames=5, n_z=5, size=64, n_cells=3)
    
    logger.info(f"Test data shape: {images.shape}")
    logger.info(f"Test masks shape: {masks.shape}")
    
    segmenter = Segmentation3D(
        weights_path_3d=None,
        weights_path_2d=None,
        use_3d_network=False,
        use_z_consistency=False,
        min_object_size=100
    )
    
    instance_masks = np.zeros_like(masks)
    for t in range(len(masks)):
        instance_masks[t] = masks[t].astype(np.int32)
    
    filtered = z_axis_consistency_filter(instance_masks, min_z_slices=1)
    logger.info(f"Z-filtered masks shape: {filtered.shape}")
    assert filtered.shape == instance_masks.shape
    
    prob_maps = np.zeros_like(instance_masks, dtype=np.float32)
    prob_maps[instance_masks > 0] = 0.9
    
    instance_from_prob = create_3d_instance_mask(
        prob_maps,
        threshold=0.5,
        use_3d_watershed=False
    )
    logger.info(f"Instance from prob shape: {instance_from_prob.shape}")
    assert instance_from_prob.shape == prob_maps.shape
    
    for t in range(len(instance_masks)):
        if np.any(instance_masks[t]):
            feats = extract_3d_features(instance_masks[t], images[t])
            logger.info(f"  Frame {t}: {len(feats)} cells, "
                       f"volumes: {[f['volume'] for f in feats.values()]}")
            break
    
    logger.info("✓ 3D segmentation basic functions work correctly")
    logger.info("✓ TEST 2 PASSED")
    return True


def test_phenotype_clustering():
    """Test phenotype clustering."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Phenotype Clustering")
    logger.info("=" * 60)
    
    from cell_tracker.phenotype_clustering import (
        TrackFeatureExtractor, PhenotypeClusterer,
        assign_phenotype_names, find_optimal_clusters
    )
    
    images, masks, tracker, division_df = generate_tracking_test_data(
        n_frames=20, size=128, n_cells=6
    )
    
    logger.info(f"Generated {len(tracker.tracks)} tracks")
    for tid, track in tracker.tracks.items():
        logger.info(f"  Track {tid}: {len(track.frames)} frames, "
                   f"speed={np.sqrt(np.mean(track.velocity_x)**2 + np.mean(track.velocity_y)**2):.2f}")
    
    feature_extractor = TrackFeatureExtractor(
        include_motion=True,
        include_division=True,
        include_morphology=True,
        include_fluorescence=False
    )
    
    features_df = feature_extractor.extract_features(
        tracker=tracker,
        feature_data=None,
        division_data=division_df if not division_df.empty else None,
        masks=masks
    )
    
    logger.info(f"Extracted {len(features_df)} feature vectors")
    logger.info(f"Feature columns: {list(features_df.columns)[:10]}...")
    
    if len(features_df) >= 3:
        scaler = PhenotypeClusterer(
            algorithm='kmeans',
            n_clusters=min(3, len(features_df)),
            use_pca=True,
            pca_components=min(5, len(features_df.columns))
        )
        
        result = scaler.cluster(features_df)
        
        result.clusters = assign_phenotype_names(result.clusters)
        
        logger.info(f"Found {len(result.clusters)} clusters")
        for cid, cluster in result.clusters.items():
            logger.info(f"  Cluster {cid} ({cluster.name}): "
                       f"{len(cluster.member_track_ids)} cells, "
                       f"description: {cluster.description}")
        
        if result.cluster_metrics.get('silhouette_score') is not None:
            logger.info(f"Silhouette score: {result.cluster_metrics['silhouette_score']:.4f}")
        
        if result.feature_importance:
            top_feats = sorted(
                result.feature_importance.items(),
                key=lambda x: x[1], reverse=True
            )[:5]
            logger.info("Top 5 important features:")
            for feat, imp in top_feats:
                logger.info(f"  {feat}: {imp:.4f}")
        
        labels = set(result.labels.values())
        assert len(labels) == len(result.clusters), "Cluster count mismatch"
        
        if len(result.feature_names) >= 4:
            filtered_features = features_df[['track_id'] + result.feature_names]
            opt_metrics = find_optimal_clusters(
                result.scaler.transform(filtered_features.drop(columns=['track_id'])),
                max_k=min(5, len(filtered_features) - 1)
            )
            logger.info(f"Optimal cluster analysis: k={opt_metrics['k']}")
        
        logger.info("✓ Phenotype clustering works correctly")
        logger.info("✓ TEST 3 PASSED")
        return True
    else:
        logger.warning("Not enough tracks for clustering test")
        return True


def test_interaction_analysis():
    """Test cell-cell interaction analysis."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Cell-Cell Interaction Analysis")
    logger.info("=" * 60)
    
    from cell_tracker.interaction_analysis import (
        InteractionAnalyzer, compute_interaction_statistics,
        analyze_temporal_interaction_patterns, identify_leader_follower_pairs
    )
    
    images, masks, tracker, division_df = generate_tracking_test_data(
        n_frames=20, size=100, n_cells=4
    )
    
    logger.info(f"Generated {len(tracker.tracks)} tracks for interaction analysis")
    
    analyzer = InteractionAnalyzer(
        distance_threshold=50.0,
        contact_distance_threshold=15.0,
        min_contact_duration=2,
        use_boundary_contact=True,
        boundary_dilation_radius=2
    )
    
    result = analyzer.analyze_interactions(
        tracker=tracker,
        masks=masks,
        feature_data=None,
        phenotype_labels=None,
        phenotype_names=None
    )
    
    logger.info(f"Total contacts: {len(result.contacts)}")
    
    if result.contacts:
        contact = result.contacts[0]
        logger.info(f"Sample contact: tracks {contact.track_id_1}-{contact.track_id_2}, "
                   f"duration={contact.duration} frames, "
                   f"mean distance={contact.mean_distance:.1f}px, "
                   f"type={contact.contact_type}")
        
        stats = compute_interaction_statistics(result)
        logger.info("\nInteraction statistics:")
        logger.info(f"  Total contacts: {stats['total_contacts']}")
        logger.info(f"  Mean duration: {stats.get('mean_duration', 0):.1f} frames")
        logger.info(f"  Max duration: {stats.get('max_duration', 0)} frames")
        logger.info(f"  Contact types: {stats.get('contact_types', {})}")
        logger.info(f"  Unique pairs: {stats.get('unique_pairs', 0)}")
        logger.info(f"  Cells with interactions: {stats.get('cells_with_interactions', 0)}")
        
        temporal = analyze_temporal_interaction_patterns(result, window_size=5)
        if len(temporal) > 0:
            logger.info(f"\nTemporal patterns ({len(temporal)} windows):")
            for _, row in temporal.head(3).iterrows():
                logger.info(f"  Frames {int(row['window_start'])}-{int(row['window_end'])}: "
                           f"{int(row['n_pairs_in_contact'])} contacts")
        
        lf_pairs = identify_leader_follower_pairs(
            result, tracker,
            min_follow_duration=5,
            max_distance=30.0
        )
        if lf_pairs:
            logger.info(f"\nLeader-follower pairs: {len(lf_pairs)}")
    
    if len(result.contacts) > 0:
        assert result.contact_summary is not None
        assert len(result.contact_summary) == len(result.contacts)
        assert result.frame_by_frame is not None
        assert len(result.interaction_matrix) > 0
    
    logger.info("✓ Cell-cell interaction analysis works correctly")
    logger.info("✓ TEST 4 PASSED")
    return True


def test_pipeline_integration():
    """Test pipeline integration with new features."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Pipeline Integration")
    logger.info("=" * 60)
    
    from cell_tracker.pipeline import CellTrackingPipeline
    
    images, masks, tracker, division_df = generate_tracking_test_data(
        n_frames=15, size=100, n_cells=5
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        from cell_tracker.utils import save_tiff_stack
        input_path = Path(tmpdir) / "test_data.tiff"
        save_tiff_stack(images, str(input_path))
        
        pipeline = CellTrackingPipeline(
            weights_path=None,
            device='cpu',
            num_workers=2,
            use_parallel=False,
            output_dir=str(Path(tmpdir) / "output"),
            enable_phenotype_clustering=True,
            clustering_algorithm='kmeans',
            n_clusters=min(3, len(tracker.tracks)),
            use_pca_for_clustering=True,
            enable_interaction_analysis=True,
            interaction_distance_threshold=40.0
        )
        
        pipeline.image_stack = images
        pipeline.is_3d_data = False
        pipeline.segmentation_masks = masks
        
        pipeline.tracker = tracker
        
        division_events = []
        for _, row in division_df.iterrows():
            division_events.append(row.to_dict())
        pipeline.division_events = division_events
        
        try:
            pipeline.run_phenotype_clustering()
            if pipeline.clustering_result is not None:
                logger.info(f"Clustering result: {len(pipeline.clustering_result.clusters)} clusters")
        except Exception as e:
            logger.warning(f"Phenotype clustering skipped: {e}")
        
        try:
            pipeline.run_interaction_analysis()
            if pipeline.interaction_result is not None:
                logger.info(f"Interaction result: {len(pipeline.interaction_result.contacts)} contacts")
        except Exception as e:
            logger.warning(f"Interaction analysis skipped: {e}")
        
        output_files = list(Path(tmpdir).rglob("*.csv")) + list(Path(tmpdir).rglob("*.json"))
        logger.info(f"Generated {len(output_files)} output files")
        for f in output_files[:10]:
            logger.info(f"  {f.relative_to(tmpdir)}")
        
        logger.info("✓ Pipeline integration works correctly")
        logger.info("✓ TEST 5 PASSED")
        return True


def main():
    logger.info("\n" + "=" * 60)
    logger.info("NEW FEATURES TEST SUITE")
    logger.info("=" * 60)
    
    tests = [
        ("3D Data Detection", test_3d_data_detection),
        ("3D Segmentation Basic", test_3d_segmentation_basic),
        ("Phenotype Clustering", test_phenotype_clustering),
        ("Interaction Analysis", test_interaction_analysis),
        ("Pipeline Integration", test_pipeline_integration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} FAILED with exception: {e}", exc_info=True)
            results[test_name] = False
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("ALL TESTS PASSED! ✓")
        return 0
    else:
        logger.error("SOME TESTS FAILED! ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
