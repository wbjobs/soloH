"""
GWAS新功能集成测试
验证多表型联合分析（MANOVA/CCA）、基因集富集分析（GO/KEGG）、贝叶斯精细定位
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy import stats
import traceback

def test_multiphenotype_service():
    """测试多表型联合分析服务"""
    print("\n" + "="*80)
    print("测试1: 多表型联合分析服务 (MANOVA/CCA)")
    print("="*80)
    
    try:
        from services.multiphenotype_service import MultiPhenotypeService
        
        service = MultiPhenotypeService()
        
        # 生成模拟数据
        np.random.seed(42)
        n_samples = 200
        n_snps = 100
        n_phenotypes = 4
        
        # 基因型矩阵 (n_variants, n_samples) - 注意服务期望的维度
        genotype_matrix = np.random.binomial(2, 0.3, size=(n_snps, n_samples))
        
        # 表型矩阵 (多表型)
        phenotypes = np.random.randn(n_samples, n_phenotypes)
        # 添加一些真实关联信号
        causal_snp_idx = 5
        phenotypes[:, 0] += 0.5 * genotype_matrix[causal_snp_idx, :]
        phenotypes[:, 1] += 0.3 * genotype_matrix[causal_snp_idx, :]
        
        # 测试MANOVA
        print("\n  [1.1] 测试MANOVA分析...")
        manova_results = service.run_manova(
            genotype_matrix=genotype_matrix,
            phenotypes=phenotypes
        )
        
        assert 'p_values' in manova_results, "MANOVA结果缺少p_values字段"
        assert 'f_statistics' in manova_results, "MANOVA结果缺少f_statistics字段"
        assert 'wilks_lambda' in manova_results, "MANOVA结果缺少wilks_lambda字段"
        assert len(manova_results['p_values']) == n_snps, f"MANOVA SNP数量不匹配: {len(manova_results['p_values'])} != {n_snps}"
        
        # 检查因果SNP是否显著
        causal_p = manova_results['p_values'][causal_snp_idx]
        print(f"    因果SNP (SNP{causal_snp_idx}) p值: {causal_p:.2e}")
        assert causal_p < 0.05, f"因果SNP应该显著: p={causal_p}"
        
        # 检查p值范围
        p_vals = np.array(manova_results['p_values'])
        assert np.all((p_vals >= 0) & (p_vals <= 1)), "MANOVA p值范围不正确"
        assert np.any(p_vals < 0.05), "应该存在显著关联"
        
        print(f"    ✓ MANOVA分析成功: {n_snps}个SNP, {n_phenotypes}个表型")
        print(f"    ✓ 最小p值: {np.min(p_vals):.2e}")
        print(f"    ✓ 显著SNP数量 (p<0.05): {np.sum(p_vals < 0.05)}")
        print(f"    ✓ 膨胀因子: {manova_results.get('inflation_factor', 'N/A')}")
        
        # 测试CCA
        print("\n  [1.2] 测试CCA分析...")
        cca_results = service.run_cca(
            genotype_matrix=genotype_matrix,
            phenotypes=phenotypes,
            n_components=3
        )
        
        assert 'canonical_correlations' in cca_results, "CCA结果缺少canonical_correlations字段"
        assert 'loading_scores' in cca_results, "CCA结果缺少loading_scores字段"
        assert 'canonical_weights_x' in cca_results, "CCA结果缺少canonical_weights_x字段"
        assert 'canonical_weights_y' in cca_results, "CCA结果缺少canonical_weights_y字段"
        assert 'p_values' in cca_results, "CCA结果缺少p_values字段"
        
        n_components = len(cca_results['canonical_correlations'])
        print(f"    ✓ CCA分析成功: {n_components}个典型成分")
        print(f"    ✓ 典型相关系数: {[round(c, 4) for c in cca_results['canonical_correlations']]}")
        print(f"    ✓ 基因型权重数量: {len(cca_results['canonical_weights_x'])}")
        print(f"    ✓ 表型权重数量: {len(cca_results['canonical_weights_y'])}")
        
        # 测试曼哈顿图数据准备
        print("\n  [1.3] 测试曼哈顿图数据准备...")
        # 生成variants列表
        variants = [{'chr': '1', 'pos': 1000 + i*100, 'snp': f'SNP{i}', 'maf': float(manova_results['maf'][i])} for i in range(n_snps)]
        manhattan_data = service.prepare_multiphenotype_manhattan_data(
            variants=variants,
            p_values=manova_results['p_values'],
            f_statistics=manova_results['f_statistics']
        )
        
        assert len(manhattan_data) == n_snps, f"曼哈顿图数据数量不匹配"
        assert 'log10P' in manhattan_data[0], "曼哈顿图数据缺少log10P字段"
        assert 'pValue' in manhattan_data[0], "曼哈顿图数据缺少pValue字段"
        
        print(f"    ✓ 曼哈顿图数据准备成功: {len(manhattan_data)}个点")
        print("\n  ✓ 多表型联合分析服务测试通过!")
        
        return True
        
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_enrichment_service():
    """测试基因集富集分析服务"""
    print("\n" + "="*80)
    print("测试2: 基因集富集分析服务 (GO/KEGG)")
    print("="*80)
    
    try:
        from services.enrichment_service import EnrichmentService
        
        service = EnrichmentService()
        
        # 模拟显著基因列表 - 使用服务中定义的基因ID格式
        significant_genes = [
            'Zm00001eb001010', 'Zm00001eb004040', 'Zm00001eb005050',
            'Zm00001eb023230', 'Zm00001eb024240', 'Zm00001eb025250',
            'Zm00001eb026260', 'Zm00001eb027270', 'Zm00001eb011110',
            'Zm00001eb028280', 'Zm00001eb029290', 'Zm00001eb03030',
            'Zm00001eb012120', 'Zm00001eb013130', 'Zm00001eb014140',
        ]
        
        # 模拟背景基因列表
        background_genes = [f'Zm00001eb{i:06d}' for i in range(100, 500)]
        background_genes.extend(significant_genes)
        
        # 测试GO富集分析
        print("\n  [2.1] 测试GO富集分析...")
        go_results = service.run_go_enrichment(
            significant_genes=significant_genes,
            background_genes=background_genes,
            p_value_threshold=0.05
        )
        
        assert 'enrichment_results' in go_results, "GO结果缺少enrichment_results字段"
        assert 'type' in go_results, "GO结果缺少type字段"
        
        enrichment_terms = go_results['enrichment_results']
        print(f"    ✓ GO分析完成: 类型={go_results['type']}")
        print(f"    ✓ 分析条目总数: {go_results.get('total_terms_analyzed', 0)}")
        print(f"    ✓ 显著富集条目: {len(enrichment_terms)}个")
        
        if len(enrichment_terms) > 0:
            term = enrichment_terms[0]
            required_fields = ['termId', 'termName', 'namespace', 'pValue', 'adjPValue', 'geneCount', 'enrichmentRatio', 'oddsRatio']
            for field in required_fields:
                assert field in term, f"GO条目缺少{field}字段"
            assert 'log10P' in term, "GO条目缺少log10P字段"
            
            print(f"    ✓ 首个条目: {term['termId']} - {term['termName']}")
            print(f"      p值: {term['pValue']:.2e}, 校正p值: {term['adjPValue']:.2e}")
            print(f"      基因数: {term['geneCount']}, 富集比: {term['enrichmentRatio']:.4f}")
            
            # 检查p值校正是否正确
            p_vals = [t['pValue'] for t in enrichment_terms]
            adj_p_vals = [t['adjPValue'] for t in enrichment_terms]
            assert all(adj >= p for adj, p in zip(adj_p_vals, p_vals)), "校正p值应该大于等于原始p值"
            assert all(0 <= p <= 1 for p in p_vals), "p值范围不正确"
            assert all(0 <= p <= 1 for p in adj_p_vals), "校正p值范围不正确"
        
        # 测试KEGG富集分析
        print("\n  [2.2] 测试KEGG富集分析...")
        kegg_results = service.run_kegg_enrichment(
            significant_genes=significant_genes,
            background_genes=background_genes,
            p_value_threshold=0.05
        )
        
        assert 'enrichment_results' in kegg_results, "KEGG结果缺少enrichment_results字段"
        print(f"    ✓ KEGG分析完成: {len(kegg_results['enrichment_results'])}个富集条目")
        
        if len(kegg_results['enrichment_results']) > 0:
            term = kegg_results['enrichment_results'][0]
            assert 'termId' in term, "KEGG条目缺少termId字段"
            assert 'termName' in term, "KEGG条目缺少termName字段"
            assert 'pathwayId' in term, "KEGG条目缺少pathwayId字段"
            print(f"    ✓ 首个通路: {term['termId']} - {term['termName']}")
        
        # 测试条形图数据准备
        print("\n  [2.3] 测试条形图数据准备...")
        barplot_data = service.prepare_enrichment_barplot_data(
            enrichment_results=enrichment_terms,
            top_n=10
        )
        
        assert isinstance(barplot_data, list), "条形图数据应该是列表"
        assert len(barplot_data) <= 10, f"条形图数据数量应该<=10: {len(barplot_data)}"
        
        if len(barplot_data) > 0:
            assert 'name' in barplot_data[0], "条形图数据缺少name字段"
            assert 'negLog10AdjP' in barplot_data[0], "条形图数据缺少negLog10AdjP字段"
            assert 'geneCount' in barplot_data[0], "条形图数据缺少geneCount字段"
            print(f"    ✓ 条形图数据准备成功: {len(barplot_data)}个条目")
        
        # 测试基因-概念网络
        print("\n  [2.4] 测试基因-概念网络...")
        network_data = service.prepare_gene_concept_network(
            enrichment_results=enrichment_terms,
            top_n_terms=5
        )
        
        assert 'nodes' in network_data, "网络数据缺少nodes字段"
        assert 'links' in network_data, "网络数据缺少links字段"
        print(f"    ✓ 网络数据准备成功: {len(network_data['nodes'])}个节点, {len(network_data['links'])}条边")
        
        print("\n  ✓ 基因集富集分析服务测试通过!")
        
        return True
        
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_finemapping_service():
    """测试贝叶斯精细定位服务"""
    print("\n" + "="*80)
    print("测试3: 贝叶斯精细定位服务 (CAVIAR)")
    print("="*80)
    
    try:
        from services.finemapping_service import BayesianFineMappingService
        
        service = BayesianFineMappingService()
        
        # 生成模拟数据
        np.random.seed(42)
        n_samples = 500
        n_snps = 50
        
        # 基因型矩阵 (n_variants, n_samples) - 注意精细定位服务期望的维度
        genotype_matrix = np.random.binomial(2, 0.3, size=(n_snps, n_samples))
        
        # 模拟p值（部分SNP显著）
        p_values = np.random.uniform(0, 1, n_snps)
        # 添加3个因果SNP
        causal_indices = [10, 25, 40]
        for idx in causal_indices:
            p_values[idx] = 10 ** (-np.random.uniform(5, 8))
            # 添加LD相关性
            for j in range(max(0, idx-5), min(n_snps, idx+6)):
                if j != idx:
                    p_values[j] = min(p_values[j], 10 ** (-np.random.uniform(2, 4)))
        
        # 测试精细定位
        print("\n  [3.1] 测试CAVIAR精细定位...")
        finemapping_results = service.run_finemapping(
            genotype_matrix=genotype_matrix,
            p_values=p_values,
            num_causal_config=3,
            n_iterations=5000,
            burn_in=1000
        )
        
        assert 'posterior_inclusion_probs' in finemapping_results, "结果缺少PIP字段"
        assert 'credible_sets' in finemapping_results, "结果缺少可信集合字段"
        assert 'model_posteriors' in finemapping_results, "结果缺少模型后验字段"
        assert 'ld_matrix' in finemapping_results, "结果缺少LD矩阵字段"
        
        # 检查PIP值
        pips = np.array(finemapping_results['posterior_inclusion_probs'])
        assert len(pips) == n_snps, f"PIP数量不匹配: {len(pips)} != {n_snps}"
        assert np.all((pips >= 0) & (pips <= 1)), f"PIP值范围不正确: {pips}"
        assert np.sum(pips) > 0, "PIP总和应该大于0"
        
        print(f"    ✓ 精细定位完成: {n_snps}个SNP")
        print(f"    ✓ PIP范围: [{np.min(pips):.4f}, {np.max(pips):.4f}]")
        print(f"    ✓ 因果SNP PIP值:")
        for idx in causal_indices:
            print(f"      SNP{idx}: PIP={pips[idx]:.4f}")
        
        # 检查95%可信集合
        credible_sets_95 = finemapping_results['credible_sets'].get('95%', [])
        print(f"\n    ✓ 95%可信集合包含 {len(credible_sets_95)} 个SNP:")
        for snp in credible_sets_95[:5]:
            print(f"      - SNP{snp['index']}: PIP={snp['pip']:.4f}")
        
        if len(credible_sets_95) > 5:
            print(f"      ... 还有 {len(credible_sets_95) - 5} 个SNP")
        
        # 检查99%可信集合
        credible_sets_99 = finemapping_results['credible_sets'].get('99%', [])
        print(f"    ✓ 99%可信集合包含 {len(credible_sets_99)} 个SNP")
        
        # 可信集合应该包含至少一个因果SNP
        credible_indices = [snp['index'] for snp in credible_sets_95]
        found_causal = [idx for idx in causal_indices if idx in credible_indices]
        print(f"    ✓ 95%可信集合包含 {len(found_causal)}/{len(causal_indices)} 个真实因果SNP")
        
        # 检查LD矩阵
        ld_matrix = np.array(finemapping_results['ld_matrix'])
        assert ld_matrix.shape == (n_snps, n_snps), f"LD矩阵形状不正确: {ld_matrix.shape}"
        assert np.allclose(np.diag(ld_matrix), 1.0, atol=0.1), "LD矩阵对角线应该接近1"
        assert np.all((ld_matrix >= -1) & (ld_matrix <= 1)), "LD相关系数范围不正确"
        print(f"    ✓ LD矩阵形状: {ld_matrix.shape}")
        
        # 检查曼哈顿图数据准备（含PIP）
        print("\n  [3.2] 测试PIP曼哈顿图数据准备...")
        variants = [{'chr': '1', 'pos': 1000 + i*100, 'snp': f'SNP{i}', 'maf': 0.3} for i in range(n_snps)]
        manhattan_data = service.prepare_finemapping_manhattan_data(
            variants=variants,
            posterior_inclusion_probs=pips,
            p_values=p_values
        )
        
        assert len(manhattan_data) == n_snps, f"曼哈顿图数据数量不匹配"
        assert 'pip' in manhattan_data[0], "曼哈顿图数据缺少pip字段"
        assert 'log10P' in manhattan_data[0], "曼哈顿图数据缺少log10P字段"
        
        # 检查PIP值是否正确传递
        for i, point in enumerate(manhattan_data):
            assert abs(point['pip'] - pips[i]) < 1e-6, f"PIP值传递错误: {point['pip']} != {pips[i]}"
        
        print(f"    ✓ PIP曼哈顿图数据准备成功: {len(manhattan_data)}个点")
        
        print("\n  ✓ 贝叶斯精细定位服务测试通过!")
        
        return True
        
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_visualization_service():
    """测试可视化服务的新增图表"""
    print("\n" + "="*80)
    print("测试4: 可视化服务 (新增图表类型)")
    print("="*80)
    
    try:
        from services.visualization_service import VisualizationService
        
        service = VisualizationService()
        
        # 模拟富集分析数据 - 使用服务实际字段名
        print("\n  [4.1] 测试富集分析条形图...")
        enrichment_data = [
            {'termId': 'GO:0006355', 'termName': 'regulation of transcription, DNA-templated', 
             'pValue': 1.2e-8, 'adjPValue': 4.5e-6, 'geneCount': 15, 'log10P': 7.92, 'negLog10AdjP': 5.35, 'enrichmentRatio': 2.5},
            {'termId': 'GO:0006351', 'termName': 'transcription, DNA-templated',
             'pValue': 3.4e-7, 'adjPValue': 5.2e-5, 'geneCount': 12, 'log10P': 6.47, 'negLog10AdjP': 4.28, 'enrichmentRatio': 2.1},
            {'termId': 'GO:0008219', 'termName': 'cell death',
             'pValue': 1.5e-5, 'adjPValue': 0.0012, 'geneCount': 8, 'log10P': 4.82, 'negLog10AdjP': 2.92, 'enrichmentRatio': 1.8},
            {'termId': 'GO:0009790', 'termName': 'embryo development',
             'pValue': 0.00023, 'adjPValue': 0.015, 'geneCount': 6, 'log10P': 3.64, 'negLog10AdjP': 1.82, 'enrichmentRatio': 1.5},
            {'termId': 'GO:0006915', 'termName': 'apoptotic process',
             'pValue': 0.0015, 'adjPValue': 0.078, 'geneCount': 5, 'log10P': 2.82, 'negLog10AdjP': 1.11, 'enrichmentRatio': 1.2},
        ]
        
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_output')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 需要先准备条形图数据
        from services.enrichment_service import EnrichmentService
        enrich_service = EnrichmentService()
        barplot_data = enrich_service.prepare_enrichment_barplot_data(enrichment_data, top_n=10)
        
        barplot_path = os.path.join(temp_dir, 'test_enrichment_barplot.png')
        result = service.create_enrichment_barplot(
            barplot_data=barplot_data,
            output_path=barplot_path,
            title='GO Biological Process Enrichment'
        )
        
        assert isinstance(result, str), "应该返回文件路径字符串"
        assert os.path.exists(result), f"富集条形图文件不存在: {result}"
        assert result.endswith('.png'), "图表格式应该是png"
        print(f"    ✓ 富集条形图创建成功: {os.path.basename(result)}")
        print(f"      包含 {len(barplot_data)} 个条目")
        
        # 测试精细定位PIP图
        print("\n  [4.2] 测试精细定位PIP图...")
        n_snps = 100
        variants = [{'chr': '1', 'pos': 1000 + i*100, 'snp': f'SNP{i}'} for i in range(n_snps)]
        p_values = np.random.uniform(0, 1, n_snps)
        p_values[20:30] = 10 ** (-np.random.uniform(4, 8, 10))
        pips = np.zeros(n_snps)
        pips[25] = 0.95
        pips[24] = 0.72
        pips[26] = 0.45
        pips[23] = 0.28
        
        # 需要先准备曼哈顿图数据
        from services.finemapping_service import BayesianFineMappingService
        fm_service = BayesianFineMappingService()
        finemapping_manhattan_data = fm_service.prepare_finemapping_manhattan_data(
            variants=variants,
            posterior_inclusion_probs=pips,
            p_values=p_values
        )
        
        finemapping_plot_path = os.path.join(temp_dir, 'test_finemapping_plot.png')
        result = service.create_finemapping_plot(
            manhattan_data=finemapping_manhattan_data,
            output_path=finemapping_plot_path
        )
        
        assert isinstance(result, str), "应该返回文件路径字符串"
        assert os.path.exists(result), f"精细定位图文件不存在: {result}"
        print(f"    ✓ 精细定位PIP图创建成功: {os.path.basename(result)}")
        print(f"      包含 {n_snps} 个SNP，上下双面板 (p值 + PIP)")
        
        # 清理测试文件
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("\n  ✓ 可视化服务测试通过!")
        
        return True
        
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*80)
    print("GWAS Web应用 - 新功能集成测试")
    print("="*80)
    print(f"测试时间: {pd.Timestamp.now()}")
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"工作目录: {os.getcwd()}")
    
    tests = [
        ('多表型联合分析 (MANOVA/CCA)', test_multiphenotype_service),
        ('基因集富集分析 (GO/KEGG)', test_enrichment_service),
        ('贝叶斯精细定位 (CAVIAR)', test_finemapping_service),
        ('可视化服务 (新增图表)', test_visualization_service),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name}: 严重错误 - {e}")
            traceback.print_exc()
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        color = "\033[92m" if result else "\033[91m"
        reset = "\033[0m"
        print(f"{color}{status}{reset}: {test_name}")
    
    print("-"*80)
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\033[92m✓ 所有测试通过!\033[0m")
    else:
        print(f"\033[91m✗ {total - passed} 个测试失败\033[0m")
        sys.exit(1)
    
    return passed == total


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    success = run_all_tests()
    sys.exit(0 if success else 1)
