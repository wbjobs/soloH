import numpy as np
import pandas as pd
from scipy.spatial import cKDTree, ConvexHull
from scipy.ndimage import label as nd_label
from typing import List, Dict, Tuple, Optional
from .data_io import PointCloudData, LABEL_NAMES


class TreeMetrics:
    def __init__(self, tree_id: int):
        self.tree_id = tree_id
        self.position_x: float = 0.0
        self.position_y: float = 0.0
        self.tree_height: float = 0.0
        self.crown_width: float = 0.0
        self.crown_depth: float = 0.0
        self.crown_area: float = 0.0
        self.crown_volume: float = 0.0
        self.lai: float = 0.0
        self.leaf_area: float = 0.0
        self.trunk_diameter: float = 0.0
        self.total_points: int = 0
        self.trunk_points: int = 0
        self.large_branch_points: int = 0
        self.small_branch_points: int = 0
        self.leaf_points: int = 0
        self.dbh: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'tree_id': self.tree_id,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'tree_height': self.tree_height,
            'crown_width': self.crown_width,
            'crown_depth': self.crown_depth,
            'crown_area': self.crown_area,
            'crown_volume': self.crown_volume,
            'lai': self.lai,
            'leaf_area': self.leaf_area,
            'trunk_diameter': self.trunk_diameter,
            'dbh': self.dbh,
            'total_points': self.total_points,
            'trunk_points': self.trunk_points,
            'large_branch_points': self.large_branch_points,
            'small_branch_points': self.small_branch_points,
            'leaf_points': self.leaf_points,
        }


def cluster_trees(points: np.ndarray, labels: np.ndarray,
                  min_points: int = 50,
                  distance_threshold: float = 0.5) -> np.ndarray:
    trunk_mask = labels == 1
    non_ground_mask = labels > 0

    if not trunk_mask.any():
        trunk_mask = non_ground_mask

    trunk_points = points[trunk_mask]

    if len(trunk_points) < min_points:
        return np.zeros(len(points), dtype=np.int32)

    from sklearn.cluster import DBSCAN
    clustering = DBSCAN(eps=distance_threshold, min_samples=min_points).fit(trunk_points[:, :2])
    trunk_labels = clustering.labels_

    tree_ids = np.zeros(len(points), dtype=np.int32) - 1
    tree_ids[trunk_mask] = trunk_labels

    valid_tree_ids = np.unique(trunk_labels[trunk_labels >= 0])

    non_ground_indices = np.where(non_ground_mask)[0]
    non_ground_xy = points[non_ground_mask][:, :2]

    tree_centers = []
    for tid in valid_tree_ids:
        tree_trunk_mask = trunk_labels == tid
        if tree_trunk_mask.any():
            center = trunk_points[tree_trunk_mask][:, :2].mean(axis=0)
            tree_centers.append((tid, center))

    if len(tree_centers) > 0 and len(non_ground_xy) > 0:
        centers = np.array([c[1] for c in tree_centers])
        tree_ids_list = np.array([c[0] for c in tree_centers])

        tree = cKDTree(centers)
        _, nearest_idx = tree.query(non_ground_xy)
        assigned_ids = tree_ids_list[nearest_idx]

        tree_ids[non_ground_indices] = assigned_ids

    return tree_ids


def cluster_by_horizontal(points: np.ndarray, labels: np.ndarray,
                          grid_size: float = 1.0,
                          min_height: float = 2.0) -> np.ndarray:
    non_ground_mask = labels > 0
    non_ground_points = points[non_ground_mask]

    if len(non_ground_points) < 10:
        return np.zeros(len(points), dtype=np.int32)

    height_mask = non_ground_points[:, 2] >= min_height
    high_points = non_ground_points[height_mask]

    if len(high_points) < 10:
        high_points = non_ground_points

    x_min, y_min = high_points[:, 0].min(), high_points[:, 1].min()
    x_max, y_max = high_points[:, 0].max(), high_points[:, 1].max()

    num_x = int(np.ceil((x_max - x_min) / grid_size)) + 1
    num_y = int(np.ceil((y_max - y_min) / grid_size)) + 1

    grid = np.zeros((num_x, num_y), dtype=np.int32)
    grid_count = np.zeros((num_x, num_y), dtype=np.int32)

    for p in high_points:
        gx = int((p[0] - x_min) / grid_size)
        gy = int((p[1] - y_min) / grid_size)
        gx = np.clip(gx, 0, num_x - 1)
        gy = np.clip(gy, 0, num_y - 1)
        grid[gx, gy] = 1
        grid_count[gx, gy] += 1

    structure = np.ones((3, 3), dtype=bool)
    labeled_grid, num_regions = nd_label(grid, structure=structure)

    tree_ids = np.zeros(len(points), dtype=np.int32) - 1
    non_ground_indices = np.where(non_ground_mask)[0]

    if num_regions > 0:
        region_centers = []
        for rid in range(1, num_regions + 1):
            mask = labeled_grid == rid
            gx, gy = np.where(mask)
            cx = x_min + (gx.mean() + 0.5) * grid_size
            cy = y_min + (gy.mean() + 0.5) * grid_size
            region_centers.append((rid - 1, np.array([cx, cy])))

        if len(region_centers) > 0:
            centers = np.array([c[1] for c in region_centers])
            rid_list = np.array([c[0] for c in region_centers])

            tree = cKDTree(centers)
            _, nearest_idx = tree.query(non_ground_points[:, :2])
            assigned_ids = rid_list[nearest_idx]

            tree_ids[non_ground_indices] = assigned_ids

    return tree_ids


def compute_tree_metrics(tree_points: np.ndarray, tree_labels: np.ndarray,
                         leaf_area_per_point: float = 0.01) -> TreeMetrics:
    metrics = TreeMetrics(tree_id=0)

    if len(tree_points) == 0:
        return metrics

    metrics.total_points = len(tree_points)
    metrics.trunk_points = np.sum(tree_labels == 1)
    metrics.large_branch_points = np.sum(tree_labels == 2)
    metrics.small_branch_points = np.sum(tree_labels == 3)
    metrics.leaf_points = np.sum(tree_labels == 4)

    trunk_mask = tree_labels == 1
    if trunk_mask.any():
        trunk_points = tree_points[trunk_mask]
        metrics.position_x = trunk_points[:, 0].mean()
        metrics.position_y = trunk_points[:, 1].mean()
    else:
        metrics.position_x = tree_points[:, 0].mean()
        metrics.position_y = tree_points[:, 1].mean()

    metrics.tree_height = tree_points[:, 2].max() - tree_points[:, 2].min()

    leaf_mask = tree_labels == 4
    leaf_points = tree_points[leaf_mask] if leaf_mask.any() else tree_points

    if len(leaf_points) > 3:
        xy = leaf_points[:, :2]
        try:
            hull = ConvexHull(xy)
            metrics.crown_area = hull.area

            min_x, max_x = xy[:, 0].min(), xy[:, 0].max()
            min_y, max_y = xy[:, 1].min(), xy[:, 1].max()
            metrics.crown_width = max_x - min_x
            metrics.crown_depth = max_y - min_y

            z_min, z_max = leaf_points[:, 2].min(), leaf_points[:, 2].max()
            metrics.crown_volume = metrics.crown_area * (z_max - z_min) * 0.5
        except:
            min_x, max_x = xy[:, 0].min(), xy[:, 0].max()
            min_y, max_y = xy[:, 1].min(), xy[:, 1].max()
            metrics.crown_width = max_x - min_x
            metrics.crown_depth = max_y - min_y
            metrics.crown_area = metrics.crown_width * metrics.crown_depth
            z_min, z_max = leaf_points[:, 2].min(), leaf_points[:, 2].max()
            metrics.crown_volume = metrics.crown_area * (z_max - z_min) * 0.5
    else:
        xy = tree_points[:, :2]
        min_x, max_x = xy[:, 0].min(), xy[:, 0].max()
        min_y, max_y = xy[:, 1].min(), xy[:, 1].max()
        metrics.crown_width = max_x - min_x
        metrics.crown_depth = max_y - min_y
        metrics.crown_area = metrics.crown_width * metrics.crown_depth
        z_min, z_max = tree_points[:, 2].min(), tree_points[:, 2].max()
        metrics.crown_volume = metrics.crown_area * (z_max - z_min) * 0.5

    metrics.leaf_area = metrics.leaf_points * leaf_area_per_point
    if metrics.crown_area > 0:
        metrics.lai = metrics.leaf_area / metrics.crown_area

    if trunk_mask.any() and len(trunk_points) > 5:
        height_sorted = np.argsort(tree_points[:, 2])
        dbh_height_range = (1.2, 1.4)
        dbh_mask = (tree_points[:, 2] >= dbh_height_range[0]) & (tree_points[:, 2] <= dbh_height_range[1])
        dbh_points = tree_points[dbh_mask & trunk_mask]

        if len(dbh_points) > 3:
            center_xy = np.mean(dbh_points[:, :2], axis=0)
            distances = np.linalg.norm(dbh_points[:, :2] - center_xy, axis=1)
            metrics.dbh = 2 * np.mean(distances)
            metrics.trunk_diameter = metrics.dbh
        else:
            center_xy = np.mean(trunk_points[:, :2], axis=0)
            distances = np.linalg.norm(trunk_points[:, :2] - center_xy, axis=1)
            metrics.trunk_diameter = 2 * np.mean(distances)
            metrics.dbh = metrics.trunk_diameter

    return metrics


def extract_individual_trees(data: PointCloudData,
                             method: str = 'dbscan',
                             min_points: int = 50,
                             distance_threshold: float = 0.5,
                             leaf_area_per_point: float = 0.01,
                             min_tree_points: int = 100) -> Tuple[List[TreeMetrics], np.ndarray, np.ndarray]:
    points = data.points
    labels = data.labels

    if labels is None:
        raise ValueError("Point cloud must have segmentation labels for tree extraction")

    if method == 'dbscan':
        tree_ids = cluster_trees(points, labels, min_points, distance_threshold)
    elif method == 'horizontal':
        tree_ids = cluster_by_horizontal(points, labels)
    else:
        raise ValueError(f"Unknown clustering method: {method}")

    tree_metrics_list = []
    unique_ids = np.unique(tree_ids)
    unique_ids = unique_ids[unique_ids >= 0]

    instance_labels = np.zeros(len(points), dtype=np.int32)

    for idx, tid in enumerate(unique_ids):
        tree_mask = tree_ids == tid
        tree_points = points[tree_mask]
        tree_labels = labels[tree_mask]

        if len(tree_points) < min_tree_points:
            continue

        metrics = compute_tree_metrics(tree_points, tree_labels, leaf_area_per_point)
        metrics.tree_id = idx
        tree_metrics_list.append(metrics)
        instance_labels[tree_mask] = idx + 1

    return tree_metrics_list, tree_ids, instance_labels


def metrics_to_dataframe(metrics_list: List[TreeMetrics]) -> pd.DataFrame:
    data = [m.to_dict() for m in metrics_list]
    return pd.DataFrame(data)


def compute_point_density(points: np.ndarray, k: int = 10) -> np.ndarray:
    tree = cKDTree(points)
    distances, _ = tree.query(points, k=k + 1)
    avg_distances = np.mean(distances[:, 1:], axis=1)
    density = 1.0 / (avg_distances ** 3 + 1e-8)
    return density


def estimate_leaf_area_index(leaf_points: np.ndarray,
                             crown_projection_area: float,
                             leaf_clumping_factor: float = 1.0) -> float:
    if crown_projection_area <= 0 or len(leaf_points) == 0:
        return 0.0

    density = compute_point_density(leaf_points, k=10)
    avg_density = np.mean(density)

    leaf_area = len(leaf_points) * (1.0 / avg_density) ** (2.0 / 3.0) * 0.5
    lai = leaf_clumping_factor * leaf_area / crown_projection_area

    return lai


def save_metrics_csv(metrics_list: List[TreeMetrics], filepath: str):
    df = metrics_to_dataframe(metrics_list)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    return df
