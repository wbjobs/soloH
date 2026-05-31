"""
Point Cloud Generation and PLY Export Module

Converts depth/disparity maps to 3D point clouds and exports to PLY format.
Supports RGB color mapping, confidence-based filtering, and normal estimation.
"""

import os
import numpy as np
import cv2
from tqdm import tqdm
from scipy.ndimage import sobel, gaussian_filter


class PointCloud:
    def __init__(self):
        self.points = None
        self.colors = None
        self.normals = None
        self.confidence = None

    def get_num_points(self):
        if self.points is not None:
            return self.points.shape[0]
        return 0

    def filter_by_confidence(self, threshold=0.3):
        if self.confidence is None:
            return

        valid = self.confidence > threshold
        self.points = self.points[valid]
        if self.colors is not None:
            self.colors = self.colors[valid]
        if self.normals is not None:
            self.normals = self.normals[valid]
        self.confidence = self.confidence[valid]

    def filter_by_depth(self, min_depth=0.1, max_depth=100.0):
        if self.points is None:
            return

        depth = self.points[:, 2]
        valid = (depth > min_depth) & (depth < max_depth)
        self.points = self.points[valid]
        if self.colors is not None:
            self.colors = self.colors[valid]
        if self.normals is not None:
            self.normals = self.normals[valid]
        if self.confidence is not None:
            self.confidence = self.confidence[valid]

    def transform(self, transform_matrix):
        if self.points is None:
            return

        ones = np.ones((self.points.shape[0], 1))
        points_hom = np.hstack([self.points, ones])
        points_transformed = (transform_matrix @ points_hom.T).T
        self.points = points_transformed[:, :3]

        if self.normals is not None:
            R = transform_matrix[:3, :3]
            self.normals = (R @ self.normals.T).T


def disparity_to_pointcloud(disparity_map, camera_params, rgb_image=None, 
                            confidence_map=None, occlusion_mask=None,
                            downsample=1):
    """
    Convert disparity map to 3D point cloud.
    
    Parameters:
        disparity_map: Disparity map [H, W]
        camera_params: CameraParameters object
        rgb_image: Optional RGB image for coloring [H, W, 3]
        confidence_map: Optional confidence map [H, W]
        occlusion_mask: Optional occlusion mask [H, W] (True = occluded)
        downsample: Downsampling factor
        
    Returns:
        PointCloud object
    """
    h, w = disparity_map.shape

    if camera_params.principal_point is not None:
        cx, cy = camera_params.principal_point
    else:
        cx, cy = w / 2, h / 2

    f = camera_params.focal_length
    B = camera_params.baseline

    if f is None or B is None:
        f = 100.0
        B = 0.5

    ys = np.arange(0, h, downsample)
    xs = np.arange(0, w, downsample)
    xv, yv = np.meshgrid(xs, ys)

    disp = disparity_map[::downsample, ::downsample]

    with np.errstate(divide='ignore', invalid='ignore'):
        depth = (f * B) / (disp + 1e-8)

    x = (xv - cx) * depth / f
    y = (yv - cy) * depth / f
    z = depth

    points = np.stack([x, y, z], axis=-1).reshape(-1, 3)

    pc = PointCloud()
    pc.points = points.astype(np.float32)

    if rgb_image is not None:
        if len(rgb_image.shape) == 3 and rgb_image.shape[2] == 3:
            rgb = rgb_image[::downsample, ::downsample, :3]
        else:
            rgb = np.stack([rgb_image[::downsample, ::downsample]] * 3, axis=-1)

        if rgb.max() <= 1.0:
            rgb = (rgb * 255).astype(np.uint8)
        else:
            rgb = rgb.astype(np.uint8)

        pc.colors = rgb.reshape(-1, 3)

    if confidence_map is not None:
        conf = confidence_map[::downsample, ::downsample]
        pc.confidence = conf.reshape(-1).astype(np.float32)

    if occlusion_mask is not None:
        occl = occlusion_mask[::downsample, ::downsample]
        valid = ~occl.reshape(-1)

        pc.points = pc.points[valid]
        if pc.colors is not None:
            pc.colors = pc.colors[valid]
        if pc.confidence is not None:
            pc.confidence = pc.confidence[valid]

    return pc


def estimate_normals(pointcloud, k_neighbors=9):
    """
    Estimate normals for point cloud using local plane fitting.
    
    Parameters:
        pointcloud: PointCloud object
        k_neighbors: Number of neighbors for plane fitting
        
    Returns:
        PointCloud object with normals
    """
    if pointcloud.points is None:
        return pointcloud

    points = pointcloud.points
    n_points = points.shape[0]

    normals = np.zeros((n_points, 3), dtype=np.float32)

    for i in tqdm(range(n_points), desc="Estimating normals"):
        p = points[i]

        diff = points - p
        dists = np.sum(diff ** 2, axis=1)
        idx = np.argsort(dists)[:k_neighbors]

        neighbors = points[idx]

        centered = neighbors - np.mean(neighbors, axis=0)

        cov = centered.T @ centered / (k_neighbors - 1)

        eigenvalues, eigenvectors = np.linalg.eigh(cov)

        normal = eigenvectors[:, 0]

        if normal[2] > 0:
            normal = -normal

        normals[i] = normal

    pointcloud.normals = normals
    return pointcloud


def save_ply(pointcloud, file_path, use_ascii=False, include_normals=False):
    """
    Save point cloud to PLY file.
    
    Parameters:
        pointcloud: PointCloud object
        file_path: Output path
        use_ascii: If True, save in ASCII format (default: binary)
        include_normals: Include normal vectors in output
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    n_points = pointcloud.get_num_points()
    if n_points == 0:
        raise ValueError("Point cloud is empty")

    has_colors = pointcloud.colors is not None and pointcloud.colors.shape[0] == n_points
    has_normals = include_normals and pointcloud.normals is not None and pointcloud.normals.shape[0] == n_points
    has_confidence = pointcloud.confidence is not None and pointcloud.confidence.shape[0] == n_points

    with open(file_path, 'wb') as f:
        header = "ply\n"
        if use_ascii:
            header += "format ascii 1.0\n"
        else:
            header += "format binary_little_endian 1.0\n"
        header += f"element vertex {n_points}\n"
        header += "property float x\n"
        header += "property float y\n"
        header += "property float z\n"
        if has_normals:
            header += "property float nx\n"
            header += "property float ny\n"
            header += "property float nz\n"
        if has_colors:
            header += "property uchar red\n"
            header += "property uchar green\n"
            header += "property uchar blue\n"
        if has_confidence:
            header += "property float confidence\n"
        header += "end_header\n"

        f.write(header.encode('utf-8'))

        if use_ascii:
            for i in range(n_points):
                line = f"{pointcloud.points[i, 0]:.6f} {pointcloud.points[i, 1]:.6f} {pointcloud.points[i, 2]:.6f}"
                if has_normals:
                    line += f" {pointcloud.normals[i, 0]:.6f} {pointcloud.normals[i, 1]:.6f} {pointcloud.normals[i, 2]:.6f}"
                if has_colors:
                    line += f" {pointcloud.colors[i, 0]} {pointcloud.colors[i, 1]} {pointcloud.colors[i, 2]}"
                if has_confidence:
                    line += f" {pointcloud.confidence[i]:.6f}"
                line += "\n"
                f.write(line.encode('utf-8'))
        else:
            for i in range(n_points):
                f.write(pointcloud.points[i].astype(np.float32).tobytes())
                if has_normals:
                    f.write(pointcloud.normals[i].astype(np.float32).tobytes())
                if has_colors:
                    f.write(pointcloud.colors[i].astype(np.uint8).tobytes())
                if has_confidence:
                    f.write(np.array([pointcloud.confidence[i]], dtype=np.float32).tobytes())


def load_ply(file_path):
    """
    Load point cloud from PLY file.
    
    Parameters:
        file_path: Path to PLY file
        
    Returns:
        PointCloud object
    """
    with open(file_path, 'rb') as f:
        header_lines = []
        while True:
            line = f.readline()
            if not line:
                break
            try:
                line_str = line.decode('utf-8').strip()
            except:
                line_str = line.decode('latin-1').strip()
            header_lines.append(line_str)
            if line_str == 'end_header':
                break

        format_type = 'ascii'
        n_points = 0
        properties = []

        for line in header_lines:
            if line.startswith('format'):
                if 'binary' in line.lower():
                    format_type = 'binary'
            elif line.startswith('element vertex'):
                n_points = int(line.split()[-1])
            elif line.startswith('property'):
                parts = line.split()
                prop_type = parts[1]
                prop_name = parts[2]
                properties.append((prop_type, prop_name))

        pc = PointCloud()

        if n_points == 0:
            return pc

        points = []
        colors = []
        normals = []
        confidence = []

        has_x = any(p[1] == 'x' for p in properties)
        has_y = any(p[1] == 'y' for p in properties)
        has_z = any(p[1] == 'z' for p in properties)
        has_nx = any(p[1] == 'nx' for p in properties)
        has_ny = any(p[1] == 'ny' for p in properties)
        has_nz = any(p[1] == 'nz' for p in properties)
        has_r = any(p[1] == 'red' for p in properties)
        has_g = any(p[1] == 'green' for p in properties)
        has_b = any(p[1] == 'blue' for p in properties)
        has_conf = any(p[1] == 'confidence' for p in properties)

        if format_type == 'ascii':
            for _ in tqdm(range(n_points), desc="Loading PLY"):
                line = f.readline().decode('utf-8').strip().split()
                vals = {p[1]: line[i] for i, p in enumerate(properties)}

                if has_x and has_y and has_z:
                    points.append([float(vals['x']), float(vals['y']), float(vals['z'])])
                if has_nx and has_ny and has_nz:
                    normals.append([float(vals['nx']), float(vals['ny']), float(vals['nz'])])
                if has_r and has_g and has_b:
                    colors.append([int(vals['red']), int(vals['green']), int(vals['blue'])])
                if has_conf:
                    confidence.append(float(vals['confidence']))
        else:
            for _ in tqdm(range(n_points), desc="Loading PLY"):
                for prop_type, prop_name in properties:
                    if prop_type == 'float':
                        val = np.frombuffer(f.read(4), dtype=np.float32)[0]
                    elif prop_type in ['uchar', 'uint8']:
                        val = np.frombuffer(f.read(1), dtype=np.uint8)[0]
                    else:
                        val = np.frombuffer(f.read(4), dtype=np.int32)[0]

                    if prop_name == 'x':
                        px = val
                    elif prop_name == 'y':
                        py = val
                    elif prop_name == 'z':
                        pz = val
                    elif prop_name == 'nx':
                        nx = val
                    elif prop_name == 'ny':
                        ny = val
                    elif prop_name == 'nz':
                        nz = val
                    elif prop_name == 'red':
                        r = val
                    elif prop_name == 'green':
                        g = val
                    elif prop_name == 'blue':
                        b = val
                    elif prop_name == 'confidence':
                        conf = val

                if has_x and has_y and has_z:
                    points.append([px, py, pz])
                if has_nx and has_ny and has_nz:
                    normals.append([nx, ny, nz])
                if has_r and has_g and has_b:
                    colors.append([r, g, b])
                if has_conf:
                    confidence.append(conf)

    if points:
        pc.points = np.array(points, dtype=np.float32)
    if colors:
        pc.colors = np.array(colors, dtype=np.uint8)
    if normals:
        pc.normals = np.array(normals, dtype=np.float32)
    if confidence:
        pc.confidence = np.array(confidence, dtype=np.float32)

    return pc


def downsample_pointcloud(pointcloud, voxel_size=0.01):
    """
    Voxel grid downsampling of point cloud.
    
    Parameters:
        pointcloud: PointCloud object
        voxel_size: Voxel grid size
        
    Returns:
        Downsampled PointCloud object
    """
    if pointcloud.points is None:
        return pointcloud

    points = pointcloud.points
    n_points = points.shape[0]

    voxel_indices = np.floor(points / voxel_size).astype(np.int64)

    voxel_dict = {}
    for i in range(n_points):
        key = tuple(voxel_indices[i])
        if key not in voxel_dict:
            voxel_dict[key] = []
        voxel_dict[key].append(i)

    sampled_points = []
    sampled_colors = []
    sampled_normals = []
    sampled_confidence = []

    has_colors = pointcloud.colors is not None
    has_normals = pointcloud.normals is not None
    has_confidence = pointcloud.confidence is not None

    for key, indices in voxel_dict.items():
        center_idx = indices[len(indices) // 2]
        sampled_points.append(points[center_idx])
        if has_colors:
            sampled_colors.append(pointcloud.colors[center_idx])
        if has_normals:
            sampled_normals.append(pointcloud.normals[center_idx])
        if has_confidence:
            sampled_confidence.append(pointcloud.confidence[center_idx])

    pc = PointCloud()
    pc.points = np.array(sampled_points, dtype=np.float32)
    if sampled_colors:
        pc.colors = np.array(sampled_colors, dtype=np.uint8)
    if sampled_normals:
        pc.normals = np.array(sampled_normals, dtype=np.float32)
    if sampled_confidence:
        pc.confidence = np.array(sampled_confidence, dtype=np.float32)

    return pc


def depth_map_to_pointcloud(depth_map, camera_params, rgb_image=None,
                            confidence_map=None, occlusion_mask=None,
                            downsample=1):
    """
    Convert depth map directly to point cloud (without disparity conversion).
    
    Parameters:
        depth_map: Depth map [H, W]
        camera_params: CameraParameters object
        rgb_image: Optional RGB image [H, W, 3]
        confidence_map: Optional confidence map [H, W]
        occlusion_mask: Optional occlusion mask [H, W]
        downsample: Downsampling factor
        
    Returns:
        PointCloud object
    """
    h, w = depth_map.shape

    if camera_params.principal_point is not None:
        cx, cy = camera_params.principal_point
    else:
        cx, cy = w / 2, h / 2

    f = camera_params.focal_length if camera_params.focal_length is not None else 100.0

    ys = np.arange(0, h, downsample)
    xs = np.arange(0, w, downsample)
    xv, yv = np.meshgrid(xs, ys)

    depth = depth_map[::downsample, ::downsample]

    x = (xv - cx) * depth / f
    y = (yv - cy) * depth / f
    z = depth

    points = np.stack([x, y, z], axis=-1).reshape(-1, 3)

    pc = PointCloud()
    pc.points = points.astype(np.float32)

    if rgb_image is not None:
        if len(rgb_image.shape) == 3 and rgb_image.shape[2] == 3:
            rgb = rgb_image[::downsample, ::downsample, :3]
        else:
            rgb = np.stack([rgb_image[::downsample, ::downsample]] * 3, axis=-1)

        if rgb.max() <= 1.0:
            rgb = (rgb * 255).astype(np.uint8)
        else:
            rgb = rgb.astype(np.uint8)

        pc.colors = rgb.reshape(-1, 3)

    if confidence_map is not None:
        conf = confidence_map[::downsample, ::downsample]
        pc.confidence = conf.reshape(-1).astype(np.float32)

    if occlusion_mask is not None:
        occl = occlusion_mask[::downsample, ::downsample]
        valid = ~occl.reshape(-1)

        pc.points = pc.points[valid]
        if pc.colors is not None:
            pc.colors = pc.colors[valid]
        if pc.confidence is not None:
            pc.confidence = pc.confidence[valid]

    return pc
