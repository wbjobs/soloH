import numpy as np
import pandas as pd

class LDService:
    def calculate_ld_matrix(self, genotype_matrix, positions=None, method='r2'):
        n_variants, n_samples = genotype_matrix.shape
        
        if n_variants < 2:
            return np.array([[1.0]])
        
        gt_centered = genotype_matrix - genotype_matrix.mean(axis=1, keepdims=True)
        
        std = gt_centered.std(axis=1, keepdims=True)
        std[std < 1e-10] = 1
        gt_normalized = gt_centered / std
        
        corr = np.corrcoef(gt_normalized)
        
        if method == 'r2':
            ld_matrix = np.square(corr)
        else:
            ld_matrix = np.abs(corr)
        
        ld_matrix = np.nan_to_num(ld_matrix, nan=0.0)
        np.fill_diagonal(ld_matrix, 1.0)
        
        return ld_matrix
    
    def calculate_ld_from_vcf(self, vcf_parser, chrom, start, end, update_progress=None):
        if update_progress:
            update_progress(0.2, '读取区域基因型数据')
        
        data = vcf_parser.parse_genotypes(chromosomes=[chrom], start=start, end=end)
        
        variants = data['variants']
        genotypes = np.array(data['genotypes'], dtype=np.float32)
        
        if len(variants) == 0:
            raise ValueError(f'在指定区域 {chrom}:{start}-{end} 没有找到变异位点')
        
        if update_progress:
            update_progress(0.5, f'找到 {len(variants)} 个SNP，计算LD矩阵')
        
        from sklearn.impute import SimpleImputer
        imputer = SimpleImputer(strategy='mean')
        genotypes_imputed = imputer.fit_transform(genotypes.T).T
        
        if update_progress:
            update_progress(0.7, '计算相关系数')
        
        ld_matrix = self.calculate_ld_matrix(genotypes_imputed)
        
        if update_progress:
            update_progress(0.9, '检测单倍型块')
        
        hap_blocks = self.detect_haplotype_blocks(ld_matrix, variants, threshold=0.8)
        
        if update_progress:
            update_progress(1.0, 'LD分析完成')
        
        return {
            'snpNames': [v['id'] for v in variants],
            'positions': [v['pos'] for v in variants],
            'variants': variants,
            'ldMatrix': ld_matrix.tolist(),
            'hapBlocks': hap_blocks
        }
    
    def detect_haplotype_blocks(self, ld_matrix, variants, threshold=0.8):
        n = ld_matrix.shape[0]
        blocks = []
        i = 0
        
        while i < n:
            block_start = i
            block_end = i
            
            for j in range(i + 1, n):
                if ld_matrix[i, j] >= threshold:
                    block_end = j
                else:
                    is_connected = True
                    for k in range(block_start, block_end + 1):
                        if ld_matrix[k, j] < threshold * 0.7:
                            is_connected = False
                            break
                    if is_connected:
                        block_end = j
                    else:
                        break
            
            if block_end > block_start:
                block_snps = [v['id'] for v in variants[block_start:block_end + 1]]
                blocks.append({
                    'start': variants[block_start]['pos'],
                    'end': variants[block_end]['pos'],
                    'start_idx': block_start,
                    'end_idx': block_end,
                    'n_snps': block_end - block_start + 1,
                    'snps': block_snps
                })
                i = block_end + 1
            else:
                i += 1
        
        return blocks
    
    def calculate_tag_snps(self, ld_matrix, snp_names, threshold=0.8):
        n = ld_matrix.shape[0]
        tagged = set()
        tag_snps = []
        
        for i in range(n):
            if i in tagged:
                continue
            
            tag_snps.append(snp_names[i])
            
            for j in range(n):
                if ld_matrix[i, j] >= threshold:
                    tagged.add(j)
        
        return tag_snps
