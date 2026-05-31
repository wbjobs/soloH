import numpy as np
from typing import Optional, Tuple, List, Dict, Union, Callable, Generator
import warnings
from collections import deque
import time
import json
from datetime import datetime

from .preprocessing import Preprocessor, BearingFaultFrequency
from .feature_extraction import FeatureExtractor
from .classifier import BearingClassifier, FAULT_TYPES, SEVERITY_LEVELS
from .rul_prediction import RULPredictor
from .explainability import FeatureExplainer


class SlidingWindowBuffer:
    """
    滑动窗口缓冲区 - 用于流式数据处理
    
    维护一个固定大小的缓冲区，新数据到来时自动滑动。
    """
    
    def __init__(self, window_size: int, step_size: Optional[int] = None):
        """
        Args:
            window_size: 窗口大小（样本点数）
            step_size: 步长（每次滑动的样本点数），None则使用window_size
        """
        self.window_size = window_size
        self.step_size = step_size or window_size
        self.buffer: deque = deque(maxlen=window_size)
        self.samples_since_last_output = 0
    
    def update(self, new_data: np.ndarray) -> List[np.ndarray]:
        """
        更新缓冲区，返回可用于处理的窗口
        
        Args:
            new_data: 新数据点 (n_samples, n_channels) 或 (n_samples,)
        
        Returns:
            可处理的窗口列表
        """
        if new_data.ndim == 1:
            new_data = new_data.reshape(-1, 1)
        
        windows = []
        
        for i in range(len(new_data)):
            self.buffer.append(new_data[i])
            self.samples_since_last_output += 1
            
            if len(self.buffer) >= self.window_size and self.samples_since_last_output >= self.step_size:
                window = np.array(self.buffer)
                windows.append(window)
                self.samples_since_last_output = 0
        
        return windows
    
    def is_full(self) -> bool:
        """缓冲区是否已满"""
        return len(self.buffer) >= self.window_size
    
    def clear(self) -> None:
        """清空缓冲区"""
        self.buffer.clear()
        self.samples_since_last_output = 0
    
    def get_current(self) -> Optional[np.ndarray]:
        """获取当前缓冲区内容"""
        if len(self.buffer) > 0:
            return np.array(self.buffer)
        return None


class StreamingDiagnostics:
    """
    流式故障诊断系统
    
    支持：
    - 滑动窗口实时处理
    - 在线故障检测与分类
    - 剩余寿命预测
    - 结果平滑与趋势分析
    - 告警触发
    """
    
    def __init__(self, fs: float,
                 window_size: int,
                 step_size: Optional[int] = None,
                 n_channels: int = 1,
                 classifier: Optional[BearingClassifier] = None,
                 rul_predictor: Optional[RULPredictor] = None,
                 bearing_params: Optional[Dict] = None,
                 rotational_speed: float = 50.0,
                 smoothing_window: int = 5,
                 alarm_threshold: float = 0.5,
                 enable_explainability: bool = False):
        """
        Args:
            fs: 采样频率 (Hz)
            window_size: 滑动窗口大小（样本点数）
            step_size: 滑动步长
            n_channels: 通道数
            classifier: 故障分类器（预训练）
            rul_predictor: RUL预测器（预训练）
            bearing_params: 轴承参数字典
            rotational_speed: 转速 (Hz)
            smoothing_window: 结果平滑窗口大小
            alarm_threshold: 告警阈值（故障概率）
            enable_explainability: 是否启用可解释性分析
        """
        self.fs = fs
        self.n_channels = n_channels
        self.window_size = window_size
        self.step_size = step_size
        self.rotational_speed = rotational_speed
        self.smoothing_window = smoothing_window
        self.alarm_threshold = alarm_threshold
        self.enable_explainability = enable_explainability
        
        self.buffer = SlidingWindowBuffer(window_size, step_size)
        
        self.preprocessor = Preprocessor(fs=fs)
        self.feature_extractor = FeatureExtractor(fs=fs)
        self.explainer = FeatureExplainer() if enable_explainability else None
        
        self.classifier = classifier
        self.rul_predictor = rul_predictor
        
        if bearing_params is not None:
            self.bearing_fault_freq = BearingFaultFrequency(**bearing_params)
            self.fault_freqs = self.bearing_fault_freq.calculate(rotational_speed)
        else:
            self.bearing_fault_freq = None
            self.fault_freqs = None
        
        self.results_history: List[Dict] = []
        self.probability_history: Dict[str, List[float]] = {
            fault: [] for fault in FAULT_TYPES
        }
        
        self.alarm_triggered: Dict[str, bool] = {
            fault: False for fault in FAULT_TYPES if fault != 'normal'
        }
        self.alarm_callbacks: List[Callable] = []
        
        self.total_samples_processed = 0
        self.total_windows_processed = 0
    
    def add_alarm_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """
        添加告警回调函数
        
        Args:
            callback: 回调函数，接收 (fault_type, alarm_info)
        """
        self.alarm_callbacks.append(callback)
    
    def _check_alarms(self, smoothed_probs: Dict[str, float], window_info: Dict) -> List[Dict]:
        """
        检查并触发告警
        
        Args:
            smoothed_probs: 平滑后的故障概率
            window_info: 窗口信息
        
        Returns:
            告警列表
        """
        alarms = []
        
        for fault_type in FAULT_TYPES:
            if fault_type == 'normal':
                continue
            
            prob = smoothed_probs.get(fault_type, 0.0)
            
            if prob >= self.alarm_threshold and not self.alarm_triggered[fault_type]:
                self.alarm_triggered[fault_type] = True
                
                alarm_info = {
                    'fault_type': fault_type,
                    'probability': prob,
                    'timestamp': window_info['timestamp'],
                    'window_index': window_info['window_index'],
                    'start_sample': window_info['start_sample'],
                    'end_sample': window_info['end_sample'],
                    'threshold': self.alarm_threshold,
                    'message': f'{fault_type} 故障告警，概率: {prob:.2%}'
                }
                
                alarms.append(alarm_info)
                
                for callback in self.alarm_callbacks:
                    try:
                        callback(fault_type, alarm_info)
                    except Exception as e:
                        warnings.warn(f"告警回调执行失败: {e}")
            
            elif prob < self.alarm_threshold * 0.5:
                self.alarm_triggered[fault_type] = False
        
        return alarms
    
    def _smooth_probabilities(self, current_probs: Dict[str, float]) -> Dict[str, float]:
        """
        平滑故障概率（移动平均）
        
        Args:
            current_probs: 当前窗口的概率
        
        Returns:
            平滑后的概率
        """
        smoothed = {}
        
        for fault_type in FAULT_TYPES:
            self.probability_history[fault_type].append(current_probs.get(fault_type, 0.0))
            
            if len(self.probability_history[fault_type]) > self.smoothing_window:
                self.probability_history[fault_type].pop(0)
            
            smoothed[fault_type] = float(np.mean(self.probability_history[fault_type]))
        
        return smoothed
    
    def process_window(self, window_data: np.ndarray,
                       window_index: int = 0) -> Dict:
        """
        处理单个窗口数据
        
        Args:
            window_data: 窗口数据 (window_size, n_channels)
            window_index: 窗口序号
        
        Returns:
            诊断结果字典
        """
        start_sample = self.total_samples_processed - self.window_size
        end_sample = self.total_samples_processed
        
        result = {
            'window_index': window_index,
            'timestamp': datetime.now().isoformat(),
            'start_sample': start_sample,
            'end_sample': end_sample,
            'start_time': start_sample / self.fs,
            'end_time': end_sample / self.fs,
            'window_duration': self.window_size / self.fs
        }
        
        try:
            processed_data = self.preprocessor.preprocess(
                window_data,
                rotational_speed=self.rotational_speed
            )
            
            features, feature_names = self.feature_extractor.extract(
                processed_data,
                fault_freqs=self.fault_freqs
            )
            
            result['feature_names'] = feature_names
            result['features'] = features.flatten().tolist()
            
            if self.classifier is not None:
                pred = self.classifier.predict(
                    features,
                    detect_multiple=True
                )
                
                result['fault_diagnosis'] = {
                    'main_fault': pred['fault_type'][0] if isinstance(pred['fault_type'], list) else pred['fault_type'],
                    'main_fault_probability': float(pred['fault_type_probability'][0]) if isinstance(pred['fault_type_probability'], list) else float(pred['fault_type_probability']),
                    'all_probabilities': {
                        ft: float(prob) for ft, prob in zip(pred.get('all_detected_faults', []), pred.get('all_detected_probabilities', []))
                    },
                    'severity': pred['severity'][0] if isinstance(pred['severity'], list) else pred['severity'],
                    'severity_probability': float(pred['severity_probability'][0]) if isinstance(pred['severity_probability'], list) else float(pred['severity_probability']),
                    'is_multi_fault': bool(pred.get('is_multi_fault', [False])[0] if isinstance(pred.get('is_multi_fault'), list) else pred.get('is_multi_fault', False)),
                    'all_detected_faults': pred.get('all_detected_faults', []),
                    'all_detected_probabilities': [float(p) for p in pred.get('all_detected_probabilities', [])]
                }
                
                current_probs = {}
                type_probs_dict = pred.get('fault_type_probabilities', {})
                for i, ft in enumerate(FAULT_TYPES):
                    probs = type_probs_dict.get(ft, [0])
                    if isinstance(probs, np.ndarray):
                        current_probs[ft] = float(probs[0]) if len(probs) > 0 else 0.0
                    elif isinstance(probs, list):
                        current_probs[ft] = float(probs[0]) if len(probs) > 0 else 0.0
                    else:
                        current_probs[ft] = float(probs)
                
                smoothed_probs = self._smooth_probabilities(current_probs)
                result['fault_diagnosis']['smoothed_probabilities'] = smoothed_probs
                
                window_info = {
                    'window_index': window_index,
                    'start_sample': start_sample,
                    'end_sample': end_sample,
                    'timestamp': result['timestamp']
                }
                alarms = self._check_alarms(smoothed_probs, window_info)
                result['alarms'] = alarms
            
            if self.rul_predictor is not None:
                try:
                    rul_pred, rul_lower, rul_upper = self.rul_predictor.predict(
                        features,
                        return_confidence=True
                    )
                    
                    result['rul_prediction'] = {
                        'rul': float(rul_pred[0]),
                        'lower_bound': float(rul_lower[0]),
                        'upper_bound': float(rul_upper[0]),
                        'confidence_level': 0.95
                    }
                except Exception as e:
                    result['rul_prediction'] = {
                        'error': str(e)
                    }
            
            if self.enable_explainability and self.classifier is not None and self.explainer is not None:
                try:
                    explanation = self.explainer.explain_prediction(
                        self.classifier,
                        features,
                        feature_names=feature_names,
                        top_k=5
                    )
                    result['explanation'] = explanation
                except Exception as e:
                    result['explanation'] = {'error': str(e)}
        
        except Exception as e:
            result['error'] = str(e)
            warnings.warn(f"窗口处理出错: {e}")
        
        self.results_history.append(result)
        self.total_windows_processed += 1
        
        return result
    
    def process(self, data: np.ndarray) -> Generator[Dict, None, None]:
        """
        处理流式数据，逐个窗口输出结果
        
        Args:
            data: 输入数据 (n_samples, n_channels)
        
        Yields:
            每个窗口的诊断结果
        """
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        
        windows = self.buffer.update(data)
        self.total_samples_processed += len(data)
        
        for i, window in enumerate(windows):
            window_idx = self.total_windows_processed + i
            result = self.process_window(window, window_idx)
            yield result
    
    def process_file(self, file_path: str,
                     batch_size: int = 1024,
                     callback: Optional[Callable[[Dict], None]] = None) -> List[Dict]:
        """
        处理文件（模拟流式处理）
        
        Args:
            file_path: 数据文件路径
            batch_size: 每批读取的样本数
            callback: 每个窗口的回调函数
        
        Returns:
            所有窗口的诊断结果
        """
        from .utils import load_signal
        
        signal_data = load_signal(file_path)
        
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        n_samples = len(signal_data)
        results = []
        
        for start in range(0, n_samples, batch_size):
            end = min(start + batch_size, n_samples)
            batch = signal_data[start:end]
            
            for result in self.process(batch):
                results.append(result)
                
                if callback is not None:
                    callback(result)
        
        return results
    
    def get_summary(self) -> Dict:
        """
        获取处理摘要
        
        Returns:
            摘要字典
        """
        if len(self.results_history) == 0:
            return {
                'total_samples_processed': self.total_samples_processed,
                'total_windows_processed': self.total_windows_processed,
                'message': 'No windows processed yet'
            }
        
        fault_counts = {ft: 0 for ft in FAULT_TYPES}
        severity_counts = {sev: 0 for sev in SEVERITY_LEVELS}
        alarm_count = 0
        multi_fault_count = 0
        
        for result in self.results_history:
            if 'fault_diagnosis' in result:
                fd = result['fault_diagnosis']
                fault_counts[fd['main_fault']] += 1
                severity_counts[fd['severity']] += 1
                
                if fd.get('is_multi_fault', False):
                    multi_fault_count += 1
                
                if 'alarms' in result:
                    alarm_count += len(result['alarms'])
        
        avg_rul = None
        if len(self.results_history) > 0 and 'rul_prediction' in self.results_history[-1]:
            rul_preds = [r['rul_prediction'].get('rul') for r in self.results_history 
                        if 'rul_prediction' in r and 'rul' in r['rul_prediction']]
            if rul_preds:
                avg_rul = float(np.mean(rul_preds))
        
        return {
            'total_samples_processed': self.total_samples_processed,
            'total_windows_processed': self.total_windows_processed,
            'window_size': self.window_size,
            'step_size': self.step_size,
            'fs': self.fs,
            'processing_duration': self.total_samples_processed / self.fs,
            'fault_distribution': fault_counts,
            'severity_distribution': severity_counts,
            'alarm_count': alarm_count,
            'multi_fault_count': multi_fault_count,
            'average_rul': avg_rul,
            'alarm_status': self.alarm_triggered.copy()
        }
    
    def save_results(self, output_path: str) -> None:
        """
        保存所有结果到JSON文件
        
        Args:
            output_path: 输出文件路径
        """
        summary = self.get_summary()
        output = {
            'summary': summary,
            'window_results': self.results_history,
            'config': {
                'fs': self.fs,
                'window_size': self.window_size,
                'step_size': self.step_size,
                'n_channels': self.n_channels,
                'rotational_speed': self.rotational_speed,
                'smoothing_window': self.smoothing_window,
                'alarm_threshold': self.alarm_threshold
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    
    def reset(self) -> None:
        """重置系统状态"""
        self.buffer.clear()
        self.results_history = []
        self.probability_history = {
            fault: [] for fault in FAULT_TYPES
        }
        self.alarm_triggered = {
            fault: False for fault in FAULT_TYPES if fault != 'normal'
        }
        self.total_samples_processed = 0
        self.total_windows_processed = 0
    
    def simulate_stream(self, signal_data: np.ndarray,
                        real_time: bool = False,
                        speed_factor: float = 1.0) -> Generator[Dict, None, None]:
        """
        模拟实时数据流处理
        
        Args:
            signal_data: 完整信号数据
            real_time: 是否模拟实时延迟
            speed_factor: 速度因子（1=实时，>1=加速，<1=减速）
        
        Yields:
            每个窗口的诊断结果
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        batch_size = self.step_size or self.window_size
        
        for start in range(0, len(signal_data), batch_size):
            end = min(start + batch_size, len(signal_data))
            batch = signal_data[start:end]
            
            if real_time:
                delay = (end - start) / self.fs / speed_factor
                time.sleep(delay)
            
            for result in self.process(batch):
                yield result
