"""
可视化模块
包含平行坐标图展示特征对比，t-SNE降维展示作家聚类
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Optional, Tuple
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px


class StyleVisualizer:
    """
    风格可视化工具
    
    支持:
    - 平行坐标图 (Parallel Coordinates)
    - t-SNE降维聚类
    - PCA降维可视化
    - 特征热力图
    - 雷达图对比
    """

    def __init__(self, feature_extractor=None):
        """
        初始化可视化工具
        
        Args:
            feature_extractor: 特征提取器实例
        """
        self.feature_extractor = feature_extractor
        self.feature_names = None
        self.feature_groups = None
        
        if feature_extractor is not None:
            self.feature_names = feature_extractor.feature_names
            self.feature_groups = feature_extractor.get_feature_groups()
        
        self.scaler = StandardScaler()
        self._setup_style()

    def _setup_style(self):
        """设置绘图风格"""
        sns.set_style("whitegrid")
        sns.set_palette("husl")
        plt.rcParams['figure.dpi'] = 100
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['font.family'] = 'DejaVu Sans'

    def _get_representative_features(self, n_per_group: int = 3) -> List[int]:
        """获取每组具有代表性的特征索引"""
        if self.feature_groups is None:
            return list(range(min(20, len(self.feature_names))))
        
        selected_indices = []
        for group_name, features in self.feature_groups.items():
            for i, feat_name in enumerate(features[:n_per_group]):
                if feat_name in self.feature_names:
                    idx = self.feature_names.index(feat_name)
                    selected_indices.append(idx)
        
        return selected_indices

    def parallel_coordinates(self, features: np.ndarray, labels: List[str],
                             authors: Optional[List[str]] = None,
                             output_path: Optional[str] = None,
                             max_features: int = 15,
                             use_plotly: bool = True) -> Optional[str]:
        """
        绘制平行坐标图展示特征对比
        
        Args:
            features: 特征矩阵 (n_samples, n_features)
            labels: 样本标签列表
            authors: 作者名称列表（可选）
            output_path: 输出文件路径（可选）
            max_features: 最大显示特征数
            use_plotly: 是否使用plotly交互式绘图
            
        Returns:
            HTML字符串（如果使用plotly）或保存路径
        """
        if authors is None:
            authors = labels
        
        feature_indices = self._get_representative_features(n_per_group=3)
        feature_indices = feature_indices[:max_features]
        
        if self.feature_names is not None:
            selected_feature_names = [self.feature_names[i] for i in feature_indices]
        else:
            selected_feature_names = [f"feature_{i}" for i in feature_indices]
        
        df_data = features[:, feature_indices]
        df_scaled = self.scaler.fit_transform(df_data)
        
        df = pd.DataFrame(df_scaled, columns=selected_feature_names)
        df['Author'] = authors
        df['Label'] = labels
        
        if use_plotly:
            unique_authors = list(set(authors))
            color_map = {author: idx for idx, author in enumerate(unique_authors)}
            df['color'] = df['Author'].map(color_map)
            
            fig = go.Figure(data=go.Parcoords(
                line=dict(color=df['color'],
                         colorscale='Viridis',
                         showscale=True,
                         colorbar=dict(title='Author', 
                                      tickvals=list(range(len(unique_authors))),
                                      ticktext=unique_authors)),
                dimensions=[dict(range=[df[col].min(), df[col].max()],
                                label=col,
                                values=df[col])
                           for col in selected_feature_names]
            ))
            
            fig.update_layout(
                title='Author Writing Style - Parallel Coordinates',
                font=dict(size=10),
                height=600
            )
            
            if output_path:
                if output_path.endswith('.html'):
                    fig.write_html(output_path)
                else:
                    fig.write_image(output_path)
                return output_path
            
            return fig.to_html()
        else:
            fig, ax = plt.subplots(figsize=(14, 8))
            
            unique_authors = list(set(authors))
            colors = plt.cm.tab20(np.linspace(0, 1, len(unique_authors)))
            color_map = {author: colors[i] for i, author in enumerate(unique_authors)}
            
            x = list(range(len(selected_feature_names)))
            for i in range(len(df)):
                ax.plot(x, df.iloc[i][selected_feature_names], 
                       color=color_map[authors[i]], 
                       alpha=0.7, linewidth=1.5)
            
            ax.set_xticks(x)
            ax.set_xticklabels(selected_feature_names, rotation=45, ha='right')
            ax.set_ylabel('Normalized Feature Value')
            ax.set_title('Author Writing Style Comparison - Parallel Coordinates')
            
            legend_handles = [plt.Line2D([0], [0], color=color_map[author], label=author)
                             for author in unique_authors]
            ax.legend(handles=legend_handles, loc='best', ncol=2, fontsize=8)
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, bbox_inches='tight')
                plt.close()
                return output_path
            
            return None

    def tsne_visualization(self, features: np.ndarray, labels: List[str],
                           authors: Optional[List[str]] = None,
                           perplexity: float = 30.0,
                           n_iter: int = 1000,
                           output_path: Optional[str] = None,
                           use_plotly: bool = True) -> Optional[str]:
        """
        t-SNE降维可视化作家聚类
        
        Args:
            features: 特征矩阵 (n_samples, n_features)
            labels: 样本标签列表
            authors: 作者名称列表（可选）
            perplexity: t-SNE困惑度
            n_iter: 迭代次数
            output_path: 输出文件路径
            use_plotly: 是否使用plotly交互式绘图
            
        Returns:
            HTML字符串或保存路径
        """
        if authors is None:
            authors = labels
        
        features_scaled = self.scaler.fit_transform(features)
        
        tsne = TSNE(n_components=2, 
                   perplexity=min(perplexity, len(features) - 1),
                   n_iter=n_iter,
                   random_state=42)
        tsne_results = tsne.fit_transform(features_scaled)
        
        df = pd.DataFrame({
            't-SNE Dimension 1': tsne_results[:, 0],
            't-SNE Dimension 2': tsne_results[:, 1],
            'Author': authors,
            'Label': labels
        })
        
        if use_plotly:
            fig = px.scatter(df, 
                           x='t-SNE Dimension 1', 
                           y='t-SNE Dimension 2',
                           color='Author',
                           hover_data=['Label'],
                           title='Author Clustering - t-SNE Visualization',
                           width=800,
                           height=600)
            
            fig.update_traces(marker=dict(size=10, 
                                        line=dict(width=1, color='DarkSlateGrey')))
            
            if output_path:
                if output_path.endswith('.html'):
                    fig.write_html(output_path)
                else:
                    fig.write_image(output_path)
                return output_path
            
            return fig.to_html()
        else:
            fig, ax = plt.subplots(figsize=(10, 8))
            
            unique_authors = list(set(authors))
            colors = plt.cm.tab20(np.linspace(0, 1, len(unique_authors)))
            color_map = {author: colors[i] for i, author in enumerate(unique_authors)}
            
            for author in unique_authors:
                mask = df['Author'] == author
                ax.scatter(df.loc[mask, 't-SNE Dimension 1'], 
                          df.loc[mask, 't-SNE Dimension 2'],
                          c=[color_map[author]], 
                          label=author,
                          s=100,
                          alpha=0.7,
                          edgecolors='black',
                          linewidth=0.5)
            
            ax.set_xlabel('t-SNE Dimension 1')
            ax.set_ylabel('t-SNE Dimension 2')
            ax.set_title('Author Clustering - t-SNE Visualization')
            ax.legend(loc='best', ncol=2, fontsize=8)
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, bbox_inches='tight')
                plt.close()
                return output_path
            
            return None

    def pca_visualization(self, features: np.ndarray, labels: List[str],
                          authors: Optional[List[str]] = None,
                          output_path: Optional[str] = None,
                          use_plotly: bool = True) -> Optional[str]:
        """
        PCA降维可视化
        
        Args:
            features: 特征矩阵
            labels: 样本标签
            authors: 作者名称
            output_path: 输出路径
            use_plotly: 是否使用plotly
            
        Returns:
            HTML字符串或保存路径
        """
        if authors is None:
            authors = labels
        
        features_scaled = self.scaler.fit_transform(features)
        
        pca = PCA(n_components=3, random_state=42)
        pca_results = pca.fit_transform(features_scaled)
        
        explained_var = pca.explained_variance_ratio_
        
        df = pd.DataFrame({
            'PC1': pca_results[:, 0],
            'PC2': pca_results[:, 1],
            'PC3': pca_results[:, 2],
            'Author': authors,
            'Label': labels
        })
        
        if use_plotly:
            fig = make_subplots(rows=1, cols=2,
                               subplot_titles=('PCA 2D View', 'PCA 3D View'),
                               specs=[[{'type': 'xy'}, {'type': 'scene'}]])
            
            for author in list(set(authors)):
                mask = df['Author'] == author
                fig.add_trace(
                    go.Scatter(x=df.loc[mask, 'PC1'],
                              y=df.loc[mask, 'PC2'],
                              mode='markers',
                              name=author,
                              text=df.loc[mask, 'Label'],
                              marker=dict(size=10)),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Scatter3d(x=df.loc[mask, 'PC1'],
                                y=df.loc[mask, 'PC2'],
                                z=df.loc[mask, 'PC3'],
                                mode='markers',
                                name=author,
                                text=df.loc[mask, 'Label'],
                                marker=dict(size=6),
                                showlegend=False),
                    row=1, col=2
                )
            
            fig.update_xaxes(title_text=f'PC1 ({explained_var[0]:.1%} variance)', row=1, col=1)
            fig.update_yaxes(title_text=f'PC2 ({explained_var[1]:.1%} variance)', row=1, col=1)
            
            fig.update_layout(
                title='Author Style - PCA Visualization',
                height=500,
                width=1200
            )
            
            if output_path:
                if output_path.endswith('.html'):
                    fig.write_html(output_path)
                else:
                    fig.write_image(output_path)
                return output_path
            
            return fig.to_html()
        else:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            
            unique_authors = list(set(authors))
            colors = plt.cm.tab20(np.linspace(0, 1, len(unique_authors)))
            color_map = {author: colors[i] for i, author in enumerate(unique_authors)}
            
            for author in unique_authors:
                mask = df['Author'] == author
                ax1.scatter(df.loc[mask, 'PC1'], df.loc[mask, 'PC2'],
                           c=[color_map[author]], label=author, s=100, alpha=0.7)
            
            ax1.set_xlabel(f'PC1 ({explained_var[0]:.1%} variance)')
            ax1.set_ylabel(f'PC2 ({explained_var[1]:.1%} variance)')
            ax1.set_title('PCA 2D Visualization')
            ax1.legend(loc='best', ncol=2, fontsize=8)
            ax1.grid(True, alpha=0.3)
            
            from mpl_toolkits.mplot3d import Axes3D
            ax2 = fig.add_subplot(122, projection='3d')
            for author in unique_authors:
                mask = df['Author'] == author
                ax2.scatter(df.loc[mask, 'PC1'], df.loc[mask, 'PC2'], df.loc[mask, 'PC3'],
                           c=[color_map[author]], label=author, s=80, alpha=0.7)
            
            ax2.set_xlabel(f'PC1')
            ax2.set_ylabel(f'PC2')
            ax2.set_zlabel(f'PC3 ({explained_var[2]:.1%})')
            ax2.set_title('PCA 3D Visualization')
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, bbox_inches='tight')
                plt.close()
                return output_path
            
            return None

    def feature_heatmap(self, features: np.ndarray, labels: List[str],
                        authors: Optional[List[str]] = None,
                        output_path: Optional[str] = None,
                        max_features: int = 50) -> Optional[str]:
        """
        绘制特征热力图
        
        Args:
            features: 特征矩阵
            labels: 样本标签
            authors: 作者名称
            output_path: 输出路径
            max_features: 最大显示特征数
            
        Returns:
            保存路径或None
        """
        if authors is None:
            authors = labels
        
        feature_indices = self._get_representative_features(n_per_group=5)
        feature_indices = feature_indices[:max_features]
        
        if self.feature_names is not None:
            selected_feature_names = [self.feature_names[i] for i in feature_indices]
        else:
            selected_feature_names = [f"feature_{i}" for i in feature_indices]
        
        df_data = features[:, feature_indices]
        df_scaled = self.scaler.fit_transform(df_data)
        
        df = pd.DataFrame(df_scaled, columns=selected_feature_names, index=labels)
        
        unique_authors = list(set(authors))
        author_colors = plt.cm.tab20(np.linspace(0, 1, len(unique_authors)))
        author_color_map = {author: author_colors[i] for i, author in enumerate(unique_authors)}
        row_colors = pd.Series(authors).map(author_color_map)
        
        fig = plt.figure(figsize=(14, 10))
        g = sns.clustermap(df, 
                          row_colors=row_colors.values,
                          cmap='RdBu_r',
                          center=0,
                          standard_scale=1,
                          figsize=(14, 10))
        
        g.fig.suptitle('Feature Heatmap - Author Writing Styles', y=1.02)
        
        for author, color in author_color_map.items():
            g.ax_row_dendrogram.bar(0, 0, color=color, label=author, linewidth=0)
        g.ax_row_dendrogram.legend(loc='center', bbox_to_anchor=(1.5, 0.5), ncol=1)
        
        if output_path:
            plt.savefig(output_path, bbox_inches='tight')
            plt.close()
            return output_path
        
        return None

    def radar_chart(self, features: np.ndarray, labels: List[str],
                    authors: Optional[List[str]] = None,
                    output_path: Optional[str] = None,
                    use_plotly: bool = True) -> Optional[str]:
        """
        雷达图对比不同作者的特征
        
        Args:
            features: 特征矩阵
            labels: 样本标签
            authors: 作者名称
            output_path: 输出路径
            use_plotly: 是否使用plotly
            
        Returns:
            HTML字符串或保存路径
        """
        if authors is None:
            authors = labels
        
        feature_indices = self._get_representative_features(n_per_group=2)
        
        if self.feature_names is not None:
            selected_feature_names = [self.feature_names[i] for i in feature_indices]
        else:
            selected_feature_names = [f"feature_{i}" for i in feature_indices]
        
        df_data = features[:, feature_indices]
        df_scaled = self.scaler.fit_transform(df_data)
        
        unique_authors = list(set(authors))
        author_means = {}
        
        for author in unique_authors:
            mask = [a == author for a in authors]
            author_means[author] = np.mean(df_scaled[mask], axis=0)
        
        if use_plotly:
            fig = go.Figure()
            
            for author in unique_authors:
                fig.add_trace(go.Scatterpolar(
                    r=author_means[author],
                    theta=selected_feature_names,
                    fill='toself',
                    name=author,
                    opacity=0.6
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[-2, 2])
                ),
                showlegend=True,
                title='Author Style Comparison - Radar Chart'
            )
            
            if output_path:
                if output_path.endswith('.html'):
                    fig.write_html(output_path)
                else:
                    fig.write_image(output_path)
                return output_path
            
            return fig.to_html()
        else:
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, projection='polar')
            
            angles = np.linspace(0, 2 * np.pi, len(selected_feature_names), endpoint=False)
            angles = np.concatenate((angles, [angles[0]]))
            
            colors = plt.cm.tab20(np.linspace(0, 1, len(unique_authors)))
            
            for i, author in enumerate(unique_authors):
                values = author_means[author]
                values = np.concatenate((values, [values[0]]))
                ax.plot(angles, values, 'o-', color=colors[i], linewidth=2, label=author)
                ax.fill(angles, values, color=colors[i], alpha=0.2)
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(selected_feature_names, fontsize=8)
            ax.set_ylim(-2, 2)
            ax.set_title('Author Style Comparison - Radar Chart')
            ax.legend(loc='best', fontsize=8)
            
            if output_path:
                plt.savefig(output_path, bbox_inches='tight')
                plt.close()
                return output_path
            
            return None

    def drift_trend_plot(self, drift_analysis: Dict,
                         output_path: Optional[str] = None,
                         use_plotly: bool = True) -> Optional[str]:
        """
        绘制风格漂移趋势图
        
        Args:
            drift_analysis: 来自StyleDriftAnalyzer的分析结果
            output_path: 输出路径
            use_plotly: 是否使用plotly
            
        Returns:
            HTML字符串或保存路径
        """
        work_titles = drift_analysis['work_titles']
        drift_trend = drift_analysis['drift_trend']
        cumulative_drift = drift_analysis['cumulative_drift']
        
        if use_plotly:
            fig = make_subplots(rows=1, cols=2,
                               subplot_titles=('Style Divergence from Earliest Work',
                                             'Cumulative Style Drift'))
            
            divergence_metrics = ['js_divergence', 'kl_divergence', 'cosine_dissimilarity']
            
            for metric in divergence_metrics:
                x_values = [d['work'] for d in drift_trend]
                y_values = [d['divergences'][metric] for d in drift_trend]
                
                fig.add_trace(
                    go.Scatter(x=x_values, y=y_values,
                              mode='lines+markers',
                              name=metric,
                              line=dict(width=2)),
                    row=1, col=1
                )
            
            x_cum = [d['work'] for d in cumulative_drift]
            y_step = [d['step_divergence'] for d in cumulative_drift]
            y_cum = [d['cumulative_divergence'] for d in cumulative_drift]
            
            fig.add_trace(
                go.Bar(x=x_cum, y=y_step,
                      name='Step Divergence',
                      opacity=0.6),
                row=1, col=2
            )
            
            fig.add_trace(
                go.Scatter(x=x_cum, y=y_cum,
                          mode='lines+markers',
                          name='Cumulative Divergence',
                          line=dict(color='red', width=3)),
                row=1, col=2
            )
            
            fig.update_xaxes(title_text='Work', row=1, col=1)
            fig.update_yaxes(title_text='Divergence Value', row=1, col=1)
            fig.update_xaxes(title_text='Work', row=1, col=2)
            fig.update_yaxes(title_text='JS Divergence', row=1, col=2)
            
            fig.update_layout(
                title='Temporal Style Drift Analysis',
                height=500,
                width=1200,
                showlegend=True
            )
            
            if output_path:
                if output_path.endswith('.html'):
                    fig.write_html(output_path)
                else:
                    fig.write_image(output_path)
                return output_path
            
            return fig.to_html()
        else:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            divergence_metrics = ['js_divergence', 'kl_divergence', 'cosine_dissimilarity']
            x_ticks = range(len(drift_trend))
            x_labels = [d['work'] for d in drift_trend]
            
            for metric in divergence_metrics:
                y_values = [d['divergences'][metric] for d in drift_trend]
                ax1.plot(x_ticks, y_values, 'o-', label=metric, linewidth=2, markersize=8)
            
            ax1.set_xticks(x_ticks)
            ax1.set_xticklabels(x_labels, rotation=45, ha='right')
            ax1.set_ylabel('Divergence Value')
            ax1.set_title('Style Divergence from Earliest Work')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            x_cum = range(len(cumulative_drift))
            x_cum_labels = [d['work'] for d in cumulative_drift]
            y_step = [d['step_divergence'] for d in cumulative_drift]
            y_cum = [d['cumulative_divergence'] for d in cumulative_drift]
            
            ax2.bar(x_cum, y_step, alpha=0.6, label='Step Divergence')
            ax2_twin = ax2.twinx()
            ax2_twin.plot(x_cum, y_cum, 'ro-', linewidth=3, markersize=8, label='Cumulative')
            
            ax2.set_xticks(x_cum)
            ax2.set_xticklabels(x_cum_labels, rotation=45, ha='right')
            ax2.set_ylabel('Step Divergence (JS)')
            ax2_twin.set_ylabel('Cumulative Divergence')
            ax2.set_title('Cumulative Style Drift')
            
            lines1, labels1 = ax2.get_legend_handles_labels()
            lines2, labels2 = ax2_twin.get_legend_handles_labels()
            ax2.legend(lines1 + lines2, labels1 + labels2, loc='best')
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, bbox_inches='tight')
                plt.close()
                return output_path
            
            return None
