"""
Example script demonstrating light field depth estimation usage.
Generates synthetic test data and runs all three depth estimation algorithms.
"""

import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightfield_depth import (
    io, calibration, subaperture,
    depth_dfd, depth_stereo, depth_epi,
    postprocessing, pointcloud
)


def generate_synthetic_lightfield(size=300, num_views=9, disparity=2.0):
    """Generate synthetic light field for testing."""
    print(f"[INFO] Generating synthetic light field ({num_views}x{num_views} views)...")
    
    sub_h = size // num_views
    sub_w = size // num_views
    
    center_v = num_views // 2
    center_u = num_views // 2
    
    y, x = np.mgrid[0:sub_h, 0:sub_w]
    
    pattern = np.zeros((sub_h, sub_w, 3), dtype=np.uint8)
    
    for i in range(5):
        for j in range(5):
            cy = (i + 0.5) * sub_h / 5
            cx = (j + 0.5) * sub_w / 5
            r = min(sub_h, sub_w) / 15
            mask = (y - cy) ** 2 + (x - cx) ** 2 < r ** 2
            color = np.random.randint(50, 255, 3)
            pattern[mask] = color
    
    bg = np.random.randint(30, 80, 3)
    pattern[np.all(pattern == 0, axis=-1)] = bg
    
    lf_data = np.zeros((num_views, num_views, sub_h, sub_w, 3), dtype=np.float32)
    
    for v in range(num_views):
        for u in range(num_views):
            shift_v = (v - center_v) * disparity
            shift_u = (u - center_u) * disparity
            
            M = np.array([[1, 0, shift_u], [0, 1, shift_v]], dtype=np.float32)
            for c in range(3):
                lf_data[v, u, :, :, c] = cv2.warpAffine(
                    pattern[:, :, c].astype(np.float32), M, (sub_w, sub_h),
                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
                )
    
    raw_img = np.zeros((size, size, 3), dtype=np.uint8)
    for v in range(num_views):
        for u in range(num_views):
            start_y = v * sub_h
            start_x = u * sub_w
            raw_img[start_y:start_y + sub_h, start_x:start_x + sub_w] = \
                lf_data[v, u].astype(np.uint8)
    
    return raw_img, lf_data


def main():
    output_dir = './output_example'
    os.makedirs(output_dir, exist_ok=True)
    
    num_views = 9
    raw_img, lf_data = generate_synthetic_lightfield(size=450, num_views=num_views, disparity=3.0)
    
    cv2.imwrite(os.path.join(output_dir, 'synthetic_input.png'), 
                cv2.cvtColor(raw_img, cv2.COLOR_RGB2BGR))
    
    lf = io.LightFieldImage()
    lf.corrected_image = raw_img
    lf.raw_image = raw_img
    lf.mla_params = {
        'image_width': raw_img.shape[1],
        'image_height': raw_img.shape[0],
        'lens_pitch_x': raw_img.shape[1] / num_views,
        'lens_pitch_y': raw_img.shape[0] / num_views,
    }
    
    print("[INFO] Extracting sub-apertures...")
    sa = subaperture.extract_subapertures(lf, num_views, num_views, lf.mla_params)
    sa.save_montage(os.path.join(output_dir, 'subapertures.png'))
    
    sa_gray = subaperture.rgb_to_gray(sa)
    
    cam_params = calibration.create_default_calibration(num_views=num_views)
    cam_params.save_to_yaml(os.path.join(output_dir, 'camera_params.yaml'))
    
    print("\n[INFO] === DFD Depth Estimation ===")
    try:
        disp_dfd, conf_dfd = depth_dfd.estimate_depth_dfd_fast(sa_gray)
        disp_dfd_pp, conf_dfd_pp, occl_dfd = postprocessing.postprocess_pipeline(
            disp_dfd, conf_dfd, subapertures=sa_gray
        )
        
        io.save_disparity_map(disp_dfd, os.path.join(output_dir, 'disparity_dfd_raw.png'))
        io.save_disparity_map(disp_dfd_pp, os.path.join(output_dir, 'disparity_dfd.png'))
        io.save_image(conf_dfd_pp, os.path.join(output_dir, 'confidence_dfd.png'), normalize=True)
        io.save_image(occl_dfd.astype(np.uint8) * 255, os.path.join(output_dir, 'occlusion_dfd.png'))
        print("[INFO] DFD completed successfully")
    except Exception as e:
        print(f"[ERROR] DFD failed: {e}")
        disp_dfd_pp, conf_dfd_pp, occl_dfd = None, None, None
    
    print("\n[INFO] === Stereo Matching ===")
    try:
        disp_stereo, conf_stereo, occl_stereo = depth_stereo.estimate_depth_stereo(
            sa_gray, min_disp=-6, max_disp=6, window_size=5, cost_type='sad'
        )
        disp_stereo_pp, conf_stereo_pp, occl_stereo_pp = postprocessing.postprocess_pipeline(
            disp_stereo, conf_stereo, occl_stereo, sa_gray
        )
        
        io.save_disparity_map(disp_stereo, os.path.join(output_dir, 'disparity_stereo_raw.png'))
        io.save_disparity_map(disp_stereo_pp, os.path.join(output_dir, 'disparity_stereo.png'))
        io.save_image(conf_stereo_pp, os.path.join(output_dir, 'confidence_stereo.png'), normalize=True)
        io.save_image(occl_stereo_pp.astype(np.uint8) * 255, os.path.join(output_dir, 'occlusion_stereo.png'))
        print("[INFO] Stereo matching completed successfully")
    except Exception as e:
        print(f"[ERROR] Stereo matching failed: {e}")
        disp_stereo_pp, conf_stereo_pp, occl_stereo_pp = None, None, None
    
    print("\n[INFO] === EPI Depth Estimation ===")
    try:
        disp_epi, conf_epi, occl_epi = depth_epi.estimate_depth_epi_fast(
            sa_gray, min_slope=-6, max_slope=6, num_slopes=49
        )
        disp_epi_pp, conf_epi_pp, occl_epi_pp = postprocessing.postprocess_pipeline(
            disp_epi, conf_epi, occl_epi, sa_gray
        )
        
        io.save_disparity_map(disp_epi, os.path.join(output_dir, 'disparity_epi_raw.png'))
        io.save_disparity_map(disp_epi_pp, os.path.join(output_dir, 'disparity_epi.png'))
        io.save_image(conf_epi_pp, os.path.join(output_dir, 'confidence_epi.png'), normalize=True)
        io.save_image(occl_epi_pp.astype(np.uint8) * 255, os.path.join(output_dir, 'occlusion_epi.png'))
        print("[INFO] EPI completed successfully")
    except Exception as e:
        print(f"[ERROR] EPI failed: {e}")
        disp_epi_pp, conf_epi_pp, occl_epi_pp = None, None, None
    
    print("\n[INFO] === Fusion ===")
    disparities = []
    confidences = []
    
    if disp_dfd_pp is not None:
        disparities.append(disp_dfd_pp)
        confidences.append(conf_dfd_pp)
    if disp_stereo_pp is not None:
        disparities.append(disp_stereo_pp)
        confidences.append(conf_stereo_pp)
    if disp_epi_pp is not None:
        disparities.append(disp_epi_pp)
        confidences.append(conf_epi_pp)
    
    if len(disparities) > 1:
        fused_disp, fused_conf = postprocessing.fuse_disparity_maps(
            disparities, confidences, method='weighted_mean'
        )
        
        fused_occl = np.zeros_like(fused_disp, dtype=bool)
        if occl_dfd is not None:
            fused_occl |= occl_dfd
        if occl_stereo is not None:
            fused_occl |= occl_stereo
        if occl_epi is not None:
            fused_occl |= occl_epi
        
        io.save_disparity_map(fused_disp, os.path.join(output_dir, 'disparity_fused.png'))
        io.save_image(fused_conf, os.path.join(output_dir, 'confidence_fused.png'), normalize=True)
        io.save_image(fused_occl.astype(np.uint8) * 255, os.path.join(output_dir, 'occlusion_fused.png'))
        
        depth_map = cam_params.disparity_to_depth(fused_disp)
        io.save_image(depth_map, os.path.join(output_dir, 'depth_map.png'), normalize=True)
        
        print("[INFO] === Point Cloud Generation ===")
        center_view = sa.get_center_view()
        if center_view.max() <= 1.0:
            center_view = (center_view * 255).astype(np.uint8)
        
        pc = pointcloud.disparity_to_pointcloud(
            fused_disp, cam_params,
            rgb_image=center_view,
            confidence_map=fused_conf,
            occlusion_mask=fused_occl,
            downsample=1
        )
        
        pointcloud.save_ply(pc, os.path.join(output_dir, 'pointcloud.ply'), use_ascii=False)
        print(f"[INFO] Point cloud saved with {pc.get_num_points()} points")
    
    print(f"\n[INFO] All results saved to: {os.path.abspath(output_dir)}")
    print("[INFO] Example completed successfully!")


if __name__ == '__main__':
    main()
