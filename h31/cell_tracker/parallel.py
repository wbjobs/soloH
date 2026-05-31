import numpy as np
from typing import List, Dict, Tuple, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from functools import partial
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


class ParallelProcessor:
    def __init__(self,
                 num_workers: int = 4,
                 use_threads: bool = True,
                 show_progress: bool = True):
        self.num_workers = num_workers
        self.use_threads = use_threads
        self.show_progress = show_progress
        
        if use_threads:
            self.executor_class = ThreadPoolExecutor
        else:
            self.executor_class = ProcessPoolExecutor
    
    def process_frames(self,
                        frames: np.ndarray,
                        process_func: Callable[[np.ndarray, Any], Any],
                        func_args: Optional[dict] = None,
                        frame_indices: Optional[List[int]] = None) -> List[Any]:
        if func_args is None:
            func_args = {}
        
        if frame_indices is None:
            frame_indices = list(range(frames.shape[0]))
        
        frames_to_process = [frames[i] for i in frame_indices]
        results = [None] * len(frames_to_process)
        
        with self.executor_class(max_workers=self.num_workers) as executor:
            futures = []
            
            for idx, frame in enumerate(frames_to_process):
                future = executor.submit(
                    self._process_single_frame,
                    idx,
                    frame,
                    process_func,
                    func_args
                )
                futures.append(future)
            
            if self.show_progress:
                futures_iterator = tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Processing frames"
                )
            else:
                futures_iterator = as_completed(futures)
            
            for future in futures_iterator:
                idx, result = future.result()
                results[idx] = result
        
        return results
    
    @staticmethod
    def _process_single_frame(idx: int,
                               frame: np.ndarray,
                               process_func: Callable,
                               func_args: dict) -> Tuple[int, Any]:
        result = process_func(frame, **func_args)
        return idx, result
    
    def segment_frames_parallel(self,
                                  segmenter: object,
                                  frames: np.ndarray,
                                  frame_indices: Optional[List[int]] = None) -> np.ndarray:
        if frame_indices is None:
            frame_indices = list(range(frames.shape[0]))
        
        logger.info(f"Segmenting {len(frame_indices)} frames with {self.num_workers} workers")
        
        process_func = segmenter.segment_image
        results = self.process_frames(
            frames=frames,
            process_func=process_func,
            frame_indices=frame_indices
        )
        
        result_shape = (len(frame_indices), frames.shape[-2], frames.shape[-1])
        masks = np.zeros(result_shape, dtype=np.int32)
        
        for i, mask in enumerate(results):
            if mask is not None:
                masks[i] = mask
        
        return masks
    
    def extract_features_parallel(self,
                                     extractor: object,
                                     image_stack: np.ndarray,
                                     masks: np.ndarray,
                                     channel: int = 0,
                                     frame_indices: Optional[List[int]] = None) -> Dict[int, Dict[int, dict]]:
        if frame_indices is None:
            frame_indices = list(range(image_stack.shape[0]))
        
        logger.info(f"Extracting features for {len(frame_indices)} frames with {self.num_workers} workers")
        
        if image_stack.ndim == 4:
            images = image_stack[:, channel, :, :]
        elif image_stack.ndim == 3:
            images = image_stack
        else:
            raise ValueError(f"Unsupported image stack shape: {image_stack.shape}")
        
        def process_frame(frame_data):
            frame_idx, image, mask = frame_data
            features = {}
            
            from .utils import extract_mask_properties
            morph_props = extract_mask_properties(mask)
            
            labels = np.unique(mask)
            labels = labels[labels != 0]
            
            for label in labels:
                cell_mask = mask == label
                cell_pixels = image[cell_mask]
                
                if len(cell_pixels) == 0:
                    continue
                
                label_features = {}
                
                if label in morph_props:
                    mp = morph_props[label]
                    label_features['morphology'] = {
                        'area': mp.get('area', 0),
                        'centroid': mp.get('centroid', (0, 0)),
                        'eccentricity': mp.get('eccentricity', 0),
                        'solidity': mp.get('solidity', 0),
                        'extent': mp.get('extent', 0),
                        'major_axis_length': mp.get('major_axis_length', 0),
                        'minor_axis_length': mp.get('minor_axis_length', 0),
                        'perimeter': mp.get('perimeter', 0),
                        'aspect_ratio': mp.get('major_axis_length', 1) / max(mp.get('minor_axis_length', 1), 1),
                        'circularity': (4 * np.pi * mp.get('area', 0)) / max(mp.get('perimeter', 1) ** 2, 1),
                    }
                
                label_features['fluorescence'] = {
                    'mean': np.mean(cell_pixels),
                    'median': np.median(cell_pixels),
                    'max': np.max(cell_pixels),
                    'min': np.min(cell_pixels),
                    'std': np.std(cell_pixels),
                    'sum': np.sum(cell_pixels),
                    'n_pixels': len(cell_pixels),
                }
                
                features[label] = label_features
            
            return frame_idx, features
        
        frame_data_list = [(idx, images[idx], masks[idx]) for idx in frame_indices]
        
        with self.executor_class(max_workers=self.num_workers) as executor:
            futures = [executor.submit(process_frame, fd) for fd in frame_data_list]
            
            if self.show_progress:
                futures_iterator = tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Extracting features"
                )
            else:
                futures_iterator = as_completed(futures)
            
            all_features: Dict[int, Dict[int, dict]] = {}
            for future in futures_iterator:
                frame_idx, features = future.result()
                all_features[frame_idx] = features
        
        return all_features
    
    def evaluate_segmentation_parallel(self,
                                        pred_masks: np.ndarray,
                                        gt_masks: np.ndarray,
                                        evaluator: Optional[object] = None,
                                        frame_indices: Optional[List[int]] = None) -> Dict[int, dict]:
        if frame_indices is None:
            frame_indices = list(range(pred_masks.shape[0]))
        
        logger.info(f"Evaluating segmentation for {len(frame_indices)} frames with {self.num_workers} workers")
        
        from .evaluation import compute_iou_binary, compute_dice_binary, compute_precision_recall
        
        def process_frame(frame_data):
            frame_idx, pred, gt = frame_data
            
            pred_binary = pred > 0
            gt_binary = gt > 0
            
            iou = compute_iou_binary(pred_binary, gt_binary)
            dice = compute_dice_binary(pred_binary, gt_binary)
            precision, recall, f1 = compute_precision_recall(pred, gt, 0.5)
            
            metrics = {
                'iou': iou,
                'dice': dice,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'n_pred': len(np.unique(pred)[np.unique(pred) != 0]),
                'n_gt': len(np.unique(gt)[np.unique(gt) != 0]),
            }
            
            return frame_idx, metrics
        
        frame_data_list = [(idx, pred_masks[idx], gt_masks[idx]) for idx in frame_indices]
        
        with self.executor_class(max_workers=self.num_workers) as executor:
            futures = [executor.submit(process_frame, fd) for fd in frame_data_list]
            
            if self.show_progress:
                futures_iterator = tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Evaluating segmentation"
                )
            else:
                futures_iterator = as_completed(futures)
            
            all_metrics: Dict[int, dict] = {}
            for future in futures_iterator:
                frame_idx, metrics = future.result()
                all_metrics[frame_idx] = metrics
        
        return all_metrics
    
    def batch_process(self,
                       items: List[Any],
                       process_func: Callable[[Any], Any],
                       batch_size: Optional[int] = None) -> List[Any]:
        if batch_size is None:
            batch_size = max(1, len(items) // self.num_workers)
        
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        
        logger.info(f"Processing {len(items)} items in {len(batches)} batches with {self.num_workers} workers")
        
        def process_batch(batch):
            return [process_func(item) for item in batch]
        
        with self.executor_class(max_workers=self.num_workers) as executor:
            futures = [executor.submit(process_batch, batch) for batch in batches]
            
            if self.show_progress:
                futures_iterator = tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Processing batches"
                )
            else:
                futures_iterator = as_completed(futures)
            
            results = []
            for future in futures_iterator:
                batch_results = future.result()
                results.extend(batch_results)
        
        return results
    
    def map(self, func: Callable, iterable, **kwargs) -> List[Any]:
        with self.executor_class(max_workers=self.num_workers) as executor:
            if self.show_progress:
                results = list(tqdm(
                    executor.map(func, iterable, **kwargs),
                    total=len(iterable),
                    desc="Processing"
                ))
            else:
                results = list(executor.map(func, iterable, **kwargs))
        
        return results
    
    def starmap(self, func: Callable, iterable, **kwargs) -> List[Any]:
        with self.executor_class(max_workers=self.num_workers) as executor:
            if self.show_progress:
                results = list(tqdm(
                    executor.starmap(func, iterable, **kwargs),
                    total=len(iterable),
                    desc="Processing"
                ))
            else:
                results = list(executor.starmap(func, iterable, **kwargs))
        
        return results


def parallel_segmentation(segmenter: object,
                            frames: np.ndarray,
                            num_workers: int = 4,
                            use_threads: bool = True) -> np.ndarray:
    processor = ParallelProcessor(
        num_workers=num_workers,
        use_threads=use_threads,
        show_progress=True
    )
    return processor.segment_frames_parallel(segmenter, frames)


def parallel_feature_extraction(extractor: object,
                                  image_stack: np.ndarray,
                                  masks: np.ndarray,
                                  channel: int = 0,
                                  num_workers: int = 4,
                                  use_threads: bool = True) -> Dict[int, Dict[int, dict]]:
    processor = ParallelProcessor(
        num_workers=num_workers,
        use_threads=use_threads,
        show_progress=True
    )
    return processor.extract_features_parallel(extractor, image_stack, masks, channel)
