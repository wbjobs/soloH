import numpy as np
from scipy.spatial import cKDTree, ConvexHull
from scipy.optimize import least_squares
from scipy.ndimage import binary_dilation, binary_erosion
from typing import Tuple, Optional, List, Dict
from .data_io import PointCloudData


# ============================================
# 1. 点云密度归一化 - 解决近密远疏问题
# ============================================

class DensityNormalizer:
    def __init__(self, target_density: float = None, k_neighbors: int = 10,
                 method: str = 'adaptive'):
        self.target_density = target_density
        self.k_neighbors = k_neighbors
        self.method = method

    def compute_point_density(self, points: np.ndarray, k: int = 10) -> np.ndarray:
        tree = cKDTree(points)
        distances, _ = tree.query(points, k=k + 1)
        avg_distances = np.mean(distances[:, 1:], axis=1)
        density = 1.0 / (avg_distances ** 3 + 1e-8)
        return density

    def compute_local_density(self, points: np.ndarray, radius: float = 1.0) -> np.ndarray:
        tree = cKDTree(points)
        counts = tree.query_ball_point(points, r=radius, return_length=True)
        volume = (4.0 / 3.0) * np.pi * (radius ** 3)
        density = counts / volume
        return density

    def normalize_density_voxel(self, points: np.ndarray, colors: Optional[np.ndarray] = None,
                                labels: Optional[np.ndarray] = None,
                                voxel_size: float = 0.1,
                                max_points_per_voxel: int = 5) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        if len(points) == 0:
            return points, colors, labels

        x_min, y_min, z_min = points.min(axis=0)
        x_max, y_max, z_max = points.max(axis=0)

        num_x = int(np.ceil((x_max - x_min) / voxel_size)) + 1
        num_y = int(np.ceil((y_max - y_min) / voxel_size)) + 1
        num_z = int(np.ceil((z_max - z_min) / voxel_size)) + 1

        grid_x = ((points[:, 0] - x_min) / voxel_size).astype(int)
        grid_y = ((points[:, 1] - y_min) / voxel_size).astype(int)
        grid_z = ((points[:, 2] - z_min) / voxel_size).astype(int)

        voxel_indices = grid_x * num_y * num_z + grid_y * num_z + grid_z

        unique_voxels, inverse_indices = np.unique(voxel_indices, return_inverse=True)

        sampled_indices = []
        for voxel_idx in range(len(unique_voxels)):
            voxel_mask = inverse_indices == voxel_idx
            voxel_point_indices = np.where(voxel_mask)[0]

            if len(voxel_point_indices) > max_points_per_voxel:
                selected = np.random.choice(voxel_point_indices, max_points_per_voxel, replace=False)
                sampled_indices.extend(selected)
            else:
                sampled_indices.extend(voxel_point_indices)

        sampled_indices = np.array(sorted(sampled_indices))

        new_points = points[sampled_indices]
        new_colors = colors[sampled_indices] if colors is not None else None
        new_labels = labels[sampled_indices] if labels is not None else None

        return new_points, new_colors, new_labels

    def normalize_density_adaptive(self, points: np.ndarray, colors: Optional[np.ndarray] = None,
                                   labels: Optional[np.ndarray] = None,
                                   k: int = 10,
                                   target_avg_distance: float = 0.05) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        if len(points) < k:
            return points, colors, labels

        tree = cKDTree(points)
        distances, _ = tree.query(points, k=k + 1)
        avg_distances = np.mean(distances[:, 1:], axis=1)

        density_weights = target_avg_distance / (avg_distances + 1e-8)
        density_weights = np.clip(density_weights, 0.1, 10.0)

        keep_probability = 1.0 / density_weights
        keep_probability = np.clip(keep_probability, 0.1, 1.0)

        random_values = np.random.random(len(points))
        keep_mask = random_values < keep_probability

        if keep_mask.sum() < 100:
            keep_mask[:] = True

        new_points = points[keep_mask]
        new_colors = colors[keep_mask] if colors is not None else None
        new_labels = labels[keep_mask] if labels is not None else None

        return new_points, new_colors, new_labels

    def normalize_density_distance_based(self, points: np.ndarray, colors: Optional[np.ndarray] = None,
                                         labels: Optional[np.ndarray] = None,
                                         sensor_position: Optional[np.ndarray] = None,
                                         max_density_factor: float = 3.0) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        if len(points) == 0:
            return points, colors, labels

        if sensor_position is None:
            sensor_position = np.array([0.0, 0.0, 0.0])

        distances_to_sensor = np.linalg.norm(points - sensor_position, axis=1)

        if len(distances_to_sensor) > 0:
            min_dist = distances_to_sensor.min()
            max_dist = distances_to_sensor.max()
            normalized_dist = (distances_to_sensor - min_dist) / (max_dist - min_dist + 1e-8)
            keep_probability = normalized_dist * (max_density_factor - 1.0) / max_density_factor + 1.0 / max_density_factor
        else:
            keep_probability = np.ones(len(points)) * 0.5

        random_values = np.random.random(len(points))
        keep_mask = random_values < keep_probability

        if keep_mask.sum() < 100:
            keep_mask[:] = True

        new_points = points[keep_mask]
        new_colors = colors[keep_mask] if colors is not None else None
        new_labels = labels[keep_mask] if labels is not None else None

        return new_points, new_colors, new_labels


def normalize_point_cloud_density(data: PointCloudData,
                                  method: str = 'voxel',
                                  **kwargs) -> PointCloudData:
    normalizer = DensityNormalizer()

    if method == 'voxel':
        points, colors, labels = normalizer.normalize_density_voxel(
            data.points, data.colors, data.labels,
            voxel_size=kwargs.get('voxel_size', 0.1),
            max_points_per_voxel=kwargs.get('max_points_per_voxel', 5)
        )
    elif method == 'adaptive':
        points, colors, labels = normalizer.normalize_density_adaptive(
            data.points, data.colors, data.labels,
            k=kwargs.get('k', 10),
            target_avg_distance=kwargs.get('target_avg_distance', 0.05)
        )
    elif method == 'distance':
        points, colors, labels = normalizer.normalize_density_distance_based(
            data.points, data.colors, data.labels,
            sensor_position=kwargs.get('sensor_position', None),
            max_density_factor=kwargs.get('max_density_factor', 3.0)
        )
    else:
        raise ValueError(f"Unknown density normalization method: {method}")

    normalized_data = PointCloudData(points, colors, labels, data.normals)
    normalized_data.ground_removed = data.ground_removed
    normalized_data.height_normalized = data.height_normalized

    return normalized_data


# ============================================
# 2. 多尺度几何特征提取 - 增强不同树种泛化能力
# ============================================

class GeometricFeatureExtractor:
    def __init__(self, radii: List[float] = None):
        if radii is None:
            self.radii = [0.1, 0.3, 0.5, 1.0]
        else:
            self.radii = radii

    def compute_eigenfeatures(self, points: np.ndarray, k: int = 10) -> np.ndarray:
        n = len(points)
        features = np.zeros((n, 11), dtype=np.float32)

        tree = cKDTree(points)

        for i in range(n):
            distances, indices = tree.query(points[i], k=k + 1)
            indices = indices[1:]
            neighborhood = points[indices]

            centered = neighborhood - np.mean(neighborhood, axis=0)
            cov_matrix = np.dot(centered.T, centered) / k
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]

            sum_eig = eigenvalues.sum() + 1e-8
            l1, l2, l3 = eigenvalues

            features[i, 0] = (l1 - l2) / sum_eig
            features[i, 1] = (l2 - l3) / sum_eig
            features[i, 2] = l3 / sum_eig
            features[i, 3] = l1 / (l3 + 1e-8)
            features[i, 4] = (l1 * l2 * l3) ** (1.0 / 3.0)
            features[i, 5] = np.sum(eigenvalues)

            normal = eigenvectors[:, 2]
            features[i, 6] = normal[0]
            features[i, 7] = normal[1]
            features[i, 8] = normal[2]

            z_values = neighborhood[:, 2]
            features[i, 9] = np.max(z_values) - np.min(z_values)
            features[i, 10] = np.std(z_values)

        return features

    def compute_multi_scale_features(self, points: np.ndarray) -> np.ndarray:
        n = len(points)
        all_features = []

        for radius in self.radii:
            features = self.compute_features_at_scale(points, radius)
            all_features.append(features)

        return np.concatenate(all_features, axis=1)

    def compute_features_at_scale(self, points: np.ndarray, radius: float) -> np.ndarray:
        n = len(points)
        features = np.zeros((n, 8), dtype=np.float32)

        tree = cKDTree(points)

        for i in range(n):
            indices = tree.query_ball_point(points[i], r=radius)
            if len(indices) < 5:
                features[i, :] = 0
                continue

            neighborhood = points[indices]

            centered = neighborhood - np.mean(neighborhood, axis=0)
            cov_matrix = np.dot(centered.T, centered) / len(indices)
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            sum_eig = eigenvalues.sum() + 1e-8

            linearity = (eigenvalues[0] - eigenvalues[1]) / sum_eig
            planarity = (eigenvalues[1] - eigenvalues[2]) / sum_eig
            sphericity = eigenvalues[2] / sum_eig
            omnivariance = np.prod(eigenvalues) ** (1.0 / 3.0)
            anisotropy = (eigenvalues[0] - eigenvalues[2]) / (eigenvalues[0] + 1e-8)
            eigenentropy = -np.sum((eigenvalues / sum_eig) * np.log(eigenvalues / sum_eig + 1e-8))

            normal = eigenvectors[:, 2]
            verticality = 1.0 - abs(normal[2])
            curvature = eigenvalues[2] / sum_eig

            features[i, 0] = linearity
            features[i, 1] = planarity
            features[i, 2] = sphericity
            features[i, 3] = omnivariance
            features[i, 4] = anisotropy
            features[i, 5] = eigenentropy
            features[i, 6] = verticality
            features[i, 7] = curvature

        return features

    def compute_shape_indices(self, points: np.ndarray, k: int = 20) -> np.ndarray:
        n = len(points)
        features = np.zeros((n, 5), dtype=np.float32)

        tree = cKDTree(points)

        for i in range(n):
            distances, indices = tree.query(points[i], k=k + 1)
            indices = indices[1:]
            neighborhood = points[indices]

            centered = neighborhood - np.mean(neighborhood, axis=0)
            cov_matrix = np.dot(centered.T, centered) / k
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
            idx = np.argsort(eigenvalues)[::-1]
            l1, l2, l3 = eigenvalues[idx]

            sum_eig = l1 + l2 + l3 + 1e-8

            features[i, 0] = (l1 - l2) / sum_eig
            features[i, 1] = (l2 - l3) / sum_eig
            features[i, 2] = l3 / sum_eig

            normal = eigenvectors[:, idx[2]]
            features[i, 3] = abs(normal[2])
            features[i, 4] = np.clip((l2 - l3) / (l1 + 1e-8), 0, 1)

        return features


def extract_geometric_features(data: PointCloudData,
                               use_multi_scale: bool = True,
                               radii: List[float] = None) -> np.ndarray:
    extractor = GeometricFeatureExtractor(radii=radii)

    if use_multi_scale:
        features = extractor.compute_multi_scale_features(data.points)
    else:
        features = extractor.compute_eigenfeatures(data.points)

    return features


# ============================================
# 3. 树干空心化补全算法
# ============================================

class TrunkCompletion:
    def __init__(self, min_height: float = 1.3, max_radius: float = 0.5,
                 fitting_method: str = 'cylinder'):
        self.min_height = min_height
        self.max_radius = max_radius
        self.fitting_method = fitting_method

    def fit_cylinder(self, points: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
        if len(points) < 5:
            return np.zeros(3), 0.1, np.array([0, 0, 1])

        centroid = np.mean(points, axis=0)

        centered = points - centroid
        cov_matrix = np.dot(centered.T, centered) / len(points)
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        axis_idx = np.argmax(eigenvalues)
        axis = eigenvectors[:, axis_idx]

        if axis[2] < 0:
            axis = -axis

        points_projected = points - np.outer(np.dot(points - centroid, axis), axis)
        distances = np.linalg.norm(points_projected - centroid, axis=1)
        radius = np.mean(distances)

        return centroid, radius, axis

    def cylinder_residuals(self, params, points):
        cx, cy, cz, axis_x, axis_y, axis_z, r = params
        axis = np.array([axis_x, axis_y, axis_z])
        axis = axis / np.linalg.norm(axis)
        center = np.array([cx, cy, cz])

        projections = points - center
        dot_product = np.dot(projections, axis)
        perpendicular = projections - np.outer(dot_product, axis)
        distances = np.linalg.norm(perpendicular, axis=1)

        return distances - r

    def fit_cylinder_optimized(self, points: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
        if len(points) < 10:
            return self.fit_cylinder(points)

        centroid_init, radius_init, axis_init = self.fit_cylinder(points)

        if radius_init > self.max_radius * 2:
            radius_init = self.max_radius

        params_init = [
            centroid_init[0], centroid_init[1], centroid_init[2],
            axis_init[0], axis_init[1], axis_init[2],
            radius_init
        ]

        try:
            result = least_squares(
                self.cylinder_residuals, params_init,
                args=(points,),
                bounds=(
                    [-np.inf, -np.inf, -np.inf, -1, -1, -1, 0.01],
                    [np.inf, np.inf, np.inf, 1, 1, 1, self.max_radius]
                ),
                max_nfev=100
            )

            params = result.x
            center = np.array([params[0], params[1], params[2]])
            axis = np.array([params[3], params[4], params[5]])
            axis = axis / np.linalg.norm(axis)
            radius = params[6]

            return center, radius, axis
        except:
            return centroid_init, radius_init, axis_init

    def generate_trunk_points(self, center: np.ndarray, axis: np.ndarray, radius: float,
                              z_min: float, z_max: float,
                              density: float = 500,
                              angular_resolution: int = 16) -> np.ndarray:
        if radius <= 0 or z_max <= z_min:
            return np.zeros((0, 3))

        height = z_max - z_min
        num_layers = int(height * density) + 2

        points = []
        for layer in range(num_layers):
            z = z_min + layer * height / (num_layers - 1)
            for angle in range(angular_resolution):
                theta = 2 * np.pi * angle / angular_resolution
                r = radius * np.sqrt(np.random.random())
                x = center[0] + r * np.cos(theta)
                y = center[1] + r * np.sin(theta)
                points.append([x, y, z])

        return np.array(points)

    def complete_trunk(self, data: PointCloudData) -> PointCloudData:
        if data.labels is None:
            return data

        trunk_mask = data.labels == 1
        trunk_points = data.points[trunk_mask]

        if len(trunk_points) < 10:
            return data

        z_min = trunk_points[:, 2].min()
        z_max = trunk_points[:, 2].max()
        height = z_max - z_min

        if height < self.min_height:
            return data

        center, radius, axis = self.fit_cylinder_optimized(trunk_points)
        print(f"  Fitted trunk: center=[{center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f}], radius={radius:.3f}m, height={height:.2f}m")

        fill_z_min = z_min
        fill_z_max = min(z_max, z_min + height * 0.8)

        completed_points = self.generate_trunk_points(
            center, axis, radius, fill_z_min, fill_z_max
        )

        if len(completed_points) == 0:
            return data

        existing_tree = cKDTree(trunk_points)
        distances, _ = existing_tree.query(completed_points, k=1)
        fill_mask = distances > radius * 0.3
        new_points = completed_points[fill_mask]

        if len(new_points) == 0:
            return data

        new_labels = np.ones(len(new_points), dtype=np.int32)

        if data.colors is not None:
            trunk_color = np.mean(data.colors[trunk_mask], axis=0)
            new_colors = np.tile(trunk_color, (len(new_points), 1))
        else:
            new_colors = None

        all_points = np.vstack([data.points, new_points])
        all_labels = np.hstack([data.labels, new_labels])
        all_colors = np.vstack([data.colors, new_colors]) if data.colors is not None else None

        completed_data = PointCloudData(all_points, all_colors, all_labels, data.normals)
        completed_data.ground_removed = data.ground_removed
        completed_data.height_normalized = data.height_normalized

        print(f"  Completed trunk: added {len(new_points)} points")

        return completed_data

    def morphological_fill(self, data: PointCloudData,
                           kernel_size: int = 3,
                           iterations: int = 2) -> PointCloudData:
        if data.labels is None:
            return data

        trunk_mask = data.labels == 1
        if not trunk_mask.any():
            return data

        points = data.points
        voxel_size = 0.05

        x_min, y_min, z_min = points.min(axis=0)
        x_max, y_max, z_max = points.max(axis=0)

        num_x = int(np.ceil((x_max - x_min) / voxel_size)) + 1
        num_y = int(np.ceil((y_max - y_min) / voxel_size)) + 1
        num_z = int(np.ceil((z_max - z_min) / voxel_size)) + 1

        grid_x = ((points[trunk_mask, 0] - x_min) / voxel_size).astype(int)
        grid_y = ((points[trunk_mask, 1] - y_min) / voxel_size).astype(int)
        grid_z = ((points[trunk_mask, 2] - z_min) / voxel_size).astype(int)

        grid = np.zeros((num_x, num_y, num_z), dtype=bool)
        grid[grid_x, grid_y, grid_z] = True

        kernel = np.ones((kernel_size, kernel_size, kernel_size), dtype=bool)

        for _ in range(iterations):
            grid = binary_dilation(grid, structure=kernel)

        for _ in range(iterations):
            grid = binary_erosion(grid, structure=kernel)

        filled_voxels = np.argwhere(grid)

        new_points = []
        for gx, gy, gz in filled_voxels:
            if not grid[gx, gy, gz]:
                continue

            x = x_min + (gx + 0.5) * voxel_size
            y = y_min + (gy + 0.5) * voxel_size
            z = z_min + (gz + 0.5) * voxel_size

            existing_tree = cKDTree(points[trunk_mask])
            dist, _ = existing_tree.query([x, y, z], k=1)
            if dist > voxel_size * 0.5:
                new_points.append([x, y, z])

        if len(new_points) == 0:
            return data

        new_points = np.array(new_points)
        new_labels = np.ones(len(new_points), dtype=np.int32)

        if data.colors is not None:
            trunk_color = np.mean(data.colors[trunk_mask], axis=0)
            new_colors = np.tile(trunk_color, (len(new_points), 1))
        else:
            new_colors = None

        all_points = np.vstack([data.points, new_points])
        all_labels = np.hstack([data.labels, new_labels])
        all_colors = np.vstack([data.colors, new_colors]) if data.colors is not None else None

        completed_data = PointCloudData(all_points, all_colors, all_labels, data.normals)
        completed_data.ground_removed = data.ground_removed
        completed_data.height_normalized = data.height_normalized

        print(f"  Morphological fill: added {len(new_points)} points")

        return completed_data


def complete_trunk_geometry(data: PointCloudData,
                            method: str = 'cylinder',
                            **kwargs) -> PointCloudData:
    completer = TrunkCompletion(
        min_height=kwargs.get('min_height', 1.3),
        max_radius=kwargs.get('max_radius', 0.5),
        fitting_method=method
    )

    if method == 'cylinder':
        return completer.complete_trunk(data)
    elif method == 'morphological':
        return completer.morphological_fill(
            data,
            kernel_size=kwargs.get('kernel_size', 3),
            iterations=kwargs.get('iterations', 2)
        )
    elif method == 'hybrid':
        data = completer.complete_trunk(data)
        return completer.morphological_fill(
            data,
            kernel_size=kwargs.get('kernel_size', 3),
            iterations=kwargs.get('iterations', 1)
        )
    else:
        raise ValueError(f"Unknown trunk completion method: {method}")


# ============================================
# 4. 综合增强处理入口
# ============================================

class PointCloudEnhancer:
    def __init__(self):
        self.density_normalizer = DensityNormalizer()
        self.feature_extractor = GeometricFeatureExtractor()
        self.trunk_completer = TrunkCompletion()

    def enhance_pipeline(self, data: PointCloudData,
                         normalize_density: bool = True,
                         density_method: str = 'adaptive',
                         extract_features: bool = True,
                         complete_trunk: bool = True,
                         trunk_method: str = 'cylinder',
                         **kwargs) -> Tuple[PointCloudData, Optional[np.ndarray]]:
        if normalize_density:
            print("  [Enhancement] Normalizing point cloud density...")
            data = normalize_point_cloud_density(data, method=density_method, **kwargs)
            print(f"    Normalized to {data.num_points} points")

        features = None
        if extract_features:
            print("  [Enhancement] Extracting multi-scale geometric features...")
            features = extract_geometric_features(data, **kwargs)
            print(f"    Extracted {features.shape[1]} features per point")

        if complete_trunk and data.labels is not None:
            print("  [Enhancement] Completing trunk geometry...")
            data = complete_trunk_geometry(data, method=trunk_method, **kwargs)

        return data, features


def enhance_point_cloud(data: PointCloudData, **kwargs) -> Tuple[PointCloudData, Optional[np.ndarray]]:
    enhancer = PointCloudEnhancer()
    return enhancer.enhance_pipeline(data, **kwargs)
