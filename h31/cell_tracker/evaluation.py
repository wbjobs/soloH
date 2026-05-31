import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

from .tracking import CellTracker
from .division_detection import DivisionDetector

logger = logging.getLogger(__name__)


def compute_iou_binary(mask1: np.ndarray, mask2: np.ndarray) -> float:
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    
    if union == 0:
        return 0.0
    
    return intersection / union


def compute_iou_per_class(pred_mask: np.ndarray, 
                          gt_mask: np.ndarray, 
                          labels: Optional[List[int]] = None) -> Dict[int, float]:
    if labels is None:
        labels = np.unique(gt_mask)
        labels = labels[labels != 0]
    
    iou_scores = {}
    
    for label in labels:
        gt_binary = gt_mask == label
        
        pred_labels = np.unique(pred_mask[gt_binary])
        pred_labels = pred_labels[pred_labels != 0]
        
        if len(pred_labels) == 0:
            iou_scores[label] = 0.0
            continue
        
        best_iou = 0.0
        for pred_label in pred_labels:
            pred_binary = pred_mask == pred_label
            iou = compute_iou_binary(gt_binary, pred_binary)
            if iou > best_iou:
                best_iou = iou
        
        iou_scores[label] = best_iou
    
    return iou_scores


def compute_dice_binary(mask1: np.ndarray, mask2: np.ndarray) -> float:
    intersection = np.logical_and(mask1, mask2).sum()
    total = mask1.sum() + mask2.sum()
    
    if total == 0:
        return 0.0
    
    return 2 * intersection / total


def compute_precision_recall(pred_mask: np.ndarray, 
                              gt_mask: np.ndarray, 
                              iou_threshold: float = 0.5) -> Tuple[float, float, float]:
    gt_labels = np.unique(gt_mask)
    gt_labels = gt_labels[gt_labels != 0]
    
    pred_labels = np.unique(pred_mask)
    pred_labels = pred_labels[pred_labels != 0]
    
    tp = 0
    matched_pred = set()
    
    for gt_label in gt_labels:
        gt_binary = gt_mask == gt_label
        
        best_iou = 0.0
        best_pred_label = None
        
        for pred_label in pred_labels:
            if pred_label in matched_pred:
                continue
            
            pred_binary = pred_mask == pred_label
            iou = compute_iou_binary(gt_binary, pred_binary)
            
            if iou > best_iou:
                best_iou = iou
                best_pred_label = pred_label
        
        if best_iou >= iou_threshold and best_pred_label is not None:
            tp += 1
            matched_pred.add(best_pred_label)
    
    fp = len(pred_labels) - len(matched_pred)
    fn = len(gt_labels) - tp
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1


class Evaluator:
    def __init__(self,
                 iou_threshold: float = 0.5,
                 min_track_length: int = 5):
        self.iou_threshold = iou_threshold
        self.min_track_length = min_track_length
        
        self.segmentation_metrics: Dict[int, dict] = {}
        self.tracking_metrics: Dict[int, dict] = {}
        self.division_metrics: dict = {}
        
    def evaluate_segmentation(self,
                              pred_masks: np.ndarray,
                              gt_masks: np.ndarray) -> dict:
        logger.info("Evaluating segmentation...")
        
        n_frames = pred_masks.shape[0]
        
        iou_per_frame = []
        dice_per_frame = []
        precision_per_frame = []
        recall_per_frame = []
        f1_per_frame = []
        
        for frame in range(n_frames):
            pred = pred_masks[frame]
            gt = gt_masks[frame]
            
            pred_binary = pred > 0
            gt_binary = gt > 0
            
            iou = compute_iou_binary(pred_binary, gt_binary)
            dice = compute_dice_binary(pred_binary, gt_binary)
            precision, recall, f1 = compute_precision_recall(pred, gt, self.iou_threshold)
            
            iou_per_frame.append(iou)
            dice_per_frame.append(dice)
            precision_per_frame.append(precision)
            recall_per_frame.append(recall)
            f1_per_frame.append(f1)
            
            self.segmentation_metrics[frame] = {
                'iou': iou,
                'dice': dice,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'n_pred': len(np.unique(pred)[np.unique(pred) != 0]),
                'n_gt': len(np.unique(gt)[np.unique(gt) != 0]),
            }
        
        overall = {
            'mean_iou': float(np.mean(iou_per_frame)),
            'std_iou': float(np.std(iou_per_frame)),
            'mean_dice': float(np.mean(dice_per_frame)),
            'std_dice': float(np.std(dice_per_frame)),
            'mean_precision': float(np.mean(precision_per_frame)),
            'mean_recall': float(np.mean(recall_per_frame)),
            'mean_f1': float(np.mean(f1_per_frame)),
            'per_frame': self.segmentation_metrics,
        }
        
        logger.info(f"Segmentation - Mean IoU: {overall['mean_iou']:.4f}, Mean F1: {overall['mean_f1']:.4f}")
        
        return overall
    
    def _match_tracks(self,
                      pred_tracker: CellTracker,
                      gt_tracks_df: pd.DataFrame) -> Dict[int, int]:
        pred_tracks = pred_tracker.tracks
        
        matches = {}
        
        for pred_id, pred_track in pred_tracks.items():
            if len(pred_track) < self.min_track_length:
                continue
            
            best_gt_id = None
            best_score = 0
            
            for gt_id in gt_tracks_df['track_id'].unique():
                gt_frames = gt_tracks_df[gt_tracks_df['track_id'] == gt_id]['frame'].values
                pred_frames = np.array(pred_track.frames)
                
                common_frames = np.intersect1d(pred_frames, gt_frames)
                
                if len(common_frames) == 0:
                    continue
                
                matched_frames = 0
                for frame in common_frames:
                    pred_idx = pred_track.frames.index(frame)
                    pred_centroid = np.array(pred_track.centroids[pred_idx])
                    
                    gt_row = gt_tracks_df[(gt_tracks_df['track_id'] == gt_id) & 
                                           (gt_tracks_df['frame'] == frame)].iloc[0]
                    gt_centroid = np.array([gt_row['y'], gt_row['x']])
                    
                    distance = np.sqrt(np.sum((pred_centroid - gt_centroid) ** 2))
                    
                    if distance < 20:
                        matched_frames += 1
                
                score = matched_frames / len(common_frames)
                
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_gt_id = gt_id
            
            if best_gt_id is not None:
                matches[pred_id] = best_gt_id
        
        return matches
    
    def evaluate_tracking(self,
                           pred_tracker: CellTracker,
                           gt_tracks_df: pd.DataFrame) -> dict:
        logger.info("Evaluating tracking...")
        
        pred_tracks = pred_tracker.tracks
        matches = self._match_tracks(pred_tracker, gt_tracks_df)
        
        total_switches = 0
        total_gt_tracks = len(gt_tracks_df['track_id'].unique())
        matched_gt_tracks = set(matches.values())
        
        gt_to_pred = defaultdict(list)
        for pred_id, gt_id in matches.items():
            gt_to_pred[gt_id].append(pred_id)
        
        for gt_id, pred_ids in gt_to_pred.items():
            total_switches += max(0, len(pred_ids) - 1)
        
        track_accuracy = len(matched_gt_tracks) / total_gt_tracks if total_gt_tracks > 0 else 0
        
        completeness = []
        precision = []
        
        for pred_id, pred_track in pred_tracks.items():
            if len(pred_track) < self.min_track_length:
                continue
            
            if pred_id not in matches:
                continue
            
            gt_id = matches[pred_id]
            
            pred_frames = set(pred_track.frames)
            gt_frames = set(gt_tracks_df[gt_tracks_df['track_id'] == gt_id]['frame'].values)
            
            common_frames = pred_frames & gt_frames
            
            if len(gt_frames) > 0:
                completeness.append(len(common_frames) / len(gt_frames))
            
            if len(pred_frames) > 0:
                precision.append(len(common_frames) / len(pred_frames))
            
            matched_count = 0
            for frame in common_frames:
                pred_idx = pred_track.frames.index(frame)
                pred_centroid = np.array(pred_track.centroids[pred_idx])
                
                gt_row = gt_tracks_df[(gt_tracks_df['track_id'] == gt_id) & 
                                       (gt_tracks_df['frame'] == frame)].iloc[0]
                gt_centroid = np.array([gt_row['y'], gt_row['x']])
                
                distance = np.sqrt(np.sum((pred_centroid - gt_centroid) ** 2))
                
                if distance < 15:
                    matched_count += 1
            
            if len(common_frames) > 0:
                self.tracking_metrics[pred_id] = {
                    'gt_id': gt_id,
                    'completeness': len(common_frames) / len(gt_frames) if len(gt_frames) > 0 else 0,
                    'precision': len(common_frames) / len(pred_frames) if len(pred_frames) > 0 else 0,
                    'frame_accuracy': matched_count / len(common_frames) if len(common_frames) > 0 else 0,
                    'track_length': len(pred_track),
                    'gt_track_length': len(gt_frames),
                }
        
        overall = {
            'total_switches': total_switches,
            'track_accuracy': track_accuracy,
            'mean_completeness': float(np.mean(completeness)) if completeness else 0,
            'mean_precision': float(np.mean(precision)) if precision else 0,
            'total_matched_tracks': len(matched_gt_tracks),
            'total_gt_tracks': total_gt_tracks,
            'total_pred_tracks': len(pred_tracks),
            'valid_pred_tracks': len([t for t in pred_tracks.values() if len(t) >= self.min_track_length]),
            'per_track': self.tracking_metrics,
        }
        
        logger.info(f"Tracking - Switches: {total_switches}, Accuracy: {track_accuracy:.4f}, Mean Completeness: {overall['mean_completeness']:.4f}")
        
        return overall
    
    def evaluate_division(self,
                           pred_division_events: List[dict],
                           gt_divisions_df: Optional[pd.DataFrame] = None) -> dict:
        logger.info("Evaluating division events...")
        
        if gt_divisions_df is None or gt_divisions_df.empty:
            self.division_metrics = {
                'n_pred': len(pred_division_events),
                'n_gt': 0,
                'tp': 0,
                'fp': len(pred_division_events),
                'fn': 0,
                'precision': 0,
                'recall': 0,
                'f1': 0,
            }
            return self.division_metrics
        
        tp = 0
        matched_gt = set()
        
        for pred_event in pred_division_events:
            pred_frame = pred_event['frame']
            pred_centroid = np.array(pred_event['parent_centroid'])
            
            best_match = None
            best_distance = float('inf')
            
            for _, gt_row in gt_divisions_df.iterrows():
                gt_id = gt_row.name
                
                if gt_id in matched_gt:
                    continue
                
                gt_frame = gt_row['frame']
                
                if abs(gt_frame - pred_frame) > 2:
                    continue
                
                gt_centroid = np.array([gt_row['y'], gt_row['x']])
                distance = np.sqrt(np.sum((pred_centroid - gt_centroid) ** 2))
                
                if distance < 30 and distance < best_distance:
                    best_distance = distance
                    best_match = gt_id
            
            if best_match is not None:
                tp += 1
                matched_gt.add(best_match)
        
        fp = len(pred_division_events) - tp
        fn = len(gt_divisions_df) - tp
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        self.division_metrics = {
            'n_pred': len(pred_division_events),
            'n_gt': len(gt_divisions_df),
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': precision,
            'recall': recall,
            'f1': f1,
        }
        
        logger.info(f"Division detection - Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")
        
        return self.division_metrics
    
    def evaluate_all(self,
                      pred_masks: np.ndarray,
                      gt_masks: Optional[np.ndarray],
                      pred_tracker: CellTracker,
                      gt_tracks_df: Optional[pd.DataFrame],
                      pred_division_events: List[dict],
                      gt_divisions_df: Optional[pd.DataFrame] = None) -> dict:
        results = {}
        
        if gt_masks is not None:
            results['segmentation'] = self.evaluate_segmentation(pred_masks, gt_masks)
        
        if gt_tracks_df is not None:
            results['tracking'] = self.evaluate_tracking(pred_tracker, gt_tracks_df)
        
        results['division'] = self.evaluate_division(pred_division_events, gt_divisions_df)
        
        return results
    
    def get_metrics_dataframe(self) -> pd.DataFrame:
        data = []
        
        for metric_type in ['segmentation', 'tracking', 'division']:
            if hasattr(self, f'{metric_type}_metrics'):
                metrics = getattr(self, f'{metric_type}_metrics')
                if isinstance(metrics, dict) and 'per_frame' not in metrics:
                    for key, value in metrics.items():
                        if isinstance(value, (int, float)):
                            data.append({
                                'metric_type': metric_type,
                                'metric': key,
                                'value': value,
                            })
        
        return pd.DataFrame(data)
    
    def generate_report(self, results: dict) -> str:
        report = []
        report.append("=" * 60)
        report.append("CELL TRACKING EVALUATION REPORT")
        report.append("=" * 60)
        
        if 'segmentation' in results:
            seg = results['segmentation']
            report.append("\n1. SEGMENTATION METRICS")
            report.append("-" * 40)
            report.append(f"   Mean IoU:        {seg['mean_iou']:.4f} ± {seg['std_iou']:.4f}")
            report.append(f"   Mean Dice:       {seg['mean_dice']:.4f} ± {seg['std_dice']:.4f}")
            report.append(f"   Mean Precision:  {seg['mean_precision']:.4f}")
            report.append(f"   Mean Recall:     {seg['mean_recall']:.4f}")
            report.append(f"   Mean F1 Score:   {seg['mean_f1']:.4f}")
        
        if 'tracking' in results:
            track = results['tracking']
            report.append("\n2. TRACKING METRICS")
            report.append("-" * 40)
            report.append(f"   Track Accuracy:      {track['track_accuracy']:.4f}")
            report.append(f"   Total Switches:      {track['total_switches']}")
            report.append(f"   Mean Completeness:   {track['mean_completeness']:.4f}")
            report.append(f"   Mean Precision:      {track['mean_precision']:.4f}")
            report.append(f"   Total GT Tracks:     {track['total_gt_tracks']}")
            report.append(f"   Total Pred Tracks:   {track['total_pred_tracks']}")
            report.append(f"   Matched Tracks:      {track['total_matched_tracks']}")
        
        if 'division' in results:
            div = results['division']
            report.append("\n3. DIVISION DETECTION METRICS")
            report.append("-" * 40)
            report.append(f"   Precision:   {div['precision']:.4f}")
            report.append(f"   Recall:      {div['recall']:.4f}")
            report.append(f"   F1 Score:    {div['f1']:.4f}")
            report.append(f"   TP:          {div['tp']}")
            report.append(f"   FP:          {div['fp']}")
            report.append(f"   FN:          {div['fn']}")
            report.append(f"   Predicted:   {div['n_pred']}")
            report.append(f"   Ground Truth:{div['n_gt']}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
