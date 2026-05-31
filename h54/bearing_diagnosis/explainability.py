import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import warnings
from sklearn.inspection import permutation_importance


class FeatureExplainer:
    """
    特征可解释性分析
    
    提供特征重要性排序、贡献度分析等可解释性输出
    """
    
    def __init__(self, feature_names: Optional[List[str]] = None):
        """
        Args:
            feature_names: 特征名称列表
        """
        self.feature_names = feature_names
        self.importance_df_: Optional[pd.DataFrame] = None
    
    def analyze_importance(self, model, X: Optional[np.ndarray] = None,
                           y: Optional[np.ndarray] = None,
                           method: str = 'auto',
                           top_k: int = 20,
                           feature_names: Optional[List[str]] = None) -> Dict:
        """
        分析特征重要性
        
        Args:
            model: 训练好的分类器模型
            X: 特征矩阵（用于排列重要性）
            y: 标签（用于排列重要性）
            method: 分析方法 ('auto', 'model', 'permutation', 'shap')
            top_k: 返回前k个最重要的特征
            feature_names: 特征名称列表
        
        Returns:
            包含特征重要性分析结果的字典
        """
        if feature_names is not None:
            self.feature_names = feature_names
        
        if method == 'auto':
            if hasattr(model, 'get_feature_importance'):
                method = 'model'
            elif X is not None and y is not None:
                method = 'permutation'
            else:
                method = 'model'
        
        results = {}
        
        if method == 'model':
            importance = self._get_model_importance(model)
        elif method == 'permutation':
            if X is None or y is None:
                raise ValueError("排列重要性需要提供 X 和 y")
            importance = self._get_permutation_importance(model, X, y)
        elif method == 'shap':
            importance = self._get_shap_importance(model, X)
        else:
            raise ValueError(f"未知的重要性分析方法: {method}")
        
        results['method'] = method
        results['importance'] = importance
        
        if self.feature_names is not None:
            importance_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': importance
            }).sort_values('importance', ascending=False)
        else:
            importance_df = pd.DataFrame({
                'feature': [f'feature_{i}' for i in range(len(importance))],
                'importance': importance
            }).sort_values('importance', ascending=False)
        
        importance_df['rank'] = range(1, len(importance_df) + 1)
        importance_df['cumulative_importance'] = importance_df['importance'].cumsum()
        total_importance = importance_df['importance'].sum()
        if total_importance > 0:
            importance_df['relative_importance'] = importance_df['importance'] / total_importance
            importance_df['cumulative_relative'] = importance_df['cumulative_importance'] / total_importance
        else:
            importance_df['relative_importance'] = 0
            importance_df['cumulative_relative'] = 0
        
        self.importance_df_ = importance_df
        
        results['importance_df'] = importance_df
        results['top_features'] = importance_df.head(top_k).to_dict('records')
        results['feature_category_importance'] = self._get_category_importance(importance_df)
        
        return results
    
    def _get_model_importance(self, model) -> np.ndarray:
        """从模型获取特征重要性（随机森林）"""
        if hasattr(model, 'get_feature_importance'):
            importance = model.get_feature_importance()
            if importance is not None:
                return importance
        
        if hasattr(model, '_model'):
            inner_model = model._model
            if hasattr(inner_model, 'feature_importances_'):
                return inner_model.feature_importances_
            if hasattr(inner_model, 'type_classifier') and hasattr(
                inner_model.type_classifier, 'feature_importances_'):
                type_imp = inner_model.type_classifier.feature_importances_
                severity_imp = inner_model.severity_classifier.feature_importances_
                return (type_imp + severity_imp) / 2
        
        warnings.warn("模型不支持直接获取特征重要性，返回等权重")
        return np.ones(len(self.feature_names) if self.feature_names else 1)
    
    def _get_permutation_importance(self, model, X: np.ndarray,
                                    y: np.ndarray, n_repeats: int = 10,
                                    random_state: int = 42) -> np.ndarray:
        """排列重要性分析"""
        if hasattr(model, '_model') and hasattr(model._model, 'type_classifier'):
            classifier = model._model.type_classifier
            if hasattr(model._model, 'scaler'):
                X = model._model.scaler.transform(X)
        else:
            classifier = model
        
        result = permutation_importance(
            classifier, X, y,
            n_repeats=n_repeats,
            random_state=random_state,
            n_jobs=-1
        )
        
        return result.importances_mean
    
    def _get_shap_importance(self, model, X: np.ndarray) -> np.ndarray:
        """SHAP 重要性分析（如果安装了shap库）"""
        try:
            import shap
            
            if hasattr(model, '_model') and hasattr(model._model, 'type_classifier'):
                classifier = model._model.type_classifier
                if hasattr(model._model, 'scaler'):
                    X = model._model.scaler.transform(X)
            else:
                classifier = model
            
            explainer = shap.TreeExplainer(classifier)
            shap_values = explainer.shap_values(X)
            
            if isinstance(shap_values, list):
                shap_values = np.mean([np.abs(sv).mean(0) for sv in shap_values], axis=0)
            else:
                shap_values = np.abs(shap_values).mean(0)
            
            return np.array(shap_values)
            
        except ImportError:
            warnings.warn("未安装 shap 库，回退到模型内置重要性")
            return self._get_model_importance(model)
    
    def _get_category_importance(self, importance_df: pd.DataFrame) -> Dict[str, Dict]:
        """
        按特征类别计算重要性
        
        Args:
            importance_df: 特征重要性DataFrame
        
        Returns:
            各类别的重要性统计
        """
        categories = {
            'time_domain': 'time_',
            'frequency_domain': 'freq_',
            'time_frequency_domain': 'tf_'
        }
        
        category_stats = {}
        total_importance = importance_df['importance'].sum()
        
        for cat_name, prefix in categories.items():
            mask = importance_df['feature'].str.startswith(prefix)
            cat_data = importance_df[mask]
            
            if len(cat_data) > 0:
                cat_importance = cat_data['importance'].sum()
                category_stats[cat_name] = {
                    'total_importance': cat_importance,
                    'relative_importance': cat_importance / total_importance if total_importance > 0 else 0,
                    'n_features': len(cat_data),
                    'top_feature': cat_data.iloc[0]['feature'] if len(cat_data) > 0 else None,
                    'top_importance': float(cat_data.iloc[0]['importance']) if len(cat_data) > 0 else 0
                }
            else:
                category_stats[cat_name] = {
                    'total_importance': 0,
                    'relative_importance': 0,
                    'n_features': 0,
                    'top_feature': None,
                    'top_importance': 0
                }
        
        return category_stats
    
    def get_top_features_by_category(self, category: str,
                                     top_k: int = 5) -> pd.DataFrame:
        """
        获取指定类别的前k个重要特征
        
        Args:
            category: 特征类别 ('time_domain', 'frequency_domain', 'time_frequency_domain')
            top_k: 返回前k个特征
        
        Returns:
            包含特征重要性的DataFrame
        """
        if self.importance_df_ is None:
            raise ValueError("请先调用 analyze_importance 方法")
        
        prefix = {
            'time_domain': 'time_',
            'frequency_domain': 'freq_',
            'time_frequency_domain': 'tf_'
        }.get(category)
        
        if prefix is None:
            raise ValueError(f"未知的特征类别: {category}")
        
        mask = self.importance_df_['feature'].str.startswith(prefix)
        return self.importance_df_[mask].head(top_k)
    
    def generate_explanation_report(self, prediction_result: Dict,
                                    top_k: int = 10) -> Dict:
        """
        生成可解释性报告
        
        Args:
            prediction_result: 预测结果字典
            top_k: 显示前k个重要特征
        
        Returns:
            解释报告字典
        """
        if self.importance_df_ is None:
            raise ValueError("请先调用 analyze_importance 方法")
        
        report = {
            'prediction': {
                'fault_type': prediction_result.get('fault_type', 'unknown'),
                'fault_type_probability': prediction_result.get('fault_type_probability', 0),
                'severity': prediction_result.get('severity', 'unknown'),
                'severity_probability': prediction_result.get('severity_probability', 0)
            },
            'top_features': [],
            'category_summary': {},
            'key_drivers': [],
            'recommendation': ''
        }
        
        top_features = self.importance_df_.head(top_k)
        for _, row in top_features.iterrows():
            report['top_features'].append({
                'feature': row['feature'],
                'importance': float(row['importance']),
                'relative_importance': float(row['relative_importance']),
                'rank': int(row['rank'])
            })
        
        category_importance = self._get_category_importance(self.importance_df_)
        report['category_summary'] = category_importance
        
        key_drivers = []
        for feat in report['top_features'][:5]:
            feature_name = feat['feature']
            interpretation = self._interpret_feature(feature_name, prediction_result)
            key_drivers.append({
                'feature': feature_name,
                'importance': feat['importance'],
                'interpretation': interpretation
            })
        report['key_drivers'] = key_drivers
        
        report['recommendation'] = self._generate_recommendation(
            prediction_result, category_importance)
        
        return report
    
    def _interpret_feature(self, feature_name: str,
                          prediction_result: Dict) -> str:
        """
        解释单个特征的含义
        
        Args:
            feature_name: 特征名称
            prediction_result: 预测结果
        
        Returns:
            特征解释文本
        """
        if feature_name.startswith('time_'):
            feat_type = feature_name.replace('time_', '').split('_ch')[0]
            channel = feature_name.split('_ch')[-1]
            
            interpretations = {
                'kurtosis': '峭度反映冲击成分的多少，故障时会显著升高',
                'impulse_factor': '脉冲因子反映脉冲冲击的强度，对早期故障敏感',
                'peak_to_peak': '峰峰值反映振动的幅度范围',
                'rms': '均方根值反映振动能量的大小',
                'crest_factor': '峰值因子反映冲击脉冲的相对强度',
                'margin_factor': '裕度因子对早期故障较为敏感',
                'shape_factor': '波形因子反映信号的形状特征',
                'skewness': '偏度反映信号分布的不对称性'
            }
            
            base = interpretations.get(feat_type, f'时域特征 {feat_type}')
            return f"{base}（通道{channel}）"
        
        elif feature_name.startswith('freq_'):
            feat_type = feature_name.replace('freq_', '').split('_ch')[0]
            channel = feature_name.split('_ch')[-1]
            
            if 'bpfi' in feat_type:
                return f"内圈故障特征频率幅值（通道{channel}）- 内圈故障时该值会显著升高"
            elif 'bpfo' in feat_type:
                return f"外圈故障特征频率幅值（通道{channel}）- 外圈故障时该值会显著升高"
            elif 'bsf' in feat_type:
                return f"滚动体故障特征频率幅值（通道{channel}）- 滚动体故障时该值会显著升高"
            elif 'ftf' in feat_type:
                return f"保持架故障特征频率幅值（通道{channel}）- 保持架故障时该值会显著升高"
            elif 'spectral_centroid' in feat_type:
                return f"频谱质心（通道{channel}）- 反映频谱能量的中心位置"
            elif 'spectral_kurtosis' in feat_type:
                return f"频谱峭度（通道{channel}）- 反映频谱中的冲击成分"
            else:
                return f"频域特征 {feat_type}（通道{channel}）"
        
        elif feature_name.startswith('tf_'):
            feat_type = feature_name.replace('tf_', '').split('_ch')[0]
            channel = feature_name.split('_ch')[-1]
            
            if 'wp_energy' in feat_type:
                node = feat_type.split('node')[-1].split('_')[0]
                return f"小波包节点{node}能量（通道{channel}）- 反映该频段的能量分布"
            elif 'wp_entropy' in feat_type:
                return f"小波包能量熵（通道{channel}）- 反映能量分布的无序程度"
            elif 'wp_std' in feat_type:
                node = feat_type.split('node')[-1].split('_')[0]
                return f"小波包节点{node}系数标准差（通道{channel}）"
            else:
                return f"时频域特征 {feat_type}（通道{channel}）"
        
        return feature_name
    
    def _generate_recommendation(self, prediction_result: Dict,
                                category_importance: Dict) -> str:
        """
        生成维护建议
        
        Args:
            prediction_result: 预测结果
            category_importance: 类别重要性
        
        Returns:
            建议文本
        """
        fault_type = prediction_result.get('fault_type', 'normal')
        severity = prediction_result.get('severity', 'normal')
        
        recommendations = []
        
        if fault_type != 'normal':
            fault_desc = {
                'inner_race': '内圈故障',
                'outer_race': '外圈故障',
                'rolling_element': '滚动体故障',
                'cage': '保持架故障'
            }.get(fault_type, fault_type)
            
            severity_action = {
                'early': '建议加强监测，安排近期检查',
                'medium': '建议尽快安排检修，考虑更换备件',
                'late': '建议立即停机检修，避免设备损坏'
            }.get(severity, '建议持续监测')
            
            recommendations.append(f"检测到{fault_desc}，严重程度：{severity}。{severity_action}。")
        
        top_category = max(
            category_importance.items(),
            key=lambda x: x[1]['total_importance']
        )[0]
        
        category_desc = {
            'time_domain': '时域特征',
            'frequency_domain': '频域特征',
            'time_frequency_domain': '时频域特征'
        }[top_category]
        
        recommendations.append(f"本次诊断中，{category_desc}贡献最大，建议重点关注相关特征的变化趋势。")
        
        if severity in ['medium', 'late']:
            recommendations.append("建议采集更多样本进行趋势分析，确认故障发展速度。")
        
        return ' '.join(recommendations)
    
    def plot_importance(self, top_k: int = 20, save_path: Optional[str] = None):
        """
        绘制特征重要性图
        
        Args:
            top_k: 显示前k个特征
            save_path: 图片保存路径
        """
        if self.importance_df_ is None:
            raise ValueError("请先调用 analyze_importance 方法")
        
        try:
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(10, 8))
            top_data = self.importance_df_.head(top_k)
            
            colors = []
            for feat in top_data['feature']:
                if feat.startswith('time_'):
                    colors.append('#3498db')
                elif feat.startswith('freq_'):
                    colors.append('#e74c3c')
                elif feat.startswith('tf_'):
                    colors.append('#2ecc71')
                else:
                    colors.append('#95a5a6')
            
            plt.barh(range(len(top_data)), top_data['importance'], color=colors)
            plt.yticks(range(len(top_data)), top_data['feature'])
            plt.xlabel('重要性')
            plt.title(f'Top {top_k} 特征重要性')
            plt.gca().invert_yaxis()
            
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#3498db', label='时域特征'),
                Patch(facecolor='#e74c3c', label='频域特征'),
                Patch(facecolor='#2ecc71', label='时频域特征')
            ]
            plt.legend(handles=legend_elements, loc='lower right')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            else:
                plt.show()
                
            plt.close()
            
        except ImportError:
            warnings.warn("matplotlib 未安装，无法绘图")
