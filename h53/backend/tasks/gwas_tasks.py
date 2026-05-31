from celery import current_app as celery_app
from datetime import datetime
import os
import numpy as np
import json

from .celery_app import make_celery
from ..models.models import db, AnalysisTask, GWASResult, SignificantSNP, VisualizationFile, UploadFile
from ..services.gwas_service import GWASService
from ..services.vcf_parser import VCFParser
from ..services.file_service import FileService
from ..services.sample_matcher import SampleMatcher
from ..services.pca_service import PCAService
from ..services.visualization_service import VisualizationService
from ..services.annotation_service import AnnotationService

celery = make_celery()

def update_task_progress(task_id, progress, stage, **kwargs):
    task = AnalysisTask.query.get(task_id)
    if task:
        task.progress = progress
        task.current_stage = stage
        if 'error' in kwargs:
            task.error_message = kwargs['error']
        db.session.commit()

@celery.task(bind=True, name='gwas.run_glm')
def run_gwas_glm(self, task_id):
    try:
        task = AnalysisTask.query.get(task_id)
        if not task or task.status == 'cancelled':
            return
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        params = task.parameters
        vcf_path = params['vcf_path']
        phenotype_path = params['phenotype_path']
        phenotype_name = params['phenotype_name']
        
        def progress_callback(progress, stage, *args):
            msg = stage.format(*args) if args else stage
            update_task_progress(task_id, progress, msg)
        
        progress_callback(0.05, '解析VCF文件')
        vcf_parser = VCFParser(vcf_path)
        vcf_parser.parse_header()
        
        progress_callback(0.15, '读取表型数据')
        file_service = FileService()
        phenotype_data = file_service.load_phenotype_data(phenotype_path, phenotype_name)
        
        progress_callback(0.2, '匹配样本')
        matcher = SampleMatcher()
        vcf_samples = vcf_parser.samples
        
        phenotype_df = file_service._load_phenotype_df(phenotype_path)
        pheno_samples = phenotype_df.index.tolist()
        
        matched_samples = list(set(vcf_samples) & set(pheno_samples))
        
        vcf_indices = [vcf_samples.index(s) for s in matched_samples]
        pheno_indices = [pheno_samples.index(s) for s in matched_samples]
        
        progress_callback(0.25, '读取基因型矩阵')
        genotype_matrix, samples, variants = vcf_parser.get_genotype_matrix()
        genotype_matrix = genotype_matrix[:, vcf_indices]
        phenotype_matched = phenotype_data[pheno_indices]
        
        covariates = params.get('covariates', {})
        cov_matrix = None
        
        if covariates.get('pcaComponents'):
            progress_callback(0.3, '计算PCA协变量')
            pca_service = PCAService()
            pca_result = pca_service.calculate_pca(genotype_matrix, n_components=max(covariates['pcaComponents']))
            pca_scores = pca_result['pc_scores']
            n_pc = len(covariates['pcaComponents'])
            cov_matrix = pca_scores[:, :n_pc]
        
        if covariates.get('customCovariateFileId') and covariates.get('customCovariateNames'):
            progress_callback(0.35, '加载自定义协变量')
            cov_path = params.get('covariate_path')
            if cov_path:
                custom_cov = file_service.load_covariate_data(
                    cov_path, 
                    covariates['customCovariateNames'],
                    sample_order=matched_samples
                )
                cov_indices = matcher.get_sample_indices(
                    file_service.parse_covariate_csv(cov_path)['samples'],
                    matched_samples
                )
                custom_cov = custom_cov[cov_indices]
                if cov_matrix is not None:
                    cov_matrix = np.column_stack([cov_matrix, custom_cov])
                else:
                    cov_matrix = custom_cov
        
        progress_callback(0.4, '执行GLM关联分析')
        gwas_service = GWASService()
        gwas_results = gwas_service.run_glm(
            genotype_matrix,
            phenotype_matched,
            covariates=cov_matrix,
            update_progress=progress_callback
        )
        
        progress_callback(0.9, '准备结果数据')
        variant_list = vcf_parser.parse_genotypes()['variants']
        
        manhattan_data = gwas_service.prepare_manhattan_data(
            variant_list,
            gwas_results['p_values'],
            gwas_results['maf'],
            gwas_results['effect_sizes']
        )
        
        qq_data = gwas_service.prepare_qq_data(gwas_results['p_values'])
        
        threshold = params.get('significance_threshold', 5e-8)
        significant_snps = gwas_service.get_significant_snps(
            variant_list,
            gwas_results['p_values'],
            gwas_results['maf'],
            gwas_results['effect_sizes'],
            threshold=threshold
        )
        
        reference_genome_id = params.get('reference_genome', 'B73_v5')
        from ..models.models import ReferenceGenome
        genome = ReferenceGenome.query.get(reference_genome_id)
        if genome and significant_snps:
            progress_callback(0.93, '注释SNP')
            annotation_service = AnnotationService()
            annotated = annotation_service.annotate_snps(genome, significant_snps)
            significant_snps = annotated
        
        progress_callback(0.95, '保存结果到数据库')
        gwas_result = GWASResult(
            task_id=task_id,
            model_type='GLM',
            phenotype=phenotype_name,
            inflation_factor=gwas_results['inflation_factor'],
            significant_snp_count=len(significant_snps),
            manhattan_data=manhattan_data,
            qq_data=qq_data
        )
        db.session.add(gwas_result)
        db.session.flush()
        
        for snp in significant_snps:
            significant_snp = SignificantSNP(
                result_id=gwas_result.id,
                snp_id=snp.get('snp_id', snp.get('snp', '')),
                chromosome=snp.get('chromosome', snp.get('chr', '')),
                position=snp.get('position', snp.get('pos', 0)),
                ref_allele=snp.get('ref_allele', snp.get('ref', '')),
                alt_allele=snp.get('alt_allele', snp.get('alt', '')),
                p_value=snp.get('p_value', snp.get('pValue', 0)),
                log10_p=snp.get('log10_p', snp.get('log10P', 0)),
                effect_size=snp.get('effect_size', snp.get('effectSize', 0)),
                maf=snp.get('maf', 0),
                gene=snp.get('gene'),
                annotation=snp.get('annotation', snp.get('region', ''))
            )
            db.session.add(significant_snp)
        
        progress_callback(0.97, '生成可视化图表')
        result_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'results', str(task.user_id), task_id)
        os.makedirs(result_dir, exist_ok=True)
        
        vis_service = VisualizationService()
        
        manhattan_path = os.path.join(result_dir, 'manhattan.png')
        vis_service.create_manhattan_plot(manhattan_data, manhattan_path, threshold)
        
        qq_path = os.path.join(result_dir, 'qq.png')
        vis_service.create_qq_plot(qq_data, qq_path, gwas_results['inflation_factor'])
        
        for file_type, file_path in [('manhattan', manhattan_path), ('qq', qq_path)]:
            vis_file = VisualizationFile(
                result_id=gwas_result.id,
                file_type=file_type,
                file_path=file_path,
                width=1920,
                height=1080
            )
            db.session.add(vis_file)
        
        task.status = 'completed'
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        db.session.commit()
        
        return {'status': 'success', 'task_id': task_id, 'n_significant': len(significant_snps)}
        
    except Exception as e:
        import traceback
        error_msg = f'{str(e)}\n{traceback.format_exc()}'
        task = AnalysisTask.query.get(task_id)
        if task:
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = datetime.utcnow()
            db.session.commit()
        return {'status': 'failed', 'task_id': task_id, 'error': error_msg}

@celery.task(bind=True, name='gwas.run_mlm')
def run_gwas_mlm(self, task_id):
    try:
        task = AnalysisTask.query.get(task_id)
        if not task or task.status == 'cancelled':
            return
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        params = task.parameters
        vcf_path = params['vcf_path']
        phenotype_path = params['phenotype_path']
        phenotype_name = params['phenotype_name']
        
        def progress_callback(progress, stage, *args):
            msg = stage.format(*args) if args else stage
            update_task_progress(task_id, progress, msg)
        
        progress_callback(0.05, '解析VCF文件')
        vcf_parser = VCFParser(vcf_path)
        vcf_parser.parse_header()
        
        progress_callback(0.15, '读取表型数据')
        file_service = FileService()
        phenotype_data = file_service.load_phenotype_data(phenotype_path, phenotype_name)
        
        progress_callback(0.2, '匹配样本')
        matcher = SampleMatcher()
        vcf_samples = vcf_parser.samples
        
        phenotype_df = file_service._load_phenotype_df(phenotype_path)
        pheno_samples = phenotype_df.index.tolist()
        
        matched_samples = list(set(vcf_samples) & set(pheno_samples))
        
        vcf_indices = [vcf_samples.index(s) for s in matched_samples]
        pheno_indices = [pheno_samples.index(s) for s in matched_samples]
        
        progress_callback(0.25, '读取基因型矩阵')
        genotype_matrix, samples, variants = vcf_parser.get_genotype_matrix()
        genotype_matrix = genotype_matrix[:, vcf_indices]
        phenotype_matched = phenotype_data[pheno_indices]
        
        covariates = params.get('covariates', {})
        cov_matrix = None
        
        if covariates.get('pcaComponents'):
            progress_callback(0.3, '计算PCA协变量')
            pca_service = PCAService()
            pca_result = pca_service.calculate_pca(genotype_matrix, n_components=max(covariates['pcaComponents']))
            pca_scores = pca_result['pc_scores']
            n_pc = len(covariates['pcaComponents'])
            cov_matrix = pca_scores[:, :n_pc]
        
        if covariates.get('customCovariateFileId') and covariates.get('customCovariateNames'):
            progress_callback(0.35, '加载自定义协变量')
            cov_path = params.get('covariate_path')
            if cov_path:
                custom_cov = file_service.load_covariate_data(
                    cov_path, 
                    covariates['customCovariateNames'],
                    sample_order=matched_samples
                )
                if cov_matrix is not None:
                    cov_matrix = np.column_stack([cov_matrix, custom_cov])
                else:
                    cov_matrix = custom_cov
        
        progress_callback(0.4, '执行MLM关联分析')
        gwas_service = GWASService()
        gwas_results = gwas_service.run_mlm(
            genotype_matrix,
            phenotype_matched,
            covariates=cov_matrix,
            update_progress=progress_callback
        )
        
        model_used = gwas_results.get('model_used', 'MLM')
        mlm_failed = gwas_results.get('mlm_failed', False)
        warnings = gwas_results.get('warnings')
        
        if mlm_failed:
            progress_callback(0.9, 'MLM收敛失败，已自动降级到GLM模型')
        
        progress_callback(0.9, '准备结果数据')
        variant_list = vcf_parser.parse_genotypes()['variants']
        
        manhattan_data = gwas_service.prepare_manhattan_data(
            variant_list,
            gwas_results['p_values'],
            gwas_results['maf'],
            gwas_results['effect_sizes']
        )
        
        qq_data = gwas_service.prepare_qq_data(gwas_results['p_values'])
        
        threshold = params.get('significance_threshold', 5e-8)
        significant_snps = gwas_service.get_significant_snps(
            variant_list,
            gwas_results['p_values'],
            gwas_results['maf'],
            gwas_results['effect_sizes'],
            threshold=threshold
        )
        
        reference_genome_id = params.get('reference_genome', 'B73_v5')
        from ..models.models import ReferenceGenome
        genome = ReferenceGenome.query.get(reference_genome_id)
        if genome and significant_snps:
            progress_callback(0.93, '注释SNP')
            annotation_service = AnnotationService()
            annotated = annotation_service.annotate_snps(genome, significant_snps)
            significant_snps = annotated
        
        progress_callback(0.95, '保存结果到数据库')
        gwas_result = GWASResult(
            task_id=task_id,
            model_type=model_used,
            phenotype=phenotype_name,
            inflation_factor=gwas_results['inflation_factor'],
            significant_snp_count=len(significant_snps),
            manhattan_data=manhattan_data,
            qq_data=qq_data,
            notes=json.dumps({
                'original_model': 'MLM',
                'mlm_failed': mlm_failed,
                'warnings': warnings,
                'sigma_g': float(gwas_results.get('sigma_g')) if 'sigma_g' in gwas_results else None,
                'sigma_e': float(gwas_results.get('sigma_e')) if 'sigma_e' in gwas_results else None,
            }, ensure_ascii=False) if mlm_failed or warnings else None
        )
        db.session.add(gwas_result)
        db.session.flush()
        
        for snp in significant_snps:
            significant_snp = SignificantSNP(
                result_id=gwas_result.id,
                snp_id=snp.get('snp_id', snp.get('snp', '')),
                chromosome=snp.get('chromosome', snp.get('chr', '')),
                position=snp.get('position', snp.get('pos', 0)),
                ref_allele=snp.get('ref_allele', snp.get('ref', '')),
                alt_allele=snp.get('alt_allele', snp.get('alt', '')),
                p_value=snp.get('p_value', snp.get('pValue', 0)),
                log10_p=snp.get('log10_p', snp.get('log10P', 0)),
                effect_size=snp.get('effect_size', snp.get('effectSize', 0)),
                maf=snp.get('maf', 0),
                gene=snp.get('gene'),
                annotation=snp.get('annotation', snp.get('region', ''))
            )
            db.session.add(significant_snp)
        
        progress_callback(0.97, '生成可视化图表')
        result_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'results', str(task.user_id), task_id)
        os.makedirs(result_dir, exist_ok=True)
        
        vis_service = VisualizationService()
        
        manhattan_path = os.path.join(result_dir, 'manhattan.png')
        vis_service.create_manhattan_plot(manhattan_data, manhattan_path, threshold)
        
        qq_path = os.path.join(result_dir, 'qq.png')
        vis_service.create_qq_plot(qq_data, qq_path, gwas_results['inflation_factor'])
        
        for file_type, file_path in [('manhattan', manhattan_path), ('qq', qq_path)]:
            vis_file = VisualizationFile(
                result_id=gwas_result.id,
                file_type=file_type,
                file_path=file_path,
                width=1920,
                height=1080
            )
            db.session.add(vis_file)
        
        task.status = 'completed'
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        db.session.commit()
        
        return {'status': 'success', 'task_id': task_id, 'n_significant': len(significant_snps)}
        
    except Exception as e:
        import traceback
        error_msg = f'{str(e)}\n{traceback.format_exc()}'
        task = AnalysisTask.query.get(task_id)
        if task:
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = datetime.utcnow()
            db.session.commit()
        return {'status': 'failed', 'task_id': task_id, 'error': error_msg}

import pandas as pd
