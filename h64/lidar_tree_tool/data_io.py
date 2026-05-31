import os
import numpy as np
import open3d as o3d
from typing import Tuple, Optional


class PointCloudData:
    def __init__(self, points: np.ndarray, colors: Optional[np.ndarray] = None,
                 labels: Optional[np.ndarray] = None, normals: Optional[np.ndarray] = None):
        self.points = points
        self.colors = colors
        self.labels = labels
        self.normals = normals
        self.height_normalized = False
        self.ground_removed = False

    @property
    def num_points(self) -> int:
        return len(self.points)

    def to_open3d(self, use_labels: bool = True) -> o3d.geometry.PointCloud:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(self.points)
        if self.colors is not None and not use_labels:
            pcd.colors = o3d.utility.Vector3dVector(self.colors)
        elif self.labels is not None and use_labels:
            pcd.colors = o3d.utility.Vector3dVector(label_to_color(self.labels))
        return pcd

    def save(self, filepath: str, save_labels: bool = True):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.ply':
            save_ply(filepath, self.points, self.colors, self.labels if save_labels else None)
        elif ext == '.las' or ext == '.laz':
            save_las(filepath, self.points, self.colors, self.labels if save_labels else None)
        else:
            raise ValueError(f"Unsupported file format: {ext}")


def load_ply(filepath: str) -> PointCloudData:
    try:
        from plyfile import PlyData, PlyElement
        plydata = PlyData.read(filepath)
        vertex = plydata['vertex']

        points = np.column_stack([vertex['x'], vertex['y'], vertex['z']])

        colors = None
        if all(attr in vertex.data.dtype.names for attr in ['red', 'green', 'blue']):
            r = vertex['red'].astype(np.float32)
            g = vertex['green'].astype(np.float32)
            b = vertex['blue'].astype(np.float32)
            if r.max() > 1.0:
                r /= 255.0
                g /= 255.0
                b /= 255.0
            colors = np.column_stack([r, g, b])

        labels = None
        if 'label' in vertex.data.dtype.names:
            labels = vertex['label'].astype(np.int32)
        elif 'class' in vertex.data.dtype.names:
            labels = vertex['class'].astype(np.int32)

        normals = None
        if all(attr in vertex.data.dtype.names for attr in ['nx', 'ny', 'nz']):
            normals = np.column_stack([vertex['nx'], vertex['ny'], vertex['nz']])

        return PointCloudData(points, colors, labels, normals)
    except Exception as e:
        pcd = o3d.io.read_point_cloud(filepath)
        points = np.asarray(pcd.points)
        colors = np.asarray(pcd.colors) if pcd.has_colors() else None
        normals = np.asarray(pcd.normals) if pcd.has_normals() else None
        return PointCloudData(points, colors, None, normals)


def load_las(filepath: str) -> PointCloudData:
    import laspy
    las = laspy.read(filepath)

    points = np.column_stack([las.x, las.y, las.z])

    colors = None
    if hasattr(las, 'red') and hasattr(las, 'green') and hasattr(las, 'blue'):
        r = las.red.astype(np.float32)
        g = las.green.astype(np.float32)
        b = las.blue.astype(np.float32)
        if r.max() > 1.0:
            r /= 65535.0 if r.max() > 255 else 255.0
            g /= 65535.0 if g.max() > 255 else 255.0
            b /= 65535.0 if b.max() > 255 else 255.0
        colors = np.column_stack([r, g, b])

    labels = None
    if hasattr(las, 'classification'):
        labels = las.classification.astype(np.int32)

    return PointCloudData(points, colors, labels)


def load_point_cloud(filepath: str) -> PointCloudData:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.ply':
        return load_ply(filepath)
    elif ext in ['.las', '.laz']:
        return load_las(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: .ply, .las, .laz")


def save_ply(filepath: str, points: np.ndarray, colors: Optional[np.ndarray] = None,
             labels: Optional[np.ndarray] = None):
    from plyfile import PlyData, PlyElement

    vertex_data = [
        ('x', points[:, 0]),
        ('y', points[:, 1]),
        ('z', points[:, 2]),
    ]

    if colors is not None:
        if colors.max() <= 1.0:
            colors = (colors * 255).astype(np.uint8)
        else:
            colors = colors.astype(np.uint8)
        vertex_data.extend([
            ('red', colors[:, 0]),
            ('green', colors[:, 1]),
            ('blue', colors[:, 2]),
        ])

    if labels is not None:
        vertex_data.append(('label', labels.astype(np.int32)))

    vertex = np.empty(len(points), dtype=[(name, type(data[0])) for name, data in vertex_data])
    for name, data in vertex_data:
        vertex[name] = data

    el = PlyElement.describe(vertex, 'vertex')
    PlyData([el], text=False).write(filepath)


def save_las(filepath: str, points: np.ndarray, colors: Optional[np.ndarray] = None,
             labels: Optional[np.ndarray] = None):
    import laspy

    las = laspy.create(point_format=7 if colors is not None else 0)
    las.x = points[:, 0]
    las.y = points[:, 1]
    las.z = points[:, 2]

    if colors is not None:
        if colors.max() <= 1.0:
            colors = (colors * 65535).astype(np.uint16)
        elif colors.max() <= 255:
            colors = (colors * 256).astype(np.uint16)
        else:
            colors = colors.astype(np.uint16)
        las.red = colors[:, 0]
        las.green = colors[:, 1]
        las.blue = colors[:, 2]

    if labels is not None:
        las.classification = labels.astype(np.uint8)

    las.write(filepath)


LABEL_NAMES = {
    0: 'ground',
    1: 'trunk',
    2: 'large_branch',
    3: 'small_branch',
    4: 'leaf',
}

LABEL_COLORS = np.array([
    [139, 69, 19],
    [160, 82, 45],
    [205, 133, 63],
    [222, 184, 135],
    [34, 139, 34],
], dtype=np.float32) / 255.0


def label_to_color(labels: np.ndarray) -> np.ndarray:
    colors = np.zeros((len(labels), 3), dtype=np.float32)
    for i in range(len(LABEL_COLORS)):
        mask = labels == i
        if mask.any():
            colors[mask] = LABEL_COLORS[i]
    return colors
