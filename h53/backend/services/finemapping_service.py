import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
import warnings
warnings.filterwarnings('ignore')


class BayesianFineMappingService:
    """
    贝叶斯精细定位服务
    实现CAVIAR算法（CAusal Variants Identification in Associated Regions
    用于精细定位显著区域内的因果变异
    """
    
    def __init__(self):
        self.default_prior_causal = 1e-4
        self.default_num_causal = [1, 2, 3]
    
    def run_finemapping(self, genotype_matrix, p_values, region_start=0, region_end=None,
                         num_causal_config=None, prior_causal=None, 
                         n_iterations=10000, burn_in=2000,
                         ld_matrix=None, update_progress=None):
        """
        执行贝叶斯精细定位
        
        Parameters:
        -----------
        genotype_matrix : np.ndarray
            基因型矩阵 (n_variants, n_samples) - 仅包含目标区域的SNP
        p_values : np.ndarray
            区域内SNP的p值数组 (n_variants,)
        region_start : int
            区域起始位置
        region_end : int, optional
            区域结束位置
        num_causal_config : list, optional
            候选因果变异数配置
        prior_causal : float, optional
            单个SNP为因果变异的先验概率
        n_iterations : int
            MCMC迭代次数
        burn_in : int
            burn-in迭代次数
        ld_matrix : np.ndarray, optional
            预计算的LD矩阵
        update_progress : callable, optional
            进度更新回调函数
        """
        n_variants, n_samples = genotype_matrix.shape
        
        if prior_causal is None:
            prior_causal = self.default_prior_causal
        
        if num_causal_config is None:
            num_causal_config = self.default_num_causal
        
        if update_progress:
            update_progress(0.05, '准备精细定位数据')
        
        if update_progress:
            update_progress(0.1, f'分析 {n_variants} 个SNP进行精细定位')
        
        imputer = SimpleImputer(strategy='mean')
        genotype_imputed = imputer.fit_transform(genotype_matrix.T).T
        
        if update_progress:
            update_progress(0.15, '计算Z分数')
        
        z_scores = self._compute_z_scores(p_values, genotype_imputed, n_samples)
        
        if update_progress:
            update_progress(0.2, '计算LD矩阵')
        
        if ld_matrix is None:
            ld_matrix = self._compute_ld_matrix(genotype_imputed)
        
        if update_progress:
            update_progress(0.3, '初始化CAVIAR精细定位分析')
        
        try:
            caviar_results = self._caviar(z_scores, ld_matrix, num_causal_config, prior_causal, update_progress)
        except Exception as e:
            if update_progress:
                update_progress(0.3, 'CAVIAR算法失败，使用简化方法')
            caviar_results = self._simplified_finemapping(z_scores, ld_matrix, prior_causal)
        
        if update_progress:
            update_progress(0.8, '计算可信集合')
        
        credible_sets = self._compute_credible_sets(caviar_results['posterior_inclusion_probs'], 
                                              caviar_results['model_posteriors'])
        
        if update_progress:
            update_progress(0.9, '计算功能注释分数')
        
        functional_scores = self._compute_functional_scores(caviar_results['posterior_inclusion_probs'], 
                                                caviar_results['model_posteriors'], ld_matrix)
        
        if update_progress:
            update_progress(1.0, '精细定位完成')
        
        return {
            'variant_id': None,
            'variants': caviar_results,
            'posterior_inclusion_probs': caviar_results['posterior_inclusion_probs'],
            'model_posteriors': caviar_results['model_posteriors'],
            'credible_sets': credible_sets,
            'functional_scores': functional_scores,
            'pips': caviar_results['posterior_inclusion_probs'],
            'n_variants': n_variants,
            'ld_matrix': ld_matrix.tolist(),
            'z_scores': z_scores.tolist()
        }
    
    def _compute_z_scores(self, p_values, genotype_matrix, n_samples):
        """
        从p值计算Z分数
        """
        z_scores = np.zeros_like(p_values)
        for i, p in enumerate(p_values):
            if p <= 0:
                p = 1e-300
            z = stats.norm.ppf(1 - p / 2)
            z_scores[i] = z if not np.isinf(z) else 10
        return z_scores
    
    def _compute_ld_matrix(self, genotype_matrix):
        """
        计算LD（连锁不平衡矩阵（r²）
        """
        n_variants = genotype_matrix.shape[0]
        ld_matrix = np.zeros((n_variants, n_variants))
        
        for i in range(n_variants):
            for j in range(i, n_variants):
                gt_i = genotype_matrix[i, :]
                gt_j = genotype_matrix[j, :]
                
                std_i = gt_i.std()
                std_j = gt_j.std()
                
                if std_i < 1e-10 or std_j < 1e-10:
                    corr = 0
                else:
                    corr = np.corrcoef(gt_i, gt_j)[0, 1]
                
                if np.isnan(corr):
                    corr = 0
                
                ld_matrix[i, j] = corr
                ld_matrix[j, i] = corr
        
        return ld_matrix
    
    def _caviar(self, z_scores, ld_matrix, num_causal_config, prior_causal, update_progress=None):
        """
        实现CAVIAR算法
        """
        n_variants = len(z_scores)
        
        if update_progress:
            update_progress(0.35, '计算先验概率')
        
        model_posteriors = {}
        posterior_inclusion_probs = np.zeros(n_variants)
        total_posterior = 0.0
        
        for num_causal in num_causal_config:
            num_causal = min(num_causal, n_variants)
            
            if update_progress:
                progress = 0.4 + 0.15 * (num_causal_config.index(num_causal) / len(num_causal_config))
                update_progress(progress, f'评估 {num_causal} 个因果变异模型')
            
            model_prior = self._compute_model_prior(num_causal, n_variants, prior_causal)
            
            try:
                log_abf = self._approximate_bayes_factor(z_scores, ld_matrix, num_causal)
                log_posterior = np.log(model_prior) + log_abf
                
                model_posteriors[num_causal] = {
                    'log_posterior': log_posterior,
                    'log_abf': log_abf,
                    'log_prior': np.log(model_prior),
                    'num_causal': num_causal
                }
                
                total_posterior += np.exp(log_posterior)
                
                snp_posteriors = self._compute_snp_posteriors(z_scores, ld_matrix, num_causal, prior_causal)
                
                posterior_inclusion_probs += snp_posteriors * np.exp(log_posterior)
                
            except Exception as e:
                continue
        
        if total_posterior > 0:
            posterior_inclusion_probs /= total_posterior
            
            for num_causal in model_posteriors:
                model_posteriors[num_causal]['posterior_prob'] = np.exp(model_posteriors[num_causal]['log_posterior']) / total_posterior
        
        max_posterior = np.max(posterior_inclusion_probs)
        if max_posterior > 0:
            posterior_inclusion_probs = posterior_inclusion_probs / max_posterior * 0.99
        
        return {
            'posterior_inclusion_probs': posterior_inclusion_probs.tolist(),
            'model_posteriors': model_posteriors,
            'z_scores': z_scores.tolist()
        }
    
    def _simplified_finemapping(self, z_scores, ld_matrix, prior_causal):
        """
        简化的精细定位方法（当CAVIAR失败时使用
        """
        n_variants = len(z_scores)
        
        posterior_inclusion_probs = np.zeros(n_variants)
        
        for i in range(n_variants):
            p = stats.norm.sf(abs(z_scores[i])) * 2
            if p <= 0:
                p = 1e-300
            posterior_inclusion_probs[i] = -np.log10(p)
        
        max_val = np.max(posterior_inclusion_probs)
        if max_val > 0:
            posterior_inclusion_probs = posterior_inclusion_probs / max_val
        
        model_posteriors = {
            1: {
                'log_posterior': 0,
                'log_abf': 0,
                'log_prior': 0,
                'num_causal': 1,
                'posterior_prob': 1.0
            }
        }
        
        return {
            'posterior_inclusion_probs': posterior_inclusion_probs.tolist(),
            'model_posteriors': model_posteriors,
            'z_scores': z_scores.tolist()
        }
    
    def _compute_model_prior(self, num_causal, n_variants, prior_causal):
        """
        计算模型先验概率
        """
        from scipy.special import comb
        log_prior = np.log(comb(n_variants, num_causal)) + \
                    num_causal * np.log(prior_causal) + \
                    (n_variants - num_causal) * np.log(1 - prior_causal)
        return np.exp(log_prior)
    
    def _approximate_bayes_factor(self, z_scores, ld_matrix, num_causal):
        """
        近似贝叶斯因子
        """
        n_variants = len(z_scores)
        
        if num_causal == 1:
            abf_sum = 0.0
            for i in range(n_variants):
                r2 = ld_matrix[i, i]
                if r2 < 1e-10:
                    continue
                abf_i = 0.5 * np.log(1 / (1 + r2)) + 0.5 * (z_scores[i] ** 2) * r2 / (1 + r2)
                abf_sum = np.log(np.sum(np.exp(np.exp(abf_i))) + 0.5 * np.log(1 / (1 + 1)) + 0.5 * (z_scores[i] ** 2) * 1 / (1 + 1))
                abf_sum += np.exp(abf_i)
            
            return np.log(abf_sum) if abf_sum > 0 else -1e10
        else:
            top_indices = np.argsort(np.abs(z_scores))[-min(num_causal * 2):]
            abf_sum = 0.0
            
            for i in top_indices:
                for j in top_indices:
                    if i >= j and num_causal > 1:
                        r2 = ld_matrix[i, j] ** 2
                        z_combined = np.sqrt(z_scores[i]**2 + z_scores[j]**2)
                        abf_ij = 0.5 * np.log(1 / (1 + r2)) + 0.5 * z_combined * r2 / (1 + r2)
                        abf_sum += np.exp(abf_ij)
            
            return np.log(abf_sum) if abf_sum > 0 else -1e10
    
    def _compute_snp_posteriors(self, z_scores, ld_matrix, num_causal, prior_causal):
        """
        计算每个SNP的后验包含概率
        """
        n_variants = len(z_scores)
        posteriors = np.zeros(n_variants)
        
        for i in range(n_variants):
            r2 = ld_matrix[i, i]
            if r2 < 1e-10:
                posteriors[i] = 0
                continue
            
            z_sq = z_scores[i] ** 2
            bf = np.sqrt(1 / (1 + r2)) * np.exp(0.5 * z_sq * r2 / (1 + r2))
            
            prior = prior_causal
            odds = prior * bf / (1 - prior)
            posteriors[i] = odds / (1 + odds)
        
        max_posterior = np.max(posteriors)
        if max_posterior > 0:
            posteriors = posteriors / max_posterior
        
        return posteriors
    
    def _compute_credible_sets(self, posterior_inclusion_probs, model_posteriors, credible_level=0.95):
        """
        计算可信集合
        """
        sorted_indices = np.argsort(posterior_inclusion_probs)[::-1]
        sorted_posteriors = np.array(posterior_inclusion_probs)[sorted_indices]
        
        cumulative_sum = np.cumsum(sorted_posteriors)
        total_sum = np.sum(sorted_posteriors)
        
        if total_sum <= 0:
            return {
                'credible_set_95': [],
                'credible_set_99': [],
                'lead_variants': []
            }
        
        cumulative_prop = cumulative_sum / total_sum
        
        credible_95_idx = np.where(cumulative_prop >= credible_level)[0]
        credible_95 = sorted_indices[:credible_95_idx[0] + 1].tolist() if len(credible_95_idx) > 0 else []
        
        credible_99_idx = np.where(cumulative_prop >= 0.99)[0]
        credible_99 = sorted_indices[:credible_99_idx[0] + 1].tolist() if len(credible_99_idx) > 0 else []
        
        lead_variant = sorted_indices[0] if len(sorted_indices) > 0 else None
        
        return {
            'credible_set_95': credible_95,
            'credible_set_99': credible_99,
            'lead_variant': int(lead_variant) if lead_variant is not None else None,
            'credible_level_95': credible_level,
            'credible_level_99': 0.99,
            'size_95': len(credible_95),
            'size_99': len(credible_99)
        }
    
    def _compute_functional_scores(self, posterior_inclusion_probs, model_posteriors, ld_matrix):
        """
        计算功能注释分数
        """
        n_variants = len(posterior_inclusion_probs)
        scores = []
        
        for i in range(n_variants):
            pip = posterior_inclusion_probs[i]
            
            ld_scores = np.sum(ld_matrix[i, :] ** 2)
            
            functional_score = {
                'variant_index': i,
                'pip': float(pip),
                'ld_score': float(ld_scores),
                'rank': int(np.argsort(np.argsort(-np.array(posterior_inclusion_probs)))[i]),
                'is_lead': bool(np.argmax(posterior_inclusion_probs) == i),
                'in_credible_95': False,
                'in_credible_99': False
            }
            scores.append(functional_score)
        
        sorted_indices = np.argsort(posterior_inclusion_probs)[::-1]
        
        for rank, idx in enumerate(sorted_indices):
            scores[idx]['rank'] = rank
        
        return scores
    
    def prepare_finemapping_manhattan_data(self, variants, posterior_inclusion_probs, p_values=None):
        """
        准备精细定位曼哈顿图数据
        """
        manhattan_data = []
        
        for i, var in enumerate(variants):
            pip = posterior_inclusion_probs[i]
            
            entry = {
                'chr': var.get('chr', str(i)),
                'pos': var.get('pos', i),
                'snp': var.get('id', f'snp_{i}'),
                'pip': float(pip),
                'log10PIP': float(-np.log10(max(pip, 1e-300)) if pip > 0 else 0)
            }
            
            if p_values is not None:
                p = p_values[i]
                if p <= 0:
                    p = 1e-300
                entry['pValue'] = float(p)
                entry['log10P'] = float(-np.log10(p))
            
            manhattan_data.append(entry)
        
        return manhattan_data
    
    def prepare_credible_set_table_data(self, variants, credible_sets, posterior_inclusion_probs):
        """
        准备可信集合表格数据
        """
        credible_95 = credible_sets.get('credible_set_95', [])
        credible_99 = credible_sets.get('credible_set_99', [])
        
        data_95 = []
        for idx in credible_95:
            var = variants[idx] if idx < len(variants) else {'id': f'snp_{idx}'}
            data_95.append({
                'snp': var.get('id', f'snp_{idx}'),
                'chr': var.get('chr'),
                'pos': var.get('pos'),
                'pip': float(posterior_inclusion_probs[idx]),
                'rank': int(np.argsort(-np.array(posterior_inclusion_probs))[idx])
            })
        
        data_99 = []
        for idx in credible_99:
            var = variants[idx] if idx < len(variants) else {'id': f'snp_{idx}'}
            data_99.append({
                'snp': var.get('id', f'snp_{idx}'),
                'chr': var.get('chr'),
                'pos': var.get('pos'),
                'pip': float(posterior_inclusion_probs[idx]),
                'rank': int(np.argsort(-np.array(posterior_inclusion_probs))[idx])
            })
        
        return {
            'credible_set_95': data_95,
            'credible_set_99': data_99,
            'lead_variant': variants[credible_sets['lead_variant']] if credible_sets.get('lead_variant') is not None else None
        }
