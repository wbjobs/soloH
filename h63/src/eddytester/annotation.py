import numpy as np
import json
import os
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
from .data_io import EddyCurrentData, DataLoader


@dataclass
class Annotation:
    sample_id: str
    has_crack: bool
    crack_depth: Optional[float] = None
    crack_length: Optional[float] = None
    crack_position: Optional[float] = None
    crack_start_idx: Optional[int] = None
    crack_end_idx: Optional[int] = None
    confidence: float = 1.0
    notes: str = ""
    annotator: str = ""
    timestamp: str = ""


@dataclass
class AnnotatedDataset:
    annotations: List[Annotation] = field(default_factory=list)
    labeled_data: List[Tuple[EddyCurrentData, Optional[Annotation]]] = field(default_factory=list)
    unlabeled_data: List[EddyCurrentData] = field(default_factory=list)

    def save(self, filepath: str) -> None:
        save_data = {
            'annotations': [asdict(a) for a in self.annotations],
            'labeled_ids': [],
            'unlabeled_ids': [],
        }
        
        labeled_dir = os.path.join(os.path.dirname(filepath), 'labeled')
        unlabeled_dir = os.path.join(os.path.dirname(filepath), 'unlabeled')
        os.makedirs(labeled_dir, exist_ok=True)
        os.makedirs(unlabeled_dir, exist_ok=True)
        
        for i, (data, annot) in enumerate(self.labeled_data):
            data_id = f"labeled_{i:05d}"
            data_path = os.path.join(labeled_dir, f"{data_id}.npy")
            DataLoader.save(data, data_path)
            save_data['labeled_ids'].append({
                'id': data_id,
                'path': data_path,
                'annotation_idx': i if annot else None
            })
        
        for i, data in enumerate(self.unlabeled_data):
            data_id = f"unlabeled_{i:05d}"
            data_path = os.path.join(unlabeled_dir, f"{data_id}.npy")
            DataLoader.save(data, data_path)
            save_data['unlabeled_ids'].append({
                'id': data_id,
                'path': data_path
            })
        
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)

    def load(self, filepath: str) -> 'AnnotatedDataset':
        with open(filepath, 'r') as f:
            save_data = json.load(f)
        
        self.annotations = [Annotation(**a) for a in save_data.get('annotations', [])]
        
        for item in save_data.get('labeled_ids', []):
            data = DataLoader.load(item['path'])
            annot = None
            if item['annotation_idx'] is not None:
                annot = self.annotations[item['annotation_idx']]
            self.labeled_data.append((data, annot))
        
        for item in save_data.get('unlabeled_ids', []):
            data = DataLoader.load(item['path'])
            self.unlabeled_data.append(data)
        
        return self


class AnnotationTool:
    def __init__(self, output_dir: str = "annotations"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.dataset = AnnotatedDataset()
        self.current_index = 0

    def add_unlabeled_data(self, data: Union[EddyCurrentData, List[EddyCurrentData]]) -> None:
        if isinstance(data, list):
            self.dataset.unlabeled_data.extend(data)
        else:
            self.dataset.unlabeled_data.append(data)

    def add_labeled_data(self, data: EddyCurrentData, annotation: Optional[Annotation] = None) -> None:
        self.dataset.labeled_data.append((data, annotation))
        if annotation is not None:
            self.dataset.annotations.append(annotation)

    def annotate_interactive(self, max_samples: Optional[int] = None) -> None:
        if not self.dataset.unlabeled_data:
            print("No unlabeled data to annotate.")
            return

        n_samples = len(self.dataset.unlabeled_data)
        if max_samples is not None:
            n_samples = min(n_samples, max_samples)

        print(f"\n=== Annotation Mode ===")
        print(f"Total unlabeled samples: {len(self.dataset.unlabeled_data)}")
        print(f"Will annotate: {n_samples} samples")
        print("Enter 'q' at any time to quit.\n")

        for i in range(n_samples):
            self.current_index = i
            data = self.dataset.unlabeled_data[i]
            
            print(f"\n--- Sample {i+1}/{n_samples} ---")
            self._display_sample_info(data)
            
            annotation = self._get_user_annotation(data, sample_id=f"sample_{i:05d}")
            
            if annotation is None:
                print("Skipping this sample...")
                continue
            
            self.dataset.labeled_data.append((data, annotation))
            self.dataset.annotations.append(annotation)
            
            print(f"Annotation saved: has_crack={annotation.has_crack}")

        print(f"\nAnnotation completed. Labeled {len(self.dataset.labeled_data)} samples.")

    def _display_sample_info(self, data: EddyCurrentData) -> None:
        print(f"Data shape: {data.impedance.shape}")
        print(f"Frequencies: {data.frequencies}")
        if data.positions is not None:
            print(f"Position range: [{data.positions.min():.4f}, {data.positions.max():.4f}]")
        
        amp = np.abs(data.impedance)
        phase = np.angle(data.impedance)
        print(f"Amplitude range: [{amp.min():.4f}, {amp.max():.4f}]")
        print(f"Phase range (rad): [{phase.min():.4f}, {phase.max():.4f}]")

    def _get_user_annotation(self, data: EddyCurrentData, sample_id: str) -> Optional[Annotation]:
        try:
            response = input("\nHas crack? (y/n/q=quit/s=skip): ").lower().strip()
            
            if response == 'q':
                return None
            if response == 's':
                return None
            if response not in ['y', 'n']:
                print("Invalid input. Please enter y, n, q, or s.")
                return self._get_user_annotation(data, sample_id)
            
            has_crack = response == 'y'
            
            annotation = Annotation(
                sample_id=sample_id,
                has_crack=has_crack,
            )
            
            if has_crack:
                crack_depth = input("Crack depth (mm, optional): ").strip()
                if crack_depth:
                    annotation.crack_depth = float(crack_depth) / 1000
                
                crack_length = input("Crack length (mm, optional): ").strip()
                if crack_length:
                    annotation.crack_length = float(crack_length) / 1000
                
                crack_position = input("Crack position (mm, optional): ").strip()
                if crack_position:
                    annotation.crack_position = float(crack_position) / 1000
                
                crack_indices = input("Crack start/end indices (start,end, optional): ").strip()
                if crack_indices:
                    start, end = map(int, crack_indices.split(','))
                    annotation.crack_start_idx = start
                    annotation.crack_end_idx = end
            
            confidence = input("Annotation confidence (0-1, default=1.0): ").strip()
            if confidence:
                annotation.confidence = float(confidence)
            
            notes = input("Notes (optional): ").strip()
            if notes:
                annotation.notes = notes
            
            annotator = input("Annotator name (optional): ").strip()
            if annotator:
                annotation.annotator = annotator
            
            from datetime import datetime
            annotation.timestamp = datetime.now().isoformat()
            
            return annotation
            
        except KeyboardInterrupt:
            return None
        except Exception as e:
            print(f"Error in annotation: {e}")
            return None

    def auto_annotate(self, identifier, confidence_threshold: float = 0.8) -> int:
        if not self.dataset.unlabeled_data:
            return 0
        
        auto_annotated = 0
        
        for data in self.dataset.unlabeled_data[:]:
            result = identifier.identify(data)
            
            if result['confidence'] >= confidence_threshold:
                annotation = Annotation(
                    sample_id=f"auto_{len(self.dataset.annotations):05d}",
                    has_crack=result['has_crack'],
                    crack_depth=result.get('depth'),
                    crack_length=result.get('length'),
                    crack_position=result.get('position'),
                    confidence=result['confidence'],
                    notes=f"Auto-annotated with confidence {result['confidence']:.3f}",
                    annotator="auto",
                    timestamp=str(np.datetime64('now'))
                )
                
                self.dataset.labeled_data.append((data, annotation))
                self.dataset.annotations.append(annotation)
                self.dataset.unlabeled_data.remove(data)
                auto_annotated += 1
        
        print(f"Auto-annotated {auto_annotated} samples with confidence >= {confidence_threshold}")
        return auto_annotated

    def save_annotations(self, filename: str = "annotations.json") -> None:
        filepath = self.output_dir / filename
        self.dataset.save(str(filepath))
        print(f"Annotations saved to {filepath}")

    def load_annotations(self, filename: str = "annotations.json") -> None:
        filepath = self.output_dir / filename
        if filepath.exists():
            self.dataset.load(str(filepath))
            print(f"Loaded {len(self.dataset.annotations)} annotations, "
                  f"{len(self.dataset.labeled_data)} labeled samples, "
                  f"{len(self.dataset.unlabeled_data)} unlabeled samples")
        else:
            print(f"No annotations file found at {filepath}")

    def get_training_data(self) -> Tuple[List[EddyCurrentData], List[Annotation]]:
        labeled_with_annotations = [(d, a) for d, a in self.dataset.labeled_data if a is not None]
        
        data_list = [d for d, a in labeled_with_annotations]
        annotations = [a for d, a in labeled_with_annotations]
        
        for i, (data, annot) in enumerate(data_list):
            if annot.has_crack:
                n_points = data.impedance.shape[0]
                labels = np.zeros((n_points, 4))
                
                if annot.crack_start_idx is not None and annot.crack_end_idx is not None:
                    start = annot.crack_start_idx
                    end = annot.crack_end_idx
                else:
                    center = int(n_points * (annot.crack_position or 0.5))
                    half_width = int(n_points * 0.1)
                    start = max(0, center - half_width)
                    end = min(n_points, center + half_width)
                
                labels[start:end, 0] = 1
                labels[:, 1] = annot.crack_depth or 0
                labels[:, 2] = annot.crack_length or 0
                labels[:, 3] = annot.crack_position or 0.5
                
                data_list[i] = EddyCurrentData(
                    impedance=data.impedance,
                    frequencies=data.frequencies,
                    positions=data.positions,
                    labels=labels,
                    metadata=data.metadata
                )
        
        return data_list, annotations

    def get_statistics(self) -> Dict:
        total_annotations = len(self.dataset.annotations)
        has_crack = sum(1 for a in self.dataset.annotations if a.has_crack)
        no_crack = total_annotations - has_crack
        
        auto = sum(1 for a in self.dataset.annotations if a.annotator == "auto")
        manual = total_annotations - auto
        
        avg_confidence = np.mean([a.confidence for a in self.dataset.annotations]) if total_annotations > 0 else 0
        
        depths = [a.crack_depth for a in self.dataset.annotations if a.has_crack and a.crack_depth is not None]
        lengths = [a.crack_length for a in self.dataset.annotations if a.has_crack and a.crack_length is not None]
        
        return {
            'total_annotations': total_annotations,
            'has_crack': has_crack,
            'no_crack': no_crack,
            'auto_annotated': auto,
            'manual_annotated': manual,
            'avg_confidence': avg_confidence,
            'unlabeled_count': len(self.dataset.unlabeled_data),
            'depth_stats': {
                'count': len(depths),
                'mean': np.mean(depths) * 1000 if depths else 0,
                'min': np.min(depths) * 1000 if depths else 0,
                'max': np.max(depths) * 1000 if depths else 0,
            } if depths else {},
            'length_stats': {
                'count': len(lengths),
                'mean': np.mean(lengths) * 1000 if lengths else 0,
                'min': np.min(lengths) * 1000 if lengths else 0,
                'max': np.max(lengths) * 1000 if lengths else 0,
            } if lengths else {},
        }

    def print_statistics(self) -> None:
        stats = self.get_statistics()
        print("\n=== Annotation Statistics ===")
        print(f"Total annotations: {stats['total_annotations']}")
        print(f"  - Has crack: {stats['has_crack']}")
        print(f"  - No crack: {stats['no_crack']}")
        print(f"  - Auto-annotated: {stats['auto_annotated']}")
        print(f"  - Manual: {stats['manual_annotated']}")
        print(f"Average confidence: {stats['avg_confidence']:.3f}")
        print(f"Unlabeled samples remaining: {stats['unlabeled_count']}")
        
        if stats['depth_stats']:
            print(f"\nCrack depth (mm):")
            print(f"  Count: {stats['depth_stats']['count']}")
            print(f"  Mean: {stats['depth_stats']['mean']:.2f}")
            print(f"  Range: [{stats['depth_stats']['min']:.2f}, {stats['depth_stats']['max']:.2f}]")
        
        if stats['length_stats']:
            print(f"\nCrack length (mm):")
            print(f"  Count: {stats['length_stats']['count']}")
            print(f"  Mean: {stats['length_stats']['mean']:.2f}")
            print(f"  Range: [{stats['length_stats']['min']:.2f}, {stats['length_stats']['max']:.2f}]")
        print()
