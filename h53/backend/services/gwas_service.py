import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.generalized_linear_model import GLM
from scipy import stats
from sklearn.impute import SimpleImputer
import warnings
warnings.filterwarnings('ignore')

class GWASService:
    def __init__(self):
        self.significance_threshold = 5e-8
    
    def run_glm(self, genotype_matrix, phenotype, covariates=None, maf_threshold=0.01, update_progress=None):
        n_variants, n_samples = genotype_matrix.shape
        
        results = []
        
        non_missing_pheno = ~np.isnan(phenotype)
        phenotype = phenotype[non_missing_pheno]
        
        genotype_matrix = genotype_matrix[:, non_missing_pheno]
        n_samples = len(phenotype)
        
        if covariates is not None:
            covariates = covariates[non_missing_pheno]
        
        if update_progress:
            update_progress(0.1, '准备分析数据')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix.T).T
        
        if update_progress:
            update_progress(0.2, '计算MAF过滤')
        
        allele_freq = genotype_imputed / 2
        maf = np.minimum(allele_freq.mean(axis=1), 1 - allele_freq.mean(axis=1))
        maf_filter = maf >= maf_threshold
        
        if update_progress:
            update_progress(0.3, '过滤后剩余 {} 个SNP进行分析', np.sum(maf_filter))
        
        variants_to_analyze = np.where(maf_filter)[0]
        n_analyze = len(variants_to_analyze)
        
        X_cov = sm.add_constant(covariates) if covariates is not None else np.ones((n_samples, 1))
        
        p_values = np.ones(n_variants)
        effect_sizes = np.zeros(n_variants)
        std_errors = np.zeros(n_variants)
        
        for idx, var_idx in enumerate(variants_to_analyze):
            if update_progress and idx % 1000 == 0:
                progress = 0.3 + 0.6 * (idx / n_analyze)
                update_progress(progress, f'正在分析第 {idx}/{n_analyze} 个SNP')
            
            gt = genotype_imputed[var_idx, :]
            
            gt_std = gt.std()
            if gt_std < 1e-10:
                continue
            
            X_full = np.column_stack([X_cov, gt])
            
            try:
                model = GLM(phenotype, X_full, family=sm.families.Gaussian())
                result = model.fit(disp=False)
                
                p_values[var_idx] = result.pvalues[-1]
                effect_sizes[var_idx] = result.params[-1]
                std_errors[var_idx] = result.bse[-1]
            except:
                continue
        
        if update_progress:
            update_progress(0.95, '计算inflation factor')
        
        inflation_factor = self._calculate_inflation_factor(p_values[maf_filter])
        
        if update_progress:
            update_progress(1.0, 'GLM分析完成')
        
        return {
            'p_values': p_values,
            'effect_sizes': effect_sizes,
            'std_errors': std_errors,
            'maf': maf,
            'inflation_factor': inflation_factor,
            'n_variants_analyzed': n_analyze,
            'model_used': 'GLM',
            'mlm_failed': False,
            'warnings': None
        }
    
    def run_mlm(self, genotype_matrix, phenotype, covariates=None, maf_threshold=0.01, update_progress=None):
        n_variants, n_samples = genotype_matrix.shape
        
        warnings_issued = []
        
        if update_progress:
            update_progress(0.1, '准备分析数据')
        
        non_missing_pheno = ~np.isnan(phenotype)
        phenotype = phenotype[non_missing_pheno]
        genotype_matrix = genotype_matrix[:, non_missing_pheno]
        n_samples = len(phenotype)
        
        if covariates is not None:
            covariates = covariates[non_missing_pheno]
        
        if update_progress:
            update_progress(0.2, '计算亲缘关系矩阵')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix.T).T
        
        K = self._calculate_kinship_matrix(genotype_imputed)
        
        if update_progress:
            update_progress(0.3, '计算MAF过滤')
        
        allele_freq = genotype_imputed / 2
        maf = np.minimum(allele_freq.mean(axis=1), 1 - allele_freq.mean(axis=1))
        maf_filter = maf >= maf_threshold
        variants_to_analyze = np.where(maf_filter)[0]
        n_analyze = len(variants_to_analyze)
        
        if update_progress:
            update_progress(0.35, f'过滤后剩余 {n_analyze} 个SNP进行分析')
        
        X_cov = sm.add_constant(covariates) if covariates is not None else np.ones((n_samples, 1))
        
        if update_progress:
            update_progress(0.4, '估计方差组分')
        
        mlm_failed = False
        try:
            sigma_g, sigma_e = self._estimate_variance_components(phenotype, K, X_cov)
            
            if np.isnan(sigma_g) or np.isnan(sigma_e) or np.isinf(sigma_g) or np.isinf(sigma_e):
                warnings_issued.append('方差组分估计产生非数值结果')
                raise ValueError('方差组分估计产生NaN或Inf')
            
            if sigma_g <= 1e-8 or sigma_e <= 1e-8:
                warnings_issued.append('方差组分估计值过小，可能存在收敛问题')
                raise ValueError('方差组分值过小')
            
        except Exception as e:
            mlm_failed = True
            warnings_issued.append(f'MLM方差组分估计失败: {str(e)}')
            warnings_issued.append('自动降级到GLM模型进行分析')
            
            if update_progress:
                update_progress(0.4, 'MLM收敛失败，降级到GLM模型')
            
            glm_result = self.run_glm(
                genotype_matrix, phenotype, covariates, 
                maf_threshold, update_progress
            )
            
            glm_result['model_used'] = 'GLM'
            glm_result['mlm_failed'] = True
            glm_result['warnings'] = warnings_issued
            glm_result['original_model'] = 'MLM'
            
            return glm_result
        
        if update_progress:
            update_progress(0.5, '计算V逆矩阵')
        
        V = sigma_g * K + sigma_e * np.eye(n_samples)
        try:
            V_inv = np.linalg.inv(V)
        except:
            try:
                V_inv = np.linalg.pinv(V)
                warnings_issued.append('V矩阵不可逆，使用广义逆代替')
            except Exception as e:
                mlm_failed = True
                warnings_issued.append(f'V矩阵求逆失败: {str(e)}')
                warnings_issued.append('自动降级到GLM模型进行分析')
                
                if update_progress:
                    update_progress(0.5, '矩阵求逆失败，降级到GLM模型')
                
                glm_result = self.run_glm(
                    genotype_matrix, phenotype, covariates, 
                    maf_threshold, update_progress
                )
                
                glm_result['model_used'] = 'GLM'
                glm_result['mlm_failed'] = True
                glm_result['warnings'] = warnings_issued
                glm_result['original_model'] = 'MLM'
                
                return glm_result
        
        try:
            XtVinvX = X_cov.T @ V_inv @ X_cov
            XtVinvY = X_cov.T @ V_inv @ phenotype
            beta_0 = np.linalg.solve(XtVinvX, XtVinvY)
            
            P = V_inv - V_inv @ X_cov @ np.linalg.solve(XtVinvX, X_cov.T @ V_inv)
        except Exception as e:
            mlm_failed = True
            warnings_issued.append(f'矩阵运算失败: {str(e)}')
            warnings_issued.append('自动降级到GLM模型进行分析')
            
            if update_progress:
                update_progress(0.5, '矩阵运算失败，降级到GLM模型')
            
            glm_result = self.run_glm(
                genotype_matrix, phenotype, covariates, 
                maf_threshold, update_progress
            )
            
            glm_result['model_used'] = 'GLM'
            glm_result['mlm_failed'] = True
            glm_result['warnings'] = warnings_issued
            glm_result['original_model'] = 'MLM'
            
            return glm_result
        
        p_values = np.ones(n_variants)
        effect_sizes = np.zeros(n_variants)
        std_errors = np.zeros(n_variants)
        successful_snps = 0
        
        for idx, var_idx in enumerate(variants_to_analyze):
            if update_progress and idx % 500 == 0:
                progress = 0.5 + 0.45 * (idx / n_analyze)
                update_progress(progress, f'正在分析第 {idx}/{n_analyze} 个SNP')
            
            gt = genotype_imputed[var_idx, :]
            
            gt_std = gt.std()
            if gt_std < 1e-10:
                continue
            
            try:
                gtVinvY = gt @ V_inv @ phenotype
                gtVinvgt = gt @ V_inv @ gt
                gtPX = gt @ P @ X_cov
                XtVingt = X_cov.T @ V_inv @ gt
                
                denom = gtVinvgt - gtPX @ np.linalg.solve(XtVinvX, gtPX.T)
                if np.abs(denom) < 1e-10:
                    continue
                
                beta = (gtVinvY - gtPX @ np.linalg.solve(XtVinvX, XtVingt)) / denom
                
                se = np.sqrt(1 / denom) if denom > 0 else np.nan
                
                if not np.isnan(se) and se > 0:
                    wald_stat = (beta / se) ** 2
                    p_values[var_idx] = stats.chi2.sf(wald_stat, 1)
                    effect_sizes[var_idx] = beta
                    std_errors[var_idx] = se
                    successful_snps += 1
            except:
                continue
        
        if successful_snps < n_analyze * 0.5:
            warnings_issued.append(f'超过50%的SNP分析失败（仅成功 {successful_snps}/{n_analyze}）')
        
        if update_progress:
            update_progress(0.98, '计算inflation factor')
        
        inflation_factor = self._calculate_inflation_factor(p_values[maf_filter])
        
        if update_progress:
            update_progress(1.0, 'MLM分析完成')
        
        return {
            'p_values': p_values,
            'effect_sizes': effect_sizes,
            'std_errors': std_errors,
            'maf': maf,
            'inflation_factor': inflation_factor,
            'n_variants_analyzed': n_analyze,
            'sigma_g': sigma_g,
            'sigma_e': sigma_e,
            'model_used': 'MLM',
            'mlm_failed': False,
            'warnings': warnings_issued if warnings_issued else None
        }
    
    def _calculate_kinship_matrix(self, genotype_matrix):
        n_variants, n_samples = genotype_matrix.shape
        
        allele_freq = genotype_matrix.mean(axis=1) / 2
        allele_freq = np.clip(allele_freq, 1e-4, 1 - 1e-4)
        
        normalized_gt = (genotype_matrix - 2 * allele_freq[:, np.newaxis]) / np.sqrt(2 * allele_freq * (1 - allele_freq))[:, np.newaxis]
        
        K = (normalized_gt.T @ normalized_gt) / n_variants
        
        return K
    
    def _estimate_variance_components(self, y, K, X):
        n = len(y)
        
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
        except np.linalg.LinAlgError:
            XtX_inv = np.linalg.pinv(X.T @ X)
        
        P0 = np.eye(n) - X @ XtX_inv @ X.T
        
        Py = P0 @ y
        
        trPK = np.trace(P0 @ K)
        trP = n - X.shape[1]
        
        yPKy = y.T @ P0 @ K @ P0 @ y
        yPy = y.T @ Py
        
        if trPK <= 0 or trP <= 0:
            raise ValueError(f"矩阵迹非正: trPK={trPK}, trP={trP}")
        
        ratio1 = yPKy / trPK
        ratio2 = yPy / trP
        denom_ratio = trPK / trP
        
        sigma_g = (ratio1 - ratio2) / denom_ratio
        
        if sigma_g < 0:
            sigma_g = max(0.01 * np.var(y), 1e-4)
        
        sigma_e = ratio2 - sigma_g * (trP / trP)
        if sigma_e < 0:
            sigma_e = max(0.01 * np.var(y), 1e-4)
        
        if sigma_g <= 0 or sigma_e <= 0:
            sigma_g = max(sigma_g, 0.01 * np.var(y))
            sigma_e = max(sigma_e, 0.01 * np.var(y))
        
        sigma_g = max(sigma_g, 1e-4)
        sigma_e = max(sigma_e, 1e-4)
        
        return sigma_g, sigma_e
    
    def _calculate_inflation_factor(self, p_values):
        p_values = np.array(p_values)
        p_values = p_values[(p_values > 0) & (p_values <= 1)]
        if len(p_values) == 0:
            return 1.0
        
        p_values = np.sort(p_values)
        
        mid_mask = (p_values >= 0.3) & (p_values <= 0.7)
        if np.sum(mid_mask) < 10:
            mid_mask = (p_values >= 0.1) & (p_values <= 0.9)
        if np.sum(mid_mask) < 10:
            mid_mask = np.ones_like(p_values, dtype=bool)
        
        p_values_mid = p_values[mid_mask]
        
        chi2_stats = stats.chi2.ppf(1 - p_values_mid, 1)
        median_chi2 = np.median(chi2_stats)
        expected_median = stats.chi2.ppf(0.5, 1)
        inflation_factor = median_chi2 / expected_median
        
        return float(inflation_factor)
    
    def prepare_manhattan_data(self, variants, p_values, maf=None, effect_sizes=None):
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
            
            if maf is not None:
                entry['maf'] = float(maf[i])
            if effect_sizes is not None:
                entry['effectSize'] = float(effect_sizes[i])
            
            manhattan_data.append(entry)
        
        return manhattan_data
    
    def prepare_qq_data(self, p_values):
        p_values = np.array(p_values)
        p_values = p_values[(p_values > 0) & (p_values <= 1)]
        p_values = np.sort(p_values)
        
        n = len(p_values)
        expected = -np.log10(np.arange(1, n + 1) / (n + 1))
        observed = -np.log10(p_values)
        
        qq_data = []
        for e, o in zip(expected, observed):
            qq_data.append({
                'expected': float(e),
                'observed': float(o)
            })
        
        return qq_data
    
    def get_significant_snps(self, variants, p_values, maf, effect_sizes, threshold=5e-8):
        significant_indices = np.where(p_values <= threshold)[0]
        
        snps = []
        for idx in significant_indices:
            var = variants[idx] if idx < len(variants) else {}
            snps.append({
                'snp_id': var.get('id', f'snp_{idx}'),
                'chromosome': var.get('chr', ''),
                'position': var.get('pos', 0),
                'ref_allele': var.get('ref', ''),
                'alt_allele': var.get('alt', ''),
                'p_value': float(p_values[idx]),
                'log10_p': float(-np.log10(max(p_values[idx], 1e-300))),
                'effect_size': float(effect_sizes[idx]),
                'maf': float(maf[idx])
            })
        
        return snps
