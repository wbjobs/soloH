"""
Camera Calibration Parameters Module

Manages light field camera intrinsic and extrinsic parameters:
- Focal length
- Baseline (between sub-apertures)
- Microlens array parameters
- Pixel pitch
- Principal point
"""

import os
import yaml
import numpy as np


class CameraParameters:
    def __init__(self):
        self.focal_length = None
        self.baseline = None
        self.pixel_pitch = None
        self.principal_point = None
        self.mla_pitch = None
        self.num_views_u = None
        self.num_views_v = None
        self.image_resolution = None
        self.subaperture_resolution = None

    def load_from_yaml(self, yaml_path):
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Calibration file not found: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            params = yaml.safe_load(f)

        self.focal_length = params.get('focal_length', None)
        self.baseline = params.get('baseline', None)
        self.pixel_pitch = params.get('pixel_pitch', None)
        self.mla_pitch = params.get('mla_pitch', None)
        self.num_views_u = params.get('num_views_u', 15)
        self.num_views_v = params.get('num_views_v', 15)
        self.image_resolution = params.get('image_resolution', None)
        self.subaperture_resolution = params.get('subaperture_resolution', None)

        pp = params.get('principal_point', None)
        if pp is not None:
            self.principal_point = np.array(pp, dtype=np.float32)

    def save_to_yaml(self, yaml_path):
        params = {
            'focal_length': self.focal_length,
            'baseline': self.baseline,
            'pixel_pitch': self.pixel_pitch,
            'mla_pitch': self.mla_pitch,
            'num_views_u': self.num_views_u,
            'num_views_v': self.num_views_v,
            'image_resolution': self.image_resolution,
            'subaperture_resolution': self.subaperture_resolution,
            'principal_point': self.principal_point.tolist() if self.principal_point is not None else None,
        }

        os.makedirs(os.path.dirname(os.path.abspath(yaml_path)), exist_ok=True)

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(params, f, default_flow_style=False, sort_keys=False)

    def disparity_to_depth(self, disparity):
        if self.focal_length is None or self.baseline is None:
            raise ValueError("Focal length and baseline must be set for depth conversion")

        with np.errstate(divide='ignore'):
            depth = (self.focal_length * self.baseline) / (disparity + 1e-8)

        return depth

    def depth_to_disparity(self, depth):
        if self.focal_length is None or self.baseline is None:
            raise ValueError("Focal length and baseline must be set for disparity conversion")

        with np.errstate(divide='ignore'):
            disparity = (self.focal_length * self.baseline) / (depth + 1e-8)

        return disparity

    def get_num_views(self):
        return self.num_views_u, self.num_views_v

    def set_defaults(self, num_views=15):
        self.num_views_u = num_views
        self.num_views_v = num_views
        self.focal_length = 100.0
        self.baseline = 0.5
        self.pixel_pitch = 1e-5
        self.mla_pitch = 15 * self.pixel_pitch

    def is_complete(self):
        required = ['focal_length', 'baseline', 'pixel_pitch']
        return all(getattr(self, attr) is not None for attr in required)

    def __repr__(self):
        return (f"CameraParameters(f={self.focal_length}, B={self.baseline}, "
                f"pitch={self.pixel_pitch}, views={self.num_views_u}x{self.num_views_v})")


def load_calibration(yaml_path):
    cam_params = CameraParameters()
    cam_params.load_from_yaml(yaml_path)
    return cam_params


def create_default_calibration(num_views=15):
    cam_params = CameraParameters()
    cam_params.set_defaults(num_views)
    return cam_params
