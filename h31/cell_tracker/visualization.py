import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class NapariVisualizer:
    def __init__(self):
        self.viewer = None
    
    def _ensure_viewer(self):
        if self.viewer is None:
            try:
                import napari
                self.viewer = napari.Viewer()
            except ImportError:
                raise ImportError("napari is not installed. Please install it with: pip install napari")
        return self.viewer
    
    def add_image(self, 
                  image_stack: np.ndarray, 
                  name: str = "Image",
                  channel: int = 0,
                  colormap: str = "gray",
                  contrast_limits: Optional[Tuple[float, float]] = None) -> None:
        viewer = self._ensure_viewer()
        
        if image_stack.ndim == 4:
            images = image_stack[:, channel, :, :]
        elif image_stack.ndim == 3:
            images = image_stack
        else:
            images = image_stack
        
        viewer.add_image(
            images,
            name=name,
            colormap=colormap,
            contrast_limits=contrast_limits,
            interpolation='nearest'
        )
    
    def add_segmentation(self, 
                         masks: np.ndarray, 
                         name: str = "Segmentation",
                         opacity: float = 0.5) -> None:
        viewer = self._ensure_viewer()
        
        viewer.add_labels(
            masks,
            name=name,
            opacity=opacity
        )
    
    def add_tracks(self,
                    tracker: object,
                    masks: np.ndarray,
                    name: str = "Tracks",
                    show_track_id: bool = True) -> None:
        viewer = self._ensure_viewer()
        
        track_overlay = np.zeros_like(masks, dtype=np.int32)
        
        for track_id, track in tracker.tracks.items():
            for frame, label in zip(track.frames, track.labels):
                if frame < masks.shape[0]:
                    track_overlay[frame][masks[frame] == label] = track_id
        
        viewer.add_labels(
            track_overlay,
            name=name,
            opacity=0.7
        )
        
        self._add_track_lines(tracker, name + "_lines")
        
        if show_track_id:
            self._add_track_labels(tracker, name + "_labels")
    
    def _add_track_lines(self, tracker: object, name: str) -> None:
        viewer = self._ensure_viewer()
        
        tracks_data = []
        
        for track_id, track in tracker.tracks.items():
            for i, frame in enumerate(track.frames):
                y, x = track.centroids[i]
                tracks_data.append([track_id, frame, y, x])
        
        if len(tracks_data) > 0:
            tracks_data = np.array(tracks_data)
            
            viewer.add_tracks(
                tracks_data,
                name=name,
                colormap='hsv',
                tail_length=10,
                tail_width=2
            )
    
    def _add_track_labels(self, tracker: object, name: str) -> None:
        viewer = self._ensure_viewer()
        
        points_data = []
        text_data = []
        
        for track_id, track in tracker.tracks.items():
            if len(track.frames) == 0:
                continue
            
            mid_idx = len(track.frames) // 2
            frame = track.frames[mid_idx]
            y, x = track.centroids[mid_idx]
            
            points_data.append([frame, y, x])
            text_data.append(str(track_id))
        
        if len(points_data) > 0:
            points_data = np.array(points_data)
            
            viewer.add_points(
                points_data,
                name=name,
                text=text_data,
                size=0,
                text_color='white',
                text_size=8
            )
    
    def add_division_events(self,
                             division_events: List[dict],
                             tracker: object,
                             masks: np.ndarray,
                             name: str = "Division Events") -> None:
        viewer = self._ensure_viewer()
        
        division_mask = np.zeros_like(masks, dtype=np.int32)
        points_data = []
        
        for event in division_events:
            frame = event['frame']
            parent_id = event['parent_id']
            children_ids = event['children_ids']
            
            if frame >= masks.shape[0]:
                continue
            
            if parent_id in tracker.tracks:
                parent_track = tracker.tracks[parent_id]
                if frame in parent_track.frames:
                    idx = parent_track.frames.index(frame)
                    parent_label = parent_track.labels[idx]
                    division_mask[frame][masks[frame] == parent_label] = 1
            
            for child_id in children_ids:
                if child_id in tracker.tracks and frame + 1 < masks.shape[0]:
                    child_track = tracker.tracks[child_id]
                    if frame + 1 in child_track.frames:
                        idx = child_track.frames.index(frame + 1)
                        child_label = child_track.labels[idx]
                        division_mask[frame + 1][masks[frame + 1] == child_label] = 2
            
            y, x = event['parent_centroid']
            points_data.append([frame, y, x])
        
        division_colormap = np.array([
            [0, 0, 0, 0],
            [255, 0, 0, 255],
            [0, 255, 0, 255]
        ])
        
        viewer.add_labels(
            division_mask,
            name=name,
            opacity=0.8,
            color=division_colormap
        )
        
        if len(points_data) > 0:
            points_data = np.array(points_data)
            viewer.add_points(
                points_data,
                name=name + "_markers",
                face_color='red',
                edge_color='yellow',
                size=10,
                symbol='ring'
            )
    
    def add_fluorescence_overlay(self,
                                  fluo_timeseries: pd.DataFrame,
                                  masks: np.ndarray,
                                  tracker: object,
                                  name: str = "Fluorescence",
                                  colormap: str = "viridis") -> None:
        viewer = self._ensure_viewer()
        
        fluo_mask = np.zeros_like(masks, dtype=np.float32)
        
        track_ids = fluo_timeseries['track_id'].unique()
        
        for track_id in track_ids:
            track_data = fluo_timeseries[fluo_timeseries['track_id'] == track_id]
            
            for _, row in track_data.iterrows():
                frame = int(row['frame'])
                label = int(row['label'])
                fluo_mean = row['fluo_mean']
                
                if frame < masks.shape[0]:
                    fluo_mask[frame][masks[frame] == label] = fluo_mean
        
        viewer.add_image(
            fluo_mask,
            name=name,
            colormap=colormap,
            opacity=0.6,
            blending='additive'
        )
    
    def visualize_all(self,
                       image_stack: np.ndarray,
                       masks: np.ndarray,
                       tracker: object,
                       division_events: Optional[List[dict]] = None,
                       fluo_timeseries: Optional[pd.DataFrame] = None) -> None:
        self.add_image(image_stack, name="Raw Image")
        self.add_segmentation(masks, name="Segmentation")
        self.add_tracks(tracker, masks, name="Tracks")
        
        if division_events is not None and len(division_events) > 0:
            self.add_division_events(division_events, tracker, masks)
        
        if fluo_timeseries is not None and not fluo_timeseries.empty:
            self.add_fluorescence_overlay(fluo_timeseries, masks, tracker)
    
    def show(self) -> None:
        if self.viewer is not None:
            try:
                import napari
                napari.run()
            except Exception as e:
                logger.warning(f"Failed to run napari: {e}")
    
    def close(self) -> None:
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None
    
    def save_screenshot(self, filepath: str, canvas_only: bool = True) -> None:
        if self.viewer is not None:
            filepath = str(filepath)
            if canvas_only:
                self.viewer.window.qt_viewer.screenshot(filepath)
            else:
                self.viewer.screenshot(filepath)
            logger.info(f"Saved screenshot to {filepath}")
    
    def export_animation(self, 
                          filepath: str,
                          fps: int = 10,
                          quality: int = 7) -> None:
        if self.viewer is None:
            raise RuntimeError("Viewer not initialized")
        
        try:
            from napari_animation import Animation
            
            animation = Animation(self.viewer)
            
            n_frames = self.viewer.dims.nsteps[0] if hasattr(self.viewer.dims, 'nsteps') else 10
            
            for frame in range(n_frames):
                self.viewer.dims.current_step = (frame,)
                animation.capture_keyframe(steps=1)
            
            animation.animate(filepath, fps=fps, quality=quality)
            logger.info(f"Exported animation to {filepath}")
            
        except ImportError:
            logger.warning("napari-animation not installed. Cannot export animation.")
            logger.info("Install with: pip install napari-animation")
        except Exception as e:
            logger.error(f"Failed to export animation: {e}")


def plot_trajectories(tracker: object, 
                      output_file: Optional[str] = None,
                      min_length: int = 10) -> None:
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    for track_id, track in tracker.tracks.items():
        if len(track) < min_length:
            continue
        
        centroids = np.array(track.centroids)
        ax.plot(centroids[:, 1], centroids[:, 0], '-', linewidth=1, alpha=0.7)
        ax.plot(centroids[0, 1], centroids[0, 0], 'o', markersize=3, alpha=0.7)
    
    ax.set_aspect('equal')
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')
    ax.set_title(f'Cell Trajectories (n={len([t for t in tracker.tracks.values() if len(t) >= min_length])})')
    ax.invert_yaxis()
    
    if output_file is not None:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"Saved trajectory plot to {output_file}")
    
    plt.close(fig)


def plot_fluorescence_timeseries(timeseries_df: pd.DataFrame,
                                  output_file: Optional[str] = None,
                                  track_ids: Optional[List[int]] = None,
                                  max_tracks: int = 10) -> None:
    import matplotlib.pyplot as plt
    
    if track_ids is None:
        track_counts = timeseries_df.groupby('track_id').size()
        track_ids = track_counts.sort_values(ascending=False).head(max_tracks).index.tolist()
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    for track_id in track_ids:
        track_data = timeseries_df[timeseries_df['track_id'] == track_id].sort_values('frame')
        
        axes[0].plot(track_data['frame'], track_data['fluo_mean'], 
                    '-', linewidth=1.5, label=f'Track {track_id}')
        axes[1].plot(track_data['frame'], track_data['area'], 
                    '-', linewidth=1.5, label=f'Track {track_id}')
    
    axes[0].set_ylabel('Mean Fluorescence')
    axes[0].set_title('Fluorescence Intensity and Area Timeseries')
    axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    axes[0].grid(True, alpha=0.3)
    
    axes[1].set_xlabel('Frame')
    axes[1].set_ylabel('Cell Area (pixels)')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_file is not None:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"Saved fluorescence timeseries plot to {output_file}")
    
    plt.close(fig)


def plot_division_timeline(division_events: List[dict],
                            output_file: Optional[str] = None,
                            max_frame: Optional[int] = None) -> None:
    import matplotlib.pyplot as plt
    
    if len(division_events) == 0:
        logger.info("No division events to plot")
        return
    
    fig, ax = plt.subplots(figsize=(12, 4))
    
    frames = [event['frame'] for event in division_events]
    
    if max_frame is None:
        max_frame = max(frames) + 10
    
    ax.hist(frames, bins=range(0, max_frame, max(1, max_frame // 20)),
            edgecolor='black', alpha=0.7)
    
    ax.set_xlabel('Frame')
    ax.set_ylabel('Number of Divisions')
    ax.set_title(f'Division Event Timeline (n={len(division_events)} total)')
    ax.grid(True, alpha=0.3, axis='y')
    
    for event in division_events:
        frame = event['frame']
        y_pos = 0.5
        ax.annotate(f"{event['parent_id']}", 
                   (frame, y_pos),
                   fontsize=8, ha='center', va='bottom',
                   rotation=90)
    
    plt.tight_layout()
    
    if output_file is not None:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"Saved division timeline plot to {output_file}")
    
    plt.close(fig)


def plot_evaluation_metrics(evaluation_results: dict,
                             output_file: Optional[str] = None) -> None:
    import matplotlib.pyplot as plt
    
    if 'per_frame' not in evaluation_results:
        logger.warning("No per-frame metrics available for plotting")
        return
    
    per_frame = evaluation_results['per_frame']
    
    frames = sorted(per_frame.keys())
    ious = [per_frame[f]['iou'] for f in frames]
    f1s = [per_frame[f]['f1'] for f in frames]
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    axes[0].plot(frames, ious, 'b-', linewidth=2)
    axes[0].fill_between(frames, ious, alpha=0.3)
    axes[0].set_ylabel('IoU')
    axes[0].set_title('Segmentation Quality Over Time')
    axes[0].set_ylim(0, 1)
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(frames, f1s, 'g-', linewidth=2)
    axes[1].fill_between(frames, f1s, alpha=0.3)
    axes[1].set_xlabel('Frame')
    axes[1].set_ylabel('F1 Score')
    axes[1].set_ylim(0, 1)
    axes[1].grid(True, alpha=0.3)
    
    mean_iou = evaluation_results.get('mean_iou', np.mean(ious))
    mean_f1 = evaluation_results.get('mean_f1', np.mean(f1s))
    
    axes[0].axhline(mean_iou, color='red', linestyle='--', 
                   label=f'Mean: {mean_iou:.3f}')
    axes[1].axhline(mean_f1, color='red', linestyle='--', 
                   label=f'Mean: {mean_f1:.3f}')
    
    axes[0].legend()
    axes[1].legend()
    
    plt.tight_layout()
    
    if output_file is not None:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"Saved evaluation metrics plot to {output_file}")
    
    plt.close(fig)
