"""
Command Line Interface for Light Field Depth Estimation

Usage:
    lf-depth --input <image> --method <dfd|stereo|epi|learning|all> [options]
    lf-depth --input <frames_dir> --video --temporal-smooth [options]
    lf-depth --edit --disparity <file.npy> --output <edited.npy>
"""

import os
import sys
import argparse
import time
import numpy as np

from .io import read_light_field, save_image, save_disparity_map
from .calibration import load_calibration, create_default_calibration
from .subaperture import (
    extract_subapertures, extract_subapertures_demosaic, rgb_to_gray,
    detect_mla_pattern, generate_distortion_maps
)
from .depth_dfd import estimate_depth_dfd, estimate_depth_dfd_fast
from .depth_stereo import estimate_depth_stereo
from .depth_epi import estimate_depth_epi, estimate_depth_epi_fast
from .depth_learning import estimate_depth_learning, LightFieldDepthNet
from .video_temporal import (
    process_video_frames, smooth_temporal_kalman,
    smooth_temporal_ema, TemporalDepthSmoother
)
from .editor import edit_depth_interactive, DepthEditor
from .postprocessing import postprocess_pipeline, fuse_disparity_maps
from .pointcloud import (
    disparity_to_pointcloud, depth_map_to_pointcloud,
    save_ply, estimate_normals, downsample_pointcloud
)


def create_parser():
    parser = argparse.ArgumentParser(
        description="Light Field Camera Depth Estimation Toolkit v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # DFD depth estimation with subpixel and anti-aliasing
  lf-depth --input input.png --method dfd --dfd-subpixel --dfd-anti-alias
  
  # Stereo matching with sub-pixel accuracy
  lf-depth --input input.png --method stereo --calib camera_params.yaml
  
  # EPI slope-based depth estimation
  lf-depth --input input.lfr --method epi --num-views 15
  
  # Deep learning end-to-end depth estimation
  lf-depth --input input.png --method learning --model-path model.pth
  
  # All methods with fusion
  lf-depth --input input.png --method all --fuse weighted_mean
  
  # Video processing with temporal smoothing
  lf-depth --input frames/ --video --temporal-smooth kalman --output output/
  
  # Interactive depth editing
  lf-depth --edit --disparity disparity.npy --reference center.png --output edited.npy
  
  # Distortion correction with white image
  lf-depth --input input.png --method stereo --white-image white.png --correct-distortion
        """
    )

    parser.add_argument('--input', '-i', required=False,
                        help='Input light field image (.lfr, .png, .jpg, etc.)')
    parser.add_argument('--white-image', '-w', default=None,
                        help='White reference image for calibration and distortion')
    parser.add_argument('--calib', '-c', default=None,
                        help='Camera calibration YAML file')
    parser.add_argument('--output', '-o', default='./output',
                        help='Output directory (default: ./output)')

    parser.add_argument('--method', '-m', default='stereo',
                        choices=['dfd', 'stereo', 'epi', 'learning', 'all'],
                        help='Depth estimation method (default: stereo)')

    parser.add_argument('--num-views', type=int, default=15,
                        help='Number of views per dimension (default: 15)')
    parser.add_argument('--extraction', default='block',
                        choices=['block', 'demosaic'],
                        help='Sub-aperture extraction method (default: block)')
    parser.add_argument('--grid-type', default='hexagonal',
                        choices=['hexagonal', 'rectangular'],
                        help='MLA grid type for distortion (default: hexagonal)')
    parser.add_argument('--correct-distortion', action='store_true',
                        help='Enable hexagonal grid distortion correction')

    parser.add_argument('--min-disp', type=float, default=-8,
                        help='Minimum disparity (default: -8)')
    parser.add_argument('--max-disp', type=float, default=8,
                        help='Maximum disparity (default: 8)')
    parser.add_argument('--window-size', type=int, default=7,
                        help='Matching window size (default: 7)')

    parser.add_argument('--cost-type', default='sad',
                        choices=['sad', 'ssd', 'ncc', 'census'],
                        help='Stereo matching cost type (default: sad)')
    parser.add_argument('--no-subpixel', action='store_true',
                        help='Disable sub-pixel refinement')
    parser.add_argument('--no-lrc', action='store_true',
                        help='Disable left-right consistency check')

    parser.add_argument('--epi-method', default='fast',
                        choices=['gradient', 'radon', 'fourier', 'fast'],
                        help='EPI slope detection method (default: fast)')

    parser.add_argument('--dfd-subpixel', action='store_true',
                        help='Enable DFD parabolic subpixel refinement')
    parser.add_argument('--dfd-anti-alias', action='store_true',
                        help='Enable DFD depth-axis anti-aliasing')
    parser.add_argument('--dfd-num-depths', type=int, default=32,
                        help='Number of depth planes for DFD (default: 32)')

    parser.add_argument('--model-path', default=None,
                        help='Path to trained deep learning model (.pth)')
    parser.add_argument('--learning-backend', default='auto',
                        choices=['auto', 'pytorch', 'numpy'],
                        help='Deep learning backend (default: auto)')
    parser.add_argument('--learning-use-uncertainty', action='store_true',
                        help='Use uncertainty estimation in learning method')

    parser.add_argument('--video', action='store_true',
                        help='Process video frames from input directory')
    parser.add_argument('--temporal-smooth', default=None,
                        choices=['kalman', 'ema', 'bilateral', 'none'],
                        help='Temporal smoothing method (default: none)')
    parser.add_argument('--temporal-window', type=int, default=5,
                        help='Temporal window size (default: 5)')
    parser.add_argument('--flow-method', default='farneback',
                        choices=['farneback', 'dis'],
                        help='Optical flow method for temporal processing')
    parser.add_argument('--temporal-alpha', type=float, default=0.3,
                        help='EMA smoothing alpha (default: 0.3)')

    parser.add_argument('--edit', action='store_true',
                        help='Interactive depth editing mode')
    parser.add_argument('--disparity', default=None,
                        help='Disparity map file (.npy) for editing')
    parser.add_argument('--reference', default=None,
                        help='Reference image for editing overlay')

    parser.add_argument('--fuse', default='weighted_mean',
                        choices=['mean', 'median', 'weighted_mean', 'select_best'],
                        help='Fusion method for multiple algorithms (default: weighted_mean)')

    parser.add_argument('--postprocess', action='store_true', default=True,
                        help='Enable post-processing (default: True)')
    parser.add_argument('--no-postprocess', action='store_true',
                        help='Disable post-processing')
    parser.add_argument('--occlusion-fill', default='ordered_inpaint',
                        choices=['ordered_inpaint', 'anisotropic', 'layered_bilateral', 'region_growing', 'telea'],
                        help='Occlusion filling method (default: ordered_inpaint)')

    parser.add_argument('--pointcloud', action='store_true', default=True,
                        help='Generate point cloud (default: True)')
    parser.add_argument('--no-pointcloud', action='store_true',
                        help='Skip point cloud generation')
    parser.add_argument('--normals', action='store_true',
                        help='Estimate normals for point cloud')
    parser.add_argument('--downsample', type=float, default=1,
                        help='Point cloud downsample factor (default: 1)')
    parser.add_argument('--voxel-size', type=float, default=None,
                        help='Voxel size for point cloud downsampling')
    parser.add_argument('--ply-ascii', action='store_true',
                        help='Save PLY in ASCII format (default: binary)')

    parser.add_argument('--save-montage', action='store_true',
                        help='Save sub-aperture montage image')
    parser.add_argument('--save-all', action='store_true',
                        help='Save all intermediate results')

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    return parser


def run_depth_estimation(args):
    os.makedirs(args.output, exist_ok=True)

    if args.verbose:
        print(f"[INFO] Reading light field image: {args.input}")
    start_time = time.time()
    lf_image = read_light_field(args.input, args.white_image)
    read_time = time.time() - start_time
    if args.verbose:
        print(f"[INFO] Image loaded in {read_time:.2f}s, shape: {lf_image.get_shape()}")

    if args.calib and os.path.exists(args.calib):
        if args.verbose:
            print(f"[INFO] Loading calibration from: {args.calib}")
        cam_params = load_calibration(args.calib)
    else:
        if args.verbose:
            print(f"[INFO] Using default calibration parameters")
        cam_params = create_default_calibration(num_views=args.num_views)

    cam_params.num_views_u = args.num_views
    cam_params.num_views_v = args.num_views

    if args.verbose:
        print(f"[INFO] Camera parameters: {cam_params}")

    if args.correct_distortion and args.white_image:
        if args.verbose:
            print(f"[INFO] Estimating distortion from white image...")
        try:
            white_img = read_light_field(args.white_image)
            white_data = white_img.raw_image if white_img.raw_image is not None else white_img.get_center_view()
            mla_info = detect_mla_pattern(white_data, num_views=args.num_views, grid_type=args.grid_type)
            if mla_info and 'distortion' in mla_info:
                distortion = mla_info['distortion']
                if args.verbose:
                    print(f"[INFO] Distortion correction enabled:")
                    print(f"       Radial: k1={distortion['radial'][0]:.6f}, k2={distortion['radial'][1]:.6f}, k3={distortion['radial'][2]:.6f}")
                    print(f"       Tangential: p1={distortion['tangential'][0]:.6f}, p2={distortion['tangential'][1]:.6f}")
                cam_params.distortion = distortion
        except Exception as e:
            print(f"[WARNING] Distortion estimation failed: {e}")

    if args.verbose:
        print(f"[INFO] Extracting sub-aperture array ({args.num_views}x{args.num_views})...")
    start_time = time.time()

    mla_params = None
    if lf_image.mla_params and len(lf_image.mla_params) > 0:
        mla_params = lf_image.mla_params

    correct_distortion = args.correct_distortion and hasattr(cam_params, 'distortion') and cam_params.distortion is not None

    if args.extraction == 'demosaic':
        subapertures = extract_subapertures_demosaic(
            lf_image, args.num_views, args.num_views, mla_params,
            correct_distortion=correct_distortion, distortion=getattr(cam_params, 'distortion', None)
        )
    else:
        subapertures = extract_subapertures(
            lf_image, args.num_views, args.num_views, mla_params,
            correct_distortion=correct_distortion, distortion=getattr(cam_params, 'distortion', None)
        )

    extract_time = time.time() - start_time
    if args.verbose:
        print(f"[INFO] Sub-apertures extracted in {extract_time:.2f}s")
        print(f"[INFO] Sub-aperture shape: {subapertures.get_shape()}")

    if args.save_montage or args.save_all:
        montage_path = os.path.join(args.output, 'subaperture_montage.png')
        if args.verbose:
            print(f"[INFO] Saving montage to: {montage_path}")
        subapertures.save_montage(montage_path)

    if subapertures.channels > 1:
        subapertures_gray = rgb_to_gray(subapertures)
    else:
        subapertures_gray = subapertures

    center_view = subapertures.get_center_view()
    if center_view.max() <= 1.0:
        center_view_rgb = (center_view * 255).astype(np.uint8)
    else:
        center_view_rgb = center_view.astype(np.uint8)

    center_view_path = os.path.join(args.output, 'center_view.png')
    if len(center_view_rgb.shape) == 2 or (len(center_view_rgb.shape) == 3 and center_view_rgb.shape[2] == 1):
        save_image(center_view_rgb.reshape(center_view_rgb.shape[:2]), center_view_path)
    else:
        save_image(center_view_rgb, center_view_path)

    disparity_maps = []
    confidence_maps = []
    occlusion_masks = []
    method_names = []

    if args.method in ['dfd', 'all']:
        if args.verbose:
            print("[INFO] Running DFD depth estimation...")
        start_time = time.time()
        try:
            disp_dfd, conf_dfd = estimate_depth_dfd_fast(
                subapertures_gray,
                num_depths=args.dfd_num_depths,
                use_subpixel=args.dfd_subpixel,
                anti_alias=args.dfd_anti_alias
            )
            if args.postprocess and not args.no_postprocess:
                disp_dfd, conf_dfd, occl_dfd = postprocess_pipeline(
                    disp_dfd, conf_dfd, subapertures=subapertures_gray,
                    occlusion_fill_method=args.occlusion_fill
                )
            else:
                occl_dfd = np.zeros_like(disp_dfd, dtype=bool)

            disparity_maps.append(disp_dfd)
            confidence_maps.append(conf_dfd)
            occlusion_masks.append(occl_dfd)
            method_names.append('dfd')

            if args.verbose:
                print(f"[INFO] DFD completed in {time.time() - start_time:.2f}s")

            save_disparity_map(disp_dfd, os.path.join(args.output, 'disparity_dfd.png'))
            save_image(conf_dfd, os.path.join(args.output, 'confidence_dfd.png'), normalize=True)
            save_image(occl_dfd.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_dfd.png'))
        except Exception as e:
            print(f"[ERROR] DFD estimation failed: {e}")

    if args.method in ['stereo', 'all']:
        if args.verbose:
            print("[INFO] Running stereo matching...")
        start_time = time.time()
        try:
            disp_stereo, conf_stereo, occl_stereo = estimate_depth_stereo(
                subapertures_gray,
                min_disp=args.min_disp,
                max_disp=args.max_disp,
                window_size=args.window_size,
                cost_type=args.cost_type,
                use_subpixel=not args.no_subpixel,
                use_lrc=not args.no_lrc
            )

            if args.postprocess and not args.no_postprocess:
                disp_stereo, conf_stereo, occl_stereo = postprocess_pipeline(
                    disp_stereo, conf_stereo, occl_stereo, subapertures_gray,
                    occlusion_fill_method=args.occlusion_fill
                )

            disparity_maps.append(disp_stereo)
            confidence_maps.append(conf_stereo)
            occlusion_masks.append(occl_stereo)
            method_names.append('stereo')

            if args.verbose:
                print(f"[INFO] Stereo matching completed in {time.time() - start_time:.2f}s")

            save_disparity_map(disp_stereo, os.path.join(args.output, 'disparity_stereo.png'))
            save_image(conf_stereo, os.path.join(args.output, 'confidence_stereo.png'), normalize=True)
            save_image(occl_stereo.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_stereo.png'))
        except Exception as e:
            print(f"[ERROR] Stereo matching failed: {e}")

    if args.method in ['epi', 'all']:
        if args.verbose:
            print(f"[INFO] Running EPI depth estimation ({args.epi_method})...")
        start_time = time.time()
        try:
            if args.epi_method == 'fast':
                disp_epi, conf_epi, occl_epi = estimate_depth_epi_fast(
                    subapertures_gray,
                    min_slope=args.min_disp,
                    max_slope=args.max_disp
                )
            else:
                disp_epi, conf_epi, occl_epi = estimate_depth_epi(
                    subapertures_gray,
                    method=args.epi_method,
                    min_slope=args.min_disp,
                    max_slope=args.max_disp,
                    subpixel_refine=not args.no_subpixel
                )

            if args.postprocess and not args.no_postprocess:
                disp_epi, conf_epi, occl_epi = postprocess_pipeline(
                    disp_epi, conf_epi, occl_epi, subapertures_gray,
                    occlusion_fill_method=args.occlusion_fill
                )

            disparity_maps.append(disp_epi)
            confidence_maps.append(conf_epi)
            occlusion_masks.append(occl_epi)
            method_names.append('epi')

            if args.verbose:
                print(f"[INFO] EPI estimation completed in {time.time() - start_time:.2f}s")

            save_disparity_map(disp_epi, os.path.join(args.output, 'disparity_epi.png'))
            save_image(conf_epi, os.path.join(args.output, 'confidence_epi.png'), normalize=True)
            save_image(occl_epi.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_epi.png'))
        except Exception as e:
            print(f"[ERROR] EPI estimation failed: {e}")

    if args.method in ['learning', 'all']:
        if args.verbose:
            print("[INFO] Running deep learning depth estimation...")
        start_time = time.time()
        try:
            disp_learning, conf_learning, uncertainty = estimate_depth_learning(
                subapertures,
                model_path=args.model_path,
                backend=args.learning_backend,
                return_uncertainty=args.learning_use_uncertainty,
                min_disp=args.min_disp,
                max_disp=args.max_disp
            )

            occl_learning = np.zeros_like(disp_learning, dtype=bool)
            if args.learning_use_uncertainty and uncertainty is not None:
                occl_learning = uncertainty > np.percentile(uncertainty, 90)

            if args.postprocess and not args.no_postprocess:
                disp_learning, conf_learning, occl_learning = postprocess_pipeline(
                    disp_learning, conf_learning, occl_learning, subapertures_gray,
                    occlusion_fill_method=args.occlusion_fill
                )

            disparity_maps.append(disp_learning)
            confidence_maps.append(conf_learning)
            occlusion_masks.append(occl_learning)
            method_names.append('learning')

            if args.verbose:
                print(f"[INFO] Learning estimation completed in {time.time() - start_time:.2f}s")

            save_disparity_map(disp_learning, os.path.join(args.output, 'disparity_learning.png'))
            save_image(conf_learning, os.path.join(args.output, 'confidence_learning.png'), normalize=True)
            save_image(occl_learning.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_learning.png'))
            if uncertainty is not None:
                save_image(uncertainty, os.path.join(args.output, 'uncertainty_learning.png'), normalize=True)
        except Exception as e:
            print(f"[ERROR] Deep learning estimation failed: {e}")

    if len(disparity_maps) == 0:
        print("[ERROR] No depth estimation results. Exiting.")
        return

    if args.method == 'all' and len(disparity_maps) > 1:
        if args.verbose:
            print(f"[INFO] Fusing results using {args.fuse}...")
        fused_disp, fused_conf = fuse_disparity_maps(
            disparity_maps, confidence_maps, method=args.fuse
        )

        fused_occl = np.zeros_like(fused_disp, dtype=bool)
        for occl in occlusion_masks:
            fused_occl |= occl

        if args.postprocess and not args.no_postprocess:
            fused_disp, fused_conf, fused_occl = postprocess_pipeline(
                fused_disp, fused_conf, fused_occl, subapertures_gray
            )

        save_disparity_map(fused_disp, os.path.join(args.output, 'disparity_fused.png'))
        save_image(fused_conf, os.path.join(args.output, 'confidence_fused.png'), normalize=True)
        save_image(fused_occl.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_fused.png'))

        final_disp = fused_disp
        final_conf = fused_conf
        final_occl = fused_occl
    else:
        final_disp = disparity_maps[0]
        final_conf = confidence_maps[0]
        final_occl = occlusion_masks[0] if len(occlusion_masks) > 0 else np.zeros_like(final_disp, dtype=bool)

    save_disparity_map(final_disp, os.path.join(args.output, 'disparity_final.png'))
    save_image(final_conf, os.path.join(args.output, 'confidence_final.png'), normalize=True)
    save_image(final_occl.astype(np.uint8) * 255, os.path.join(args.output, 'occlusion_final.png'))

    if cam_params.is_complete():
        try:
            depth_map = cam_params.disparity_to_depth(final_disp)
            save_image(depth_map, os.path.join(args.output, 'depth_final.png'), normalize=True)
            np.save(os.path.join(args.output, 'depth_final.npy'), depth_map)
        except Exception as e:
            print(f"[WARNING] Depth map computation failed: {e}")
            depth_map = None
    else:
        depth_map = None

    np.save(os.path.join(args.output, 'disparity_final.npy'), final_disp)
    np.save(os.path.join(args.output, 'confidence_final.npy'), final_conf)
    np.save(os.path.join(args.output, 'occlusion_final.npy'), final_occl)

    if args.pointcloud and not args.no_pointcloud:
        if args.verbose:
            print("[INFO] Generating point cloud...")
        start_time = time.time()

        try:
            if depth_map is not None:
                pc = depth_map_to_pointcloud(
                    depth_map, cam_params,
                    rgb_image=center_view_rgb,
                    confidence_map=final_conf,
                    occlusion_mask=final_occl,
                    downsample=args.downsample
                )
            else:
                pc = disparity_to_pointcloud(
                    final_disp, cam_params,
                    rgb_image=center_view_rgb,
                    confidence_map=final_conf,
                    occlusion_mask=final_occl,
                    downsample=args.downsample
                )

            if args.voxel_size is not None:
                if args.verbose:
                    print(f"[INFO] Voxel downsampling (voxel_size={args.voxel_size})...")
                pc = downsample_pointcloud(pc, voxel_size=args.voxel_size)

            if args.normals:
                if args.verbose:
                    print("[INFO] Estimating normals...")
                pc = estimate_normals(pc)

            ply_path = os.path.join(args.output, 'pointcloud.ply')
            save_ply(pc, ply_path, use_ascii=args.ply_ascii, include_normals=args.normals)

            if args.verbose:
                print(f"[INFO] Point cloud saved with {pc.get_num_points()} points")
                print(f"[INFO] Point cloud generation took {time.time() - start_time:.2f}s")
        except Exception as e:
            print(f"[ERROR] Point cloud generation failed: {e}")

    if args.save_all:
        for name, disp, conf, occl in zip(method_names, disparity_maps, confidence_maps, occlusion_masks):
            np.save(os.path.join(args.output, f'disparity_{name}.npy'), disp)
            np.save(os.path.join(args.output, f'confidence_{name}.npy'), conf)
            if occl is not None:
                np.save(os.path.join(args.output, f'occlusion_{name}.npy'), occl)

    if cam_params is not None:
        cam_params.save_to_yaml(os.path.join(args.output, 'camera_params.yaml'))

    total_time = time.time() - read_time
    if args.verbose:
        print(f"\n[INFO] Processing complete!")
        print(f"[INFO] Total time: {total_time:.2f}s")
        print(f"[INFO] Output saved to: {os.path.abspath(args.output)}")

    return True


def run_video_processing(args):
    os.makedirs(args.output, exist_ok=True)

    if args.verbose:
        print(f"[INFO] Processing video frames from: {args.input}")
        print(f"[INFO] Temporal smoothing method: {args.temporal_smooth}")

    try:
        disparity_sequence, confidence_sequence, reference_images = process_video_frames(
            args.input,
            num_views=args.num_views,
            method=args.method if args.method != 'all' else 'stereo',
            calib_file=args.calib,
            temporal_smooth=args.temporal_smooth,
            temporal_window=args.temporal_window,
            flow_method=args.flow_method,
            alpha=args.temporal_alpha,
            verbose=args.verbose
        )

        if args.verbose:
            print(f"[INFO] Saving {len(disparity_sequence)} frames to: {args.output}")

        for i, (disp, conf, ref) in enumerate(zip(disparity_sequence, confidence_sequence, reference_images)):
            frame_dir = os.path.join(args.output, f'frame_{i:04d}')
            os.makedirs(frame_dir, exist_ok=True)

            save_disparity_map(disp, os.path.join(frame_dir, 'disparity.png'))
            save_image(conf, os.path.join(frame_dir, 'confidence.png'), normalize=True)
            np.save(os.path.join(frame_dir, 'disparity.npy'), disp)
            np.save(os.path.join(frame_dir, 'confidence.npy'), conf)
            if ref is not None:
                save_image(ref, os.path.join(frame_dir, 'reference.png'))

        return True

    except Exception as e:
        print(f"[ERROR] Video processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_edit_mode(args):
    if args.disparity is None or not os.path.exists(args.disparity):
        print("[ERROR] Please specify a valid disparity map file with --disparity")
        return False

    try:
        disparity = np.load(args.disparity)
        reference = None
        if args.reference and os.path.exists(args.reference):
            reference = read_light_field(args.reference).get_center_view()
            if reference.max() <= 1.0:
                reference = (reference * 255).astype(np.uint8)

        print("[INFO] Starting interactive depth editor...")
        print("[INFO] Controls: Left-click draw, Right-click sample, Scroll resize brush")
        print("[INFO] Keys: 1-4 switch mode, Z undo, Y redo, F flood fill, Enter save, ESC cancel")

        edited_disparity, mask = edit_depth_interactive(
            disparity,
            reference_image=reference,
            output_path=args.output
        )

        if edited_disparity is not None:
            output_path = args.output
            if os.path.isdir(output_path) or '.' not in os.path.basename(output_path):
                output_path = os.path.join(output_path, 'edited_disparity.npy')

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            np.save(output_path, edited_disparity)

            base, ext = os.path.splitext(output_path)
            save_disparity_map(edited_disparity, base + '.png')

            if mask is not None:
                np.save(base + '_mask.npy', mask)
                save_image(mask.astype(np.uint8) * 255, base + '_mask.png')

            print(f"[SUCCESS] Edited disparity saved to: {output_path}")
            return True
        else:
            print("[INFO] Editing cancelled or failed.")
            return False

    except Exception as e:
        print(f"[ERROR] Interactive editing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.edit:
            success = run_edit_mode(args)
            if success:
                print("\n[SUCCESS] Depth editing completed!")
            else:
                print("\n[FAILURE] Depth editing failed or cancelled.")
                sys.exit(1 if not success else 0)

        elif args.video:
            if not os.path.exists(args.input) or not os.path.isdir(args.input):
                print(f"[ERROR] Input directory not found: {args.input}")
                sys.exit(1)

            success = run_video_processing(args)
            if success:
                print("\n[SUCCESS] Video processing completed successfully!")
            else:
                print("\n[FAILURE] Video processing failed.")
                sys.exit(1)

        else:
            if args.input is None or not os.path.exists(args.input):
                print(f"[ERROR] Input file not found: {args.input}")
                sys.exit(1)

            success = run_depth_estimation(args)
            if success:
                print("\n[SUCCESS] Depth estimation completed successfully!")
            else:
                print("\n[FAILURE] Depth estimation failed.")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
