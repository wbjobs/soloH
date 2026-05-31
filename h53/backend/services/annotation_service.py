import pandas as pd
import os

class AnnotationService:
    def __init__(self):
        self.gene_cache = {}
    
    def annotate_snps(self, genome, snps):
        annotations = []
        
        for snp in snps:
            annotation = self._annotate_single_snp(genome, snp)
            annotations.append(annotation)
        
        return annotations
    
    def _annotate_single_snp(self, genome, snp):
        from ..models.models import GeneAnnotation
        
        chrom = snp.get('chr') or snp.get('chromosome')
        pos = snp.get('pos') or snp.get('position')
        
        if not chrom or not pos:
            return {**snp, 'gene': None, 'annotation': None, 'region': None}
        
        nearby_genes = GeneAnnotation.query.filter(
            GeneAnnotation.genome_id == genome.id,
            GeneAnnotation.chromosome == str(chrom),
            GeneAnnotation.start_pos <= pos + 50000,
            GeneAnnotation.end_pos >= pos - 50000
        ).all()
        
        if not nearby_genes:
            return {**snp, 'gene': None, 'annotation': 'intergenic', 'region': 'intergenic'}
        
        best_gene = None
        best_distance = float('inf')
        best_region = None
        
        for gene in nearby_genes:
            if gene.start_pos <= pos <= gene.end_pos:
                best_gene = gene
                best_distance = 0
                if pos <= gene.start_pos + gene.end_pos * 0.1:
                    best_region = '5\' UTR'
                elif pos >= gene.end_pos - gene.end_pos * 0.1:
                    best_region = '3\' UTR'
                else:
                    best_region = 'exon'
                break
            else:
                distance = min(abs(pos - gene.start_pos), abs(pos - gene.end_pos))
                if distance < best_distance:
                    best_distance = distance
                    best_gene = gene
                    if pos < gene.start_pos:
                        best_region = f'upstream ({int(distance/1000)}kb)'
                    else:
                        best_region = f'downstream ({int(distance/1000)}kb)'
        
        return {
            **snp,
            'gene': best_gene.gene_name if best_gene else None,
            'gene_id': best_gene.gene_id if best_gene else None,
            'annotation': best_region,
            'region': best_region,
            'distance_to_gene': best_distance if best_distance < float('inf') else None,
            'gene_description': best_gene.description if best_gene else None
        }
    
    def annotate_snps_with_vep(self, snps, genome_id='B73_v5'):
        annotations = []
        for snp in snps:
            annotations.append({
                **snp,
                'consequence': self._predict_consequence(snp),
                'impact': self._predict_impact(snp),
                'codon_change': None,
                'amino_acid_change': None
            })
        return annotations
    
    def _predict_consequence(self, snp):
        region = snp.get('region', '')
        if 'exon' in region:
            return 'exonic'
        elif 'UTR' in region:
            return 'UTR'
        elif 'upstream' in region or 'downstream' in region:
            return 'regulatory_region'
        else:
            return 'intergenic'
    
    def _predict_impact(self, snp):
        consequence = self._predict_consequence(snp)
        if consequence == 'exonic':
            return 'MODERATE'
        elif consequence == 'UTR' or consequence == 'regulatory_region':
            return 'MODIFIER'
        else:
            return 'LOW'
