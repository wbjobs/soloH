import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests


class GroupStatistics:
    def __init__(self, n_permutations=1000, alpha=0.05):
        self.n_permutations = n_permutations
        self.alpha = alpha

    def t_test_independent(self, group1, group2):
        t_values, p_values = stats.ttest_ind(group1, group2, axis=0, equal_var=False)
        return t_values, p_values

    def t_test_paired(self, group1, group2):
        t_values, p_values = stats.ttest_rel(group1, group2, axis=0)
        return t_values, p_values

    def anova_oneway(self, *groups):
        f_values, p_values = stats.f_oneway(*groups, axis=0)
        return f_values, p_values

    def wilcoxon_rank_sum(self, group1, group2):
        n_features = group1.shape[1]
        u_values = np.zeros(n_features)
        p_values = np.zeros(n_features)
        
        for i in range(n_features):
            u, p = stats.ranksums(group1[:, i], group2[:, i])
            u_values[i] = u
            p_values[i] = p
        
        return u_values, p_values

    def wilcoxon_signed_rank(self, group1, group2):
        n_features = group1.shape[1]
        z_values = np.zeros(n_features)
        p_values = np.zeros(n_features)
        
        for i in range(n_features):
            z, p = stats.wilcoxon(group1[:, i], group2[:, i])
            z_values[i] = z
            p_values[i] = p
        
        return z_values, p_values

    def permutation_test_independent(self, group1, group2, stat_func='t_test'):
        n1 = group1.shape[0]
        n2 = group2.shape[0]
        n_features = group1.shape[1]
        
        combined = np.vstack([group1, group2])
        
        if stat_func == 't_test':
            obs_t, _ = self.t_test_independent(group1, group2)
        elif stat_func == 'mean_diff':
            obs_t = np.mean(group1, axis=0) - np.mean(group2, axis=0)
        elif stat_func == 'median_diff':
            obs_t = np.median(group1, axis=0) - np.median(group2, axis=0)
        else:
            raise ValueError(f"不支持的统计函数: {stat_func}")
        
        perm_t = np.zeros((self.n_permutations, n_features))
        
        for perm in range(self.n_permutations):
            perm_indices = np.random.permutation(n1 + n2)
            perm_group1 = combined[perm_indices[:n1]]
            perm_group2 = combined[perm_indices[n1:]]
            
            if stat_func == 't_test':
                t, _ = self.t_test_independent(perm_group1, perm_group2)
                perm_t[perm] = t
            elif stat_func == 'mean_diff':
                perm_t[perm] = np.mean(perm_group1, axis=0) - np.mean(perm_group2, axis=0)
            elif stat_func == 'median_diff':
                perm_t[perm] = np.median(perm_group1, axis=0) - np.median(perm_group2, axis=0)
        
        p_values = np.zeros(n_features)
        for i in range(n_features):
            if obs_t[i] >= 0:
                p_values[i] = np.sum(perm_t[:, i] >= obs_t[i]) / self.n_permutations
            else:
                p_values[i] = np.sum(perm_t[:, i] <= obs_t[i]) / self.n_permutations
        
        p_values = 2 * np.minimum(p_values, 1 - p_values)
        p_values = np.maximum(p_values, 1 / self.n_permutations)
        
        return obs_t, p_values, perm_t

    def permutation_test_paired(self, group1, group2, stat_func='t_test'):
        n_samples = group1.shape[0]
        n_features = group1.shape[1]
        
        if stat_func == 't_test':
            obs_t, _ = self.t_test_paired(group1, group2)
        elif stat_func == 'mean_diff':
            obs_t = np.mean(group1 - group2, axis=0)
        elif stat_func == 'median_diff':
            obs_t = np.median(group1 - group2, axis=0)
        else:
            raise ValueError(f"不支持的统计函数: {stat_func}")
        
        perm_t = np.zeros((self.n_permutations, n_features))
        diff = group1 - group2
        
        for perm in range(self.n_permutations):
            sign_flip = np.random.choice([-1, 1], size=(n_samples, 1))
            perm_diff = diff * sign_flip
            
            if stat_func == 't_test':
                t, _ = self.t_test_paired(perm_diff, np.zeros_like(perm_diff))
                perm_t[perm] = t
            elif stat_func == 'mean_diff':
                perm_t[perm] = np.mean(perm_diff, axis=0)
            elif stat_func == 'median_diff':
                perm_t[perm] = np.median(perm_diff, axis=0)
        
        p_values = np.zeros(n_features)
        for i in range(n_features):
            if obs_t[i] >= 0:
                p_values[i] = np.sum(perm_t[:, i] >= obs_t[i]) / self.n_permutations
            else:
                p_values[i] = np.sum(perm_t[:, i] <= obs_t[i]) / self.n_permutations
        
        p_values = 2 * np.minimum(p_values, 1 - p_values)
        p_values = np.maximum(p_values, 1 / self.n_permutations)
        
        return obs_t, p_values, perm_t

    def fdr_correction(self, p_values, method='fdr_bh'):
        if method == 'fdr_bh':
            reject, pvals_corrected, _, _ = multipletests(
                p_values, alpha=self.alpha, method='fdr_bh'
            )
        elif method == 'fdr_by':
            reject, pvals_corrected, _, _ = multipletests(
                p_values, alpha=self.alpha, method='fdr_by'
            )
        elif method == 'bonferroni':
            reject, pvals_corrected, _, _ = multipletests(
                p_values, alpha=self.alpha, method='bonferroni'
            )
        elif method == 'holm':
            reject, pvals_corrected, _, _ = multipletests(
                p_values, alpha=self.alpha, method='holm'
            )
        else:
            raise ValueError(f"不支持的多重比较校正方法: {method}")
        
        return reject, pvals_corrected

    def cluster_permutation_test(self, group1, group2, threshold=None, 
                                  stat_func='t_test', tail='both'):
        n_features = group1.shape[1]
        
        if stat_func == 't_test':
            obs_t, _ = self.t_test_independent(group1, group2)
        elif stat_func == 'mean_diff':
            obs_t = np.mean(group1, axis=0) - np.mean(group2, axis=0)
        else:
            raise ValueError(f"不支持的统计函数: {stat_func}")
        
        if threshold is None:
            threshold = stats.t.ppf(1 - 0.05 / 2, group1.shape[0] + group2.shape[0] - 2)
        
        obs_clusters = self._find_clusters(obs_t, threshold, tail)
        
        if len(obs_clusters) == 0:
            return obs_t, np.ones(n_features), [], [], []
        
        obs_cluster_stats = []
        obs_cluster_masks = []
        for cluster in obs_clusters:
            cluster_mask = np.zeros(n_features, dtype=bool)
            cluster_mask[cluster] = True
            obs_cluster_masks.append(cluster_mask)
            
            if tail == 'both':
                cluster_stat = np.sum(np.abs(obs_t[cluster]))
            elif tail == 'right':
                cluster_stat = np.sum(obs_t[cluster])
            else:
                cluster_stat = np.sum(-obs_t[cluster])
            obs_cluster_stats.append(cluster_stat)
        
        n1 = group1.shape[0]
        n2 = group2.shape[0]
        combined = np.vstack([group1, group2])
        
        perm_max_cluster_stats = np.zeros(self.n_permutations)
        
        for perm in range(self.n_permutations):
            perm_indices = np.random.permutation(n1 + n2)
            perm_group1 = combined[perm_indices[:n1]]
            perm_group2 = combined[perm_indices[n1:]]
            
            if stat_func == 't_test':
                perm_t, _ = self.t_test_independent(perm_group1, perm_group2)
            else:
                perm_t = np.mean(perm_group1, axis=0) - np.mean(perm_group2, axis=0)
            
            perm_clusters = self._find_clusters(perm_t, threshold, tail)
            
            if len(perm_clusters) > 0:
                perm_cluster_stats = []
                for cluster in perm_clusters:
                    if tail == 'both':
                        cs = np.sum(np.abs(perm_t[cluster]))
                    elif tail == 'right':
                        cs = np.sum(perm_t[cluster])
                    else:
                        cs = np.sum(-perm_t[cluster])
                    perm_cluster_stats.append(cs)
                perm_max_cluster_stats[perm] = np.max(perm_cluster_stats)
            else:
                perm_max_cluster_stats[perm] = 0
        
        p_values = np.zeros(n_features)
        cluster_p_values = []
        for i, obs_stat in enumerate(obs_cluster_stats):
            if tail == 'both':
                p = np.sum(perm_max_cluster_stats >= obs_stat) / self.n_permutations
            elif tail == 'right':
                p = np.sum(perm_max_cluster_stats >= obs_stat) / self.n_permutations
            else:
                p = np.sum(perm_max_cluster_stats >= obs_stat) / self.n_permutations
            
            p = max(p, 1 / self.n_permutations)
            cluster_p_values.append(p)
            p_values[obs_cluster_masks[i]] = p
        
        return obs_t, p_values, obs_clusters, cluster_p_values, perm_max_cluster_stats

    def _find_clusters(self, stat_map, threshold, tail='both'):
        n_features = len(stat_map)
        
        if tail == 'both':
            above_threshold = np.abs(stat_map) > threshold
        elif tail == 'right':
            above_threshold = stat_map > threshold
        else:
            above_threshold = stat_map < -threshold
        
        clusters = []
        visited = np.zeros(n_features, dtype=bool)
        
        for i in range(n_features):
            if above_threshold[i] and not visited[i]:
                cluster = []
                stack = [i]
                
                while stack:
                    idx = stack.pop()
                    if not visited[idx] and above_threshold[idx]:
                        visited[idx] = True
                        cluster.append(idx)
                        
                        if idx > 0 and not visited[idx - 1] and above_threshold[idx - 1]:
                            stack.append(idx - 1)
                        if idx < n_features - 1 and not visited[idx + 1] and above_threshold[idx + 1]:
                            stack.append(idx + 1)
                
                if len(cluster) > 0:
                    clusters.append(cluster)
        
        return clusters

    def effect_size_cohens_d(self, group1, group2):
        n1 = group1.shape[0]
        n2 = group2.shape[0]
        
        mean_diff = np.mean(group1, axis=0) - np.mean(group2, axis=0)
        
        var1 = np.var(group1, axis=0, ddof=1)
        var2 = np.var(group2, axis=0, ddof=1)
        
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        pooled_std = np.sqrt(pooled_var)
        
        cohens_d = mean_diff / pooled_std
        
        return cohens_d

    def effect_size_hedges_g(self, group1, group2):
        n1 = group1.shape[0]
        n2 = group2.shape[0]
        
        cohens_d = self.effect_size_cohens_d(group1, group2)
        
        correction_factor = 1 - (3 / (4 * (n1 + n2 - 2) - 1))
        hedges_g = cohens_d * correction_factor
        
        return hedges_g

    def summarize_results(self, p_values, pvals_corrected=None, effect_sizes=None, 
                          feature_names=None, alpha=None):
        if alpha is None:
            alpha = self.alpha
        
        n_features = len(p_values)
        if feature_names is None:
            feature_names = [f'特征 {i+1}' for i in range(n_features)]
        
        results = []
        for i in range(n_features):
            result = {
                'feature': feature_names[i],
                'p_value': p_values[i],
                'significant_uncorrected': p_values[i] < alpha
            }
            
            if pvals_corrected is not None:
                result['p_value_corrected'] = pvals_corrected[i]
                result['significant_corrected'] = pvals_corrected[i] < alpha
            
            if effect_sizes is not None:
                result['effect_size'] = effect_sizes[i]
            
            results.append(result)
        
        return results

    def compare_groups(self, group1, group2, paired=False, 
                        stat_func='t_test', correction_method='fdr_bh',
                        permutation=False):
        results = {}
        
        if permutation:
            if paired:
                obs_stat, p_values, perm_dist = self.permutation_test_paired(
                    group1, group2, stat_func
                )
            else:
                obs_stat, p_values, perm_dist = self.permutation_test_independent(
                    group1, group2, stat_func
                )
            results['permutation_distribution'] = perm_dist
        else:
            if paired:
                obs_stat, p_values = self.t_test_paired(group1, group2)
            else:
                obs_stat, p_values = self.t_test_independent(group1, group2)
        
        results['statistic'] = obs_stat
        results['p_values'] = p_values
        
        reject, pvals_corrected = self.fdr_correction(p_values, correction_method)
        results['p_values_corrected'] = pvals_corrected
        results['significant'] = reject
        
        if paired:
            results['effect_size'] = self.effect_size_cohens_d(group1, group2)
        else:
            results['effect_size'] = self.effect_size_hedges_g(group1, group2)
        
        results['summary'] = self.summarize_results(
            p_values, pvals_corrected, results['effect_size']
        )
        
        return results

    def compute_group_statistics(self, data):
        stats_results = {
            'mean': np.mean(data, axis=0),
            'median': np.median(data, axis=0),
            'std': np.std(data, axis=0, ddof=1),
            'sem': stats.sem(data, axis=0),
            'min': np.min(data, axis=0),
            'max': np.max(data, axis=0),
            'count': data.shape[0]
        }
        
        ci_lower, ci_upper = [], []
        for i in range(data.shape[1]):
            ci = stats.t.interval(0.95, data.shape[0] - 1,
                                  loc=np.mean(data[:, i]),
                                  scale=stats.sem(data[:, i]))
            ci_lower.append(ci[0])
            ci_upper.append(ci[1])
        
        stats_results['ci95_lower'] = np.array(ci_lower)
        stats_results['ci95_upper'] = np.array(ci_upper)
        
        return stats_results
