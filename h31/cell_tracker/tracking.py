import numpy as np
import pandas as pd
import networkx as nx
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from typing import List, Dict, Tuple, Optional
import logging
from collections import defaultdict

from .utils import instance_mask_to_centroids, extract_mask_properties

logger = logging.getLogger(__name__)


def hungarian_assignment(cost_matrix: np.ndarray, 
                          max_cost: float = float('inf')) -> Tuple[np.ndarray, np.ndarray]:
    if cost_matrix.size == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    
    n_rows, n_cols = cost_matrix.shape
    
    if n_rows == 0 or n_cols == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    
    max_val = np.max(cost_matrix[np.isfinite(cost_matrix)]) if np.any(np.isfinite(cost_matrix)) else 1.0
    safe_matrix = np.where(np.isfinite(cost_matrix), cost_matrix, max_val * 2)
    
    row_ind, col_ind = linear_sum_assignment(safe_matrix)
    
    valid_mask = cost_matrix[row_ind, col_ind] < max_cost
    row_ind = row_ind[valid_mask]
    col_ind = col_ind[valid_mask]
    
    return row_ind, col_ind


def compute_iou(mask1: np.ndarray, mask2: np.ndarray, label1: int, label2: int) -> float:
    bin1 = mask1 == label1
    bin2 = mask2 == label2
    
    intersection = np.logical_and(bin1, bin2).sum()
    union = np.logical_or(bin1, bin2).sum()
    
    if union == 0:
        return 0.0
    
    return intersection / union


def compute_cost_matrix(prev_mask: np.ndarray,
                        curr_mask: np.ndarray,
                        prev_props: Dict[int, dict],
                        curr_props: Dict[int, dict],
                        max_distance: float = 50.0,
                        distance_weight: float = 1.0,
                        iou_weight: float = 1.0,
                        area_weight: float = 0.5,
                        predicted_positions: Optional[Dict[int, Tuple[float, float]]] = None,
                        adaptive_max_distances: Optional[Dict[int, float]] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    prev_labels = np.array(sorted(list(prev_props.keys())))
    curr_labels = np.array(sorted(list(curr_props.keys())))
    
    n_prev = len(prev_labels)
    n_curr = len(curr_labels)
    
    cost_matrix = np.full((n_prev, n_curr), np.inf)
    distance_matrix = np.zeros((n_prev, n_curr))
    iou_matrix = np.zeros((n_prev, n_curr))
    
    if n_prev == 0 or n_curr == 0:
        return cost_matrix, distance_matrix, iou_matrix
    
    if predicted_positions is not None:
        prev_centroids = np.array([
            predicted_positions.get(l, prev_props[l]['centroid']) 
            for l in prev_labels
        ])
    else:
        prev_centroids = np.array([prev_props[l]['centroid'] for l in prev_labels])
    
    curr_centroids = np.array([curr_props[l]['centroid'] for l in curr_labels])
    
    distances = cdist(prev_centroids, curr_centroids)
    
    for i, prev_label in enumerate(prev_labels):
        current_max_dist = max_distance
        if adaptive_max_distances is not None and prev_label in adaptive_max_distances:
            current_max_dist = adaptive_max_distances[prev_label]
        
        for j, curr_label in enumerate(curr_labels):
            dist = distances[i, j]
            
            if dist > current_max_dist:
                continue
            
            iou = compute_iou(prev_mask, curr_mask, prev_label, curr_label)
            
            area_prev = prev_props[prev_label]['area']
            area_curr = curr_props[curr_label]['area']
            area_diff = abs(area_prev - area_curr) / max(area_prev, area_curr, 1)
            
            norm_dist = dist / current_max_dist
            norm_iou = 1.0 - iou
            norm_area = area_diff
            
            cost = (distance_weight * norm_dist + 
                    iou_weight * norm_iou + 
                    area_weight * norm_area)
            
            cost_matrix[i, j] = cost
            distance_matrix[i, j] = dist
            iou_matrix[i, j] = iou
    
    return cost_matrix, distance_matrix, iou_matrix


class CellTrack:
    def __init__(self, track_id: int):
        self.track_id = track_id
        self.frames: List[int] = []
        self.labels: List[int] = []
        self.centroids: List[Tuple[float, float]] = []
        self.areas: List[float] = []
        self.properties: List[dict] = []
        self.fluorescence: List[float] = []
        self.parent_id: Optional[int] = None
        self.children_ids: List[int] = []
        self.division_frame: Optional[int] = None
        self.disappearance_frame: Optional[int] = None
        self.appearance_frame: Optional[int] = None
        
        self.velocity_y: List[float] = []
        self.velocity_x: List[float] = []
        self.kalman_state: Optional[np.ndarray] = None
        self.kalman_cov: Optional[np.ndarray] = None
    
    def add_detection(self, 
                      frame: int, 
                      label: int, 
                      centroid: Tuple[float, float], 
                      area: float,
                      properties: dict,
                      fluorescence: float = 0.0):
        self.frames.append(frame)
        self.labels.append(label)
        self.centroids.append(centroid)
        self.areas.append(area)
        self.properties.append(properties)
        self.fluorescence.append(fluorescence)
        
        if self.appearance_frame is None or frame < self.appearance_frame:
            self.appearance_frame = frame
        
        if self.disappearance_frame is None or frame > self.disappearance_frame:
            self.disappearance_frame = frame
        
        if len(self.centroids) >= 2:
            dy = centroid[0] - self.centroids[-2][0]
            dx = centroid[1] - self.centroids[-2][1]
            dt = frame - self.frames[-2] if len(self.frames) >= 2 else 1
            dt = max(dt, 1)
            self.velocity_y.append(dy / dt)
            self.velocity_x.append(dx / dt)
        
        self._update_kalman_filter(centroid, frame)
    
    def _init_kalman_filter(self, initial_pos: Tuple[float, float]):
        self.kalman_state = np.array([initial_pos[0], initial_pos[1], 0.0, 0.0], dtype=float)
        self.kalman_cov = np.eye(4) * 10.0
    
    def _update_kalman_filter(self, pos: Tuple[float, float], frame: int):
        if self.kalman_state is None:
            self._init_kalman_filter(pos)
            return
        
        dt = 1.0
        if len(self.frames) >= 2:
            dt = max(frame - self.frames[-2], 1)
        
        F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=float)
        
        Q = np.eye(4) * 1.0
        Q[2:, 2:] *= 5.0
        
        self.kalman_state = F @ self.kalman_state
        self.kalman_cov = F @ self.kalman_cov @ F.T + Q
        
        H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=float)
        
        R = np.eye(2) * 5.0
        
        y = np.array(pos) - H @ self.kalman_state
        S = H @ self.kalman_cov @ H.T + R
        K = self.kalman_cov @ H.T @ np.linalg.inv(S)
        
        self.kalman_state = self.kalman_state + K @ y
        self.kalman_cov = (np.eye(4) - K @ H) @ self.kalman_cov
    
    def predict_next_position(self, current_frame: int) -> Tuple[float, float]:
        if self.kalman_state is not None and len(self.frames) > 0:
            dt = max(current_frame - self.frames[-1], 1)
            
            F = np.array([
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ], dtype=float)
            
            predicted = F @ self.kalman_state
            return (float(predicted[0]), float(predicted[1]))
        
        if len(self.centroids) >= 2 and len(self.velocity_y) >= 1:
            dt = max(current_frame - self.frames[-1], 1)
            vy = np.mean(self.velocity_y[-3:]) if len(self.velocity_y) >= 3 else self.velocity_y[-1]
            vx = np.mean(self.velocity_x[-3:]) if len(self.velocity_x) >= 3 else self.velocity_x[-1]
            last_pos = self.centroids[-1]
            return (last_pos[0] + vy * dt, last_pos[1] + vx * dt)
        
        if len(self.centroids) > 0:
            return self.centroids[-1]
        
        return (0.0, 0.0)
    
    def get_expected_max_distance(self, base_max_distance: float) -> float:
        if len(self.velocity_y) >= 1:
            speed = np.sqrt(np.mean(self.velocity_y[-3:])**2 + np.mean(self.velocity_x[-3:])**2)
            adaptive_distance = base_max_distance + speed * 3.0
            return max(base_max_distance, min(adaptive_distance, base_max_distance * 3.0))
        return base_max_distance
    
    def get_detection_at_frame(self, frame: int) -> Optional[dict]:
        if frame not in self.frames:
            return None
        idx = self.frames.index(frame)
        return {
            'label': self.labels[idx],
            'centroid': self.centroids[idx],
            'area': self.areas[idx],
            'properties': self.properties[idx],
            'fluorescence': self.fluorescence[idx],
        }
    
    def to_dict(self) -> dict:
        return {
            'track_id': self.track_id,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids.copy(),
            'frames': self.frames.copy(),
            'centroids': self.centroids.copy(),
            'areas': self.areas.copy(),
            'fluorescence': self.fluorescence.copy(),
            'division_frame': self.division_frame,
            'appearance_frame': self.appearance_frame,
            'disappearance_frame': self.disappearance_frame,
            'length': len(self.frames),
        }
    
    def __len__(self) -> int:
        return len(self.frames)


class CellTracker:
    def __init__(self,
                 max_distance: float = 50.0,
                 distance_weight: float = 1.0,
                 iou_weight: float = 1.0,
                 area_weight: float = 0.5,
                 max_lost_frames: int = 3,
                 min_track_length: int = 5):
        self.max_distance = max_distance
        self.distance_weight = distance_weight
        self.iou_weight = iou_weight
        self.area_weight = area_weight
        self.max_lost_frames = max_lost_frames
        self.min_track_length = min_track_length
        
        self.tracks: Dict[int, CellTrack] = {}
        self.next_track_id = 1
        self.frame_properties: Dict[int, Dict[int, dict]] = {}
        
        self.assignments: Dict[int, Dict[int, int]] = {}
        self.division_events: List[dict] = []
        
    def _initialize_tracks(self, 
                           frame: int, 
                           mask: np.ndarray, 
                           props: Dict[int, dict],
                           fluorescence_values: Optional[Dict[int, float]] = None):
        if fluorescence_values is None:
            fluorescence_values = {k: 0.0 for k in props.keys()}
        
        for label in props.keys():
            track = CellTrack(self.next_track_id)
            centroid = props[label]['centroid']
            area = props[label]['area']
            
            track.add_detection(
                frame=frame,
                label=label,
                centroid=centroid,
                area=area,
                properties=props[label],
                fluorescence=fluorescence_values.get(label, 0.0)
            )
            
            self.tracks[self.next_track_id] = track
            self.next_track_id += 1
        
        logger.info(f"Initialized {len(props)} tracks at frame {frame}")
    
    def _find_active_tracks(self, frame: int) -> List[int]:
        active = []
        for track_id, track in self.tracks.items():
            if track.disappearance_frame is not None:
                if frame - track.disappearance_frame <= self.max_lost_frames:
                    active.append(track_id)
            else:
                active.append(track_id)
        return active
    
    def update(self,
               frame: int,
               mask: np.ndarray,
               fluorescence_values: Optional[Dict[int, float]] = None) -> Dict[int, int]:
        if fluorescence_values is None:
            fluorescence_values = {}
        
        props = extract_mask_properties(mask)
        self.frame_properties[frame] = props
        
        if frame == 0:
            self._initialize_tracks(frame, mask, props, fluorescence_values)
            return {k: k for k in props.keys()}
        
        active_track_ids = self._find_active_tracks(frame)
        
        prev_props = {}
        predicted_positions = {}
        adaptive_max_distances = {}
        
        for track_id in active_track_ids:
            track = self.tracks[track_id]
            last_detection = track.get_detection_at_frame(track.disappearance_frame)
            if last_detection is not None:
                prev_props[track_id] = last_detection['properties']
                predicted_positions[track_id] = track.predict_next_position(frame)
                adaptive_max_distances[track_id] = track.get_expected_max_distance(self.max_distance)
        
        cost_matrix, dist_matrix, iou_matrix = compute_cost_matrix(
            prev_mask=mask,
            curr_mask=mask,
            prev_props=prev_props,
            curr_props=props,
            max_distance=self.max_distance,
            distance_weight=self.distance_weight,
            iou_weight=self.iou_weight,
            area_weight=self.area_weight,
            predicted_positions=predicted_positions,
            adaptive_max_distances=adaptive_max_distances
        )
        
        prev_label_list = sorted(list(prev_props.keys()))
        curr_label_list = sorted(list(props.keys()))
        
        row_ind, col_ind = hungarian_assignment(cost_matrix)
        
        label_to_track = {}
        
        for r, c in zip(row_ind, col_ind):
            track_id = prev_label_list[r]
            curr_label = curr_label_list[c]
            
            track = self.tracks[track_id]
            centroid = props[curr_label]['centroid']
            area = props[curr_label]['area']
            
            track.add_detection(
                frame=frame,
                label=curr_label,
                centroid=centroid,
                area=area,
                properties=props[curr_label],
                fluorescence=fluorescence_values.get(curr_label, 0.0)
            )
            
            label_to_track[curr_label] = track_id
        
        unmatched_tracks = [prev_label_list[i] for i in range(len(prev_label_list)) if i not in row_ind]
        unmatched_detections = [curr_label_list[i] for i in range(len(curr_label_list)) if i not in col_ind]
        
        for label in unmatched_detections:
            track = CellTrack(self.next_track_id)
            centroid = props[label]['centroid']
            area = props[label]['area']
            
            track.add_detection(
                frame=frame,
                label=label,
                centroid=centroid,
                area=area,
                properties=props[label],
                fluorescence=fluorescence_values.get(label, 0.0)
            )
            
            self.tracks[self.next_track_id] = track
            label_to_track[label] = self.next_track_id
            self.next_track_id += 1
        
        self.assignments[frame] = label_to_track
        
        return label_to_track
    
    def get_tracks_dataframe(self, min_length: Optional[int] = None) -> pd.DataFrame:
        if min_length is None:
            min_length = self.min_track_length
        
        data = []
        for track_id, track in self.tracks.items():
            if len(track) < min_length:
                continue
            
            track_dict = track.to_dict()
            for i, frame in enumerate(track.frames):
                row = {
                    'track_id': track_id,
                    'frame': frame,
                    'y': track.centroids[i][0],
                    'x': track.centroids[i][1],
                    'area': track.areas[i],
                    'fluorescence': track.fluorescence[i],
                    'label': track.labels[i],
                    'parent_id': track.parent_id,
                    'children_ids': ','.join(map(str, track.children_ids)),
                    'is_division': track.division_frame == frame,
                }
                
                if track.properties and i < len(track.properties):
                    props = track.properties[i]
                    row['eccentricity'] = props.get('eccentricity', np.nan)
                    row['solidity'] = props.get('solidity', np.nan)
                    row['major_axis'] = props.get('major_axis_length', np.nan)
                    row['minor_axis'] = props.get('minor_axis_length', np.nan)
                    row['perimeter'] = props.get('perimeter', np.nan)
                
                data.append(row)
        
        return pd.DataFrame(data)
    
    def get_lineage_graph(self) -> nx.DiGraph:
        G = nx.DiGraph()
        
        for track_id, track in self.tracks.items():
            G.add_node(track_id, **track.to_dict())
            
            if track.parent_id is not None:
                G.add_edge(track.parent_id, track_id)
        
        return G
    
    def filter_short_tracks(self, min_length: Optional[int] = None) -> None:
        if min_length is None:
            min_length = self.min_track_length
        
        to_remove = [tid for tid, track in self.tracks.items() if len(track) < min_length]
        
        for tid in to_remove:
            del self.tracks[tid]
        
        logger.info(f"Removed {len(to_remove)} short tracks (< {min_length} frames)")
    
    def get_track_mask(self, track_id: int, masks: np.ndarray) -> np.ndarray:
        track = self.tracks[track_id]
        track_mask = np.zeros_like(masks[0], dtype=np.int32)
        
        for frame, label in zip(track.frames, track.labels):
            if frame < masks.shape[0]:
                track_mask[masks[frame] == label] = track_id
        
        return track_mask
    
    def get_tracks_overlay(self, masks: np.ndarray) -> np.ndarray:
        overlay = np.zeros_like(masks, dtype=np.int32)
        
        for track_id, track in self.tracks.items():
            for frame, label in zip(track.frames, track.labels):
                if frame < masks.shape[0]:
                    overlay[frame][masks[frame] == label] = track_id
        
        return overlay
