import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import numpy as np
import pandas as pd
import os

sns.set_style('whitegrid')

class VisualizationService:
    def __init__(self):
        self.colors = {
            'primary': '#165DFF',
            'secondary': '#00B42A',
            'accent': '#FF7D00',
            'background': '#0F172A',
            'text': '#FFFFFF',
            'grid': '#1E293B'
        }
    
    def create_manhattan_plot(self, manhattan_data, output_path, threshold=5e-8):
        df = pd.DataFrame(manhattan_data)
        
        if df.empty:
            fig, ax = plt.subplots(figsize=(16, 8))
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=16)
            ax.axis('off')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            return output_path
        
        df['chr_num'] = pd.Categorical(df['chr'], categories=sorted(df['chr'].unique(), key=lambda x: int(x) if x.isdigit() else 999)).codes
        df = df.sort_values(['chr_num', 'pos'])
        
        chrom_order = sorted(df['chr'].unique(), key=lambda x: int(x) if x.isdigit() else 999)
        chrom_spacing = 50000000
        
        cumulative_pos = 0
        chrom_offsets = {}
        for chrom in chrom_order:
            chrom_offsets[chrom] = cumulative_pos
            chrom_max_pos = df[df['chr'] == chrom]['pos'].max()
            cumulative_pos += chrom_max_pos + chrom_spacing
        
        df['cumulative_pos'] = df.apply(lambda row: chrom_offsets[row['chr']] + row['pos'], axis=1)
        
        fig, ax = plt.subplots(figsize=(16, 8), facecolor=self.colors['background'])
        ax.set_facecolor(self.colors['background'])
        
        chr_colors = ['#165DFF', '#00B42A', '#FF7D00', '#86909C', '#722ED1', '#F53F3F', '#14C9C9', '#FB7AFC']
        
        for i, chrom in enumerate(chrom_order):
            chrom_df = df[df['chr'] == chrom]
            color = chr_colors[i % len(chr_colors)]
            ax.scatter(chrom_df['cumulative_pos'], chrom_df['log10P'], 
                      c=color, s=15, alpha=0.8, edgecolors='none', label=f'Chr {chrom}')
        
        threshold_log10 = -np.log10(threshold)
        ax.axhline(y=threshold_log10, color='#FF7D00', linestyle='--', linewidth=1.5, 
                  label=f'Significance threshold (p={threshold})')
        
        sig_df = df[df['log10P'] >= threshold_log10]
        if not sig_df.empty:
            ax.scatter(sig_df['cumulative_pos'], sig_df['log10P'], 
                      c='white', s=40, alpha=0.9, edgecolors='#FF7D00', linewidths=1.5, zorder=5)
            
            top_snps = sig_df.nlargest(5, 'log10P')
            for _, row in top_snps.iterrows():
                ax.annotate(row['snp'], 
                           xy=(row['cumulative_pos'], row['log10P']),
                           xytext=(5, 5), textcoords='offset points',
                           color='white', fontsize=9, fontweight='bold')
        
        ax.set_xlabel('Chromosome', fontsize=14, fontweight='bold', color=self.colors['text'])
        ax.set_ylabel('-log10(P-value)', fontsize=14, fontweight='bold', color=self.colors['text'])
        ax.set_title('Manhattan Plot', fontsize=18, fontweight='bold', color=self.colors['text'], pad=20)
        
        ax.tick_params(colors=self.colors['text'])
        
        chrom_midpoints = []
        for chrom in chrom_order:
            offset = chrom_offsets[chrom]
            chrom_max = df[df['chr'] == chrom]['pos'].max()
            chrom_midpoints.append(offset + chrom_max / 2)
        
        ax.set_xticks(chrom_midpoints)
        ax.set_xticklabels(chrom_order, rotation=0, fontsize=11)
        
        for spine in ax.spines.values():
            spine.set_color(self.colors['grid'])
        
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.set_axisbelow(True)
        
        legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
                          fontsize=9, framealpha=0.3, facecolor=self.colors['background'])
        for text in legend.get_texts():
            text.set_color(self.colors['text'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path
    
    def create_qq_plot(self, qq_data, output_path, inflation_factor=None):
        expected = np.array([d['expected'] for d in qq_data])
        observed = np.array([d['observed'] for d in qq_data])
        
        if len(expected) == 0 or len(observed) == 0:
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=16)
            ax.axis('off')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            return output_path
        
        max_val = max(expected.max(), observed.max())
        
        fig, ax = plt.subplots(figsize=(10, 10), facecolor=self.colors['background'])
        ax.set_facecolor(self.colors['background'])
        
        ax.plot([0, max_val], [0, max_val], 'w--', linewidth=1.5, label='Expected under null')
        
        ax.scatter(expected, observed, c=self.colors['primary'], s=20, alpha=0.8, 
                  edgecolors='none', zorder=5)
        
        if inflation_factor is not None:
            ax.text(0.05, 0.95, f'λ = {inflation_factor:.3f}', 
                   transform=ax.transAxes, color='white', fontsize=14, 
                   fontweight='bold', bbox=dict(facecolor=self.colors['primary'], 
                                               alpha=0.3, edgecolor='none', pad=10))
        
        confidence = 0.95
        n = len(expected)
        lower = -np.log10(stats.beta.ppf((1 - confidence) / 2, np.arange(1, n + 1), np.arange(n, 0, -1)))
        upper = -np.log10(stats.beta.ppf(1 - (1 - confidence) / 2, np.arange(1, n + 1), np.arange(n, 0, -1)))
        
        ax.fill_between(expected, lower, upper, color='white', alpha=0.1, label=f'{int(confidence*100)}% Confidence Band')
        
        ax.set_xlabel('Expected -log10(P-value)', fontsize=14, fontweight='bold', color=self.colors['text'])
        ax.set_ylabel('Observed -log10(P-value)', fontsize=14, fontweight='bold', color=self.colors['text'])
        ax.set_title('Quantile-Quantile (QQ) Plot', fontsize=18, fontweight='bold', color=self.colors['text'], pad=20)
        
        ax.tick_params(colors=self.colors['text'])
        
        for spine in ax.spines.values():
            spine.set_color(self.colors['grid'])
        
        ax.grid(True, alpha=0.3, color=self.colors['grid'])
        ax.set_axisbelow(True)
        
        legend = ax.legend(fontsize=11, framealpha=0.3, facecolor=self.colors['background'])
        for text in legend.get_texts():
            text.set_color(self.colors['text'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path
    
    def create_ld_heatmap(self, ld_matrix, snp_names, positions, output_path, hap_blocks=None):
        n_snps = len(snp_names)
        
        if n_snps == 0:
            fig, ax = plt.subplots(figsize=(12, 10))
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=16)
            ax.axis('off')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            return output_path
        
        fig, (ax_heatmap, ax_pos) = plt.subplots(2, 1, figsize=(14, 12), 
                                                 facecolor=self.colors['background'],
                                                 gridspec_kw={'height_ratios': [10, 1]},
                                                 sharex=True)
        
        ax_heatmap.set_facecolor(self.colors['background'])
        ax_pos.set_facecolor(self.colors['background'])
        
        ld_matrix = np.array(ld_matrix)
        ld_matrix_sq = ld_matrix ** 2
        
        mask = np.triu(np.ones_like(ld_matrix_sq, dtype=bool), k=1)
        ld_plot = np.ma.masked_where(mask, ld_matrix_sq)
        
        cmap = plt.cm.get_cmap('Reds')
        cmap.set_bad(color=self.colors['background'])
        
        im = ax_heatmap.imshow(ld_plot, cmap=cmap, vmin=0, vmax=1, 
                              interpolation='nearest', aspect='auto')
        
        if hap_blocks:
            for block in hap_blocks:
                start_idx = None
                end_idx = None
                for i, snp in enumerate(snp_names):
                    if snp in block.get('snps', []):
                        if start_idx is None:
                            start_idx = i
                        end_idx = i
                
                if start_idx is not None and end_idx is not None:
                    rect = patches.Rectangle((start_idx - 0.5, start_idx - 0.5), 
                                           end_idx - start_idx + 1, 
                                           end_idx - start_idx + 1,
                                           fill=False, edgecolor='#FF7D00', 
                                           linewidth=2, linestyle='--')
                    ax_heatmap.add_patch(rect)
        
        tick_indices = np.linspace(0, n_snps - 1, min(10, n_snps)).astype(int)
        ax_heatmap.set_yticks(tick_indices)
        ax_heatmap.set_yticklabels([snp_names[i] for i in tick_indices], 
                                  color=self.colors['text'], fontsize=8, rotation=0)
        ax_heatmap.set_xticks(tick_indices)
        ax_heatmap.set_xticklabels([snp_names[i] for i in tick_indices], 
                                  color=self.colors['text'], fontsize=8, rotation=45, ha='right')
        
        for spine in ax_heatmap.spines.values():
            spine.set_color(self.colors['grid'])
        
        ax_heatmap.set_title('Linkage Disequilibrium (LD) Heatmap (r²)', 
                            fontsize=16, fontweight='bold', color=self.colors['text'], pad=20)
        
        cbar = plt.colorbar(im, ax=ax_heatmap, shrink=0.8)
        cbar.ax.yaxis.label.set_color(self.colors['text'])
        cbar.ax.tick_params(colors=self.colors['text'])
        cbar.set_label('r²', color=self.colors['text'], fontsize=12)
        
        if positions:
            pos_arr = np.array(positions)
            ax_pos.plot(range(n_snps), pos_arr / 1e6, color=self.colors['secondary'], linewidth=2)
            ax_pos.set_ylabel('Position (Mb)', color=self.colors['text'], fontsize=10)
            ax_pos.tick_params(colors=self.colors['text'])
            for spine in ax_pos.spines.values():
                spine.set_color(self.colors['grid'])
            ax_pos.grid(True, alpha=0.3, color=self.colors['grid'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path
    
    def create_pca_plot(self, pc_data, output_path):
        fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor=self.colors['background'])
        
        for ax in axes:
            ax.set_facecolor(self.colors['background'])
        
        pc1 = [d['PC1'] for d in pc_data]
        pc2 = [d['PC2'] for d in pc_data]
        pc3 = [d.get('PC3', 0) for d in pc_data]
        sample_ids = [d.get('sampleId', '') for d in pc_data]
        
        scatter1 = axes[0].scatter(pc1, pc2, c=self.colors['primary'], s=60, alpha=0.8, 
                                  edgecolors='white', linewidths=0.5)
        axes[0].set_xlabel('PC1', fontsize=12, fontweight='bold', color=self.colors['text'])
        axes[0].set_ylabel('PC2', fontsize=12, fontweight='bold', color=self.colors['text'])
        axes[0].set_title('PCA: PC1 vs PC2', fontsize=14, fontweight='bold', color=self.colors['text'])
        
        scatter2 = axes[1].scatter(pc1, pc3, c=self.colors['secondary'], s=60, alpha=0.8,
                                  edgecolors='white', linewidths=0.5)
        axes[1].set_xlabel('PC1', fontsize=12, fontweight='bold', color=self.colors['text'])
        axes[1].set_ylabel('PC3', fontsize=12, fontweight='bold', color=self.colors['text'])
        axes[1].set_title('PCA: PC1 vs PC3', fontsize=14, fontweight='bold', color=self.colors['text'])
        
        for ax in axes:
            ax.tick_params(colors=self.colors['text'])
            for spine in ax.spines.values():
                spine.set_color(self.colors['grid'])
            ax.grid(True, alpha=0.3, color=self.colors['grid'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path

    def create_enrichment_barplot(self, barplot_data, output_path, title='Enrichment Analysis'):
        if not barplot_data or len(barplot_data) == 0:
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(0.5, 0.5, 'No significant enrichment terms', ha='center', va='center', fontsize=16, color=self.colors['text'])
            ax.axis('off')
            fig.patch.set_facecolor(self.colors['background'])
            plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
            plt.close()
            return output_path
        
        df = pd.DataFrame(barplot_data)
        df = df.sort_values('negLog10AdjP', ascending=True)
        
        n_terms = len(df)
        fig_height = max(6, n_terms * 0.4)
        fig, ax = plt.subplots(figsize=(12, fig_height), facecolor=self.colors['background'])
        ax.set_facecolor(self.colors['background'])
        
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, n_terms))
        
        y_pos = np.arange(n_terms)
        bars = ax.barh(y_pos, df['negLog10AdjP'], color=colors, height=0.7, alpha=0.9)
        
        for i, (bar, gene_count, enrich_ratio) in enumerate(zip(bars, df['geneCount'], df['enrichmentRatio'])):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                   f'{gene_count} genes (ER={enrich_ratio:.1f}x)',
                   va='center', ha='left', color=self.colors['text'], fontsize=9)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(df['name'], fontsize=10, color=self.colors['text'])
        ax.set_xlabel('-log10(Adjusted P-value)', fontsize=12, fontweight='bold', color=self.colors['text'])
        ax.set_title(title, fontsize=16, fontweight='bold', color=self.colors['text'], pad=20)
        
        significance_line = -np.log10(0.05)
        ax.axvline(x=significance_line, color='#FF7D00', linestyle='--', linewidth=1.5, alpha=0.7)
        ax.text(significance_line, -0.5, 'P=0.05', color='#FF7D00', fontsize=9, ha='center')
        
        ax.tick_params(axis='x', colors=self.colors['text'])
        for spine in ax.spines.values():
            spine.set_color(self.colors['grid'])
        ax.grid(True, alpha=0.3, color=self.colors['grid'], axis='x')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path
    
    def create_finemapping_plot(self, manhattan_data, output_path):
        if not manhattan_data or len(manhattan_data) == 0:
            fig, ax = plt.subplots(figsize=(16, 8))
            ax.text(0.5, 0.5, 'No fine-mapping data available', ha='center', va='center', fontsize=16)
            ax.axis('off')
            fig.patch.set_facecolor(self.colors['background'])
            plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
            plt.close()
            return output_path
        
        df = pd.DataFrame(manhattan_data)
        df = df.sort_values('pos')
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), facecolor=self.colors['background'], sharex=True)
        
        for ax in [ax1, ax2]:
            ax.set_facecolor(self.colors['background'])
        
        positions = df['pos'].values / 1e6
        
        scatter1 = ax1.scatter(positions, df['log10P'], 
                               c=self.colors['primary'], s=80, alpha=0.8,
                               edgecolors='white', linewidths=0.5)
        ax1.set_ylabel('-log10(P-value)', fontsize=12, fontweight='bold', color=self.colors['text'])
        ax1.set_title('GWAS Association P-values', fontsize=14, fontweight='bold', color=self.colors['text'], pad=10)
        
        significance_line = -np.log10(5e-8)
        ax1.axhline(y=significance_line, color='#FF7D00', linestyle='--', linewidth=1.5, alpha=0.7)
        ax1.text(positions[0], significance_line + 0.5, 'P=5e-8', color='#FF7D00', fontsize=9)
        
        pip_colors = np.where(df['pip'] >= 0.95, '#00B42A',
                             np.where(df['pip'] >= 0.5, '#FF7D00', '#165DFF'))
        scatter2 = ax2.scatter(positions, df['pip'], c=pip_colors, s=100, alpha=0.9,
                               edgecolors='white', linewidths=0.5)
        
        high_pip_indices = np.where(df['pip'] >= 0.95)[0]
        for idx in high_pip_indices:
            ax2.annotate(f'{df.iloc[idx]["pip"]:.2f}',
                        (positions[idx], df.iloc[idx]['pip']),
                        textcoords="offset points", xytext=(0, 10), ha='center',
                        fontsize=10, fontweight='bold', color='#00B42A')
        
        ax2.axhline(y=0.95, color='#00B42A', linestyle='--', linewidth=1.5, alpha=0.7)
        ax2.text(positions[0], 0.97, 'PIP ≥ 0.95', color='#00B42A', fontsize=9)
        
        ax2.axhline(y=0.5, color='#FF7D00', linestyle='--', linewidth=1.5, alpha=0.5)
        ax2.text(positions[0], 0.52, 'PIP ≥ 0.5', color='#FF7D00', fontsize=9)
        
        ax2.set_xlabel('Position (Mb)', fontsize=12, fontweight='bold', color=self.colors['text'])
        ax2.set_ylabel('Posterior Inclusion Probability', fontsize=12, fontweight='bold', color=self.colors['text'])
        ax2.set_title('Bayesian Fine-mapping (PIP)', fontsize=14, fontweight='bold', color=self.colors['text'], pad=10)
        ax2.set_ylim(-0.05, 1.05)
        
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#00B42A', markersize=10, label='PIP ≥ 0.95'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF7D00', markersize=10, label='0.5 ≤ PIP < 0.95'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#165DFF', markersize=10, label='PIP < 0.5')
        ]
        ax2.legend(handles=legend_elements, loc='upper right', facecolor=self.colors['grid'], 
                  edgecolor=self.colors['grid'], labelcolor=self.colors['text'])
        
        for ax in [ax1, ax2]:
            ax.tick_params(colors=self.colors['text'])
            for spine in ax.spines.values():
                spine.set_color(self.colors['grid'])
            ax.grid(True, alpha=0.3, color=self.colors['grid'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=self.colors['background'])
        plt.close()
        
        return output_path


from scipy import stats
