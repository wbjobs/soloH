import numpy as np
import pandas as pd

class SampleMatcher:
    def match(self, vcf_file, phenotype_file):
        vcf_samples = vcf_file.metadata.get('samples', [])
        phenotype_samples = phenotype_file.metadata.get('samples', [])
        
        vcf_samples_lower = [s.lower() for s in vcf_samples]
        phenotype_samples_lower = [s.lower() for s in phenotype_samples]
        
        vcf_sample_dict = dict(zip(vcf_samples_lower, vcf_samples))
        phenotype_sample_dict = dict(zip(phenotype_samples_lower, phenotype_samples))
        
        matched_lower = list(set(vcf_samples_lower) & set(phenotype_samples_lower))
        
        matched = []
        for s_lower in matched_lower:
            matched.append(vcf_sample_dict[s_lower])
        
        vcf_only = [vcf_sample_dict[s] for s in vcf_samples_lower if s not in phenotype_samples_lower]
        phenotype_only = [phenotype_sample_dict[s] for s in phenotype_samples_lower if s not in vcf_samples_lower]
        
        return {
            'matched': matched,
            'vcf_only': vcf_only,
            'phenotype_only': phenotype_only,
            'vcf_samples': vcf_samples,
            'phenotype_samples': phenotype_samples
        }
    
    def get_sample_indices(self, sample_list, target_samples):
        sample_to_idx = {s: i for i, s in enumerate(sample_list)}
        indices = []
        for s in target_samples:
            if s in sample_to_idx:
                indices.append(sample_to_idx[s])
            elif s.lower() in [k.lower() for k in sample_to_idx.keys()]:
                for k, v in sample_to_idx.items():
                    if k.lower() == s.lower():
                        indices.append(v)
                        break
        
        return indices
    
    def align_data(self, vcf_parser, phenotype_data, sample_order):
        vcf_samples = vcf_parser.samples
        
        vcf_indices = self.get_sample_indices(vcf_samples, sample_order)
        phenotype_indices = self.get_sample_indices(list(phenotype_data.index), sample_order)
        
        return vcf_indices, phenotype_indices
