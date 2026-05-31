"""
Interactive Depth Map Editor for Light Field Depth Estimation.

Provides a GUI-based tool for manual correction of depth maps:
- Click to select and edit individual pixels or regions
- Brush tool for painting depth values
- Region interpolation for filling holes
- Undo/redo functionality
- Visual feedback with colormap overlay
"""

import numpy as np
import cv2
import os
from collections import deque


class DepthEditor:
    """
    Interactive depth map editor using OpenCV GUI.
    
    Controls:
    - Left click: Select point / draw with brush
    - Right click: Sample depth value from image
    - Mouse wheel: Adjust brush size
    - Keys:
      'b': Brush mode
      'i': Interpolation mode
      's': Sample mode
      'e': Eraser mode
      '+': Increase brush size
      '-': Decrease brush size
      'z': Undo
      'r': Redo
      '[': Decrease depth value
      ']': Increase depth value
      'u': Update display
      'q': Quit and save
      'ESC': Quit without saving
    """
    
    def __init__(self, depth_map, reference_image=None, confidence_map=None):
        """
        Initialize depth editor.
        
        Parameters:
            depth_map: Input depth map [H, W]
            reference_image: Optional reference image for visualization [H, W, 3]
            confidence_map: Optional confidence map [H, W]
        """
        self.original_depth = depth_map.copy()
        self.depth_map = depth_map.copy()
        self.reference_image = reference_image
        self.confidence_map = confidence_map
        
        self.h, self.w = depth_map.shape
        
        self.depth_min = np.nanmin(depth_map)
        self.depth_max = np.nanmax(depth_map)
        self.depth_range = self.depth_max - self.depth_min
        
        self.brush_size = 5
        self.brush_value = np.median(depth_map)
        self.mode = 'brush'
        
        self.history = deque(maxlen=50)
        self.future = deque(maxlen=50)
        
        self.dragging = False
        self.last_pos = None
        self.selected_points = []
        self.interpolation_points = []
        
        self.window_name = 'Depth Editor'
        self.display_scale = 1.0
        
        self._save_state()
    
    def _save_state(self):
        """Save current state for undo."""
        self.history.append(self.depth_map.copy())
        self.future.clear()
    
    def undo(self):
        """Undo last operation."""
        if len(self.history) > 1:
            self.future.appendleft(self.history.pop())
            self.depth_map = self.history[-1].copy()
            return True
        return False
    
    def redo(self):
        """Redo last undone operation."""
        if self.future:
            self.history.append(self.future.popleft())
            self.depth_map = self.history[-1].copy()
            return True
        return False
    
    def normalize_depth(self, depth=None):
        """Normalize depth map to 0-255 for display."""
        if depth is None:
            depth = self.depth_map
        
        d = np.nan_to_num(depth, nan=self.depth_min)
        normalized = (d - self.depth_min) / (self.depth_range + 1e-8)
        return np.clip(normalized * 255, 0, 255).astype(np.uint8)
    
    def apply_colormap(self, depth_8bit):
        """Apply colormap to normalized depth."""
        return cv2.applyColorMap(depth_8bit, cv2.COLORMAP_JET)
    
    def create_display(self):
        """Create combined display image."""
        disp_depth = self.normalize_depth()
        disp_colored = self.apply_colormap(disp_depth)
        
        if self.reference_image is not None:
            ref = self.reference_image.copy()
            if ref.ndim == 2:
                ref = cv2.cvtColor(ref, cv2.COLOR_GRAY2BGR)
            
            if ref.shape[:2] != disp_colored.shape[:2]:
                ref = cv2.resize(ref, (self.w, self.h))
            
            ref = (ref - ref.min()) / (ref.max() - ref.min() + 1e-8)
            ref = (ref * 255).astype(np.uint8)
            
            alpha = 0.6
            blended = cv2.addWeighted(ref, alpha, disp_colored, 1 - alpha, 0)
            
            if self.confidence_map is not None:
                conf_vis = (self.confidence_map * 255).astype(np.uint8)
                conf_vis = cv2.applyColorMap(conf_vis, cv2.COLORMAP_BONE)
                conf_vis = cv2.resize(conf_vis, (self.w, self.h))
            
            display = np.hstack([blended, disp_colored])
        else:
            display = disp_colored
        
        return display
    
    def draw_brush_preview(self, img, x, y):
        """Draw brush preview circle."""
        if self.mode == 'eraser':
            color = (255, 255, 255)
        elif self.mode == 'sample':
            color = (0, 255, 0)
        else:
            color = (0, 0, 255)
        
        cv2.circle(img, (x, y), self.brush_size, color, 1)
    
    def apply_brush(self, x, y):
        """Apply brush at given position."""
        if self.mode == 'sample':
            if 0 <= y < self.h and 0 <= x < self.w:
                self.brush_value = self.depth_map[y, x]
                print(f"Sampled depth value: {self.brush_value:.3f}")
            return
        
        self._save_state()
        
        y_coords, x_coords = np.mgrid[0:self.h, 0:self.w]
        dist = np.sqrt((x_coords - x) ** 2 + (y_coords - y) ** 2)
        mask = dist <= self.brush_size
        
        if self.mode == 'brush':
            self.depth_map[mask] = self.brush_value
        elif self.mode == 'eraser':
            self.depth_map[mask] = self.original_depth[mask]
        elif self.mode == 'interpolate':
            self._interpolate_region(mask)
    
    def _interpolate_region(self, mask):
        """Interpolate depth values in masked region from boundary."""
        from scipy.interpolate import griddata
        
        if not np.any(mask):
            return
        
        y_coords, x_coords = np.mgrid[0:self.h, 0:self.w]
        
        boundary = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        boundary = boundary & ~mask
        
        if not np.any(boundary):
            return
        
        boundary_points = np.column_stack([y_coords[boundary], x_coords[boundary]])
        boundary_values = self.depth_map[boundary]
        
        mask_points = np.column_stack([y_coords[mask], x_coords[mask]])
        
        try:
            interpolated = griddata(boundary_points, boundary_values, mask_points, 
                                    method='linear', fill_value=np.mean(boundary_values))
            self.depth_map[mask] = interpolated
        except:
            self.depth_map[mask] = np.mean(boundary_values)
    
    def flood_fill(self, seed_x, seed_y, tolerance=0.1):
        """Flood fill region with similar depth values."""
        seed_value = self.depth_map[seed_y, seed_x]
        
        mask = np.abs(self.depth_map - seed_value) < tolerance * self.depth_range
        
        from scipy.ndimage import label
        labeled, num_regions = label(mask)
        
        seed_label = labeled[seed_y, seed_x]
        region_mask = labeled == seed_label
        
        self._save_state()
        self._interpolate_region(region_mask)
    
    def adjust_depth_value(self, delta):
        """Adjust current brush depth value."""
        step = self.depth_range * 0.01
        self.brush_value = np.clip(self.brush_value + delta * step, 
                                  self.depth_min, self.depth_max)
        print(f"Brush value: {self.brush_value:.3f}")
    
    def adjust_brush_size(self, delta):
        """Adjust brush size."""
        self.brush_size = max(1, self.brush_size + delta)
        print(f"Brush size: {self.brush_size}")
    
    def set_mode(self, mode):
        """Set editor mode."""
        valid_modes = ['brush', 'eraser', 'sample', 'interpolate']
        if mode in valid_modes:
            self.mode = mode
            print(f"Mode: {self.mode}")
    
    def on_mouse(self, event, x, y, flags, param):
        """Mouse event handler."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.dragging = True
            self.last_pos = (x, y)
            self.apply_brush(x, y)
        
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.set_mode('sample')
            self.apply_brush(x, y)
            self.set_mode('brush')
        
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.dragging and self.last_pos is not None:
                dx = x - self.last_pos[0]
                dy = y - self.last_pos[1]
                dist = np.sqrt(dx * dx + dy * dy)
                
                if dist > 1:
                    steps = int(dist) + 1
                    for i in range(1, steps + 1):
                        t = i / steps
                        ix = int(self.last_pos[0] + t * dx)
                        iy = int(self.last_pos[1] + t * dy)
                        self.apply_brush(ix, iy)
                
                self.last_pos = (x, y)
                self.apply_brush(x, y)
        
        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = False
            self.last_pos = None
        
        elif event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:
                self.adjust_brush_size(1)
            else:
                self.adjust_brush_size(-1)
    
    def run(self):
        """Run the interactive editor."""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, min(1600, self.w * 2), min(800, self.h))
        cv2.setMouseCallback(self.window_name, self.on_mouse)
        
        mouse_x, mouse_y = 0, 0
        
        while True:
            display = self.create_display()
            
            if mouse_x >= 0 and mouse_y >= 0 and self.mode != 'sample':
                h, w = display.shape[:2]
                if mouse_x < w and mouse_y < h:
                    self.draw_brush_preview(display, mouse_x, mouse_y)
            
            info_text = f"Mode: {self.mode} | Brush: {self.brush_size} | Value: {self.brush_value:.3f} | Undo: {len(self.history)-1}"
            cv2.putText(display, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow(self.window_name, display)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27:
                cv2.destroyAllWindows()
                return None
            
            elif key == ord('q'):
                break
            
            elif key == ord('z'):
                if self.undo():
                    print("Undo")
                else:
                    print("Nothing to undo")
            
            elif key == ord('r'):
                if self.redo():
                    print("Redo")
                else:
                    print("Nothing to redo")
            
            elif key == ord('b'):
                self.set_mode('brush')
            elif key == ord('e'):
                self.set_mode('eraser')
            elif key == ord('i'):
                self.set_mode('interpolate')
            elif key == ord('s'):
                self.set_mode('sample')
            
            elif key == ord('+') or key == ord('='):
                self.adjust_brush_size(1)
            elif key == ord('-'):
                self.adjust_brush_size(-1)
            
            elif key == ord(']'):
                self.adjust_depth_value(1)
            elif key == ord('['):
                self.adjust_depth_value(-1)
            
            elif key == ord('f'):
                if self.last_pos:
                    self.flood_fill(self.last_pos[0], self.last_pos[1])
            
            elif key == ord('u'):
                self.depth_min = np.nanmin(self.depth_map)
                self.depth_max = np.nanmax(self.depth_map)
                self.depth_range = self.depth_max - self.depth_min
            
            elif key == ord('?') or key == ord('h'):
                self._print_help()
            
            if key != 255:
                mouse_pos = cv2.getWindowProperty(self.window_name, 0)
        
        cv2.destroyAllWindows()
        return self.depth_map
    
    def _print_help(self):
        """Print help text."""
        help_text = """
Depth Editor Controls:
  Left click/drag   - Draw with current tool
  Right click      - Sample depth value
  Mouse wheel      - Adjust brush size
  
  Modes:
    'b' - Brush (paint current value)
    'e' - Eraser (restore original)
    'i' - Interpolate (fill from boundaries)
    's' - Sample (click to pick value)
  
  Brush:
    '+'/'-' - Increase/decrease size
    '['/']' - Decrease/increase value
  
  Other:
    'z' - Undo
    'r' - Redo
    'f' - Flood fill at cursor
    'u' - Update colormap range
    'q' - Quit and save
    'ESC' - Quit without saving
    'h' - Show this help
"""
        print(help_text)
    
    def save(self, filepath):
        """Save edited depth map."""
        if filepath.endswith('.npy'):
            np.save(filepath, self.depth_map)
        else:
            disp = self.normalize_depth()
            colored = self.apply_colormap(disp)
            cv2.imwrite(filepath, colored)
        print(f"Saved depth map to {filepath}")


def edit_depth_interactive(depth_map, reference_image=None, confidence_map=None, 
                           output_path=None):
    """
    Interactive depth editing convenience function.
    
    Parameters:
        depth_map: Input depth map [H, W]
        reference_image: Optional reference image [H, W, 3]
        confidence_map: Optional confidence map [H, W]
        output_path: Optional path to save edited depth map
        
    Returns:
        edited_depth: Edited depth map, or None if canceled
    """
    editor = DepthEditor(depth_map, reference_image, confidence_map)
    
    print("Depth Editor")
    print("Press 'h' for help, 'ESC' to cancel, 'q' to finish")
    
    edited = editor.run()
    
    if edited is not None and output_path is not None:
        editor.save(output_path)
    
    return edited


class BatchDepthEditor:
    """
    Batch processing tool for editing multiple depth maps.
    
    Supports:
    - Sequential editing of depth maps
    - Applying the same edits to all frames
    - Copying edits from one frame to others
    - Propagation of edits across video sequence
    """
    
    def __init__(self, depth_maps, reference_images=None, confidence_maps=None):
        """
        Initialize batch editor.
        
        Parameters:
            depth_maps: List of depth maps [T, H, W]
            reference_images: Optional list of reference images [T, H, W, 3]
            confidence_maps: Optional list of confidence maps [T, H, W]
        """
        self.depth_maps = [d.copy() for d in depth_maps]
        self.reference_images = reference_images
        self.confidence_maps = confidence_maps
        
        self.current_index = 0
        self.num_frames = len(depth_maps)
        
        self.edit_masks = [np.zeros_like(d, dtype=bool) for d in depth_maps]
        self.edit_values = [np.zeros_like(d) for d in depth_maps]
        
        self.edits_complete = [False] * self.num_frames
    
    def edit_frame(self, index):
        """Edit a single frame."""
        if index < 0 or index >= self.num_frames:
            return
        
        self.current_index = index
        
        ref_img = self.reference_images[index] if self.reference_images else None
        conf_map = self.confidence_maps[index] if self.confidence_maps else None
        
        editor = DepthEditor(self.depth_maps[index], ref_img, conf_map)
        
        print(f"\nEditing frame {index+1}/{self.num_frames}")
        print("'n' - Next frame, 'p' - Previous frame, 'c' - Copy to all frames")
        print("'q' - Finish, 'ESC' - Cancel")
        
        edited = editor.run()
        
        if edited is not None:
            edit_mask = edited != self.depth_maps[index]
            self.edit_masks[index] = edit_mask
            self.edit_values[index] = edited
            self.depth_maps[index] = edited
            self.edits_complete[index] = True
            return True
        
        return False
    
    def copy_edits_to_all(self, source_index):
        """Copy edits from source frame to all other frames."""
        if not self.edits_complete[source_index]:
            print(f"Frame {source_index+1} has not been edited")
            return False
        
        source_mask = self.edit_masks[source_index]
        source_values = self.edit_values[source_index]
        
        for i in range(self.num_frames):
            if i == source_index:
                continue
            
            self.depth_maps[i][source_mask] = source_values[source_mask]
            self.edit_masks[i] = source_mask
            self.edit_values[i] = source_values
            self.edits_complete[i] = True
        
        print(f"Copied edits from frame {source_index+1} to all frames")
        return True
    
    def propagate_edits_temporal(self, source_index, forward=True, backward=True):
        """
        Propagate edits temporally using optical flow.
        
        Parameters:
            source_index: Source frame index
            forward: Propagate forward in time
            backward: Propagate backward in time
        """
        if not self.edits_complete[source_index]:
            print(f"Frame {source_index+1} has not been edited")
            return False
        
        from .video_temporal import estimate_optical_flow, warp_depth
        
        source_mask = self.edit_masks[source_index]
        source_values = self.edit_values[source_index]
        
        if forward:
            for i in range(source_index + 1, self.num_frames):
                if self.reference_images is None:
                    break
                
                flow = estimate_optical_flow(
                    self.reference_images[i-1], self.reference_images[i]
                )
                
                warped_mask = warp_depth(source_mask.astype(np.float32), flow) > 0.5
                warped_values = warp_depth(source_values, flow)
                
                self.depth_maps[i][warped_mask] = warped_values[warped_mask]
                self.edit_masks[i] = warped_mask
                self.edit_values[i] = warped_values
                self.edits_complete[i] = True
                
                source_mask = warped_mask
                source_values = warped_values
        
        if backward:
            source_mask = self.edit_masks[source_index]
            source_values = self.edit_values[source_index]
            
            for i in range(source_index - 1, -1, -1):
                if self.reference_images is None:
                    break
                
                flow = estimate_optical_flow(
                    self.reference_images[i+1], self.reference_images[i]
                )
                
                warped_mask = warp_depth(source_mask.astype(np.float32), flow) > 0.5
                warped_values = warp_depth(source_values, flow)
                
                self.depth_maps[i][warped_mask] = warped_values[warped_mask]
                self.edit_masks[i] = warped_mask
                self.edit_values[i] = warped_values
                self.edits_complete[i] = True
                
                source_mask = warped_mask
                source_values = warped_values
        
        print(f"Propagated edits from frame {source_index+1}")
        return True
    
    def run(self):
        """Run batch editing session."""
        print(f"\nBatch Depth Editor - {self.num_frames} frames")
        print("=" * 50)
        
        while True:
            print(f"\nCurrent frame: {self.current_index+1}/{self.num_frames}")
            print(f"Completed: {sum(self.edits_complete)}/{self.num_frames}")
            print("\nCommands:")
            print("  [index] - Edit specific frame")
            print("  'n'     - Next frame")
            print("  'p'     - Previous frame")
            print("  'c'     - Copy current edits to all frames")
            print("  't'     - Temporally propagate current edits")
            print("  's'     - Show status")
            print("  'q'     - Finish and save")
            print("  'ESC'   - Cancel")
            
            cmd = input("\nEnter command: ").strip().lower()
            
            if cmd == 'q':
                break
            elif cmd == '':
                continue
            elif cmd.isdigit():
                idx = int(cmd) - 1
                self.edit_frame(idx)
            elif cmd == 'n':
                self.edit_frame(min(self.current_index + 1, self.num_frames - 1))
            elif cmd == 'p':
                self.edit_frame(max(self.current_index - 1, 0))
            elif cmd == 'c':
                self.copy_edits_to_all(self.current_index)
            elif cmd == 't':
                self.propagate_edits_temporal(self.current_index)
            elif cmd == 's':
                print("\nStatus:")
                for i, complete in enumerate(self.edits_complete):
                    mark = '✓' if complete else ' '
                    print(f"  Frame {i+1}: [{mark}]")
        
        return self.depth_maps
    
    def save_all(self, output_dir, prefix='depth_edited_'):
        """Save all edited depth maps."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        for i, depth in enumerate(self.depth_maps):
            filepath = os.path.join(output_dir, f"{prefix}{i:04d}.npy")
            np.save(filepath, depth)
            
            disp = (depth - np.nanmin(depth)) / (np.nanmax(depth) - np.nanmin(depth) + 1e-8)
            disp = (disp * 255).astype(np.uint8)
            colored = cv2.applyColorMap(disp, cv2.COLORMAP_JET)
            filepath_img = os.path.join(output_dir, f"{prefix}{i:04d}.png")
            cv2.imwrite(filepath_img, colored)
        
        print(f"Saved {len(self.depth_maps)} depth maps to {output_dir}")
