import numpy as np
import pandas as pd
from scipy import stats
from scipy.linalg import svd
from sklearn.cross_decomposition import CCA
from sklearn.preprocessing import StandardScaler
from statsmodels.multivariate.manova import MANOVA
from sklearn.impute import SimpleImputer
import warnings
warnings.filterwarnings('ignore')


class MultiPhenotypeService:
    """
    多表型联合分析服务
    支持MANOVA（多元方差分析）和CCA（典型相关分析）
    """
    
    def __init__(self):
        self.significance_threshold = 5e-8
    
    def run_manova(self, genotype_matrix, phenotypes, covariates=None, maf_threshold=0.01, update_progress=None):
        """
        执行MANOVA多表型联合分析
        
        Parameters:
        -----------
        genotype_matrix : np.ndarray
            基因型矩阵 (n_variants, n_samples)
        phenotypes : np.ndarray
            表型矩阵 (n_samples, n_phenotypes)
        covariates : np.ndarray, optional
            协变量矩阵 (n_samples, n_covariates)
        maf_threshold : float
            MAF过滤阈值
        update_progress : callable, optional
            进度更新回调函数
        """
        n_variants, n_samples = genotype_matrix.shape
        n_phenotypes = phenotypes.shape[1]
        
        if update_progress:
            update_progress(0.05, '准备多表型分析数据')
        
        non_missing_mask = ~np.any(np.isnan(phenotypes), axis=1)
        phenotypes = phenotypes[non_missing_mask]
        genotype_matrix = genotype_matrix[:, non_missing_mask]
        n_samples = len(phenotypes)
        
        if covariates is not None:
            covariates = covariates[non_missing_mask]
        
        if update_progress:
            update_progress(0.1, '处理缺失基因型')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix.T).T
        
        if update_progress:
            update_progress(0.2, '计算MAF过滤')
        
        allele_freq = genotype_imputed / 2
        maf = np.minimum(allele_freq.mean(axis=1), 1 - allele_freq.mean(axis=1))
        maf_filter = maf >= maf_threshold
        variants_to_analyze = np.where(maf_filter)[0]
        n_analyze = len(variants_to_analyze)
        
        if update_progress:
            update_progress(0.25, f'过滤后剩余 {n_analyze} 个SNP进行分析')
        
        if covariates is not None:
            from statsmodels.regression.linear_model import OLS
            import statsmodels.api as sm
            
            phenotypes_residual = np.zeros_like(phenotypes)
            for i in range(n_phenotypes):
                X_cov = sm.add_constant(covariates)
                model = OLS(phenotypes[:, i], X_cov)
                result = model.fit()
                phenotypes_residual[:, i] = result.resid
            phenotypes_analysis = phenotypes_residual
        else:
            phenotypes_analysis = phenotypes
        
        scaler = StandardScaler()
        phenotypes_scaled = scaler.fit_transform(phenotypes_analysis)
        
        p_values = np.ones(n_variants)
        f_statistics = np.zeros(n_variants)
        effect_sizes = np.zeros((n_variants, n_phenotypes))
        wilks_lambda = np.ones(n_variants)
        
        for idx, var_idx in enumerate(variants_to_analyze):
            if update_progress and idx % 500 == 0:
                progress = 0.3 + 0.6 * (idx / n_analyze)
                update_progress(progress, f'正在分析第 {idx}/{n_analyze} 个SNP')
            
            gt = genotype_imputed[var_idx, :]
            gt_std = gt.std()
            
            if gt_std < 1e-10:
                continue
            
            try:
                gt_groups = np.zeros((n_samples, 3))
                gt_groups[:, 0] = (gt == 0).astype(float)
                gt_groups[:, 1] = (gt == 1).astype(float)
                gt_groups[:, 2] = (gt == 2).astype(float)
                
                has_group = gt_groups.sum(axis=0) > 5
                if np.sum(has_group) < 2:
                    gt_centered = gt - gt.mean()
                    X_full = np.column_stack([np.ones(n_samples), gt_centered])
                    
                    from statsmodels.multivariate.manova import MANOVA
                    data = pd.DataFrame(
                        np.column_stack([gt_centered, phenotypes_scaled]),
                        columns=['genotype'] + [f'pheno_{i}' for i in range(n_phenotypes)]
                    )
                    formula = f'pheno_0 + pheno_1 + pheno_2 + pheno_3 + pheno_4 ~ genotype' if n_phenotypes >= 5 else \
                              ' + '.join([f'pheno_{i}' for i in range(n_phenotypes)]) + ' ~ genotype'
                    
                    try:
                        manova = MANOVA.from_formula(formula, data)
                        manova_result = manova.mv_test()
                        p_val = manova_result.results['genotype']['stat']['Pr > F']['Pillai\'s trace']
                        f_stat = manova_result.results['genotype']['stat']['F stat']['Pillai\'s trace']
                        p_values[var_idx] = max(p_val, 1e-300)
                        f_statistics[var_idx] = f_stat if not np.isnan(f_stat) else 0
                    except:
                        corr = np.corrcoef(gt_centered, phenotypes_scaled.T)[0, 1:]
                        f_stat = np.sum(corr**2) / (1 - np.sum(corr**2)) * (n_samples - 2)
                        p_values[var_idx] = max(stats.f.sf(f_stat, n_phenotypes, n_samples - n_phenotypes - 1), 1e-300)
                        f_statistics[var_idx] = f_stat
                    
                    for i in range(n_phenotypes):
                        corr = np.corrcoef(gt_centered, phenotypes_scaled[:, i])[0, 1]
                        effect_sizes[var_idx, i] = corr
                    continue
                
                try:
                    data_dict = {f'pheno_{i}': phenotypes_scaled[:, i] for i in range(n_phenotypes)}
                    for j in range(3):
                        if has_group[j]:
                            data_dict[f'gt_{j}'] = gt_groups[:, j]
                    
                    data = pd.DataFrame(data_dict)
                    
                    if n_phenotypes == 1:
                        formula = 'pheno_0 ~ ' + ' + '.join([f'gt_{j}' for j in range(3) if has_group[j]])
                    else:
                        formula = ' + '.join([f'pheno_{i}' for i in range(n_phenotypes)]) + ' ~ ' + \
                                  ' + '.join([f'gt_{j}' for j in range(3) if has_group[j]])
                    
                    manova = MANOVA.from_formula(formula, data)
                    manova_result = manova.mv_test()
                    
                    effect_key = [k for k in manova_result.results.keys()][0]
                    p_val = manova_result.results[effect_key]['stat']['Pr > F']['Pillai\'s trace']
                    f_stat = manova_result.results[effect_key]['stat']['F stat']['Pillai\'s trace']
                    wilks = manova_result.results[effect_key]['stat']['value']['Wilks\' lambda']
                    
                    p_values[var_idx] = max(p_val, 1e-300)
                    f_statistics[var_idx] = f_stat if not np.isnan(f_stat) else 0
                    wilks_lambda[var_idx] = wilks if not np.isnan(wilks) else 1.0
                    
                    for i in range(n_phenotypes):
                        for j in range(3):
                            if has_group[j]:
                                break
                        if has_group[1]:
                            effect = np.mean(phenotypes_scaled[gt == 1, i]) - np.mean(phenotypes_scaled[gt == 0, i])
                        elif has_group[2]:
                            effect = np.mean(phenotypes_scaled[gt == 2, i]) - np.mean(phenotypes_scaled[gt == 0, i])
                        else:
                            effect = 0
                        effect_sizes[var_idx, i] = effect
                    
                except Exception as e:
                    corr = np.corrcoef(gt, phenotypes_scaled.T)[0, 1:]
                    f_stat = np.sum(corr**2) / (1 - np.sum(corr**2) + 1e-10) * (n_samples - n_phenotypes - 1) / n_phenotypes
                    p_values[var_idx] = max(stats.f.sf(f_stat, n_phenotypes, n_samples - n_phenotypes - 1), 1e-300)
                    f_statistics[var_idx] = f_stat
                    for i in range(n_phenotypes):
                        corr = np.corrcoef(gt, phenotypes_scaled[:, i])[0, 1]
                        effect_sizes[var_idx, i] = corr
                    
            except:
                continue
        
        if update_progress:
            update_progress(0.95, '计算inflation factor')
        
        from .gwas_service import GWASService
        gwas_service = GWASService()
        inflation_factor = gwas_service._calculate_inflation_factor(p_values[maf_filter])
        
        if update_progress:
            update_progress(1.0, 'MANOVA多表型分析完成')
        
        return {
            'p_values': p_values,
            'f_statistics': f_statistics,
            'wilks_lambda': wilks_lambda,
            'effect_sizes': effect_sizes,
            'maf': maf,
            'inflation_factor': inflation_factor,
            'n_variants_analyzed': n_analyze,
            'n_phenotypes': n_phenotypes,
            'model': 'MANOVA'
        }
    
    def run_cca(self, genotype_matrix, phenotypes, covariates=None, n_components=3, maf_threshold=0.01, update_progress=None):
        """
        执行CCA（典型相关分析）识别基因型和表型之间的关联模式
        
        Parameters:
        -----------
        genotype_matrix : np.ndarray
            基因型矩阵 (n_variants, n_samples)
        phenotypes : np.ndarray
            表型矩阵 (n_samples, n_phenotypes)
        covariates : np.ndarray, optional
            协变量矩阵 (n_samples, n_covariates)
        n_components : int
            CCA成分数
        maf_threshold : float
            MAF过滤阈值
        update_progress : callable, optional
            进度更新回调函数
        """
        n_variants, n_samples = genotype_matrix.shape
        n_phenotypes = phenotypes.shape[1]
        
        if update_progress:
            update_progress(0.05, '准备CCA分析数据')
        
        non_missing_mask = ~np.any(np.isnan(phenotypes), axis=1)
        phenotypes = phenotypes[non_missing_mask]
        genotype_matrix = genotype_matrix[:, non_missing_mask]
        n_samples = len(phenotypes)
        
        if covariates is not None:
            covariates = covariates[non_missing_mask]
        
        if update_progress:
            update_progress(0.1, '处理缺失基因型')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix.T).T
        
        if update_progress:
            update_progress(0.2, '计算MAF过滤')
        
        allele_freq = genotype_imputed / 2
        maf = np.minimum(allele_freq.mean(axis=1), 1 - allele_freq.mean(axis=1))
        maf_filter = maf >= maf_threshold
        genotype_filtered = genotype_imputed[maf_filter, :].T
        
        n_analyze = np.sum(maf_filter)
        
        if update_progress:
            update_progress(0.3, f'使用 {n_analyze} 个SNP进行CCA分析')
        
        if covariates is not None:
            from statsmodels.regression.linear_model import OLS
            import statsmodels.api as sm
            
            phenotypes_residual = np.zeros_like(phenotypes)
            for i in range(n_phenotypes):
                X_cov = sm.add_constant(covariates)
                model = OLS(phenotypes[:, i], X_cov)
                result = model.fit()
                phenotypes_residual[:, i] = result.resid
            phenotypes_analysis = phenotypes_residual
            
            genotype_residual = np.zeros_like(genotype_filtered)
            for i in range(genotype_filtered.shape[1]):
                X_cov = sm.add_constant(covariates)
                model = OLS(genotype_filtered[:, i], X_cov)
                result = model.fit()
                genotype_residual[:, i] = result.resid
            genotype_analysis = genotype_residual
        else:
            phenotypes_analysis = phenotypes
            genotype_analysis = genotype_filtered
        
        scaler = StandardScaler()
        phenotypes_scaled = scaler.fit_transform(phenotypes_analysis)
        genotype_scaled = scaler.fit_transform(genotype_analysis)
        
        if update_progress:
            update_progress(0.4, '执行CCA分析')
        
        n_components_actual = min(n_components, n_phenotypes, n_analyze)
        
        try:
            cca = CCA(n_components=n_components_actual, max_iter=2000)
            X_c, Y_c = cca.fit_transform(genotype_scaled, phenotypes_scaled)
            
            canonical_correlations = []
            for i in range(n_components_actual):
                corr = np.corrcoef(X_c[:, i], Y_c[:, i])[0, 1]
                canonical_correlations.append(corr if not np.isnan(corr) else 0)
            
            p_values = np.ones(n_variants)
            loading_scores = np.zeros((n_variants, n_components_actual))
            
            if update_progress:
                update_progress(0.6, '计算SNP关联显著性')
            
            for idx, var_idx in enumerate(np.where(maf_filter)[0]):
                if update_progress and idx % 500 == 0:
                    progress = 0.6 + 0.3 * (idx / n_analyze)
                    update_progress(progress, f'正在计算第 {idx}/{n_analyze} 个SNP的显著性')
                
                gt = genotype_analysis[:, idx]
                
                for comp in range(n_components_actual):
                    loading_scores[var_idx, comp] = cca.x_loadings_[idx, comp] if hasattr(cca, 'x_loadings_') else 0
                
                try:
                    r_matrix = np.corrcoef(gt, phenotypes_scaled.T)[0, 1:]
                    f_stat = np.sum(r_matrix**2) / (1 - np.sum(r_matrix**2) + 1e-10) * (n_samples - n_phenotypes - 1) / n_phenotypes
                    p_values[var_idx] = max(stats.f.sf(f_stat, n_phenotypes, n_samples - n_phenotypes - 1), 1e-300)
                except:
                    continue
            
            canonical_weights_x = cca.x_weights_.T.tolist() if hasattr(cca, 'x_weights_') else []
            canonical_weights_y = cca.y_weights_.T.tolist() if hasattr(cca, 'y_weights_') else []
            
        except Exception as e:
            canonical_correlations = [0] * n_components_actual
            loading_scores = np.zeros((n_variants, n_components_actual))
            p_values = np.ones(n_variants)
            canonical_weights_x = []
            canonical_weights_y = []
        
        if update_progress:
            update_progress(0.95, '计算inflation factor')
        
        from .gwas_service import GWASService
        gwas_service = GWASService()
        inflation_factor = gwas_service._calculate_inflation_factor(p_values[maf_filter])
        
        if update_progress:
            update_progress(1.0, 'CCA分析完成')
        
        return {
            'p_values': p_values,
            'loading_scores': loading_scores,
            'canonical_correlations': canonical_correlations,
            'canonical_weights_x': canonical_weights_x,
            'canonical_weights_y': canonical_weights_y,
            'maf': maf,
            'inflation_factor': inflation_factor,
            'n_variants_analyzed': n_analyze,
            'n_phenotypes': n_phenotypes,
            'n_components': n_components_actual,
            'model': 'CCA'
        }
    
    def prepare_multiphenotype_manhattan_data(self, variants, p_values, f_statistics=None, maf=None):
        """
        准备多表型分析的曼哈顿图数据
        """
        manhattan_data = []
        
        for i, var in enumerate(variants):
            p = p_values[i]
            if p <= 0:
                p = 1e-300
            
            log10_p = -np.log10(p)
            
            entry = {
                'chr': var.get('chr', str(i)),
                'pos': var.get('pos', i),
                'snp': var.get('id', f'snp_{i}'),
                'pValue': float(p),
                'log10P': float(log10_p)
            }
            
            if f_statistics is not None:
                entry['fStatistic'] = float(f_statistics[i])
            if maf is not None:
                entry['maf'] = float(maf[i])
            
            manhattan_data.append(entry)
        
        return manhattan_data
