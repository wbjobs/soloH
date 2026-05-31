import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DivisionDetector:
    def __init__(self,
                 area_drop_threshold: float = 0.4,
                 area_increase_threshold: float = 1.6,
                 morphology_change_threshold: float = 0.3,
                 area_drop_hysteresis: float = 0.1,
                 area_increase_hysteresis: float = 0.15,
                 morphology_hysteresis: float = 0.08,
                 min_consecutive_frames: int = 1,
                 require_both_metrics: bool = True,
                 min_cell_area: int = 100,
                 max_cell_area: int = 10000,
                 min_tracks_for_division: int = 2,
                 max_distance_for_children: float = 40.0,
                 area_smoothing_window: int = 3):
        self.area_drop_threshold = area_drop_threshold
        self.area_drop_low = area_drop_threshold + area_drop_hysteresis
        self.area_increase_threshold = area_increase_threshold
        self.area_increase_low = area_increase_threshold - area_increase_hysteresis
        self.morphology_change_threshold = morphology_change_threshold
        self.morphology_low = morphology_change_threshold - morphology_hysteresis
        self.area_drop_hysteresis = area_drop_hysteresis
        self.area_increase_hysteresis = area_increase_hysteresis
        self.morphology_hysteresis = morphology_hysteresis
        self.min_consecutive_frames = min_consecutive_frames
        self.require_both_metrics = require_both_metrics
        self.min_cell_area = min_cell_area
        self.max_cell_area = max_cell_area
        self.min_tracks_for_division = min_tracks_for_division
        self.max_distance_for_children = max_distance_for_children
        self.area_smoothing_window = area_smoothing_window
        
        self.division_events: List[dict] = []
    
    def smooth_area(self, areas: np.ndarray, window: Optional[int] = None) -> np.ndarray:
        if window is None:
            window = self.area_smoothing_window
        
        if len(areas) < window:
            return areas.astype(float)
        
        kernel = np.ones(window) / window
        smoothed = np.convolve(areas, kernel, mode='same')
        
        return smoothed
    
    def detect_area_mutation(self,
                            track_areas: np.ndarray,
                            track_frames: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if len(track_areas) < 3:
            return np.array([]), np.array([]), np.array([]), np.array([])
        
        smoothed_areas = self.smooth_area(track_areas)
        
        area_ratios = np.zeros(len(smoothed_areas) - 1)
        for i in range(len(smoothed_areas) - 1):
            if smoothed_areas[i] > 0:
                area_ratios[i] = smoothed_areas[i + 1] / smoothed_areas[i]
            else:
                area_ratios[i] = 1.0
        
        area_drops_high = area_ratios < self.area_drop_threshold
        area_drops_low = area_ratios < self.area_drop_low
        area_increases_high = area_ratios > self.area_increase_threshold
        area_increases_low = area_ratios > self.area_increase_low
        
        candidate_indices = self._apply_hysteresis(
            area_drops_high, 
            area_drops_low, 
            area_increases_high, 
            area_increases_low,
            self.min_consecutive_frames
        )
        
        candidate_frames = np.array(track_frames[1:])[candidate_indices] if len(candidate_indices) > 0 else np.array([])
        candidate_ratios = area_ratios[candidate_indices] if len(candidate_indices) > 0 else np.array([])
        
        return candidate_indices, candidate_frames, area_ratios, candidate_ratios
    
    def _apply_hysteresis(self,
                         drops_high: np.ndarray,
                         drops_low: np.ndarray,
                         increases_high: np.ndarray,
                         increases_low: np.ndarray,
                         min_consecutive: int) -> np.ndarray:
        n = len(drops_high)
        candidate_mask = np.zeros(n, dtype=bool)
        
        in_drop = False
        in_increase = False
        consecutive_count = 0
        
        for i in range(n):
            if drops_high[i]:
                in_drop = True
                consecutive_count = 1
            elif drops_low[i] and in_drop:
                consecutive_count += 1
            else:
                if in_drop:
                    if consecutive_count >= min_consecutive:
                        start_idx = max(0, i - consecutive_count)
                        candidate_mask[start_idx:i] = True
                    in_drop = False
                    consecutive_count = 0
            
            if increases_high[i]:
                in_increase = True
                consecutive_count = 1
            elif increases_low[i] and in_increase:
                consecutive_count += 1
            else:
                if in_increase:
                    if consecutive_count >= min_consecutive:
                        start_idx = max(0, i - consecutive_count)
                        candidate_mask[start_idx:i] = True
                    in_increase = False
                    consecutive_count = 0
        
        if in_drop and consecutive_count >= min_consecutive:
            start_idx = max(0, n - consecutive_count)
            candidate_mask[start_idx:n] = True
        
        if in_increase and consecutive_count >= min_consecutive:
            start_idx = max(0, n - consecutive_count)
            candidate_mask[start_idx:n] = True
        
        return np.where(candidate_mask)[0]
    
    def detect_morphology_change(self,
                                  track_properties: List[dict],
                                  track_frames: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if len(track_properties) < 3:
            return np.array([]), np.array([]), np.array([])
        
        n = len(track_properties)
        morphology_changes = np.zeros(n - 1)
        
        for i in range(n - 1):
            props_prev = track_properties[i]
            props_curr = track_properties[i + 1]
            
            ecc_prev = props_prev.get('eccentricity', 0)
            ecc_curr = props_curr.get('eccentricity', 0)
            ecc_change = abs(ecc_prev - ecc_curr)
            
            solidity_prev = props_prev.get('solidity', 0)
            solidity_curr = props_curr.get('solidity', 0)
            solidity_change = abs(solidity_prev - solidity_curr)
            
            extent_prev = props_prev.get('extent', 0)
            extent_curr = props_curr.get('extent', 0)
            extent_change = abs(extent_prev - extent_curr)
            
            combined_change = (ecc_change + solidity_change + extent_change) / 3.0
            morphology_changes[i] = combined_change
        
        morph_high = morphology_changes > self.morphology_change_threshold
        morph_low = morphology_changes > self.morphology_low
        
        candidate_indices = self._apply_morphology_hysteresis(
            morph_high, 
            morph_low, 
            self.min_consecutive_frames
        )
        
        candidate_values = morphology_changes[candidate_indices] if len(candidate_indices) > 0 else np.array([])
        
        return candidate_indices, morphology_changes, candidate_values
    
    def _apply_morphology_hysteresis(self,
                                     high_threshold: np.ndarray,
                                     low_threshold: np.ndarray,
                                     min_consecutive: int) -> np.ndarray:
        n = len(high_threshold)
        candidate_mask = np.zeros(n, dtype=bool)
        
        in_candidate = False
        consecutive_count = 0
        
        for i in range(n):
            if high_threshold[i]:
                in_candidate = True
                consecutive_count = 1
            elif low_threshold[i] and in_candidate:
                consecutive_count += 1
            else:
                if in_candidate:
                    if consecutive_count >= min_consecutive:
                        start_idx = max(0, i - consecutive_count)
                        candidate_mask[start_idx:i] = True
                    in_candidate = False
                    consecutive_count = 0
        
        if in_candidate and consecutive_count >= min_consecutive:
            start_idx = max(0, n - consecutive_count)
            candidate_mask[start_idx:n] = True
        
        return np.where(candidate_mask)[0]
    
    def find_potential_children(self,
                                  parent_end_frame: int,
                                  parent_centroid: Tuple[float, float],
                                  all_tracks: Dict[int, object],
                                  active_track_ids: List[int]) -> List[int]:
        potential_children = []
        
        for track_id in active_track_ids:
            track = all_tracks[track_id]
            
            if track.appearance_frame != parent_end_frame + 1:
                continue
            
            child_centroid = track.centroids[0]
            distance = np.sqrt(
                (parent_centroid[0] - child_centroid[0]) ** 2 +
                (parent_centroid[1] - child_centroid[1]) ** 2
            )
            
            if distance <= self.max_distance_for_children:
                child_area = track.areas[0]
                if self.min_cell_area <= child_area <= self.max_cell_area:
                    potential_children.append(track_id)
        
        return potential_children
    
    def check_division_event(self,
                               parent_track: object,
                               parent_end_idx: int,
                               all_tracks: Dict[int, object],
                               candidate_tracks: List[int]) -> Optional[dict]:
        if parent_end_idx >= len(parent_track.areas) - 1:
            return None
        
        parent_centroid = parent_track.centroids[parent_end_idx]
        parent_frame = parent_track.frames[parent_end_idx]
        parent_area = parent_track.areas[parent_end_idx]
        
        if parent_area < self.min_cell_area or parent_area > self.max_cell_area:
            return None
        
        potential_children = self.find_potential_children(
            parent_end_frame=parent_frame,
            parent_centroid=parent_centroid,
            all_tracks=all_tracks,
            active_track_ids=candidate_tracks
        )
        
        if len(potential_children) < self.min_tracks_for_division:
            return None
        
        potential_children = sorted(
            potential_children,
            key=lambda tid: np.sqrt(
                (all_tracks[tid].centroids[0][0] - parent_centroid[0]) ** 2 +
                (all_tracks[tid].centroids[0][1] - parent_centroid[1]) ** 2
            )
        )[:2]
        
        children_areas = [all_tracks[tid].areas[0] for tid in potential_children]
        total_child_area = sum(children_areas)
        
        area_ratio = total_child_area / parent_area if parent_area > 0 else 0
        
        next_frame = parent_frame + 1
        
        division_event = {
            'parent_id': parent_track.track_id,
            'children_ids': potential_children,
            'frame': parent_frame,
            'next_frame': next_frame,
            'parent_centroid': parent_centroid,
            'parent_area': parent_area,
            'children_areas': children_areas,
            'total_child_area': total_child_area,
            'area_ratio': area_ratio,
            'children_centroids': [all_tracks[tid].centroids[0] for tid in potential_children],
        }
        
        return division_event
    
    def detect_divisions(self,
                         tracker: object,
                         masks: Optional[np.ndarray] = None) -> List[dict]:
        all_tracks = tracker.tracks
        track_ids = list(all_tracks.keys())
        
        area_candidates = defaultdict(list)
        morphology_candidates = defaultdict(list)
        area_candidate_indices = defaultdict(set)
        morphology_candidate_indices = defaultdict(set)
        
        for track_id in track_ids:
            track = all_tracks[track_id]
            
            if len(track) < 3:
                continue
            
            areas = np.array(track.areas)
            frames = track.frames
            props = track.properties
            
            area_indices, area_frames, area_ratios, _ = self.detect_area_mutation(areas, frames)
            for idx in area_indices:
                area_candidates[track_id].append({
                    'frame_idx': idx,
                    'frame': area_frames[idx],
                    'area_ratio': area_ratios[idx],
                })
                area_candidate_indices[track_id].add(int(idx))
            
            morph_indices, morph_changes, _ = self.detect_morphology_change(props, frames)
            for idx in morph_indices:
                morphology_candidate_indices[track_id].add(int(idx))
                morphology_candidates[track_id].append({
                    'frame_idx': idx,
                    'frame': frames[idx + 1],
                    'morphology_change': morph_changes[idx],
                })
        
        division_events = []
        
        for track_id in track_ids:
            track = all_tracks[track_id]
            
            if track.parent_id is not None:
                continue
            
            candidates = []
            
            area_idx_set = area_candidate_indices.get(track_id, set())
            morph_idx_set = morphology_candidate_indices.get(track_id, set())
            
            if self.require_both_metrics:
                valid_indices = area_idx_set & morph_idx_set
                
                for area_cand in area_candidates.get(track_id, []):
                    frame_idx = area_cand['frame_idx']
                    if frame_idx in valid_indices and frame_idx < len(track.areas) - 1:
                        cand_data = area_cand.copy()
                        morph_matches = [m for m in morphology_candidates.get(track_id, []) 
                                        if m['frame_idx'] == frame_idx]
                        if morph_matches:
                            cand_data['morphology_change'] = morph_matches[0]['morphology_change']
                        candidates.append((frame_idx, 'combined', cand_data))
            else:
                for area_cand in area_candidates.get(track_id, []):
                    frame_idx = area_cand['frame_idx']
                    if frame_idx < len(track.areas) - 1:
                        cand_type = 'area'
                        if frame_idx in morph_idx_set:
                            cand_type = 'area+morph'
                        candidates.append((frame_idx, cand_type, area_cand))
                
                for morph_cand in morphology_candidates.get(track_id, []):
                    frame_idx = morph_cand['frame_idx']
                    if frame_idx < len(track.areas) - 1 and frame_idx not in area_idx_set:
                        candidates.append((frame_idx, 'morphology', morph_cand))
            
            candidates = sorted(candidates, key=lambda x: x[0])
            
            for frame_idx, cand_type, cand_data in candidates:
                candidate_child_tracks = [
                    tid for tid in track_ids 
                    if tid != track_id and all_tracks[tid].parent_id is None
                ]
                
                division_event = self.check_division_event(
                    parent_track=track,
                    parent_end_idx=frame_idx,
                    all_tracks=all_tracks,
                    candidate_tracks=candidate_child_tracks
                )
                
                if division_event is not None:
                    division_event['detection_type'] = cand_type
                    division_event['detection_data'] = cand_data
                    
                    division_events.append(division_event)
        
        division_events = self._resolve_duplicate_divisions(division_events, all_tracks)
        
        self._update_tracker_with_divisions(tracker, division_events)
        self.division_events = division_events
        
        logger.info(f"Detected {len(division_events)} division events")
        
        return division_events
    
    def _resolve_duplicate_divisions(self,
                                     division_events: List[dict],
                                     all_tracks: Dict[int, object]) -> List[dict]:
        if len(division_events) == 0:
            return []
        
        child_to_division = {}
        
        for event in division_events:
            for child_id in event['children_ids']:
                if child_id not in child_to_division:
                    child_to_division[child_id] = []
                child_to_division[child_id].append(event)
        
        unique_events = []
        used_children = set()
        
        for event in division_events:
            children = event['children_ids']
            children_available = all(cid not in used_children for cid in children)
            
            if not children_available:
                continue
            
            has_better_event = False
            for cid in children:
                for other_event in child_to_division.get(cid, []):
                    if other_event is event:
                        continue
                    if other_event['area_ratio'] > event['area_ratio']:
                        has_better_event = True
                        break
                if has_better_event:
                    break
            
            if not has_better_event:
                unique_events.append(event)
                for cid in children:
                    used_children.add(cid)
        
        return unique_events
    
    def _update_tracker_with_divisions(self,
                                        tracker: object,
                                        division_events: List[dict]) -> None:
        for event in division_events:
            parent_id = event['parent_id']
            children_ids = event['children_ids']
            division_frame = event['frame']
            
            if parent_id in tracker.tracks:
                tracker.tracks[parent_id].division_frame = division_frame
                tracker.tracks[parent_id].children_ids = children_ids
            
            for child_id in children_ids:
                if child_id in tracker.tracks:
                    tracker.tracks[child_id].parent_id = parent_id
        
        tracker.division_events = division_events
    
    def get_division_dataframe(self) -> pd.DataFrame:
        if len(self.division_events) == 0:
            return pd.DataFrame()
        
        data = []
        for event in self.division_events:
            row = {
                'parent_id': event['parent_id'],
                'children_ids': ','.join(map(str, event['children_ids'])),
                'frame': event['frame'],
                'next_frame': event['next_frame'],
                'parent_area': event['parent_area'],
                'total_child_area': event['total_child_area'],
                'area_ratio': event['area_ratio'],
                'parent_y': event['parent_centroid'][0],
                'parent_x': event['parent_centroid'][1],
                'detection_type': event.get('detection_type', 'unknown'),
            }
            
            if len(event['children_centroids']) >= 1:
                row['child1_y'] = event['children_centroids'][0][0]
                row['child1_x'] = event['children_centroids'][0][1]
                row['child1_area'] = event['children_areas'][0]
            
            if len(event['children_centroids']) >= 2:
                row['child2_y'] = event['children_centroids'][1][0]
                row['child2_x'] = event['children_centroids'][1][1]
                row['child2_area'] = event['children_areas'][1]
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    def get_division_mask(self,
                           masks: np.ndarray,
                           tracker: object) -> np.ndarray:
        division_mask = np.zeros_like(masks, dtype=np.int32)
        
        for event in self.division_events:
            frame = event['frame']
            parent_id = event['parent_id']
            children_ids = event['children_ids']
            
            if frame >= masks.shape[0]:
                continue
            
            if parent_id in tracker.tracks:
                parent_track = tracker.tracks[parent_id]
                if frame in parent_track.frames:
                    idx = parent_track.frames.index(frame)
                    parent_label = parent_track.labels[idx]
                    division_mask[frame][masks[frame] == parent_label] = 1
            
            if frame + 1 < masks.shape[0]:
                for child_id in children_ids:
                    if child_id in tracker.tracks:
                        child_track = tracker.tracks[child_id]
                        if frame + 1 in child_track.frames:
                            idx = child_track.frames.index(frame + 1)
                            child_label = child_track.labels[idx]
                            division_mask[frame + 1][masks[frame + 1] == child_label] = 2
        
        return division_mask
