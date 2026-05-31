import numpy as np
import pandas as pd
from scipy import stats
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


class EnrichmentService:
    """
    基因集富集分析服务
    支持GO（Gene Ontology）和KEGG（Kyoto Encyclopedia of Genes and Genomes）通路富集分析
    """
    
    def __init__(self):
        self.go_terms = self._initialize_go_terms()
        self.kegg_pathways = self._initialize_kegg_pathways()
        self.gene_set_mappings = self._initialize_gene_set_mappings()
    
    def _initialize_go_terms(self):
        """
        初始化玉米GO术语库（示例数据）
        """
        return {
            'GO:0008152': {
                'name': '代谢过程',
                'namespace': 'biological_process',
                'definition': '细胞内发生的化学反应和通路',
                'genes': ['Zm00001eb001010', 'Zm00001eb002020', 'Zm00001eb003030', 'Zm00001eb004040', 'Zm00001eb005050']
            },
            'GO:0009987': {
                'name': '细胞过程',
                'namespace': 'biological_process',
                'definition': '细胞水平的生理过程',
                'genes': ['Zm00001eb006060', 'Zm00001eb007070', 'Zm00001eb008080', 'Zm00001eb001010']
            },
            'GO:0030154': {
                'name': '细胞分化',
                'namespace': 'biological_process',
                'definition': '细胞特化的过程',
                'genes': ['Zm00001eb009090', 'Zm00001eb010100', 'Zm00001eb002020']
            },
            'GO:0015979': {
                'name': '光合作用',
                'namespace': 'biological_process',
                'definition': '将光能转化为化学能的过程',
                'genes': ['Zm00001eb011110', 'Zm00001eb012120', 'Zm00001eb013130', 'Zm00001eb014140']
            },
            'GO:0009733': {
                'name': '激素信号通路',
                'namespace': 'biological_process',
                'definition': '植物激素介导的信号转导',
                'genes': ['Zm00001eb015150', 'Zm00001eb016160', 'Zm00001eb017170', 'Zm00001eb003030']
            },
            'GO:0006281': {
                'name': 'DNA修复',
                'namespace': 'biological_process',
                'definition': 'DNA损伤的修复过程',
                'genes': ['Zm00001eb018180', 'Zm00001eb019190', 'Zm00001eb020200']
            },
            'GO:0005634': {
                'name': '细胞核',
                'namespace': 'cellular_component',
                'definition': '细胞核的结构组分',
                'genes': ['Zm00001eb001010', 'Zm00001eb006060', 'Zm00001eb009090', 'Zm00001eb018180']
            },
            'GO:0005886': {
                'name': '细胞质膜',
                'namespace': 'cellular_component',
                'definition': '细胞质膜的结构组分',
                'genes': ['Zm00001eb011110', 'Zm00001eb015150', 'Zm00001eb021210', 'Zm00001eb022220']
            },
            'GO:0003824': {
                'name': '催化活性',
                'namespace': 'molecular_function',
                'definition': '催化生化反应的能力',
                'genes': ['Zm00001eb001010', 'Zm00001eb002020', 'Zm00001eb004040', 'Zm00001eb011110', 'Zm00001eb018180']
            },
            'GO:0005515': {
                'name': '蛋白质结合',
                'namespace': 'molecular_function',
                'definition': '与蛋白质特异性结合的能力',
                'genes': ['Zm00001eb003030', 'Zm00001eb007070', 'Zm00001eb015150', 'Zm00001eb019190']
            }
        }
    
    def _initialize_kegg_pathways(self):
        """
        初始化玉米KEGG通路库（示例数据）
        """
        return {
            'zma00010': {
                'name': '糖酵解/糖异生',
                'description': '葡萄糖代谢的核心通路',
                'genes': ['Zm00001eb001010', 'Zm00001eb004040', 'Zm00001eb005050', 'Zm00001eb023230', 'Zm00001eb024240']
            },
            'zma00020': {
                'name': '三羧酸循环',
                'description': '柠檬酸循环，能量代谢核心',
                'genes': ['Zm00001eb001010', 'Zm00001eb004040', 'Zm00001eb025250', 'Zm00001eb026260', 'Zm00001eb027270']
            },
            'zma00190': {
                'name': '氧化磷酸化',
                'description': '线粒体呼吸链和ATP合成',
                'genes': ['Zm00001eb011110', 'Zm00001eb028280', 'Zm00001eb029290', 'Zm00001eb030300']
            },
            'zma00710': {
                'name': '光合生物碳固定',
                'description': '卡尔文循环，CO2固定',
                'genes': ['Zm00001eb011110', 'Zm00001eb012120', 'Zm00001eb013130', 'Zm00001eb014140', 'Zm00001eb031310']
            },
            'zma00900': {
                'name': '类萜生物合成',
                'description': '萜类化合物生物合成',
                'genes': ['Zm00001eb005050', 'Zm00001eb032320', 'Zm00001eb033330', 'Zm00001eb034340']
            },
            'zma00940': {
                'name': '类黄酮生物合成',
                'description': '类黄酮和花青素生物合成',
                'genes': ['Zm00001eb035350', 'Zm00001eb036360', 'Zm00001eb037370', 'Zm00001eb003030']
            },
            'zma04075': {
                'name': '植物激素信号转导',
                'description': '植物激素介导的信号通路',
                'genes': ['Zm00001eb015150', 'Zm00001eb016160', 'Zm00001eb017170', 'Zm00001eb038380', 'Zm00001eb039390']
            },
            'zma04626': {
                'name': '植物-病原体互作',
                'description': '植物免疫系统和抗病反应',
                'genes': ['Zm00001eb018180', 'Zm00001eb040400', 'Zm00001eb041410', 'Zm00001eb042420']
            },
            'zma04016': {
                'name': 'MAPK信号通路',
                'description': '丝裂原活化蛋白激酶信号通路',
                'genes': ['Zm00001eb003030', 'Zm00001eb007070', 'Zm00001eb015150', 'Zm00001eb043430']
            },
            'zma00480': {
                'name': '谷胱甘肽代谢',
                'description': '抗氧化系统，氧化应激响应',
                'genes': ['Zm00001eb019190', 'Zm00001eb044440', 'Zm00001eb045450', 'Zm00001eb046460']
            }
        }
    
    def _initialize_gene_set_mappings(self):
        """
        初始化基因到基因集的映射
        """
        mappings = defaultdict(lambda: {'GO': [], 'KEGG': []})
        
        for go_id, term in self.go_terms.items():
            for gene in term['genes']:
                mappings[gene]['GO'].append(go_id)
        
        for kegg_id, pathway in self.kegg_pathways.items():
            for gene in pathway['genes']:
                mappings[gene]['KEGG'].append(kegg_id)
        
        return mappings
    
    def run_go_enrichment(self, significant_genes, background_genes=None, p_value_threshold=0.05, update_progress=None):
        """
        执行GO富集分析
        
        Parameters:
        -----------
        significant_genes : list
            显著基因列表
        background_genes : list, optional
            背景基因列表（默认为所有基因）
        p_value_threshold : float
            显著性阈值
        update_progress : callable, optional
            进度更新回调函数
        """
        if update_progress:
            update_progress(0.1, '准备GO富集分析数据')
        
        if background_genes is None:
            background_genes = list(self.gene_set_mappings.keys())
        
        significant_genes_set = set(significant_genes) & set(background_genes)
        
        if update_progress:
            update_progress(0.3, f'分析 {len(significant_genes_set)} 个显著基因')
        
        enrichment_results = []
        total_go_terms = len(self.go_terms)
        
        for idx, (go_id, term) in enumerate(self.go_terms.items()):
            if update_progress and idx % 5 == 0:
                progress = 0.3 + 0.5 * (idx / total_go_terms)
                update_progress(progress, f'正在分析第 {idx}/{total_go_terms} 个GO术语')
            
            gene_set = set(term['genes']) & set(background_genes)
            
            if len(gene_set) < 3:
                continue
            
            in_set_sig = significant_genes_set & gene_set
            in_set_total = len(gene_set)
            in_sig_total = len(significant_genes_set)
            background_total = len(background_genes)
            
            table = [
                [len(in_set_sig), in_set_total - len(in_set_sig)],
                [in_sig_total - len(in_set_sig), background_total - in_set_total - in_sig_total + len(in_set_sig)]
            ]
            
            try:
                oddsratio, p_value = stats.fisher_exact(table, alternative='greater')
                
                if np.isnan(p_value):
                    p_value = 1.0
                
                expected = (in_set_total * in_sig_total) / background_total
                enrichment_ratio = len(in_set_sig) / expected if expected > 0 else 0
                
                result = {
                    'termId': go_id,
                    'termName': term['name'],
                    'namespace': term['namespace'],
                    'definition': term['definition'],
                    'pValue': float(p_value),
                    'oddsRatio': float(oddsratio) if not np.isnan(oddsratio) else 0,
                    'enrichmentRatio': float(enrichment_ratio),
                    'geneCount': len(in_set_sig),
                    'geneSetSize': in_set_total,
                    'significantGenes': sorted(list(in_set_sig)),
                    'expectedCount': float(expected)
                }
                enrichment_results.append(result)
            except:
                continue
        
        if update_progress:
            update_progress(0.9, '计算FDR校正')
        
        enrichment_results = sorted(enrichment_results, key=lambda x: x['pValue'])
        
        p_values = [r['pValue'] for r in enrichment_results]
        fdr_values = self._calculate_fdr(p_values)
        
        for i, result in enumerate(enrichment_results):
            result['adjPValue'] = float(fdr_values[i])
            result['log10P'] = float(-np.log10(max(result['pValue'], 1e-300)))
            result['negLog10AdjP'] = float(-np.log10(max(result['adjPValue'], 1e-300)))
        
        enrichment_results = [r for r in enrichment_results if r['adjPValue'] <= p_value_threshold]
        
        if update_progress:
            update_progress(1.0, f'GO富集分析完成，发现 {len(enrichment_results)} 个显著富集术语')
        
        return {
            'enrichment_results': enrichment_results,
            'total_terms_analyzed': total_go_terms,
            'significant_terms_count': len(enrichment_results),
            'type': 'GO'
        }
    
    def run_kegg_enrichment(self, significant_genes, background_genes=None, p_value_threshold=0.05, update_progress=None):
        """
        执行KEGG通路富集分析
        
        Parameters:
        -----------
        significant_genes : list
            显著基因列表
        background_genes : list, optional
            背景基因列表
        p_value_threshold : float
            显著性阈值
        update_progress : callable, optional
            进度更新回调函数
        """
        if update_progress:
            update_progress(0.1, '准备KEGG通路富集分析数据')
        
        if background_genes is None:
            background_genes = list(self.gene_set_mappings.keys())
        
        significant_genes_set = set(significant_genes) & set(background_genes)
        
        if update_progress:
            update_progress(0.3, f'分析 {len(significant_genes_set)} 个显著基因')
        
        enrichment_results = []
        total_pathways = len(self.kegg_pathways)
        
        for idx, (kegg_id, pathway) in enumerate(self.kegg_pathways.items()):
            if update_progress and idx % 2 == 0:
                progress = 0.3 + 0.5 * (idx / total_pathways)
                update_progress(progress, f'正在分析第 {idx}/{total_pathways} 个通路')
            
            gene_set = set(pathway['genes']) & set(background_genes)
            
            if len(gene_set) < 3:
                continue
            
            in_set_sig = significant_genes_set & gene_set
            in_set_total = len(gene_set)
            in_sig_total = len(significant_genes_set)
            background_total = len(background_genes)
            
            table = [
                [len(in_set_sig), in_set_total - len(in_set_sig)],
                [in_sig_total - len(in_set_sig), background_total - in_set_total - in_sig_total + len(in_set_sig)]
            ]
            
            try:
                oddsratio, p_value = stats.fisher_exact(table, alternative='greater')
                
                if np.isnan(p_value):
                    p_value = 1.0
                
                expected = (in_set_total * in_sig_total) / background_total
                enrichment_ratio = len(in_set_sig) / expected if expected > 0 else 0
                
                result = {
                    'termId': kegg_id,
                    'termName': pathway['name'],
                    'pathwayId': kegg_id,
                    'pathwayName': pathway['name'],
                    'description': pathway['description'],
                    'pValue': float(p_value),
                    'oddsRatio': float(oddsratio) if not np.isnan(oddsratio) else 0,
                    'enrichmentRatio': float(enrichment_ratio),
                    'geneCount': len(in_set_sig),
                    'geneSetSize': in_set_total,
                    'pathwaySize': in_set_total,
                    'significantGenes': sorted(list(in_set_sig)),
                    'expectedCount': float(expected)
                }
                enrichment_results.append(result)
            except:
                continue
        
        if update_progress:
            update_progress(0.9, '计算FDR校正')
        
        enrichment_results = sorted(enrichment_results, key=lambda x: x['pValue'])
        
        p_values = [r['pValue'] for r in enrichment_results]
        fdr_values = self._calculate_fdr(p_values)
        
        for i, result in enumerate(enrichment_results):
            result['adjPValue'] = float(fdr_values[i])
            result['log10P'] = float(-np.log10(max(result['pValue'], 1e-300)))
            result['negLog10AdjP'] = float(-np.log10(max(result['adjPValue'], 1e-300)))
        
        enrichment_results = [r for r in enrichment_results if r['adjPValue'] <= p_value_threshold]
        
        if update_progress:
            update_progress(1.0, f'KEGG通路富集分析完成，发现 {len(enrichment_results)} 个显著富集通路')
        
        return {
            'enrichment_results': enrichment_results,
            'total_pathways_analyzed': total_pathways,
            'significant_pathways_count': len(enrichment_results),
            'type': 'KEGG'
        }
    
    def _calculate_fdr(self, p_values):
        """
        计算Benjamini-Hochberg FDR校正
        """
        p_values = np.array(p_values, dtype=float)
        n = len(p_values)
        
        if n == 0:
            return []
        
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]
        
        fdr = np.zeros(n)
        for i in range(n):
            fdr[i] = sorted_p[i] * n / (i + 1)
        
        fdr = np.minimum.accumulate(fdr[::-1])[::-1]
        fdr = np.minimum(fdr, 1.0)
        
        original_order_fdr = np.zeros(n)
        original_order_fdr[sorted_indices] = fdr
        
        return original_order_fdr.tolist()
    
    def get_genes_for_snps(self, significant_snps, genome, window_size=50000):
        """
        根据显著SNP定位候选基因
        
        Parameters:
        -----------
        significant_snps : list
            显著SNP列表
        genome : ReferenceGenome
            参考基因组对象
        window_size : int
            上下游窗口大小（bp）
        """
        from ..models.models import GeneAnnotation
        
        candidate_genes = set()
        snp_gene_mapping = {}
        
        for snp in significant_snps:
            snp_chr = str(snp.get('chr') or snp.get('chromosome'))
            snp_pos = int(snp.get('pos') or snp.get('position'))
            snp_id = snp.get('snp') or snp.get('snp_id')
            
            start = snp_pos - window_size
            end = snp_pos + window_size
            
            nearby_genes = GeneAnnotation.query.filter(
                GeneAnnotation.genome_id == genome.id,
                GeneAnnotation.chromosome == snp_chr,
                GeneAnnotation.start_pos <= end,
                GeneAnnotation.end_pos >= start
            ).all()
            
            mapped_genes = []
            for gene in nearby_genes:
                candidate_genes.add(gene.gene_id)
                mapped_genes.append({
                    'geneId': gene.gene_id,
                    'geneName': gene.gene_name,
                    'distance': min(abs(snp_pos - gene.start_pos), abs(snp_pos - gene.end_pos)),
                    'overlapping': gene.start_pos <= snp_pos <= gene.end_pos
                })
            
            snp_gene_mapping[snp_id] = mapped_genes
        
        return {
            'candidate_genes': sorted(list(candidate_genes)),
            'snp_gene_mapping': snp_gene_mapping
        }
    
    def prepare_enrichment_barplot_data(self, enrichment_results, top_n=20):
        """
        准备富集分析条形图数据
        """
        top_results = sorted(enrichment_results, key=lambda x: x['negLog10AdjP'], reverse=True)[:top_n]
        
        bar_data = []
        for result in top_results:
            entry = {
                'name': result.get('termName') or result.get('pathwayName'),
                'id': result.get('termId') or result.get('pathwayId'),
                'negLog10AdjP': result['negLog10AdjP'],
                'enrichmentRatio': result['enrichmentRatio'],
                'geneCount': result['geneCount'],
                'adjPValue': result['adjPValue']
            }
            bar_data.append(entry)
        
        return bar_data
    
    def prepare_gene_concept_network(self, enrichment_results, top_n_terms=10):
        """
        准备基因-概念网络图数据
        """
        top_results = sorted(enrichment_results, key=lambda x: x['negLog10AdjP'], reverse=True)[:top_n_terms]
        
        nodes = []
        links = []
        gene_nodes = set()
        
        for result in top_results:
            term_id = result.get('termId') or result.get('pathwayId')
            term_name = result.get('termName') or result.get('pathwayName')
            
            nodes.append({
                'id': term_id,
                'name': term_name,
                'type': 'term',
                'size': result['geneCount'],
                'negLog10AdjP': result['negLog10AdjP']
            })
            
            for gene in result['significantGenes']:
                if gene not in gene_nodes:
                    nodes.append({
                        'id': gene,
                        'name': gene,
                        'type': 'gene',
                        'size': 5
                    })
                    gene_nodes.add(gene)
                
                links.append({
                    'source': gene,
                    'target': term_id,
                    'value': 1
                })
        
        return {
            'nodes': nodes,
            'links': links
        }
