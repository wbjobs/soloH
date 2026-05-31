import numpy as np
import pandas as pd
import os
import json
import pickle
from typing import Optional, Union, Tuple


def load_signal(file_path: str, delimiter: Optional[str] = None,
                skiprows: int = 0, usecols: Optional[Union[int, list]] = None) -> np.ndarray:
    """
    加载振动信号数据
    
    Args:
        file_path: 数据文件路径，支持 .npy, .csv, .txt, .mat 格式
        delimiter: 文本文件分隔符
        skiprows: 跳过的行数
        usecols: 使用的列
    
    Returns:
        振动信号数组 (n_samples, n_channels)
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.npy':
        data = np.load(file_path)
    elif ext == '.csv':
        data = pd.read_csv(file_path, delimiter=delimiter or ',',
                           skiprows=skiprows, usecols=usecols).values
    elif ext == '.txt':
        data = np.loadtxt(file_path, delimiter=delimiter,
                          skiprows=skiprows, usecols=usecols)
    elif ext == '.mat':
        try:
            from scipy.io import loadmat
            mat_data = loadmat(file_path)
            data_key = [k for k in mat_data.keys() if not k.startswith('__')][0]
            data = mat_data[data_key]
        except ImportError:
            raise ImportError("请安装 scipy 以读取 .mat 文件")
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
    
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    
    return data


def save_results(results: dict, output_path: str, format: str = 'json') -> None:
    """
    保存诊断结果
    
    Args:
        results: 结果字典
        output_path: 输出文件路径
        format: 输出格式 ('json', 'csv', 'pickle')
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    if format == 'json':
        def convert(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.floating, np.integer)):
                return float(obj)
            return str(obj)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=convert)
    elif format == 'csv':
        df = pd.DataFrame({k: [v] for k, v in results.items()
                          if not isinstance(v, (list, np.ndarray, dict))})
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
    elif format == 'pickle':
        with open(output_path, 'wb') as f:
            pickle.dump(results, f)
    else:
        raise ValueError(f"不支持的输出格式: {format}")


def save_model(model, model_path: str) -> None:
    """
    保存模型
    
    Args:
        model: 模型对象
        model_path: 模型保存路径
    """
    os.makedirs(os.path.dirname(model_path) or '.', exist_ok=True)
    
    if hasattr(model, 'state_dict'):
        import torch
        torch.save(model.state_dict(), model_path)
    else:
        import joblib
        joblib.dump(model, model_path)


def load_model(model_path: str, model_type: str = 'auto'):
    """
    加载模型
    
    Args:
        model_path: 模型路径
        model_type: 模型类型 ('auto', 'pytorch', 'sklearn')
    
    Returns:
        加载的模型
    """
    if model_type == 'auto':
        ext = os.path.splitext(model_path)[1].lower()
        if ext in ['.pt', '.pth']:
            model_type = 'pytorch'
        elif ext in ['.pkl', '.joblib']:
            model_type = 'sklearn'
        else:
            model_type = 'sklearn'
    
    if model_type == 'pytorch':
        import torch
        return torch.load(model_path)
    else:
        import joblib
        return joblib.load(model_path)


def train_test_split_data(X: np.ndarray, y: Optional[np.ndarray] = None,
                          test_size: float = 0.2, random_state: int = 42) -> Tuple:
    """
    划分训练集和测试集
    
    Args:
        X: 特征矩阵
        y: 标签
        test_size: 测试集比例
        random_state: 随机种子
    
    Returns:
        (X_train, X_test, y_train, y_test) 或 (X_train, X_test)
    """
    from sklearn.model_selection import train_test_split
    
    if y is not None:
        return train_test_split(X, y, test_size=test_size,
                               random_state=random_state, stratify=y)
    else:
        return train_test_split(X, test_size=test_size, random_state=random_state)
