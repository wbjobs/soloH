import os
import gzip
import pandas as pd
import numpy as np

class VCFParser:
    def __init__(self, vcf_path):
        self.vcf_path = vcf_path
        self._is_gzipped = vcf_path.endswith('.gz')
        self.samples = []
        self.chromosomes = []
        self.variant_count = 0
        
    def _open_file(self):
        if self._is_gzipped:
            return gzip.open(self.vcf_path, 'rt')
        return open(self.vcf_path, 'r')
    
    def parse_header(self):
        metadata = {
            'fileformat': None,
            'samples': [],
            'sample_count': 0,
            'chromosomes': [],
            'variant_count': 0,
            'filters': [],
            'info_fields': [],
            'format_fields': []
        }
        
        chromosomes_set = set()
        variant_count = 0
        
        with self._open_file() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('##fileformat'):
                    metadata['fileformat'] = line.split('=')[1]
                elif line.startswith('##contig'):
                    if 'ID=' in line:
                        chrom = line.split('ID=')[1].split(',')[0].split('>')[0]
                        chromosomes_set.add(chrom)
                elif line.startswith('##FILTER'):
                    if 'ID=' in line:
                        filt = line.split('ID=')[1].split(',')[0]
                        metadata['filters'].append(filt)
                elif line.startswith('##INFO'):
                    if 'ID=' in line:
                        info = line.split('ID=')[1].split(',')[0]
                        metadata['info_fields'].append(info)
                elif line.startswith('##FORMAT'):
                    if 'ID=' in line:
                        fmt = line.split('ID=')[1].split(',')[0]
                        metadata['format_fields'].append(fmt)
                elif line.startswith('#CHROM'):
                    headers = line.split('\t')
                    if len(headers) > 9:
                        self.samples = headers[9:]
                        metadata['samples'] = self.samples
                        metadata['sample_count'] = len(self.samples)
                    break
                elif not line.startswith('#'):
                    variant_count += 1
                    parts = line.split('\t')
                    if len(parts) > 0:
                        chromosomes_set.add(parts[0])
        
        metadata['chromosomes'] = sorted(list(chromosomes_set))
        self.chromosomes = metadata['chromosomes']
        
        if variant_count == 0:
            variant_count = self._count_variants()
        
        metadata['variant_count'] = variant_count
        self.variant_count = variant_count
        
        return metadata
    
    def _count_variants(self):
        count = 0
        with self._open_file() as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    count += 1
        return count
    
    def get_preview(self, limit=10):
        preview_data = {
            'headers': ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER'],
            'rows': []
        }
        
        count = 0
        with self._open_file() as f:
            for line in f:
                line = line.strip()
                if line.startswith('#CHROM'):
                    headers = line.split('\t')
                    if len(headers) > 9:
                        preview_data['headers'].extend(headers[9:min(15, len(headers))])
                elif not line.startswith('#'):
                    if count >= limit:
                        break
                    parts = line.split('\t')
                    row = parts[:7]
                    if len(parts) > 9:
                        row.extend(parts[9:min(15, len(parts))])
                    preview_data['rows'].append(row)
                    count += 1
        
        return preview_data
    
    def parse_genotypes(self, chromosomes=None, start=None, end=None):
        data = {
            'variants': [],
            'genotypes': [],
            'samples': self.samples
        }
        
        with self._open_file() as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    continue
                    
                parts = line.split('\t')
                chrom = parts[0]
                pos = int(parts[1])
                
                if chromosomes and chrom not in chromosomes:
                    continue
                if start and pos < start:
                    continue
                if end and pos > end:
                    continue
                
                variant = {
                    'chr': chrom,
                    'pos': pos,
                    'id': parts[2] if parts[2] != '.' else f'{chrom}_{pos}',
                    'ref': parts[3],
                    'alt': parts[4],
                    'qual': float(parts[5]) if parts[5] != '.' else None,
                    'filter': parts[6]
                }
                
                gt_format = parts[8].split(':')
                gt_idx = gt_format.index('GT') if 'GT' in gt_format else 0
                
                genotypes = []
                for sample_gt in parts[9:]:
                    gt_parts = sample_gt.split(':')
                    if len(gt_parts) > gt_idx:
                        gt = gt_parts[gt_idx]
                        genotypes.append(self._parse_gt(gt))
                    else:
                        genotypes.append(np.nan)
                
                data['variants'].append(variant)
                data['genotypes'].append(genotypes)
        
        return data
    
    def _parse_gt(self, gt):
        if gt == './.' or gt == '.':
            return np.nan
        
        alleles = gt.replace('|', '/').split('/')
        try:
            alleles = [int(a) for a in alleles if a != '.']
            if len(alleles) == 0:
                return np.nan
            return sum(alleles)
        except:
            return np.nan
    
    def get_genotype_matrix(self, max_variants=None):
        variants = []
        genotypes = []
        
        count = 0
        with self._open_file() as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    continue
                    
                if max_variants and count >= max_variants:
                    break
                    
                parts = line.split('\t')
                variant_id = parts[2] if parts[2] != '.' else f'{parts[0]}_{parts[1]}'
                variants.append(variant_id)
                
                gt_format = parts[8].split(':')
                gt_idx = gt_format.index('GT') if 'GT' in gt_format else 0
                
                gt_list = []
                for sample_gt in parts[9:]:
                    gt_parts = sample_gt.split(':')
                    if len(gt_parts) > gt_idx:
                        gt = gt_parts[gt_idx]
                        gt_list.append(self._parse_gt(gt))
                    else:
                        gt_list.append(np.nan)
                
                genotypes.append(gt_list)
                count += 1
        
        return np.array(genotypes, dtype=np.float32), self.samples, variants
    
    def calculate_maf(self):
        genotypes, samples, variants = self.get_genotype_matrix()
        n_samples = len(samples)
        
        mafs = []
        for i in range(len(variants)):
            gt = genotypes[i]
            non_missing = gt[~np.isnan(gt)]
            if len(non_missing) == 0:
                mafs.append(0)
                continue
            
            allele_count = np.nansum(gt)
            total_alleles = 2 * len(non_missing)
            af = allele_count / total_alleles if total_alleles > 0 else 0
            maf = min(af, 1 - af)
            mafs.append(maf)
        
        return np.array(mafs), variants
