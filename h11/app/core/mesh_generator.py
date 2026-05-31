import numpy as np
import triangle as tr
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Scatterer:
    shape: str
    position: Tuple[float, float]
    size: float
    material: str


@dataclass
class UnitCell:
    size: Tuple[float, float]
    scatterers: List[Scatterer]
    background_material: str
    mesh_resolution: float = 0.1


def generate_unit_cell_geometry(unit_cell: UnitCell) -> Dict:
    lx, ly = unit_cell.size
    dx, dy = lx / 2, ly / 2

    outer_poly = np.array([
        [-dx, -dy], [dx, -dy], [dx, dy], [-dx, dy]
    ])

    segments = []
    holes = []
    regions = []
    vertices = outer_poly.tolist()

    for i in range(4):
        segments.append([i, (i + 1) % 4])

    seg_id = len(segments)
    vert_id = len(vertices)

    region_id = 0
    regions.append([0.0, 0.0, region_id, unit_cell.mesh_resolution])
    region_id += 1

    for scatterer in unit_cell.scatterers:
        cx, cy = scatterer.position
        size = scatterer.size

        if scatterer.shape.lower() == 'circle':
            n_pts = max(16, int(2 * np.pi * size / unit_cell.mesh_resolution))
            angles = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
            circle_pts = np.array([
                [cx + size * np.cos(a), cy + size * np.sin(a)]
                for a in angles
            ])
            vertices.extend(circle_pts.tolist())

            for i in range(n_pts):
                segments.append([vert_id + i, vert_id + (i + 1) % n_pts])
            vert_id += n_pts

            holes.append([cx, cy])

        elif scatterer.shape.lower() == 'square':
            half_size = size / 2
            square_pts = np.array([
                [cx - half_size, cy - half_size],
                [cx + half_size, cy - half_size],
                [cx + half_size, cy + half_size],
                [cx - half_size, cy + half_size]
            ])
            vertices.extend(square_pts.tolist())

            for i in range(4):
                segments.append([vert_id + i, vert_id + (i + 1) % 4])
            vert_id += 4

            holes.append([cx, cy])

    vertices = np.array(vertices)
    segments = np.array(segments)
    holes = np.array(holes) if holes else np.empty((0, 2))
    regions = np.array(regions)

    tri_input = {
        'vertices': vertices,
        'segments': segments,
    }
    if len(holes) > 0:
        tri_input['holes'] = holes

    return tri_input, vertices, segments, holes, regions


def generate_mesh(unit_cell: UnitCell) -> Dict:
    tri_input, vertices, segments, holes, regions = generate_unit_cell_geometry(unit_cell)

    tri_options = f'q20a{unit_cell.mesh_resolution ** 2}'
    mesh = tr.triangulate(tri_input, tri_options)

    mesh['materials'] = assign_material_properties(mesh, unit_cell)

    return mesh


def assign_material_properties(mesh: Dict, unit_cell: UnitCell) -> np.ndarray:
    points = mesh['vertices']
    triangles = mesh['triangles']

    centroids = np.mean(points[triangles], axis=1)

    material_ids = np.zeros(len(triangles), dtype=int)

    for i, centroid in enumerate(centroids):
        cx, cy = centroid
        material_id = 0
        for j, scatterer in enumerate(unit_cell.scatterers):
            scx, scy = scatterer.position
            size = scatterer.size
            if scatterer.shape.lower() == 'circle':
                dist = np.sqrt((cx - scx) ** 2 + (cy - scy) ** 2)
                if dist < size:
                    material_id = j + 1
                    break
            elif scatterer.shape.lower() == 'square':
                half_size = size / 2
                if (abs(cx - scx) < half_size and abs(cy - scy) < half_size):
                    material_id = j + 1
                    break
        material_ids[i] = material_id

    return material_ids


def get_boundary_nodes(mesh: Dict, unit_cell: UnitCell) -> Dict:
    lx, ly = unit_cell.size
    dx, dy = lx / 2, ly / 2
    points = mesh['vertices']

    tol = 1e-8

    left_nodes = np.where(np.abs(points[:, 0] + dx) < tol)[0]
    right_nodes = np.where(np.abs(points[:, 0] - dx) < tol)[0]
    bottom_nodes = np.where(np.abs(points[:, 1] + dy) < tol)[0]
    top_nodes = np.where(np.abs(points[:, 1] - dy) < tol)[0]

    left_sorted = left_nodes[np.argsort(points[left_nodes, 1])]
    right_sorted = right_nodes[np.argsort(points[right_nodes, 1])]
    bottom_sorted = bottom_nodes[np.argsort(points[bottom_nodes, 0])]
    top_sorted = top_nodes[np.argsort(points[top_nodes, 0])]

    paired_x = []
    for ln, rn in zip(left_sorted, right_sorted):
        if np.abs(points[ln, 1] - points[rn, 1]) < tol:
            paired_x.append((ln, rn))

    paired_y = []
    for bn, tn in zip(bottom_sorted, top_sorted):
        if np.abs(points[bn, 0] - points[tn, 0]) < tol:
            paired_y.append((bn, tn))

    interior_mask = np.ones(len(points), dtype=bool)
    for ln, rn in paired_x:
        interior_mask[rn] = False
    for bn, tn in paired_y:
        interior_mask[tn] = False

    interior_nodes = np.where(interior_mask)[0]

    return {
        'paired_x': paired_x,
        'paired_y': paired_y,
        'interior_nodes': interior_nodes,
        'left_nodes': left_sorted,
        'right_nodes': right_sorted,
        'bottom_nodes': bottom_sorted,
        'top_nodes': top_sorted
    }
