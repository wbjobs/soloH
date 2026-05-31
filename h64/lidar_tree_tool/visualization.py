import numpy as np
import open3d as o3d
from typing import Optional, List, Tuple, Dict
from .data_io import PointCloudData, LABEL_COLORS, LABEL_NAMES


def create_colored_point_cloud(points: np.ndarray, labels: np.ndarray,
                               leaf_alpha: float = 0.5,
                               colors: Optional[np.ndarray] = None,
                               use_original_colors: bool = False) -> o3d.geometry.PointCloud:
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    if use_original_colors and colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(colors)
    else:
        point_colors = np.zeros((len(points), 3), dtype=np.float32)
        for i in range(len(LABEL_COLORS)):
            mask = labels == i
            if mask.any():
                point_colors[mask] = LABEL_COLORS[i]

        if leaf_alpha < 1.0:
            leaf_mask = labels == 4
            if leaf_mask.any():
                background_color = np.array([1.0, 1.0, 1.0])
                leaf_colors = point_colors[leaf_mask]
                blended = leaf_alpha * leaf_colors + (1 - leaf_alpha) * background_color
                point_colors[leaf_mask] = blended

        pcd.colors = o3d.utility.Vector3dVector(point_colors)

    return pcd


def create_instance_colored_point_cloud(points: np.ndarray,
                                        instance_labels: np.ndarray,
                                        seg_labels: Optional[np.ndarray] = None) -> o3d.geometry.PointCloud:
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    num_instances = len(np.unique(instance_labels[instance_labels > 0]))

    instance_colors = np.random.rand(max(num_instances + 1, 10), 3)
    instance_colors[0] = [0.8, 0.8, 0.8]

    point_colors = np.zeros((len(points), 3), dtype=np.float32)
    unique_instances = np.unique(instance_labels)

    for inst_id in unique_instances:
        mask = instance_labels == inst_id
        if mask.any():
            color_idx = int(inst_id) % len(instance_colors)
            point_colors[mask] = instance_colors[color_idx]

    if seg_labels is not None:
        leaf_mask = seg_labels == 4
        if leaf_mask.any():
            point_colors[leaf_mask] *= 0.8 + 0.2 * np.array([0.3, 0.8, 0.3])

    pcd.colors = o3d.utility.Vector3dVector(point_colors)
    return pcd


def visualize_segmentation(data: PointCloudData,
                           leaf_alpha: float = 0.5,
                           use_original_colors: bool = False,
                           window_name: str = "Segmentation Result",
                           show_ground: bool = True) -> None:
    if not show_ground and data.labels is not None:
        non_ground_mask = data.labels > 0
        points = data.points[non_ground_mask]
        labels = data.labels[non_ground_mask]
        colors = data.colors[non_ground_mask] if data.colors is not None else None
    else:
        points = data.points
        labels = data.labels
        colors = data.colors

    if labels is None:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        if colors is not None and use_original_colors:
            pcd.colors = o3d.utility.Vector3dVector(colors)
        o3d.visualization.draw_geometries([pcd], window_name=window_name)
        return

    pcd = create_colored_point_cloud(points, labels, leaf_alpha, colors, use_original_colors)

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=window_name, width=1200, height=800)
    vis.add_geometry(pcd)

    opt = vis.get_render_option()
    opt.background_color = np.array([0.1, 0.1, 0.1])
    opt.point_size = 2.0

    vis.run()
    vis.destroy_window()


def visualize_instances(data: PointCloudData,
                        instance_labels: np.ndarray,
                        window_name: str = "Individual Trees") -> None:
    pcd = create_instance_colored_point_cloud(data.points, instance_labels, data.labels)

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=window_name, width=1200, height=800)
    vis.add_geometry(pcd)

    opt = vis.get_render_option()
    opt.background_color = np.array([0.1, 0.1, 0.1])
    opt.point_size = 2.0

    vis.run()
    vis.destroy_window()


def visualize_comparison(original_data: PointCloudData,
                         processed_data: PointCloudData,
                         window_name: str = "Comparison") -> None:
    original_pcd = o3d.geometry.PointCloud()
    original_pcd.points = o3d.utility.Vector3dVector(original_data.points)
    if original_data.colors is not None:
        original_pcd.colors = o3d.utility.Vector3dVector(original_data.colors)

    if processed_data.labels is not None:
        processed_pcd = create_colored_point_cloud(
            processed_data.points, processed_data.labels
        )
    else:
        processed_pcd = o3d.geometry.PointCloud()
        processed_pcd.points = o3d.utility.Vector3dVector(processed_data.points)
        if processed_data.colors is not None:
            processed_pcd.colors = o3d.utility.Vector3dVector(processed_data.colors)

    offset = original_data.points[:, 0].max() - original_data.points[:, 0].min() + 2.0
    processed_pcd.translate([offset, 0, 0])

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=window_name, width=1600, height=800)
    vis.add_geometry(original_pcd)
    vis.add_geometry(processed_pcd)

    opt = vis.get_render_option()
    opt.background_color = np.array([0.1, 0.1, 0.1])
    opt.point_size = 2.0

    vis.run()
    vis.destroy_window()


def create_legend() -> Dict[str, np.ndarray]:
    legend = {}
    for label_id, label_name in LABEL_NAMES.items():
        legend[label_name] = LABEL_COLORS[label_id]
    return legend


def save_visualization(data: PointCloudData,
                       filepath: str,
                       leaf_alpha: float = 0.5,
                       use_original_colors: bool = False) -> None:
    if data.labels is None:
        pcd = data.to_open3d(use_labels=False)
        o3d.io.write_point_cloud(filepath, pcd)
        return

    pcd = create_colored_point_cloud(
        data.points, data.labels, leaf_alpha, data.colors, use_original_colors
    )
    o3d.io.write_point_cloud(filepath, pcd)


def render_to_image(data: PointCloudData,
                    filepath: str,
                    leaf_alpha: float = 0.5,
                    use_original_colors: bool = False,
                    width: int = 1920,
                    height: int = 1080,
                    show_ground: bool = True) -> None:
    if not show_ground and data.labels is not None:
        non_ground_mask = data.labels > 0
        points = data.points[non_ground_mask]
        labels = data.labels[non_ground_mask]
        colors = data.colors[non_ground_mask] if data.colors is not None else None
    else:
        points = data.points
        labels = data.labels
        colors = data.colors

    if labels is not None:
        pcd = create_colored_point_cloud(points, labels, leaf_alpha, colors, use_original_colors)
    else:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        if colors is not None and use_original_colors:
            pcd.colors = o3d.utility.Vector3dVector(colors)

    vis = o3d.visualization.Visualizer()
    vis.create_window(width=width, height=height, visible=False)
    vis.add_geometry(pcd)

    opt = vis.get_render_option()
    opt.background_color = np.array([0.1, 0.1, 0.1])
    opt.point_size = 2.0
    opt.show_coordinate_frame = True

    ctr = vis.get_view_control()
    ctr.set_front([0, -1, 0.5])
    ctr.set_up([0, 0, 1])
    ctr.set_zoom(0.8)

    vis.poll_events()
    vis.update_renderer()
    vis.capture_screen_image(filepath)
    vis.destroy_window()
