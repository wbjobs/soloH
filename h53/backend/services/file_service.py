import pandas as pd
import numpy as np
import os

class FileService:
    def parse_phenotype_csv(self, file_path):
        df = pd.read_csv(file_path)
        
        sample_col = None
        for col in df.columns:
            if col.lower() in ['sample', 'sampleid', 'sample_id', 'id', 'ind', 'individual']:
                sample_col = col
                break
        
        if sample_col is None:
            sample_col = df.columns[0]
        
        phenotype_cols = [col for col in df.columns if col != sample_col]
        
        metadata = {
            'sample_column': sample_col,
            'samples': df[sample_col].astype(str).tolist(),
            'sample_count': len(df),
            'phenotype_names': phenotype_cols,
            'phenotype_count': len(phenotype_cols),
            'summary': {}
        }
        
        for col in phenotype_cols:
            col_data = pd.to_numeric(df[col], errors='coerce')
            metadata['summary'][col] = {
                'mean': float(col_data.mean()) if not col_data.isna().all() else None,
                'std': float(col_data.std()) if not col_data.isna().all() else None,
                'min': float(col_data.min()) if not col_data.isna().all() else None,
                'max': float(col_data.max()) if not col_data.isna().all() else None,
                'missing_count': int(col_data.isna().sum()),
                'type': 'numeric' if col_data.dtype in [np.float64, np.int64] else 'categorical'
            }
        
        return metadata
    
    def parse_covariate_csv(self, file_path):
        df = pd.read_csv(file_path)
        
        sample_col = None
        for col in df.columns:
            if col.lower() in ['sample', 'sampleid', 'sample_id', 'id', 'ind', 'individual']:
                sample_col = col
                break
        
        if sample_col is None:
            sample_col = df.columns[0]
        
        covariate_cols = [col for col in df.columns if col != sample_col]
        
        metadata = {
            'sample_column': sample_col,
            'samples': df[sample_col].astype(str).tolist(),
            'sample_count': len(df),
            'covariate_names': covariate_cols,
            'covariate_count': len(covariate_cols)
        }
        
        return metadata
    
    def get_csv_preview(self, file_path, limit=10):
        df = pd.read_csv(file_path, nrows=limit)
        
        return {
            'headers': df.columns.tolist(),
            'rows': df.astype(object).where(pd.notnull(df), None).values.tolist()
        }
    
    def _load_phenotype_df(self, file_path):
        df = pd.read_csv(file_path)
        
        sample_col = None
        for col in df.columns:
            if col.lower() in ['sample', 'sampleid', 'sample_id', 'id', 'ind', 'individual']:
                sample_col = col
                break
        
        if sample_col is None:
            sample_col = df.columns[0]
        
        df[sample_col] = df[sample_col].astype(str)
        df = df.set_index(sample_col)
        
        return df
    
    def load_phenotype_data(self, file_path, phenotype_name, sample_order=None):
        df = self._load_phenotype_df(file_path)
        
        if phenotype_name not in df.columns:
            raise ValueError(f'表型 {phenotype_name} 不存在于文件中')
        
        phenotype_data = pd.to_numeric(df[phenotype_name], errors='coerce')
        
        if sample_order:
            phenotype_data = phenotype_data.reindex(sample_order)
        
        return phenotype_data.values.astype(np.float64)
    
    def load_covariate_data(self, file_path, covariate_names, sample_order=None):
        df = pd.read_csv(file_path)
        
        sample_col = None
        for col in df.columns:
            if col.lower() in ['sample', 'sampleid', 'sample_id', 'id', 'ind', 'individual']:
                sample_col = col
                break
        
        if sample_col is None:
            sample_col = df.columns[0]
        
        df[sample_col] = df[sample_col].astype(str)
        df = df.set_index(sample_col)
        
        for name in covariate_names:
            if name not in df.columns:
                raise ValueError(f'协变量 {name} 不存在于文件中')
        
        cov_data = df[covariate_names].apply(pd.to_numeric, errors='coerce')
        
        if sample_order:
            cov_data = cov_data.reindex(sample_order)
        
        return cov_data.values.astype(np.float64)
