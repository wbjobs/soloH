"""
遮挡分析模块
Occlusion Analysis Module

功能：
- 卫星本体几何建模 (长方体、圆柱体等)
- 天线几何建模
- 太阳能帆板遮挡计算
- 光线追踪与遮挡因子计算
- 坐标系转换 (ECI -> 卫星本体坐标系)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union
import numpy as np
from enum import Enum


class GeometryType(Enum):
    """几何体类型枚举"""
    BOX = "box"
    CYLINDER = "cylinder"
    SPHERE = "sphere"
    POLYGON = "polygon"


@dataclass
class GeometryObject:
    """几何对象基类"""
    name: str
    geometry_type: GeometryType
    position: np.ndarray  # 位置 (本体坐标系, m)
    orientation: np.ndarray  # 欧拉角 (x, y, z), rad
    dimensions: np.ndarray  # 尺寸参数 (m)

    def get_rotation_matrix(self) -> np.ndarray:
        """获取旋转矩阵 (ZYX顺序)"""
        rx, ry, rz = self.orientation
        
        R_x = np.array([
            [1, 0, 0],
            [0, np.cos(rx), -np.sin(rx)],
            [0, np.sin(rx), np.cos(rx)]
        ])
        
        R_y = np.array([
            [np.cos(ry), 0, np.sin(ry)],
            [0, 1, 0],
            [-np.sin(ry), 0, np.cos(ry)]
        ])
        
        R_z = np.array([
            [np.cos(rz), -np.sin(rz), 0],
            [np.sin(rz), np.cos(rz), 0],
            [0, 0, 1]
        ])
        
        return R_z @ R_y @ R_x


@dataclass
class SolarArray:
    """太阳能帆板模型"""
    name: str
    position: np.ndarray  # 帆板中心位置 (本体坐标系, m)
    normal: np.ndarray  # 帆板法向量 (本体坐标系, 单位矢量)
    size: Tuple[float, float]  # (宽度, 高度), m
    n_cells: int = 100  # 电池片数量
    cell_area: float = 0.0225  # 单电池片面积 (m^2)

    @property
    def total_area(self) -> float:
        """帆板总面积"""
        return self.size[0] * self.size[1]

    @property
    def x_axis(self) -> np.ndarray:
        """帆板局部x轴"""
        z = self.normal
        if abs(z[2]) < 0.9:
            x = np.cross(np.array([0, 0, 1]), z)
        else:
            x = np.cross(np.array([1, 0, 0]), z)
        return x / np.linalg.norm(x)

    @property
    def y_axis(self) -> np.ndarray:
        """帆板局部y轴"""
        return np.cross(self.normal, self.x_axis)


@dataclass
class OcclusionResult:
    """遮挡计算结果"""
    occlusion_factor: float  # 遮挡因子: 0=无遮挡, 1=完全遮挡
    visible_area_ratio: float  # 可见面积比例
    blocked_cells: List[bool]  # 各电池片是否被遮挡
    shadow_map: np.ndarray  # 阴影图 (2D数组)


class ShadowCalculator:
    """
    阴影计算器
    计算卫星本体和天线对太阳能帆板的遮挡
    """

    def __init__(self, 
                 solar_array: SolarArray,
                 occlusion_objects: List[GeometryObject] = None):
        """
        初始化阴影计算器
        
        参数:
            solar_array: 太阳能帆板模型
            occlusion_objects: 可能造成遮挡的物体列表
        """
        self.solar_array = solar_array
        self.occlusion_objects = occlusion_objects or []
        self._grid_resolution = 50  # 阴影图网格分辨率

    def add_occlusion_object(self, obj: GeometryObject):
        """添加遮挡物体"""
        self.occlusion_objects.append(obj)

    def set_grid_resolution(self, resolution: int):
        """设置阴影图网格分辨率"""
        self._grid_resolution = resolution

    def _ray_plane_intersection(self, 
                                 ray_origin: np.ndarray, 
                                 ray_dir: np.ndarray,
                                 plane_point: np.ndarray, 
                                 plane_normal: np.ndarray) -> Tuple[bool, float]:
        """
        计算射线与平面的交点
        
        返回:
            (是否相交, 交点距离)
        """
        denom = np.dot(ray_dir, plane_normal)
        if abs(denom) < 1e-10:
            return False, 0.0
        
        t = np.dot(plane_point - ray_origin, plane_normal) / denom
        if t < 1e-10:
            return False, 0.0
        
        return True, t

    def _point_in_box(self, 
                      point: np.ndarray, 
                      box_obj: GeometryObject) -> bool:
        """
        判断点是否在长方体内
        """
        R = box_obj.get_rotation_matrix()
        local_point = R.T @ (point - box_obj.position)
        w, h, d = box_obj.dimensions
        
        return (abs(local_point[0]) <= w / 2 and
                abs(local_point[1]) <= h / 2 and
                abs(local_point[2]) <= d / 2)

    def _ray_box_intersection(self, 
                               ray_origin: np.ndarray, 
                               ray_dir: np.ndarray,
                               box_obj: GeometryObject) -> Tuple[bool, float]:
        """
        射线与长方体相交检测 (改进的Slab方法)
        修复旋转关节等薄结构的边界条件处理问题
        """
        R = box_obj.get_rotation_matrix()
        local_origin = R.T @ (ray_origin - box_obj.position)
        local_dir = R.T @ ray_dir
        w, h, d = box_obj.dimensions
        
        # 自适应数值容差: 根据薄尺寸调整
        min_dim = min(w, h, d)
        eps = max(1e-12, 1e-10 * min_dim)  # 自适应epsilon
        
        t_min = float('-inf')
        t_max = float('inf')
        
        for i, extent in enumerate([w/2, h/2, d/2]):
            dir_i = local_dir[i]
            origin_i = local_origin[i]
            
            if abs(dir_i) < eps:
                # 射线几乎平行于该面, 检查是否在内部
                if origin_i < -extent - eps or origin_i > extent + eps:
                    return False, 0.0
            else:
                t1 = (-extent - origin_i) / dir_i
                t2 = (extent - origin_i) / dir_i
                if t1 > t2:
                    t1, t2 = t2, t1
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                
                # 边界条件处理: 处理薄结构的数值问题
                if t_min > t_max + eps:
                    # 检查是否是由于数值误差导致的伪相交失败
                    # 执行边缘和顶点的精确检测
                    if self._check_box_edge_intersection(local_origin, local_dir, w, h, d, eps):
                        # 返回一个合理的相交距离
                        return True, max(eps, t_min)
                    return False, 0.0
        
        # 检查射线起点是否在盒子内部
        if (abs(local_origin[0]) <= w/2 + eps and
            abs(local_origin[1]) <= h/2 + eps and
            abs(local_origin[2]) <= d/2 + eps):
            # 射线从内部发出, 返回第一个出射点
            if t_max > eps:
                return True, t_max
        
        if t_min < eps:
            t_min = t_max
            if t_min < eps:
                # 再次检查边缘相交
                if self._check_box_edge_intersection(local_origin, local_dir, w, h, d, eps):
                    return True, eps * 10
                return False, 0.0
        
        return True, t_min
    
    def _check_box_edge_intersection(self, 
                                    origin: np.ndarray, 
                                    direction: np.ndarray,
                                    w: float, h: float, d: float,
                                    eps: float) -> bool:
        """
        检查射线与长方体边缘和顶点的相交 (针对薄结构的精确检测)
        """
        # 生成长方体的12条边
        hw, hh, hd = w/2, h/2, d/2
        vertices = np.array([
            [-hw, -hh, -hd], [hw, -hh, -hd], [hw, hh, -hd], [-hw, hh, -hd],
            [-hw, -hh, hd], [hw, -hh, hd], [hw, hh, hd], [-hw, hh, hd]
        ])
        
        # 12条边的顶点索引
        edges = [
            (0,1), (1,2), (2,3), (3,0),  # 底面
            (4,5), (5,6), (6,7), (7,4),  # 顶面
            (0,4), (1,5), (2,6), (3,7)   # 侧面连接
        ]
        
        # 使用更合理的容差：基于物体大小的相对容差
        # 对于薄结构，使用最大尺寸的1e-4作为容差
        max_dim = max(w, h, d)
        edge_tol = max(1e-6, 1e-4 * max_dim)
        
        for v1_idx, v2_idx in edges:
            v1 = vertices[v1_idx]
            v2 = vertices[v2_idx]
            
            # 检查射线与线段的最近距离
            dist, t = self._ray_segment_distance(origin, direction, v1, v2, eps)
            if dist < edge_tol and t > 0:
                return True
        
        # 检查顶点附近
        for v in vertices:
            dist = np.linalg.norm(np.cross(direction, v - origin))
            if dist < edge_tol:
                t = np.dot(v - origin, direction)
                if t > 0:
                    return True
        
        return False
    
    def _ray_segment_distance(self, 
                              ro: np.ndarray, 
                              rd: np.ndarray, 
                              v1: np.ndarray, 
                              v2: np.ndarray,
                              eps: float = 1e-12) -> Tuple[float, float]:
        """
        计算射线与线段之间的最小距离
        
        返回:
            (distance, t): 最小距离和对应的射线参数t
        """
        v = v2 - v1
        w = ro - v1
        
        a = np.dot(rd, rd)
        b = np.dot(rd, v)
        c = np.dot(v, v)
        d = np.dot(rd, w)
        e = np.dot(v, w)
        
        denom = a * c - b * b
        if abs(denom) < 1e-12:
            # 平行情况 - 检查线段上最近点
            t_proj = np.dot(-w, rd) / max(a, eps)
            t = max(0.0, t_proj)
            # 线段上最近点
            s_proj = np.dot(w + t * rd, v) / max(c, eps)
            s = max(0.0, min(1.0, s_proj))
            diff = (v1 + s * v) - (ro + t * rd)
            return np.linalg.norm(diff), t
        
        s = (b * e - c * d) / denom
        t = (a * e - b * d) / denom
        
        # 限制在线段和射线范围内
        s = max(0.0, min(1.0, s))
        t = max(0.0, t)
        
        diff = (v1 + s * v) - (ro + t * rd)
        return np.linalg.norm(diff), t

    def _ray_cylinder_intersection(self,
                                    ray_origin: np.ndarray,
                                    ray_dir: np.ndarray,
                                    cyl_obj: GeometryObject) -> Tuple[bool, float]:
        """
        射线与圆柱体相交检测
        圆柱体假设沿y轴方向
        修复薄圆柱（旋转关节）的边界条件处理
        """
        R = cyl_obj.get_rotation_matrix()
        local_origin = R.T @ (ray_origin - cyl_obj.position)
        local_dir = R.T @ ray_dir
        
        radius, height, _ = cyl_obj.dimensions
        
        # 自适应数值容差，针对薄圆柱/旋转关节
        min_dim = min(radius, height)
        eps = max(1e-12, 1e-10 * min_dim)
        
        # 检测与圆柱侧面的相交
        ox, oy, oz = local_origin
        dx, dy, dz = local_dir
        
        a = dx ** 2 + dz ** 2
        b = 2 * (ox * dx + oz * dz)
        c = ox ** 2 + oz ** 2 - radius ** 2
        
        # 检查是否在圆柱内部
        inside_radius = (ox ** 2 + oz ** 2) <= (radius + eps) ** 2
        inside_height = abs(oy) <= height / 2 + eps
        
        valid_ts = []
        
        if a > eps:
            discriminant = b ** 2 - 4 * a * c
            if discriminant >= -eps:
                discriminant = max(0.0, discriminant)
                sqrt_disc = np.sqrt(discriminant)
                t1 = (-b - sqrt_disc) / (2 * a)
                t2 = (-b + sqrt_disc) / (2 * a)
                
                # 检查是否在高度范围内，带边界容差
                for t in [t1, t2]:
                    if t > -eps:
                        y = oy + dy * t
                        if abs(y) <= height / 2 + eps:
                            t_clamped = max(eps, t)
                            valid_ts.append(t_clamped)
        
        # 检查与上下底面的相交 (针对薄圆柱改进)
        for y_plane in [-height/2, height/2]:
            if abs(dy) > eps:
                t = (y_plane - oy) / dy
                if t > -eps:
                    x = ox + dx * t
                    z = oz + dz * t
                    # 带容差的边界检查
                    if x ** 2 + z ** 2 <= (radius + eps) ** 2:
                        t_clamped = max(eps, t)
                        valid_ts.append(t_clamped)
            elif inside_radius and abs(oy - y_plane) < eps:
                # 射线平行于底面且接近底面
                # 检查射线是否在圆盘范围内
                t_proj = np.dot(-local_origin, local_dir) / (np.dot(local_dir, local_dir) + eps)
                if t_proj > eps:
                    valid_ts.append(t_proj)
        
        # 处理射线从圆柱内部发出的情况
        if inside_radius and inside_height:
            # 从内部寻找最近的出射点
            if not valid_ts and abs(dy) > eps:
                # 计算两个底面的出射距离
                t_exit1 = (height/2 - oy) / dy if dy > eps else float('inf')
                t_exit2 = (-height/2 - oy) / dy if dy < -eps else float('inf')
                t_exit3 = np.sqrt(radius**2 - (ox**2 + oz**2)) / (np.sqrt(dx**2 + dz**2) + eps)
                t_min_exit = min(t for t in [t_exit1, t_exit2, t_exit3] if t > eps)
                if t_min_exit != float('inf'):
                    valid_ts.append(t_min_exit)
        
        # 边界条件：检查边缘相切情况
        if not valid_ts:
            if self._check_cylinder_edge_intersection(local_origin, local_dir, radius, height, eps):
                valid_ts.append(eps * 10)
        
        if not valid_ts:
            return False, 0.0
        
        return True, min(valid_ts)
    
    def _check_cylinder_edge_intersection(self,
                                          origin: np.ndarray,
                                          direction: np.ndarray,
                                          radius: float,
                                          height: float,
                                          eps: float) -> bool:
        """
        检查射线与圆柱边缘（上下边缘圆环）的相切/相交
        """
        # 检查上下两个边缘圆环
        for y_plane in [-height/2, height/2]:
            # 计算射线到圆环的最近距离
            # 参数化圆环: (r*cosθ, y, r*sinθ)
            # 求最近距离的参数θ
            
            # 射线在y=y_plane平面上的投影
            if abs(direction[1]) < eps:
                # 射线平行于圆环平面
                y_dist = abs(origin[1] - y_plane)
                if y_dist > eps:
                    continue
                # 在平面内求点到圆环的距离
                ox, _, oz = origin
                dx, _, dz = direction
                t_param = -(ox * dx + oz * dz) / (dx**2 + dz**2 + eps)
                if t_param < 0:
                    continue
                x_proj = ox + dx * t_param
                z_proj = oz + dz * t_param
                r_proj = np.sqrt(x_proj**2 + z_proj**2)
                if abs(r_proj - radius) < eps:
                    return True
            else:
                t = (y_plane - origin[1]) / direction[1]
                if t < 0:
                    continue
                x = origin[0] + direction[0] * t
                z = origin[2] + direction[2] * t
                r = np.sqrt(x**2 + z**2)
                if abs(r - radius) < eps:
                    return True
        
        return False

    def _ray_sphere_intersection(self,
                                  ray_origin: np.ndarray,
                                  ray_dir: np.ndarray,
                                  sphere_obj: GeometryObject) -> Tuple[bool, float]:
        """
        射线与球体相交检测
        """
        radius, _, _ = sphere_obj.dimensions
        
        oc = ray_origin - sphere_obj.position
        a = np.dot(ray_dir, ray_dir)
        b = 2 * np.dot(oc, ray_dir)
        c = np.dot(oc, oc) - radius ** 2
        
        discriminant = b ** 2 - 4 * a * c
        if discriminant < 0:
            return False, 0.0
        
        sqrt_disc = np.sqrt(discriminant)
        t = (-b - sqrt_disc) / (2 * a)
        
        if t < 1e-10:
            t = (-b + sqrt_disc) / (2 * a)
            if t < 1e-10:
                return False, 0.0
        
        return True, t

    def _ray_object_intersection(self,
                                  ray_origin: np.ndarray,
                                  ray_dir: np.ndarray,
                                  obj: GeometryObject) -> Tuple[bool, float]:
        """
        射线与任意几何体相交检测
        """
        if obj.geometry_type == GeometryType.BOX:
            return self._ray_box_intersection(ray_origin, ray_dir, obj)
        elif obj.geometry_type == GeometryType.CYLINDER:
            return self._ray_cylinder_intersection(ray_origin, ray_dir, obj)
        elif obj.geometry_type == GeometryType.SPHERE:
            return self._ray_sphere_intersection(ray_origin, ray_dir, obj)
        else:
            return False, 0.0

    def calculate_occlusion(self,
                             sun_direction_body: np.ndarray,
                             sa_normal_body: np.ndarray = None) -> OcclusionResult:
        """
        计算遮挡因子
        
        参数:
            sun_direction_body: 太阳方向矢量 (卫星本体坐标系, 单位矢量)
            sa_normal_body: 帆板法向量 (卫星本体坐标系, 单位矢量)
            
        返回:
            OcclusionResult
        """
        if sa_normal_body is None:
            sa_normal_body = self.solar_array.normal
        
        cos_angle = np.dot(sun_direction_body, sa_normal_body)
        if cos_angle <= 0:
            return OcclusionResult(
                occlusion_factor=1.0,
                visible_area_ratio=0.0,
                blocked_cells=[True] * self.solar_array.n_cells,
                shadow_map=np.zeros((self._grid_resolution, self._grid_resolution))
            )
        
        nx = self.solar_array.x_axis
        ny = self.solar_array.y_axis
        sa_center = self.solar_array.position
        width, height = self.solar_array.size
        
        shadow_map = np.ones((self._grid_resolution, self._grid_resolution))
        
        for i in range(self._grid_resolution):
            for j in range(self._grid_resolution):
                x_rel = (j / (self._grid_resolution - 1) - 0.5) * width
                y_rel = (i / (self._grid_resolution - 1) - 0.5) * height
                
                point_on_sa = sa_center + x_rel * nx + y_rel * ny
                
                blocked = False
                min_distance = float('inf')
                
                for obj in self.occlusion_objects:
                    hit, distance = self._ray_object_intersection(
                        point_on_sa, sun_direction_body, obj
                    )
                    if hit and distance < min_distance:
                        min_distance = distance
                        blocked = True
                
                if blocked:
                    shadow_map[i, j] = 0.0
        
        visible_ratio = np.mean(shadow_map)
        occlusion_factor = 1.0 - visible_ratio
        
        cells_per_side = int(np.sqrt(self.solar_array.n_cells))
        if cells_per_side * cells_per_side != self.solar_array.n_cells:
            cells_per_side = self.solar_array.n_cells
        
        blocked_cells = []
        if cells_per_side > 0:
            for i in range(self.solar_array.n_cells):
                row = i // cells_per_side
                col = i % cells_per_side
                grid_row = int(row * self._grid_resolution / cells_per_side)
                grid_col = int(col * self._grid_resolution / cells_per_side)
                grid_row = min(grid_row, self._grid_resolution - 1)
                grid_col = min(grid_col, self._grid_resolution - 1)
                blocked_cells.append(shadow_map[grid_row, grid_col] < 0.5)
        
        return OcclusionResult(
            occlusion_factor=occlusion_factor,
            visible_area_ratio=visible_ratio,
            blocked_cells=blocked_cells,
            shadow_map=shadow_map
        )

    def calculate_effective_irradiance(self,
                                        sun_direction_body: np.ndarray,
                                        direct_irradiance: float,
                                        sa_normal_body: np.ndarray = None) -> Tuple[float, OcclusionResult]:
        """
        计算考虑遮挡后的有效辐照度
        
        参数:
            sun_direction_body: 太阳方向矢量 (本体坐标系)
            direct_irradiance: 直射辐照度 (W/m^2)
            sa_normal_body: 帆板法向量
            
        返回:
            (有效辐照度, 遮挡结果)
        """
        occlusion = self.calculate_occlusion(sun_direction_body, sa_normal_body)
        
        normal = sa_normal_body if sa_normal_body is not None else self.solar_array.normal
        cos_incidence = max(0.0, np.dot(sun_direction_body, normal))
        
        effective_irradiance = (
            direct_irradiance * cos_incidence * occlusion.visible_area_ratio
        )
        
        return effective_irradiance, occlusion


def create_default_satellite_model() -> Tuple[SolarArray, List[GeometryObject]]:
    """
    创建默认的卫星几何模型
    
    返回:
        (太阳能帆板, 遮挡物体列表)
    """
    solar_array = SolarArray(
        name="Main_Solar_Array",
        position=np.array([1.5, 0.0, 0.0]),
        normal=np.array([1.0, 0.0, 0.0]),
        size=(2.0, 1.5),
        n_cells=120,
        cell_area=0.025
    )
    
    satellite_body = GeometryObject(
        name="Satellite_Body",
        geometry_type=GeometryType.BOX,
        position=np.array([-0.25, 0.0, 0.0]),
        orientation=np.array([0.0, 0.0, 0.0]),
        dimensions=np.array([1.0, 1.2, 1.5])
    )
    
    antenna = GeometryObject(
        name="Communication_Antenna",
        geometry_type=GeometryType.CYLINDER,
        position=np.array([-0.5, 0.8, 0.0]),
        orientation=np.array([0.0, 0.0, np.pi / 4]),
        dimensions=np.array([0.15, 1.0, 0.0])
    )
    
    sensor = GeometryObject(
        name="Earth_Sensor",
        geometry_type=GeometryType.SPHERE,
        position=np.array([-0.5, 0.0, 0.8]),
        orientation=np.array([0.0, 0.0, 0.0]),
        dimensions=np.array([0.1, 0.0, 0.0])
    )
    
    return solar_array, [satellite_body, antenna, sensor]


def transform_eci_to_body(eci_vector: np.ndarray,
                           sat_position: np.ndarray,
                           sat_velocity: np.ndarray) -> np.ndarray:
    """
    将ECI坐标系的矢量转换到卫星本体坐标系
    本体坐标系定义:
        X轴: 速度方向
        Y轴: -角动量方向 (指向地心的垂直方向)
        Z轴: 位置方向 (指向地心)
    
    参数:
        eci_vector: ECI坐标系中的矢量
        sat_position: 卫星位置 (ECI, km)
        sat_velocity: 卫星速度 (ECI, km/s)
        
    返回:
        本体坐标系中的矢量
    """
    r = sat_position
    v = sat_velocity
    
    z = -r / np.linalg.norm(r)
    h = np.cross(r, v)
    y = -h / np.linalg.norm(h)
    x = np.cross(y, z)
    
    R_body = np.column_stack([x, y, z])
    
    return R_body.T @ eci_vector
