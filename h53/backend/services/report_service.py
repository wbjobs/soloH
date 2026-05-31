import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from datetime import datetime

class ReportService:
    def __init__(self):
        self.colors = {
            'primary': '#165DFF',
            'secondary': '#00B42A',
            'accent': '#FF7D00',
            'background': '#FFFFFF',
            'text': '#0F172A',
            'grid': '#E2E8F0'
        }
    
    def generate_pdf_report(self, task_id, gwas_result, output_dir=None):
        from ..models.models import SignificantSNP, VisualizationFile
        
        if output_dir is None:
            output_dir = os.path.dirname(os.path.dirname(__file__))
        
        report_path = os.path.join(output_dir, f'{task_id}_gwas_report.pdf')
        
        significant_snps = SignificantSNP.query.filter_by(result_id=gwas_result.id) \
                                                .order_by(SignificantSNP.p_value) \
                                                .limit(50) \
                                                .all()
        
        with PdfPages(report_path) as pdf:
            self._create_cover_page(pdf, gwas_result, task_id)
            self._create_summary_page(pdf, gwas_result, significant_snps)
            self._create_manhattan_page(pdf, gwas_result)
            self._create_qq_page(pdf, gwas_result)
            self._create_snps_page(pdf, significant_snps)
            self._create_methods_page(pdf, gwas_result)
        
        return report_path
    
    def _create_cover_page(self, pdf, gwas_result, task_id):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')
        
        ax.axvspan(0, 0.05, color=self.colors['primary'], alpha=0.8)
        
        ax.text(0.12, 0.75, 'GWAS Analysis Report', fontsize=32, fontweight='bold', color=self.colors['text'])
        ax.text(0.12, 0.68, 'Genome-Wide Association Study', fontsize=16, color=self.colors['primary'])
        
        ax.text(0.12, 0.55, f'Phenotype: {gwas_result.phenotype}', fontsize=14, color=self.colors['text'])
        ax.text(0.12, 0.50, f'Model: {gwas_result.model_type}', fontsize=14, color=self.colors['text'])
        ax.text(0.12, 0.45, f'Significant SNPs: {gwas_result.significant_snp_count}', fontsize=14, color=self.colors['text'])
        if gwas_result.inflation_factor:
            ax.text(0.12, 0.40, f'Inflation Factor (λ): {gwas_result.inflation_factor:.3f}', fontsize=14, color=self.colors['text'])
        
        ax.text(0.12, 0.25, f'Task ID: {task_id}', fontsize=11, color='#64748B')
        ax.text(0.12, 0.20, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', fontsize=11, color='#64748B')
        
        ax.text(0.12, 0.10, 'Maize GWAS Analysis Platform', fontsize=10, color='#94A3B8')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _create_summary_page(self, pdf, gwas_result, significant_snps):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        ax = fig.add_axes([0.1, 0.1, 0.85, 0.8])
        ax.axis('off')
        
        ax.text(0.02, 0.95, 'Analysis Summary', fontsize=20, fontweight='bold', color=self.colors['text'])
        
        summary_data = [
            ['Parameter', 'Value'],
            ['Analysis Model', gwas_result.model_type],
            ['Phenotype Trait', gwas_result.phenotype],
            ['Number of Significant SNPs', str(gwas_result.significant_snp_count)],
            ['Inflation Factor (λ)', f'{gwas_result.inflation_factor:.3f}' if gwas_result.inflation_factor else 'N/A'],
            ['Significance Threshold', '5e-8'],
            ['Reference Genome', 'B73 v5'],
        ]
        
        table = ax.table(cellText=summary_data, loc='center', cellLoc='left', bbox=[0.02, 0.6, 0.96, 0.3])
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 1.5)
        
        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor(self.colors['primary'])
                cell.set_text_props(color='white', fontweight='bold')
            else:
                cell.set_facecolor('white' if i % 2 == 0 else '#F8FAFC')
            cell.set_edgecolor(self.colors['grid'])
            cell.PAD = 0.1
        
        if significant_snps:
            ax.text(0.02, 0.48, 'Top 5 Significant SNPs', fontsize=16, fontweight='bold', color=self.colors['text'])
            
            top_snps_data = [['SNP', 'Chr', 'Position', 'P-value', '-log10(P)', 'Effect Size', 'MAF']]
            for snp in significant_snps[:5]:
                top_snps_data.append([
                    snp.snp_id,
                    snp.chromosome,
                    f'{snp.position:,}',
                    f'{snp.p_value:.2e}',
                    f'{snp.log10_p:.2f}',
                    f'{snp.effect_size:.3f}' if snp.effect_size else 'N/A',
                    f'{snp.maf:.3f}' if snp.maf else 'N/A'
                ])
            
            table2 = ax.table(cellText=top_snps_data, loc='center', cellLoc='left', bbox=[0.02, 0.05, 0.96, 0.4])
            table2.auto_set_font_size(False)
            table2.set_fontsize(10)
            table2.scale(1, 1.5)
            
            for (i, j), cell in table2.get_celld().items():
                if i == 0:
                    cell.set_facecolor(self.colors['secondary'])
                    cell.set_text_props(color='white', fontweight='bold')
                else:
                    cell.set_facecolor('white' if i % 2 == 0 else '#F8FAFC')
                cell.set_edgecolor(self.colors['grid'])
                cell.PAD = 0.05
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _create_manhattan_page(self, pdf, gwas_result):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        ax = fig.add_axes([0.1, 0.1, 0.85, 0.8])
        
        manhattan_data = gwas_result.manhattan_data or []
        
        if manhattan_data:
            df = pd.DataFrame(manhattan_data)
            
            chrom_order = sorted(df['chr'].unique(), key=lambda x: int(x) if x.isdigit() else 999)
            df['chr_num'] = pd.Categorical(df['chr'], categories=chrom_order).codes
            df = df.sort_values(['chr_num', 'pos'])
            
            chrom_spacing = 50000000
            cumulative_pos = 0
            chrom_offsets = {}
            for chrom in chrom_order:
                chrom_offsets[chrom] = cumulative_pos
                chrom_max_pos = df[df['chr'] == chrom]['pos'].max()
                cumulative_pos += chrom_max_pos + chrom_spacing
            
            df['cumulative_pos'] = df.apply(lambda row: chrom_offsets[row['chr']] + row['pos'], axis=1)
            
            chr_colors = ['#165DFF', '#00B42A', '#FF7D00', '#86909C', '#722ED1', '#F53F3F']
            
            for i, chrom in enumerate(chrom_order):
                chrom_df = df[df['chr'] == chrom]
                ax.scatter(chrom_df['cumulative_pos'], chrom_df['log10P'], 
                          c=chr_colors[i % len(chr_colors)], s=10, alpha=0.7)
            
            threshold = 5e-8
            ax.axhline(y=-np.log10(threshold), color='#FF7D00', linestyle='--', 
                      linewidth=1.5, label=f'Threshold (p={threshold})')
            
            sig_df = df[df['log10P'] >= -np.log10(threshold)]
            if not sig_df.empty:
                ax.scatter(sig_df['cumulative_pos'], sig_df['log10P'], 
                          c='red', s=30, alpha=0.9, zorder=5, label='Significant SNPs')
            
            ax.set_xlabel('Chromosome', fontsize=12, fontweight='bold')
            ax.set_ylabel('-log10(P-value)', fontsize=12, fontweight='bold')
            ax.set_title('Manhattan Plot', fontsize=16, fontweight='bold', pad=15)
            
            chrom_midpoints = []
            for chrom in chrom_order:
                offset = chrom_offsets[chrom]
                chrom_max = df[df['chr'] == chrom]['pos'].max()
                chrom_midpoints.append(offset + chrom_max / 2)
            
            ax.set_xticks(chrom_midpoints)
            ax.set_xticklabels(chrom_order, fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=10)
        else:
            ax.text(0.5, 0.5, 'No Manhattan plot data available', ha='center', va='center', fontsize=14)
            ax.axis('off')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _create_qq_page(self, pdf, gwas_result):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        ax = fig.add_axes([0.1, 0.1, 0.85, 0.8])
        
        qq_data = gwas_result.qq_data or []
        
        if qq_data:
            expected = np.array([d['expected'] for d in qq_data])
            observed = np.array([d['observed'] for d in qq_data])
            
            max_val = max(expected.max(), observed.max()) if len(expected) > 0 else 10
            
            ax.plot([0, max_val], [0, max_val], 'k--', linewidth=1.5, label='Expected under null')
            ax.scatter(expected, observed, c=self.colors['primary'], s=20, alpha=0.7)
            
            if gwas_result.inflation_factor:
                ax.text(0.05, 0.95, f'λ = {gwas_result.inflation_factor:.3f}', 
                       transform=ax.transAxes, fontsize=14, fontweight='bold',
                       bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray', pad=10))
            
            ax.set_xlabel('Expected -log10(P-value)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Observed -log10(P-value)', fontsize=12, fontweight='bold')
            ax.set_title('Quantile-Quantile (QQ) Plot', fontsize=16, fontweight='bold', pad=15)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=11)
        else:
            ax.text(0.5, 0.5, 'No QQ plot data available', ha='center', va='center', fontsize=14)
            ax.axis('off')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _create_snps_page(self, pdf, significant_snps):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        ax = fig.add_axes([0.1, 0.1, 0.85, 0.8])
        ax.axis('off')
        
        ax.text(0.02, 0.95, 'Significant SNPs', fontsize=20, fontweight='bold', color=self.colors['text'])
        
        if significant_snps:
            snps_data = [['SNP', 'Chr', 'Position', 'P-value', '-log10(P)', 'Effect Size', 'MAF', 'Gene']]
            for snp in significant_snps:
                snps_data.append([
                    snp.snp_id,
                    snp.chromosome,
                    f'{snp.position:,}',
                    f'{snp.p_value:.2e}',
                    f'{snp.log10_p:.2f}',
                    f'{snp.effect_size:.3f}' if snp.effect_size else 'N/A',
                    f'{snp.maf:.3f}' if snp.maf else 'N/A',
                    snp.gene or 'N/A'
                ])
            
            table = ax.table(cellText=snps_data, loc='center', cellLoc='left', bbox=[0.02, 0.05, 0.96, 0.85])
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.3)
            
            for (i, j), cell in table.get_celld().items():
                if i == 0:
                    cell.set_facecolor(self.colors['primary'])
                    cell.set_text_props(color='white', fontweight='bold')
                else:
                    cell.set_facecolor('white' if i % 2 == 0 else '#F8FAFC')
                cell.set_edgecolor(self.colors['grid'])
                cell.PAD = 0.05
        else:
            ax.text(0.5, 0.5, 'No significant SNPs found', ha='center', va='center', fontsize=14)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _create_methods_page(self, pdf, gwas_result):
        fig = plt.figure(figsize=(11.69, 8.27), facecolor='white')
        ax = fig.add_axes([0.1, 0.1, 0.85, 0.8])
        ax.axis('off')
        
        ax.text(0.02, 0.95, 'Analysis Methods', fontsize=20, fontweight='bold', color=self.colors['text'])
        
        methods_text = f"""
        1. 基因型数据处理
           - 输入格式: VCF (Variant Call Format)
           - 基因型编码: 0/1/2 (次要等位基因计数)
           - 缺失处理: 均值插补 (mean imputation)
           - MAF过滤: ≥ 0.01
        
        2. 表型数据
           - 分析性状: {gwas_result.phenotype}
        
        3. 统计模型
           - 使用模型: {gwas_result.model_type}
           - {'广义线性模型 (Generalized Linear Model) - 适合无亲缘关系群体' if gwas_result.model_type == 'GLM' else 
             '混合线性模型 (Mixed Linear Model) - 控制群体结构和亲缘关系'}
        
        4. 显著性检验
           - 检验方法: Wald test
           - 全基因组显著阈值: P < 5e-8
        
        5. 质量控制
           - Inflation factor (λ): {gwas_result.inflation_factor:.3f} if gwas_result.inflation_factor else 'N/A'
           - {'λ接近1表示群体结构控制良好' if gwas_result.inflation_factor and abs(gwas_result.inflation_factor - 1) < 0.1 else 
             'λ偏离1可能存在未校正的群体结构'}
        
        6. 参考基因组
           - 物种: 玉米 (Zea mays)
           - 参考基因组: B73 v5
        """
        
        ax.text(0.02, 0.9, methods_text, fontsize=11, color=self.colors['text'], 
                verticalalignment='top', linespacing=1.8, family='monospace')
        
        ax.text(0.02, 0.05, 'Generated by Maize GWAS Analysis Platform', fontsize=9, color='#64748B')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
