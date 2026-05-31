import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d
from typing import Tuple, List
from .data_io import PointCloudData


class CSFParams:
    def __init__(self, bSloopSmooth=True, cloth_resolution=0.5,
                 rigidness=3, time_step=0.65, class_threshold=0.5,
                 interations=500):
        self.bSloopSmooth = bSloopSmooth
        self.cloth_resolution = cloth_resolution
        self.rigidness = rigidness
        self.time_step = time_step
        self.class_threshold = class_threshold
        self.interations = interations


class Particle:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.prev_z = z
        self.tmp_z = z
        self.is_ground = False
        self.neighbors = []


def cloth_simulation_filter(points: np.ndarray, params: CSFParams) -> Tuple[np.ndarray, np.ndarray]:
    if len(points) < 3:
        return np.zeros(len(points), dtype=bool), np.zeros(len(points), dtype=bool)

    xyz = points.copy()
    min_z = xyz[:, 2].min()
    xyz[:, 2] = -xyz[:, 2] + (max(xyz[:, 2]) + min_z)

    x_min, y_min = xyz[:, 0].min(), xyz[:, 1].min()
    x_max, y_max = xyz[:, 0].max(), xyz[:, 1].max()

    res = params.cloth_resolution
    num_x = int(np.ceil((x_max - x_min) / res)) + 1
    num_y = int(np.ceil((y_max - y_min) / res)) + 1

    particles = []
    for i in range(num_x):
        row = []
        for j in range(num_y):
            x = x_min + i * res
            y = y_min + j * res
            row.append(Particle(x, y, xyz[:, 2].max()))
        particles.append(row)

    for i in range(num_x):
        for j in range(num_y):
            if i > 0:
                particles[i][j].neighbors.append(particles[i-1][j])
            if i < num_x - 1:
                particles[i][j].neighbors.append(particles[i+1][j])
            if j > 0:
                particles[i][j].neighbors.append(particles[i][j-1])
            if j < num_y - 1:
                particles[i][j].neighbors.append(particles[i][j+1])

    tree = cKDTree(xyz[:, :2])
    _, nearest_indices = tree.query(
        np.array([[p.x, p.y] for row in particles for p in row]), k=1
    )
    nearest_indices = nearest_indices.reshape(num_x, num_y)

    for i in range(num_x):
        for j in range(num_y):
            particles[i][j].tmp_z = xyz[nearest_indices[i, j], 2]

    for iteration in range(params.interations):
        for i in range(num_x):
            for j in range(num_y):
                p = particles[i][j]
                p.prev_z = p.z
                if p.z > p.tmp_z:
                    p.z = p.tmp_z

        if params.bSloopSmooth:
            for _ in range(params.rigidness):
                for i in range(num_x):
                    for j in range(num_y):
                        p = particles[i][j]
                        if p.z == p.tmp_z:
                            continue
                        neighbors = p.neighbors
                        if len(neighbors) > 0:
                            avg_z = np.mean([n.prev_z for n in neighbors])
                            p.z += (avg_z - p.z) * 0.5

        max_move = max(abs(p.z - p.prev_z) for row in particles for p in row)
        if max_move < 0.001:
            break

    cloth_heights = np.zeros((num_x, num_y))
    for i in range(num_x):
        for j in range(num_y):
            cloth_heights[i, j] = -(particles[i][j].z - (max(xyz[:, 2]) + min_z))

    original_xyz = points
    grid_x = ((original_xyz[:, 0] - x_min) / res).astype(int)
    grid_y = ((original_xyz[:, 1] - y_min) / res).astype(int)
    grid_x = np.clip(grid_x, 0, num_x - 1)
    grid_y = np.clip(grid_y, 0, num_y - 1)

    interp_heights = cloth_heights[grid_x, grid_y]
    height_diff = original_xyz[:, 2] - interp_heights

    ground_mask = height_diff <= params.class_threshold
    non_ground_mask = ~ground_mask

    return ground_mask, non_ground_mask


def simple_ground_filter(points: np.ndarray, grid_size: float = 1.0,
                         height_threshold: float = 0.3) -> Tuple[np.ndarray, np.ndarray]:
    if len(points) < 3:
        return np.zeros(len(points), dtype=bool), np.zeros(len(points), dtype=bool)

    x_min, y_min = points[:, 0].min(), points[:, 1].min()
    x_max, y_max = points[:, 0].max(), points[:, 1].max()

    num_x = int(np.ceil((x_max - x_min) / grid_size)) + 1
    num_y = int(np.ceil((y_max - y_min) / grid_size)) + 1

    grid_x = ((points[:, 0] - x_min) / grid_size).astype(int)
    grid_y = ((points[:, 1] - y_min) / grid_size).astype(int)

    grid_x = np.clip(grid_x, 0, num_x - 1)
    grid_y = np.clip(grid_y, 0, num_y - 1)

    grid_indices = grid_x * num_y + grid_y

    ground_mask = np.zeros(len(points), dtype=bool)

    unique_indices = np.unique(grid_indices)
    for idx in unique_indices:
        cell_mask = grid_indices == idx
        cell_points = points[cell_mask]
        if len(cell_points) > 0:
            min_z = cell_points[:, 2].min()
            cell_ground_mask = cell_points[:, 2] <= min_z + height_threshold
            ground_mask[cell_mask] = cell_ground_mask

    non_ground_mask = ~ground_mask
    return ground_mask, non_ground_mask


def remove_ground(data: PointCloudData, method: str = 'csf',
                  **kwargs) -> Tuple[PointCloudData, np.ndarray, np.ndarray]:
    points = data.points

    if method == 'csf':
        params = CSFParams(
            cloth_resolution=kwargs.get('cloth_resolution', 0.5),
            rigidness=kwargs.get('rigidness', 3),
            class_threshold=kwargs.get('class_threshold', 0.5)
        )
        ground_mask, non_ground_mask = cloth_simulation_filter(points, params)
    elif method == 'simple':
        ground_mask, non_ground_mask = simple_ground_filter(
            points,
            grid_size=kwargs.get('grid_size', 1.0),
            height_threshold=kwargs.get('height_threshold', 0.3)
        )
    else:
        raise ValueError(f"Unknown ground filtering method: {method}")

    non_ground_points = points[non_ground_mask]
    non_ground_colors = data.colors[non_ground_mask] if data.colors is not None else None
    non_ground_labels = data.labels[non_ground_mask] if data.labels is not None else None
    non_ground_normals = data.normals[non_ground_mask] if data.normals is not None else None

    filtered_data = PointCloudData(
        non_ground_points, non_ground_colors, non_ground_labels, non_ground_normals
    )
    filtered_data.ground_removed = True
    filtered_data.height_normalized = data.height_normalized

    return filtered_data, ground_mask, non_ground_mask


def normalize_height(data: PointCloudData, ground_points: np.ndarray = None,
                     grid_size: float = 5.0) -> PointCloudData:
    points = data.points.copy()

    if ground_points is None:
        if data.ground_removed:
            raise ValueError("Ground points not provided and data has ground removed")
        _, ground_mask = simple_ground_filter(points, grid_size=grid_size)
        ground_points = points[ground_mask]

    if len(ground_points) < 3:
        print("Warning: insufficient ground points for height normalization")
        return data

    ground_tree = cKDTree(ground_points[:, :2])
    distances, indices = ground_tree.query(points[:, :2], k=min(5, len(ground_points)))

    weights = 1.0 / (distances + 1e-8)
    weights /= weights.sum(axis=1, keepdims=True)

    ground_z = (ground_points[indices, 2] * weights).sum(axis=1)
    normalized_z = points[:, 2] - ground_z
    points[:, 2] = normalized_z

    normalized_data = PointCloudData(
        points, data.colors, data.labels, data.normals
    )
    normalized_data.ground_removed = data.ground_removed
    normalized_data.height_normalized = True

    return normalized_data


def downsample(data: PointCloudData, voxel_size: float = 0.05) -> PointCloudData:
    pcd = data.to_open3d(use_labels=False)
    downsampled = pcd.voxel_down_sample(voxel_size=voxel_size)

    points = np.asarray(downsampled.points)
    colors = np.asarray(downsampled.colors) if downsampled.has_colors() else None

    if data.labels is not None:
        original_tree = cKDTree(data.points)
        _, indices = original_tree.query(points, k=1)
        labels = data.labels[indices]
    else:
        labels = None

    normals = np.asarray(downsampled.normals) if downsampled.has_normals() else None

    downsampled_data = PointCloudData(points, colors, labels, normals)
    downsampled_data.ground_removed = data.ground_removed
    downsampled_data.height_normalized = data.height_normalized

    return downsampled_data


def statistical_outlier_removal(data: PointCloudData, nb_neighbors: int = 20,
                                std_ratio: float = 2.0) -> PointCloudData:
    pcd = data.to_open3d(use_labels=False)
    _, inlier_indices = pcd.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio
    )

    points = data.points[inlier_indices]
    colors = data.colors[inlier_indices] if data.colors is not None else None
    labels = data.labels[inlier_indices] if data.labels is not None else None
    normals = data.normals[inlier_indices] if data.normals is not None else None

    filtered_data = PointCloudData(points, colors, labels, normals)
    filtered_data.ground_removed = data.ground_removed
    filtered_data.height_normalized = data.height_normalized

    return filtered_data


def preprocess_pipeline(data: PointCloudData,
                        downsample_voxel: float = 0.05,
                        ground_filter_method: str = 'csf',
                        normalize: bool = True,
                        normalize_density: bool = False,
                        density_method: str = 'adaptive',
                        **kwargs) -> PointCloudData:
    original_data = data

    if downsample_voxel > 0:
        data = downsample(data, voxel_size=downsample_voxel)

    ground_points = None
    if ground_filter_method is not None:
        filtered_data, ground_mask, _ = remove_ground(
            original_data if downsample_voxel > 0 else data,
            method=ground_filter_method,
            **kwargs
        )
        ground_points = original_data.points[ground_mask] if downsample_voxel > 0 else data.points[ground_mask]
        data = filtered_data

    if normalize:
        data = normalize_height(data, ground_points=ground_points)

    if normalize_density:
        from .enhancement import normalize_point_cloud_density
        data = normalize_point_cloud_density(data, method=density_method, **kwargs)

    return data
