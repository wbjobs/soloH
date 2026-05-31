import numpy as np
import pandas as pd
from sklearn.decomposition import PCA as SKPCA
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

class PCAService:
    def calculate_pca(self, genotype_matrix, n_components=10):
        n_variants, n_samples = genotype_matrix.shape
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix)
        
        scaler = StandardScaler()
        genotype_scaled = scaler.fit_transform(genotype_imputed.T)
        
        pca = SKPCA(n_components=min(n_components, n_samples, n_variants))
        pc_scores = pca.fit_transform(genotype_scaled)
        
        explained_variance_ratio = pca.explained_variance_ratio_.tolist()
        
        pc_data = []
        for i in range(pc_scores.shape[0]):
            pc_dict = {
                'PC1': float(pc_scores[i, 0]) if pc_scores.shape[1] > 0 else 0,
                'PC2': float(pc_scores[i, 1]) if pc_scores.shape[1] > 1 else 0,
                'PC3': float(pc_scores[i, 2]) if pc_scores.shape[1] > 2 else 0,
            }
            for j in range(3, min(n_components, pc_scores.shape[1])):
                pc_dict[f'PC{j+1}'] = float(pc_scores[i, j])
            pc_data.append(pc_dict)
        
        return {
            'explained_variance_ratio': explained_variance_ratio,
            'pc_data': pc_data,
            'pc_scores': pc_scores,
            'loadings': pca.components_.T.tolist() if hasattr(pca, 'components_') else None
        }
    
    def calculate_pca_from_vcf(self, vcf_parser, sample_indices=None, n_components=10, update_progress=None):
        if update_progress:
            update_progress(0.1, '读取基因型数据')
        
        genotypes, samples, variants = vcf_parser.get_genotype_matrix()
        
        if sample_indices is not None:
            genotypes = genotypes[:, sample_indices]
            samples = [samples[i] for i in sample_indices]
        
        if update_progress:
            update_progress(0.3, '预处理基因型数据')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotypes)
        
        scaler = StandardScaler()
        genotype_scaled = scaler.fit_transform(genotype_imputed.T)
        
        if update_progress:
            update_progress(0.5, '执行PCA分析')
        
        pca = SKPCA(n_components=min(n_components, len(samples), len(variants)))
        pc_scores = pca.fit_transform(genotype_scaled)
        
        if update_progress:
            update_progress(0.8, '处理结果')
        
        explained_variance_ratio = pca.explained_variance_ratio_.tolist()
        
        pc_data = []
        for i, sample in enumerate(samples):
            pc_dict = {'sampleId': sample}
            for j in range(min(n_components, pc_scores.shape[1])):
                pc_dict[f'PC{j+1}'] = float(pc_scores[i, j])
            pc_data.append(pc_dict)
        
        if update_progress:
            update_progress(1.0, 'PCA计算完成')
        
        return {
            'explained_variance_ratio': explained_variance_ratio,
            'pc_data': pc_data,
            'pc_scores': pc_scores,
            'samples': samples
        }
    
    def select_pc_components(self, explained_variance_ratio, threshold=0.8):
        cumulative = 0
        n_components = 0
        for i, var in enumerate(explained_variance_ratio):
            cumulative += var
            n_components = i + 1
            if cumulative >= threshold:
                break
        return n_components
