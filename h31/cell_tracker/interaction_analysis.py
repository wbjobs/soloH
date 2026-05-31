import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import logging
from dataclasses import dataclass, field
from collections import defaultdict
from scipy.ndimage import distance_transform_edt, binary_dilation
from scipy.spatial.distance import cdist
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class CellContact:
    track_id_1: int
    track_id_2: int
    start_frame: int
    end_frame: int
    duration: int
    mean_distance: float
    min_distance: float
    max_distance: float
    mean_contact_area: float
    max_contact_area: float
    total_contact_area: float
    contact_frames: List[int] = field(default_factory=list)
    contact_type: str = "unknown"
    phenotype_1: Optional[str] = None
    phenotype_2: Optional[str] = None


@dataclass
class InteractionResult:
    contacts: List[CellContact]
    contact_summary: pd.DataFrame
    network: Dict[int, Dict[int, CellContact]]
    interaction_matrix: pd.DataFrame
    frame_by_frame: pd.DataFrame


class InteractionAnalyzer:
    """
    Analyze cell-cell interactions including contact duration and area.
    """
    
    def __init__(self,
                 distance_threshold: float = 15.0,
                 contact_distance_threshold: float = 5.0,
                 min_contact_duration: int = 3,
                 boundary_dilation_radius: int = 2,
                 use_boundary_contact: bool = True,
                 use_3d_distance: bool = False,
                 voxel_size: Tuple[float, float, float] = (1.0, 1.0, 1.0)):
        self.distance_threshold = distance_threshold
        self.contact_distance_threshold = contact_distance_threshold
        self.min_contact_duration = min_contact_duration
        self.boundary_dilation_radius = boundary_dilation_radius
        self.use_boundary_contact = use_boundary_contact
        self.use_3d_distance = use_3d_distance
        self.voxel_size = voxel_size
    
    def analyze_interactions(self,
                              tracker: object,
                              masks: np.ndarray,
                              feature_data: Optional[pd.DataFrame] = None,
                              phenotype_labels: Optional[Dict[int, int]] = None,
                              phenotype_names: Optional[Dict[int, str]] = None) -> InteractionResult:
        """
        Analyze cell-cell interactions over time.
        """
        T = len(masks) if masks.ndim in (3, 4) else masks.shape[0]
        
        frame_data = self._analyze_frame_by_frame(
            tracker, masks, T
        )
        
        contacts = self._extract_contacts(
            frame_data, tracker, T
        )
        
        contacts = self._classify_contacts(
            contacts, phenotype_labels, phenotype_names
        )
        
        summary = self._create_contact_summary(contacts)
        
        network = self._build_interaction_network(contacts)
        
        interaction_matrix = self._build_interaction_matrix(contacts, tracker)
        
        return InteractionResult(
            contacts=contacts,
            contact_summary=summary,
            network=network,
            interaction_matrix=interaction_matrix,
            frame_by_frame=frame_data
        )
    
    def _analyze_frame_by_frame(self,
                                  tracker: object,
                                  masks: np.ndarray,
                                  T: int) -> pd.DataFrame:
        """
        Analyze interactions for each frame.
        """
        all_pairs = []
        
        for frame in range(T):
            frame_pairs = self._analyze_single_frame(
                frame, tracker, masks
            )
            all_pairs.extend(frame_pairs)
        
        return pd.DataFrame(all_pairs)
    
    def _analyze_single_frame(self,
                               frame: int,
                               tracker: object,
                               masks: np.ndarray) -> List[Dict]:
        """
        Analyze cell-cell interactions in a single frame.
        """
        present_tracks = []
        track_positions = {}
        track_labels = {}
        track_areas = {}
        
        for track_id, track in tracker.tracks.items():
            if frame in track.frames:
                idx = track.frames.index(frame)
                present_tracks.append(track_id)
                track_positions[track_id] = track.centroids[idx]
                if hasattr(track, 'labels') and idx < len(track.labels):
                    track_labels[track_id] = track.labels[idx]
                    track_areas[track_id] = np.sum(
                        masks[frame] == track.labels[idx]
                    )
        
        if len(present_tracks) < 2:
            return []
        
        track_ids = sorted(present_tracks)
        positions = np.array([track_positions[tid] for tid in track_ids])
        
        distances = cdist(positions, positions)
        
        frame_results = []
        
        for i, tid1 in enumerate(track_ids):
            for j, tid2 in enumerate(track_ids):
                if i >= j:
                    continue
                
                dist = float(distances[i, j])
                
                if dist > self.distance_threshold:
                    continue
                
                contact_area = 0.0
                in_contact = dist < self.contact_distance_threshold
                
                if self.use_boundary_contact and track_labels:
                    label1 = track_labels.get(tid1, 0)
                    label2 = track_labels.get(tid2, 0)
                    if label1 > 0 and label2 > 0:
                        contact_area = self._calculate_contact_area(
                            masks[frame], label1, label2
                        )
                        if contact_area > 0:
                            in_contact = True
                
                frame_results.append({
                    'frame': frame,
                    'track_id_1': tid1,
                    'track_id_2': tid2,
                    'distance': dist,
                    'contact_area': contact_area,
                    'in_contact': in_contact,
                    'area_1': track_areas.get(tid1, 0),
                    'area_2': track_areas.get(tid2, 0),
                    'position_1_y': track_positions[tid1][0],
                    'position_1_x': track_positions[tid1][1],
                    'position_2_y': track_positions[tid2][0],
                    'position_2_x': track_positions[tid2][1],
                })
        
        return frame_results
    
    def _calculate_contact_area(self,
                                 mask_frame: np.ndarray,
                                 label1: int,
                                 label2: int) -> float:
        """
        Calculate contact area between two cells using boundary dilation.
        """
        mask1 = mask_frame == label1
        mask2 = mask_frame == label2
        
        if not np.any(mask1) or not np.any(mask2):
            return 0.0
        
        struct = np.ones((3, 3)) if mask_frame.ndim == 2 else np.ones((3, 3, 3))
        
        dilated1 = binary_dilation(mask1, structure=struct, iterations=self.boundary_dilation_radius)
        dilated2 = binary_dilation(mask2, structure=struct, iterations=self.boundary_dilation_radius)
        
        boundary_contact = np.logical_and(
            np.logical_and(dilated1, mask2),
            np.logical_not(mask1)
        )
        boundary_contact2 = np.logical_and(
            np.logical_and(dilated2, mask1),
            np.logical_not(mask2)
        )
        
        contact_pixels = np.sum(boundary_contact) + np.sum(boundary_contact2)
        
        if self.use_3d_distance and mask_frame.ndim == 3:
            voxel_area = self.voxel_size[1] * self.voxel_size[2]
            return float(contact_pixels * voxel_area)
        else:
            pixel_area = self.voxel_size[0] * self.voxel_size[1]
            return float(contact_pixels * pixel_area)
    
    def _extract_contacts(self,
                           frame_data: pd.DataFrame,
                           tracker: object,
                           T: int) -> List[CellContact]:
        """
        Extract contact events from frame-by-frame data.
        """
        if len(frame_data) == 0:
            return []
        
        contacts = []
        
        grouped = frame_data.groupby(['track_id_1', 'track_id_2'])
        
        for (tid1, tid2), group in grouped:
            group_sorted = group.sort_values('frame').reset_index(drop=True)
            
            contact_segments = self._identify_contact_segments(
                group_sorted, T
            )
            
            for seg in contact_segments:
                start_frame, end_frame = seg
                segment_data = group_sorted[
                    (group_sorted['frame'] >= start_frame) &
                    (group_sorted['frame'] <= end_frame)
                ]
                
                if len(segment_data) < self.min_contact_duration:
                    continue
                
                contact = CellContact(
                    track_id_1=int(tid1),
                    track_id_2=int(tid2),
                    start_frame=int(start_frame),
                    end_frame=int(end_frame),
                    duration=int(end_frame - start_frame + 1),
                    mean_distance=float(segment_data['distance'].mean()),
                    min_distance=float(segment_data['distance'].min()),
                    max_distance=float(segment_data['distance'].max()),
                    mean_contact_area=float(segment_data['contact_area'].mean()),
                    max_contact_area=float(segment_data['contact_area'].max()),
                    total_contact_area=float(segment_data['contact_area'].sum()),
                    contact_frames=segment_data['frame'].tolist()
                )
                contacts.append(contact)
        
        contacts.sort(key=lambda c: (c.start_frame, c.track_id_1, c.track_id_2))
        
        logger.info(f"Extracted {len(contacts)} contact events")
        
        return contacts
    
    def _identify_contact_segments(self,
                                    group: pd.DataFrame,
                                    T: int) -> List[Tuple[int, int]]:
        """
        Identify continuous contact segments for a pair of cells.
        """
        if len(group) == 0:
            return []
        
        all_frames = set(range(T))
        pair_frames = set(group['frame'].values)
        
        contact_frames = group[group['in_contact']]['frame'].values
        
        if len(contact_frames) == 0:
            contact_frames = group[
                group['distance'] < self.distance_threshold
            ]['frame'].values
        
        if len(contact_frames) == 0:
            return []
        
        contact_frames = np.sort(contact_frames)
        
        segments = []
        seg_start = contact_frames[0]
        seg_end = contact_frames[0]
        
        for i in range(1, len(contact_frames)):
            gap = contact_frames[i] - seg_end
            if gap <= 2:
                seg_end = contact_frames[i]
            else:
                segments.append((seg_start, seg_end))
                seg_start = contact_frames[i]
                seg_end = contact_frames[i]
        
        segments.append((seg_start, seg_end))
        
        return segments
    
    def _classify_contacts(self,
                            contacts: List[CellContact],
                            phenotype_labels: Optional[Dict[int, int]] = None,
                            phenotype_names: Optional[Dict[int, str]] = None) -> List[CellContact]:
        """
        Classify contacts by interaction type and add phenotype information.
        """
        for contact in contacts:
            if contact.mean_contact_area > 0:
                if contact.duration > 10 and contact.mean_contact_area > 50:
                    contact.contact_type = "stable_adhesion"
                elif contact.duration > 5:
                    contact.contact_type = "transient_contact"
                else:
                    contact.contact_type = "brief_touch"
            else:
                if contact.min_distance < self.contact_distance_threshold * 2:
                    contact.contact_type = "close_proximity"
                else:
                    contact.contact_type = "distant_approach"
            
            if phenotype_labels is not None:
                p1 = phenotype_labels.get(contact.track_id_1, -1)
                p2 = phenotype_labels.get(contact.track_id_2, -1)
                
                if phenotype_names is not None:
                    contact.phenotype_1 = phenotype_names.get(p1, f"phenotype_{p1}")
                    contact.phenotype_2 = phenotype_names.get(p2, f"phenotype_{p2}")
                else:
                    contact.phenotype_1 = str(p1)
                    contact.phenotype_2 = str(p2)
        
        return contacts
    
    def _create_contact_summary(self, contacts: List[CellContact]) -> pd.DataFrame:
        """
        Create summary DataFrame for all contacts.
        """
        if len(contacts) == 0:
            return pd.DataFrame()
        
        data = []
        for c in contacts:
            data.append({
                'track_id_1': c.track_id_1,
                'track_id_2': c.track_id_2,
                'start_frame': c.start_frame,
                'end_frame': c.end_frame,
                'duration': c.duration,
                'mean_distance': c.mean_distance,
                'min_distance': c.min_distance,
                'mean_contact_area': c.mean_contact_area,
                'max_contact_area': c.max_contact_area,
                'total_contact_area': c.total_contact_area,
                'contact_type': c.contact_type,
                'phenotype_1': c.phenotype_1,
                'phenotype_2': c.phenotype_2,
            })
        
        return pd.DataFrame(data)
    
    def _build_interaction_network(self,
                                    contacts: List[CellContact]) -> Dict[int, Dict[int, CellContact]]:
        """
        Build interaction network as nested dictionary.
        """
        network: Dict[int, Dict[int, CellContact]] = defaultdict(dict)
        
        for contact in contacts:
            tid1, tid2 = contact.track_id_1, contact.track_id_2
            network[tid1][tid2] = contact
            network[tid2][tid1] = contact
        
        return dict(network)
    
    def _build_interaction_matrix(self,
                                   contacts: List[CellContact],
                                   tracker: object) -> pd.DataFrame:
        """
        Build interaction matrix (cells x cells) with interaction strengths.
        """
        all_track_ids = sorted(tracker.tracks.keys())
        n = len(all_track_ids)
        
        matrix = np.zeros((n, n))
        track_to_idx = {tid: i for i, tid in enumerate(all_track_ids)}
        
        for contact in contacts:
            i = track_to_idx.get(contact.track_id_1, -1)
            j = track_to_idx.get(contact.track_id_2, -1)
            if i >= 0 and j >= 0:
                strength = contact.duration * (1 + contact.mean_contact_area / 100.0)
                matrix[i, j] += strength
                matrix[j, i] += strength
        
        return pd.DataFrame(
            matrix,
            index=[f"track_{tid}" for tid in all_track_ids],
            columns=[f"track_{tid}" for tid in all_track_ids]
        )


def compute_interaction_statistics(result: InteractionResult,
                                    phenotype_labels: Optional[Dict[int, int]] = None) -> Dict:
    """
    Compute comprehensive interaction statistics.
    """
    stats = {}
    
    contacts = result.contacts
    if len(contacts) == 0:
        stats['total_contacts'] = 0
        return stats
    
    durations = [c.duration for c in contacts]
    areas = [c.mean_contact_area for c in contacts]
    distances = [c.min_distance for c in contacts]
    
    stats['total_contacts'] = len(contacts)
    stats['mean_duration'] = float(np.mean(durations))
    stats['median_duration'] = float(np.median(durations))
    stats['max_duration'] = float(np.max(durations))
    stats['total_contact_frames'] = int(np.sum(durations))
    
    stats['mean_min_distance'] = float(np.mean(distances))
    stats['min_distance_overall'] = float(np.min(distances))
    
    area_contacts = [c for c in contacts if c.mean_contact_area > 0]
    stats['contacts_with_area'] = len(area_contacts)
    if area_contacts:
        stats['mean_contact_area'] = float(np.mean([c.mean_contact_area for c in area_contacts]))
        stats['max_contact_area'] = float(np.max([c.max_contact_area for c in area_contacts]))
    
    contact_types = defaultdict(int)
    for c in contacts:
        contact_types[c.contact_type] += 1
    stats['contact_types'] = dict(contact_types)
    
    if phenotype_labels is not None:
        homo_contacts = 0
        hetero_contacts = 0
        for c in contacts:
            p1 = phenotype_labels.get(c.track_id_1, -1)
            p2 = phenotype_labels.get(c.track_id_2, -1)
            if p1 >= 0 and p2 >= 0:
                if p1 == p2:
                    homo_contacts += 1
                else:
                    hetero_contacts += 1
        
        stats['homotypic_contacts'] = homo_contacts
        stats['heterotypic_contacts'] = hetero_contacts
        stats['homotypic_ratio'] = homo_contacts / max(homo_contacts + hetero_contacts, 1)
    
    pair_interactions = defaultdict(list)
    for c in contacts:
        key = tuple(sorted([c.track_id_1, c.track_id_2]))
        pair_interactions[key].append(c)
    
    stats['unique_pairs'] = len(pair_interactions)
    interactions_per_pair = [len(v) for v in pair_interactions.values()]
    stats['mean_interactions_per_pair'] = float(np.mean(interactions_per_pair))
    
    cell_interaction_counts = defaultdict(int)
    for c in contacts:
        cell_interaction_counts[c.track_id_1] += 1
        cell_interaction_counts[c.track_id_2] += 1
    
    stats['cells_with_interactions'] = len(cell_interaction_counts)
    if cell_interaction_counts:
        stats['mean_interactions_per_cell'] = float(np.mean(list(cell_interaction_counts.values())))
        stats['max_interactions_per_cell'] = float(np.max(list(cell_interaction_counts.values())))
    
    return stats


def analyze_temporal_interaction_patterns(result: InteractionResult,
                                           window_size: int = 5) -> pd.DataFrame:
    """
    Analyze how interaction patterns change over time.
    """
    frame_data = result.frame_by_frame
    if len(frame_data) == 0:
        return pd.DataFrame()
    
    T = int(frame_data['frame'].max()) + 1
    temporal_stats = []
    
    for start in range(0, T, window_size):
        end = min(start + window_size, T)
        window = frame_data[
            (frame_data['frame'] >= start) &
            (frame_data['frame'] < end)
        ]
        
        if len(window) == 0:
            continue
        
        contact_window = window[window['in_contact']]
        pairs = set()
        for _, row in contact_window.iterrows():
            pairs.add(tuple(sorted([row['track_id_1'], row['track_id_2']])))
        
        temporal_stats.append({
            'window_start': start,
            'window_end': end - 1,
            'n_pairs_in_proximity': len(window),
            'n_pairs_in_contact': len(pairs),
            'mean_distance': float(window['distance'].mean()),
            'total_contact_area': float(window['contact_area'].sum()),
        })
    
    return pd.DataFrame(temporal_stats)


def identify_leader_follower_pairs(result: InteractionResult,
                                     tracker: object,
                                     min_follow_duration: int = 10,
                                     max_distance: float = 20.0) -> List[Dict]:
    """
    Identify leader-follower relationships between cells.
    """
    contacts = [c for c in result.contacts 
                if c.min_distance < max_distance 
                and c.duration >= min_follow_duration]
    
    leader_follower = []
    
    for contact in contacts:
        tid1, tid2 = contact.track_id_1, contact.track_id_2
        
        track1 = tracker.tracks.get(tid1)
        track2 = tracker.tracks.get(tid2)
        
        if track1 is None or track2 is None:
            continue
        
        common_frames = sorted(set(contact.contact_frames) & set(track1.frames) & set(track2.frames))
        
        if len(common_frames) < min_follow_duration:
            continue
        
        positions1 = []
        positions2 = []
        for f in common_frames:
            idx1 = track1.frames.index(f)
            idx2 = track2.frames.index(f)
            positions1.append(track1.centroids[idx1])
            positions2.append(track2.centroids[idx2])
        
        positions1 = np.array(positions1)
        positions2 = np.array(positions2)
        
        direction_vectors = positions2 - positions1
        avg_direction = np.mean(direction_vectors, axis=0)
        
        if hasattr(track1, 'velocity_x') and len(track1.velocity_x) > 0:
            velocity1 = np.array([
                np.mean(track1.velocity_y[-5:]),
                np.mean(track1.velocity_x[-5:])
            ])
            velocity2 = np.array([
                np.mean(track2.velocity_y[-5:]),
                np.mean(track2.velocity_x[-5:])
            ])
            
            direction_1 = velocity1 / np.linalg.norm(velocity1) if np.linalg.norm(velocity1) > 0 else np.zeros(2)
            direction_2 = velocity2 / np.linalg.norm(velocity2) if np.linalg.norm(velocity2) > 0 else np.zeros(2)
            
            dir_similarity = np.dot(direction_1, direction_2)
            
            if dir_similarity > 0.7:
                proj1 = np.dot(positions1[0], direction_1)
                proj2 = np.dot(positions2[0], direction_1)
                
                if proj1 > proj2:
                    leader, follower = tid1, tid2
                else:
                    leader, follower = tid2, tid1
                
                leader_follower.append({
                    'leader_track_id': leader,
                    'follower_track_id': follower,
                    'start_frame': contact.start_frame,
                    'end_frame': contact.end_frame,
                    'duration': contact.duration,
                    'direction_similarity': float(dir_similarity),
                    'mean_distance': contact.mean_distance,
                })
    
    return leader_follower
