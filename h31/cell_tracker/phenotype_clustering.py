import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import logging
from dataclasses import dataclass, field
from collections import defaultdict

from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

logger = logging.getLogger(__name__)


@dataclass
class PhenotypeCluster:
    cluster_id: int
    name: str = ""
    description: str = ""
    member_track_ids: List[int] = field(default_factory=list)
    centroid: np.ndarray = field(default_factory=lambda: np.array([]))
    feature_means: Dict[str, float] = field(default_factory=dict)
    feature_stds: Dict[str, float] = field(default_factory=dict)


@dataclass
class ClusteringResult:
    labels: Dict[int, int]
    clusters: Dict[int, PhenotypeCluster]
    feature_names: List[str]
    cluster_metrics: Dict[str, float]
    feature_importance: Dict[str, float]
    scaler: object
    pca: Optional[object] = None
    pca_coordinates: Optional[Dict[int, Tuple[float, float]]] = None


class TrackFeatureExtractor:
    """
    Extract phenotypic features from cell tracks for clustering.
    """
    
    def __init__(self, 
                 include_motion: bool = True,
                 include_division: bool = True,
                 include_morphology: bool = True,
                 include_fluorescence: bool = True,
                 smoothing_window: int = 3):
        self.include_motion = include_motion
        self.include_division = include_division
        self.include_morphology = include_morphology
        self.include_fluorescence = include_fluorescence
        self.smoothing_window = smoothing_window
    
    def extract_features(self, 
                          tracker: object,
                          feature_data: Optional[pd.DataFrame] = None,
                          division_data: Optional[pd.DataFrame] = None,
                          masks: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        Extract features for all tracks.
        """
        all_features = []
        
        for track_id, track in tracker.tracks.items():
            if len(track.frames) < self.smoothing_window:
                continue
            
            track_feats = self._extract_track_features(
                track, feature_data, division_data, masks, tracker=tracker
            )
            track_feats['track_id'] = track_id
            all_features.append(track_feats)
        
        return pd.DataFrame(all_features)
    
    def _extract_track_features(self,
                                 track: object,
                                 feature_data: Optional[pd.DataFrame],
                                 division_data: Optional[pd.DataFrame],
                                 masks: Optional[np.ndarray],
                                 tracker: object) -> Dict[str, float]:
        features = {}
        
        if self.include_motion:
            motion_feats = self._extract_motion_features(track)
            features.update(motion_feats)
        
        if self.include_division:
            division_feats = self._extract_division_features(track, division_data)
            features.update(division_feats)
        
        if self.include_morphology and feature_data is not None:
            morph_feats = self._extract_morphology_features(track, feature_data)
            features.update(morph_feats)
        
        if self.include_fluorescence and feature_data is not None:
            fluo_feats = self._extract_fluorescence_features(track, feature_data)
            features.update(fluo_feats)
        
        if masks is not None:
            shape_feats = self._extract_shape_features(track, masks)
            features.update(shape_feats)
        
        features['track_duration'] = len(track.frames)
        
        return features
    
    def _extract_motion_features(self, track: object) -> Dict[str, float]:
        feats = {}
        
        positions = np.array(track.centroids)
        frames = np.array(track.frames)
        
        if len(positions) < 2:
            return {
                'mean_speed': 0, 'std_speed': 0, 'max_speed': 0,
                'mean_displacement': 0, 'total_displacement': 0,
                'directionality': 0, 'meandering_index': 0,
                'velocity_x': 0, 'velocity_y': 0
            }
        
        velocities = np.diff(positions, axis=0)
        time_diffs = np.diff(frames).reshape(-1, 1)
        time_diffs[time_diffs == 0] = 1
        
        speed = np.sqrt(np.sum((velocities / time_diffs) ** 2, axis=1))
        
        feats['mean_speed'] = float(np.mean(speed))
        feats['std_speed'] = float(np.std(speed))
        feats['max_speed'] = float(np.max(speed))
        feats['median_speed'] = float(np.median(speed))
        
        total_path = np.sum(speed)
        net_displacement = np.linalg.norm(positions[-1] - positions[0])
        feats['total_displacement'] = float(net_displacement)
        feats['mean_displacement'] = float(net_displacement / len(frames))
        
        if total_path > 0:
            feats['directionality'] = float(net_displacement / total_path)
        else:
            feats['directionality'] = 0
        
        feats['meandering_index'] = float(1.0 - feats['directionality'])
        
        if hasattr(track, 'velocity_x') and len(track.velocity_x) > 0:
            feats['mean_velocity_x'] = float(np.mean(track.velocity_x))
            feats['std_velocity_x'] = float(np.std(track.velocity_x))
            feats['mean_velocity_y'] = float(np.mean(track.velocity_y))
            feats['std_velocity_y'] = float(np.std(track.velocity_y))
        
        if len(velocities) >= 3:
            velocity_vectors = velocities / time_diffs
            cos_similarities = []
            for i in range(len(velocity_vectors) - 1):
                v1 = velocity_vectors[i]
                v2 = velocity_vectors[i + 1]
                norm1 = np.linalg.norm(v1)
                norm2 = np.linalg.norm(v2)
                if norm1 > 0 and norm2 > 0:
                    cos_sim = np.dot(v1, v2) / (norm1 * norm2)
                    cos_similarities.append(cos_sim)
            if cos_similarities:
                feats['directional_consistency'] = float(np.mean(cos_similarities))
                feats['turning_angle'] = float(np.mean(np.arccos(np.clip(cos_similarities, -1, 1))))
        
        return feats
    
    def _extract_division_features(self,
                                    track: object,
                                    division_data: Optional[pd.DataFrame]) -> Dict[str, float]:
        feats = {
            'division_count': 0,
            'time_to_first_division': -1,
            'division_interval_mean': -1,
            'is_parent': 0,
            'is_child': 0,
            'sibling_pair_id': -1
        }
        
        if division_data is None or len(division_data) == 0:
            return feats
        
        if 'parent_track_id' in division_data.columns:
            parent_divisions = division_data[division_data['parent_track_id'] == track.track_id]
            feats['division_count'] = len(parent_divisions)
            feats['is_parent'] = 1 if len(parent_divisions) > 0 else 0
            
            if len(parent_divisions) > 0 and 'frame' in parent_divisions.columns:
                division_times = parent_divisions['frame'].values
                if len(division_times) > 0 and len(track.frames) > 0:
                    feats['time_to_first_division'] = float(division_times[0] - track.frames[0])
                
                if len(division_times) >= 2:
                    intervals = np.diff(division_times)
                    feats['division_interval_mean'] = float(np.mean(intervals))
        
        if 'child_track_id' in division_data.columns:
            child_divisions = division_data[division_data['child_track_id'] == track.track_id]
            feats['is_child'] = 1 if len(child_divisions) > 0 else 0
            
            if len(child_divisions) > 0 and 'parent_track_id' in child_divisions.columns:
                parent_id = child_divisions.iloc[0]['parent_track_id']
                feats['parent_track_id'] = int(parent_id)
                
                siblings = division_data[division_data['parent_track_id'] == parent_id]
                if len(siblings) >= 2:
                    feats['sibling_pair_id'] = int(parent_id)
        
        if hasattr(track, 'daughter_tracks') and track.daughter_tracks:
            feats['num_daughters'] = len(track.daughter_tracks)
        
        if hasattr(track, 'parent_id') and track.parent_id is not None:
            feats['is_child'] = 1
            feats['parent_track_id'] = int(track.parent_id)
        
        if hasattr(track, 'children_ids') and len(track.children_ids) > 0:
            feats['is_parent'] = 1
            feats['division_count'] = len(track.children_ids)
            if track.division_frame is not None and len(track.frames) > 0:
                feats['time_to_first_division'] = float(track.division_frame - track.frames[0])
        
        return feats
    
    def _extract_morphology_features(self,
                                      track: object,
                                      feature_data: pd.DataFrame) -> Dict[str, float]:
        feats = {}
        
        track_features = feature_data[feature_data['track_id'] == track.track_id]
        
        if len(track_features) == 0:
            return feats
        
        for col in ['area', 'eccentricity', 'solidity', 'compactness', 
                    'extent', 'perimeter', 'aspect_ratio']:
            if col in track_features.columns:
                values = track_features[col].values
                feats[f'mean_{col}'] = float(np.mean(values))
                feats[f'std_{col}'] = float(np.std(values))
                feats[f'cv_{col}'] = float(np.std(values) / max(np.mean(values), 1e-6))
        
        if 'area' in track_features.columns:
            areas = track_features['area'].values
            feats['area_growth_rate'] = float(
                (areas[-1] - areas[0]) / max(areas[0], 1e-6) / max(len(areas), 1)
            )
            feats['max_area_change'] = float(np.max(np.abs(np.diff(areas))))
        
        if 'eccentricity' in track_features.columns:
            ecc = track_features['eccentricity'].values
            feats['mean_circularity'] = float(1.0 - np.mean(ecc))
        
        return feats
    
    def _extract_fluorescence_features(self,
                                        track: object,
                                        feature_data: pd.DataFrame) -> Dict[str, float]:
        feats = {}
        
        track_features = feature_data[feature_data['track_id'] == track.track_id]
        
        if len(track_features) == 0:
            return feats
        
        fluo_cols = [col for col in track_features.columns 
                     if 'fluorescence' in col.lower() or 'intensity' in col.lower()]
        
        for col in fluo_cols:
            values = track_features[col].values
            feats[f'mean_{col}'] = float(np.mean(values))
            feats[f'std_{col}'] = float(np.std(values))
            feats[f'max_{col}'] = float(np.max(values))
            feats[f'min_{col}'] = float(np.min(values))
            
            if len(values) > 1:
                feats[f'slope_{col}'] = float(np.polyfit(range(len(values)), values, 1)[0])
                feats[f'cv_{col}'] = float(np.std(values) / max(np.mean(values), 1e-6))
        
        if 'corrected_fluorescence' in track_features.columns:
            corr = track_features['corrected_fluorescence'].values
            feats['fluorescence_decay_rate'] = float(
                np.polyfit(range(len(corr)), corr, 1)[0] / max(np.mean(corr), 1e-6)
            )
        
        return feats
    
    def _extract_shape_features(self,
                                 track: object,
                                 masks: np.ndarray) -> Dict[str, float]:
        feats = {}
        
        from skimage.measure import regionprops
        
        volumes = []
        surface_areas = []
        sphericities = []
        
        for i, frame in enumerate(track.frames):
            if frame >= len(masks):
                continue
            
            label = track.labels[i] if hasattr(track, 'labels') and i < len(track.labels) else 0
            if label == 0:
                continue
            
            mask = masks[frame] == label
            if not np.any(mask):
                continue
            
            try:
                if mask.ndim == 3:
                    props = regionprops(mask.astype(int))[0]
                    volumes.append(props.area)
                    surface_areas.append(props.perimeter)
                    
                    if props.area > 0:
                        sphere_r = (3 * props.area / (4 * np.pi)) ** (1/3)
                        sphere_surface = 4 * np.pi * sphere_r ** 2
                        sphericities.append(sphere_surface / max(props.perimeter, 1))
            except:
                pass
        
        if volumes:
            feats['mean_volume'] = float(np.mean(volumes))
            feats['std_volume'] = float(np.std(volumes))
        
        if surface_areas:
            feats['mean_surface_area'] = float(np.mean(surface_areas))
        
        if sphericities:
            feats['mean_sphericity'] = float(np.mean(sphericities))
        
        return feats


class PhenotypeClusterer:
    """
    Cluster cells based on phenotypic features.
    """
    
    def __init__(self,
                 algorithm: str = 'kmeans',
                 n_clusters: int = 3,
                 scaler: str = 'standard',
                 use_pca: bool = True,
                 pca_components: int = 10,
                 random_state: int = 42,
                 dbscan_eps: float = 0.5,
                 dbscan_min_samples: int = 5,
                 feature_filter_threshold: float = 0.1):
        self.algorithm = algorithm
        self.n_clusters = n_clusters
        self.scaler_type = scaler
        self.use_pca = use_pca
        self.pca_components = pca_components
        self.random_state = random_state
        self.dbscan_eps = dbscan_eps
        self.dbscan_min_samples = dbscan_min_samples
        self.feature_filter_threshold = feature_filter_threshold
        
        self.scaler = None
        self.pca = None
        self.model = None
        self.feature_names_ = None
    
    def cluster(self,
                 features_df: pd.DataFrame,
                 ignore_columns: List[str] = None) -> ClusteringResult:
        """
        Perform phenotypic clustering.
        """
        if ignore_columns is None:
            ignore_columns = ['track_id']
        
        feature_matrix = features_df.drop(columns=ignore_columns, errors='ignore')
        feature_matrix = feature_matrix.replace([np.inf, -np.inf], np.nan)
        feature_matrix = feature_matrix.fillna(feature_matrix.median())
        
        feature_matrix = self._filter_constant_features(feature_matrix)
        
        self.feature_names_ = feature_matrix.columns.tolist()
        X = feature_matrix.values
        
        X_scaled = self._scale_features(X)
        
        if self.use_pca:
            X_transformed, self.pca = self._apply_pca(X_scaled)
        else:
            X_transformed = X_scaled
        
        labels = self._fit_clustering(X_transformed)
        
        result = self._build_result(
            labels, features_df, feature_matrix, X_transformed
        )
        
        return result
    
    def _filter_constant_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove features with low variance."""
        from sklearn.feature_selection import VarianceThreshold
        
        selector = VarianceThreshold(threshold=self.feature_filter_threshold)
        selector.fit(df)
        
        kept_cols = df.columns[selector.get_support()]
        logger.info(f"Kept {len(kept_cols)}/{len(df.columns)} features after variance filtering")
        
        return df[kept_cols]
    
    def _scale_features(self, X: np.ndarray) -> np.ndarray:
        """Scale features."""
        if self.scaler_type == 'standard':
            self.scaler = StandardScaler()
        elif self.scaler_type == 'robust':
            self.scaler = RobustScaler()
        else:
            self.scaler = None
            return X
        
        return self.scaler.fit_transform(X)
    
    def _apply_pca(self, X: np.ndarray) -> Tuple[np.ndarray, PCA]:
        """Apply PCA dimensionality reduction."""
        n_components = min(self.pca_components, X.shape[1], X.shape[0])
        pca = PCA(n_components=n_components, random_state=self.random_state)
        X_pca = pca.fit_transform(X)
        
        explained = sum(pca.explained_variance_ratio_)
        logger.info(f"PCA: {n_components} components explaining {explained:.1%} variance")
        
        return X_pca, pca
    
    def _fit_clustering(self, X: np.ndarray) -> np.ndarray:
        """Fit clustering model."""
        if self.algorithm == 'kmeans':
            self.model = KMeans(
                n_clusters=self.n_clusters,
                random_state=self.random_state,
                n_init=10
            )
        elif self.algorithm == 'hierarchical':
            self.model = AgglomerativeClustering(
                n_clusters=self.n_clusters,
                affinity='euclidean',
                linkage='ward'
            )
        elif self.algorithm == 'dbscan':
            self.model = DBSCAN(
                eps=self.dbscan_eps,
                min_samples=self.dbscan_min_samples
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
        
        labels = self.model.fit_predict(X)
        n_clusters_found = len(set(labels)) - (1 if -1 in labels else 0)
        logger.info(f"Clustering found {n_clusters_found} clusters with {sum(labels == -1)} noise points")
        
        return labels
    
    def _build_result(self,
                       labels: np.ndarray,
                       features_df: pd.DataFrame,
                       feature_matrix: pd.DataFrame,
                       X_transformed: np.ndarray) -> ClusteringResult:
        """Build clustering result object."""
        track_ids = features_df['track_id'].values
        label_dict = {int(tid): int(lab) for tid, lab in zip(track_ids, labels)}
        
        cluster_metrics = self._compute_clustering_metrics(X_transformed, labels)
        
        feature_importance = self._compute_feature_importance(
            feature_matrix.values, labels
        )
        
        clusters = self._build_clusters(
            labels, track_ids, feature_matrix
        )
        
        pca_coords = None
        if self.use_pca and X_transformed.shape[1] >= 2:
            pca_coords = {
                int(tid): (float(X_transformed[i, 0]), float(X_transformed[i, 1]))
                for i, tid in enumerate(track_ids)
            }
        
        return ClusteringResult(
            labels=label_dict,
            clusters=clusters,
            feature_names=self.feature_names_,
            cluster_metrics=cluster_metrics,
            feature_importance=feature_importance,
            scaler=self.scaler,
            pca=self.pca,
            pca_coordinates=pca_coords
        )
    
    def _compute_clustering_metrics(self, X: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
        """Compute clustering quality metrics."""
        metrics = {}
        
        unique_labels = set(labels)
        n_clusters = len(unique_labels) - (1 if -1 in labels else 0)
        
        if n_clusters > 1 and len(X) > n_clusters:
            try:
                if n_clusters > 1 and len(set(labels)) > 1:
                    noise_mask = labels != -1
                    if np.sum(noise_mask) > n_clusters:
                        metrics['silhouette_score'] = float(silhouette_score(
                            X[noise_mask], labels[noise_mask]
                        ))
                        metrics['calinski_harabasz'] = float(calinski_harabasz_score(
                            X[noise_mask], labels[noise_mask]
                        ))
                        metrics['davies_bouldin'] = float(davies_bouldin_score(
                            X[noise_mask], labels[noise_mask]
                        ))
            except:
                pass
        
        metrics['n_clusters'] = n_clusters
        metrics['n_noise'] = int(np.sum(labels == -1))
        
        return metrics
    
    def _compute_feature_importance(self,
                                     X: np.ndarray,
                                     labels: np.ndarray) -> Dict[str, float]:
        """Compute feature importance for cluster discrimination."""
        importance = {}
        
        try:
            mask = labels != -1
            if len(set(labels[mask])) > 1:
                clf = RandomForestClassifier(
                    n_estimators=100,
                    random_state=self.random_state
                )
                clf.fit(X[mask], labels[mask])
                
                result = permutation_importance(
                    clf, X[mask], labels[mask],
                    n_repeats=5,
                    random_state=self.random_state,
                    n_jobs=-1
                )
                
                for i, name in enumerate(self.feature_names_):
                    importance[name] = float(result.importances_mean[i])
        except:
            for name in self.feature_names_:
                importance[name] = 0.0
        
        return importance
    
    def _build_clusters(self,
                         labels: np.ndarray,
                         track_ids: np.ndarray,
                         feature_matrix: pd.DataFrame) -> Dict[int, PhenotypeCluster]:
        """Build cluster descriptions."""
        clusters = {}
        
        for cluster_id in set(labels):
            if cluster_id == -1:
                continue
            
            mask = labels == cluster_id
            cluster_tracks = track_ids[mask]
            cluster_features = feature_matrix[mask]
            
            centroid = np.mean(cluster_features.values, axis=0)
            
            feature_means = {}
            feature_stds = {}
            for col in feature_matrix.columns:
                feature_means[col] = float(cluster_features[col].mean())
                feature_stds[col] = float(cluster_features[col].std())
            
            cluster = PhenotypeCluster(
                cluster_id=int(cluster_id),
                name=f"Phenotype {cluster_id}",
                member_track_ids=[int(tid) for tid in cluster_tracks],
                centroid=centroid,
                feature_means=feature_means,
                feature_stds=feature_stds
            )
            
            cluster.description = self._generate_cluster_description(cluster)
            clusters[int(cluster_id)] = cluster
        
        return clusters
    
    def _generate_cluster_description(self, cluster: PhenotypeCluster) -> str:
        """Generate human-readable description of phenotype."""
        if not cluster.feature_means:
            return ""
        
        top_feats = sorted(
            cluster.feature_means.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]
        
        parts = []
        for feat, val in top_feats:
            if 'speed' in feat:
                if val > 1:
                    parts.append(f"high mobility ({val:.2f})")
                elif val < 0.5:
                    parts.append(f"low mobility ({val:.2f})")
            elif 'division' in feat:
                if 'count' in feat and val > 0:
                    parts.append(f"dividing ({val:.1f}x)")
            elif 'eccentricity' in feat:
                if val > 0.7:
                    parts.append("elongated shape")
                elif val < 0.3:
                    parts.append("rounded shape")
            elif 'directionality' in feat:
                if val > 0.7:
                    parts.append("directed movement")
                elif val < 0.3:
                    parts.append("random movement")
        
        return "; ".join(parts) if parts else "Average phenotype"


def find_optimal_clusters(X: np.ndarray,
                           max_k: int = 10,
                           algorithm: str = 'kmeans') -> Dict[str, np.ndarray]:
    """
    Find optimal number of clusters using elbow method and silhouette analysis.
    """
    metrics = {'k': [], 'silhouette': [], 'calinski': [], 'davies': []}
    
    X_clean = X.copy()
    if isinstance(X_clean, pd.DataFrame):
        X_clean = X_clean.values
    X_clean = np.where(np.isfinite(X_clean), X_clean, 0)
    
    for k in range(2, max_k + 1):
        if algorithm == 'kmeans':
            model = KMeans(n_clusters=k, random_state=42, n_init=10)
        else:
            model = AgglomerativeClustering(n_clusters=k)
        
        labels = model.fit_predict(X_clean)
        
        if len(set(labels)) > 1:
            metrics['k'].append(k)
            metrics['silhouette'].append(silhouette_score(X_clean, labels))
            metrics['calinski'].append(calinski_harabasz_score(X_clean, labels))
            metrics['davies'].append(davies_bouldin_score(X_clean, labels))
    
    return metrics


def assign_phenotype_names(clusters: Dict[int, PhenotypeCluster]) -> Dict[int, PhenotypeCluster]:
    """
    Automatically assign meaningful names to clusters based on features.
    """
    name_templates = [
        'high_speed', 'low_speed',
        'dividing', 'non_dividing',
        'elongated', 'rounded',
        'directed', 'random',
        'large', 'small'
    ]
    
    for cid, cluster in clusters.items():
        feats = cluster.feature_means
        name_parts = []
        
        if 'mean_speed' in feats:
            if feats['mean_speed'] > 2:
                name_parts.append('Fast')
            elif feats['mean_speed'] < 0.5:
                name_parts.append('Slow')
        
        if 'division_count' in feats and feats['division_count'] > 0:
            name_parts.append('Dividing')
        elif 'is_parent' in feats and feats['is_parent'] < 0.5:
            name_parts.append('Quiescent')
        
        if 'mean_eccentricity' in feats:
            if feats['mean_eccentricity'] > 0.6:
                name_parts.append('Elongated')
            elif feats['mean_eccentricity'] < 0.4:
                name_parts.append('Rounded')
        
        if 'directionality' in feats:
            if feats['directionality'] > 0.6:
                name_parts.append('Directed')
            elif feats['directionality'] < 0.4:
                name_parts.append('Exploratory')
        
        if not name_parts:
            name_parts = [f'Phenotype {cid}']
        
        cluster.name = ' '.join(name_parts)
    
    return clusters
