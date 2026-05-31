from celery import shared_task
from datetime import datetime
import json
import numpy as np
import os

from .. import create_app
from ..models.models import db, AnalysisTask, MultiPhenotypeResult, SignificantSNP, VisualizationFile
from ..services.vcf_parser import VCFParser
from ..services.file_service import FileService
from ..services.multiphenotype_service import MultiPhenotypeService
from ..services.gwas_service import GWASService
from ..services.annotation_service import AnnotationService
from ..services.visualization_service import VisualizationService
from ..config import Config

def update_task_progress(task_id, progress, stage, *args):
    app = create_app()
    with app.app_context():
        task = AnalysisTask.query.get(task_id)
        if task:
            task.progress = progress
            task.current_stage = stage.format(*args) if args else stage
            db.session.commit()

@shared_task(bind=True, max_retries=0)
def run_multiphenotype_manova(self, task_id):
    app = create_app()
    with app.app_context():
        task = AnalysisTask.query.get(task_id)
        if not task:
            return
        
        try:
            task.status = 'running'
            task.started_at = datetime.utcnow()
            db.session.commit()
            
            params = task.parameters
            vcf_path = params['vcf_path']
            phenotype_path = params['phenotype_path']
            phenotype_names = params['phenotype_names']
            covariate_path = params.get('covariate_path')
            threshold = params.get('significance_threshold', 5e-8)
            
            def progress_callback(progress, stage, *args):
                update_task_progress(task_id, progress, stage, *args)
            
            progress_callback(0.1, '解析VCF文件')
            vcf_parser = VCFParser(vcf_path)
            genotype_matrix = vcf_parser.get_genotype_matrix()
            variant_list = vcf_parser.parse_genotypes()['variants']
            
            progress_callback(0.15, '解析表型数据')
            file_service = FileService()
            phenotype_df = file_service._load_phenotype_df(phenotype_path)
            vcf_samples = vcf_parser.parse_header()['samples']
            
            matched_samples = file_service.match_samples(vcf_samples, phenotype_df)
            sample_indices = [vcf_samples.index(s) for s in matched_samples]
            phenotype_matched = phenotype_df.loc[matched_samples, phenotype_names].values
            
            genotype_matrix = genotype_matrix[:, sample_indices]
            
            cov_matrix = None
            if covariate_path:
                cov_df = file_service.load_covariates(covariate_path, matched_samples)
                cov_matrix = cov_df.values
            
            progress_callback(0.2, f'执行MANOVA分析，{len(phenotype_names)}个表型')
            multipheno_service = MultiPhenotypeService()
            result = multipheno_service.run_manova(
                genotype_matrix,
                phenotype_matched,
                covariates=cov_matrix,
                update_progress=progress_callback
            )
            
            progress_callback(0.92, '准备结果数据')
            manhattan_data = multipheno_service.prepare_multiphenotype_manhattan_data(
                variant_list,
                result['p_values'],
                result['f_statistics'],
                result['maf']
            )
            
            gwas_service = GWASService()
            qq_data = gwas_service.prepare_qq_data(result['p_values'])
            
            significant_snps = gwas_service.get_significant_snps(
                variant_list,
                result['p_values'],
                result['maf'],
                result['effect_sizes'][:, 0] if result['n_phenotypes'] > 0 else np.zeros_like(result['p_values']),
                threshold=threshold
            )
            
            reference_genome_id = params.get('reference_genome', 'B73_v5')
            from ..models.models import ReferenceGenome
            genome = ReferenceGenome.query.get(reference_genome_id)
            if genome and significant_snps:
                progress_callback(0.95, '注释SNP')
                annotation_service = AnnotationService()
                annotated = annotation_service.annotate_snps(genome, significant_snps)
                significant_snps = annotated
            
            progress_callback(0.97, '保存结果到数据库')
            multipheno_result = MultiPhenotypeResult(
                task_id=task_id,
                method='MANOVA',
                phenotypes=phenotype_names,
                n_phenotypes=result['n_phenotypes'],
                inflation_factor=result['inflation_factor'],
                significant_snp_count=len(significant_snps),
                manhattan_data=manhattan_data,
                qq_data=qq_data,
                f_statistics=result['f_statistics'].tolist(),
                wilks_lambda=result['wilks_lambda'].tolist(),
                loading_scores=result['effect_sizes'].tolist(),
                notes=json.dumps({'model': 'MANOVA', 'n_phenotypes': result['n_phenotypes']}, ensure_ascii=False)
            )
            
            db.session.add(multipheno_result)
            db.session.flush()
            
            for snp_data in significant_snps:
                snp = SignificantSNP(
                    multiphenotype_result_id=multipheno_result.id,
                    snp_id=snp_data['id'],
                    chromosome=snp_data['chr'],
                    position=snp_data['pos'],
                    ref_allele=snp_data.get('ref', ''),
                    alt_allele=snp_data.get('alt', ''),
                    p_value=snp_data['p_value'],
                    log10_p=-np.log10(max(snp_data['p_value'], 1e-300)),
                    effect_size=snp_data.get('effect_size'),
                    maf=snp_data.get('maf'),
                    gene=snp_data.get('gene'),
                    annotation=snp_data.get('annotation')
                )
                db.session.add(snp)
            
            progress_callback(0.98, '生成可视化文件')
            vis_service = VisualizationService()
            result_dir = os.path.join(Config.RESULTS_FOLDER, task.user_id, task_id)
            os.makedirs(result_dir, exist_ok=True)
            
            manhattan_path = os.path.join(result_dir, 'manhattan.png')
            vis_service.create_manhattan_plot(manhattan_data, manhattan_path)
            db.session.add(VisualizationFile(
                multiphenotype_result_id=multipheno_result.id,
                file_type='manhattan',
                file_path=manhattan_path,
                width=1200,
                height=600
            ))
            
            qq_path = os.path.join(result_dir, 'qq.png')
            vis_service.create_qq_plot(qq_data, qq_path)
            db.session.add(VisualizationFile(
                multiphenotype_result_id=multipheno_result.id,
                file_type='qq',
                file_path=qq_path,
                width=600,
                height=600
            ))
            
            task.status = 'completed'
            task.progress = 1.0
            task.current_stage = 'MANOVA多表型分析完成'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {'status': 'success', 'task_id': task_id}
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
            raise

@shared_task(bind=True, max_retries=0)
def run_multiphenotype_cca(self, task_id):
    app = create_app()
    with app.app_context():
        task = AnalysisTask.query.get(task_id)
        if not task:
            return
        
        try:
            task.status = 'running'
            task.started_at = datetime.utcnow()
            db.session.commit()
            
            params = task.parameters
            vcf_path = params['vcf_path']
            phenotype_path = params['phenotype_path']
            phenotype_names = params['phenotype_names']
            covariate_path = params.get('covariate_path')
            n_components = params.get('n_components', 3)
            threshold = params.get('significance_threshold', 5e-8)
            
            def progress_callback(progress, stage, *args):
                update_task_progress(task_id, progress, stage, *args)
            
            progress_callback(0.1, '解析VCF文件')
            vcf_parser = VCFParser(vcf_path)
            genotype_matrix = vcf_parser.get_genotype_matrix()
            variant_list = vcf_parser.parse_genotypes()['variants']
            
            progress_callback(0.15, '解析表型数据')
            file_service = FileService()
            phenotype_df = file_service._load_phenotype_df(phenotype_path)
            vcf_samples = vcf_parser.parse_header()['samples']
            
            matched_samples = file_service.match_samples(vcf_samples, phenotype_df)
            sample_indices = [vcf_samples.index(s) for s in matched_samples]
            phenotype_matched = phenotype_df.loc[matched_samples, phenotype_names].values
            
            genotype_matrix = genotype_matrix[:, sample_indices]
            
            cov_matrix = None
            if covariate_path:
                cov_df = file_service.load_covariates(covariate_path, matched_samples)
                cov_matrix = cov_df.values
            
            progress_callback(0.2, f'执行CCA分析，{len(phenotype_names)}个表型，{n_components}个成分')
            multipheno_service = MultiPhenotypeService()
            result = multipheno_service.run_cca(
                genotype_matrix,
                phenotype_matched,
                covariates=cov_matrix,
                n_components=n_components,
                update_progress=progress_callback
            )
            
            progress_callback(0.92, '准备结果数据')
            manhattan_data = multipheno_service.prepare_multiphenotype_manhattan_data(
                variant_list,
                result['p_values'],
                maf=result['maf']
            )
            
            gwas_service = GWASService()
            qq_data = gwas_service.prepare_qq_data(result['p_values'])
            
            significant_snps = gwas_service.get_significant_snps(
                variant_list,
                result['p_values'],
                result['maf'],
                result['loading_scores'][:, 0] if result['n_components'] > 0 else np.zeros_like(result['p_values']),
                threshold=threshold
            )
            
            reference_genome_id = params.get('reference_genome', 'B73_v5')
            from ..models.models import ReferenceGenome
            genome = ReferenceGenome.query.get(reference_genome_id)
            if genome and significant_snps:
                progress_callback(0.95, '注释SNP')
                annotation_service = AnnotationService()
                annotated = annotation_service.annotate_snps(genome, significant_snps)
                significant_snps = annotated
            
            progress_callback(0.97, '保存结果到数据库')
            multipheno_result = MultiPhenotypeResult(
                task_id=task_id,
                method='CCA',
                phenotypes=phenotype_names,
                n_phenotypes=result['n_phenotypes'],
                inflation_factor=result['inflation_factor'],
                significant_snp_count=len(significant_snps),
                manhattan_data=manhattan_data,
                qq_data=qq_data,
                canonical_correlations=result['canonical_correlations'],
                canonical_weights=result['canonical_weights'],
                loading_scores=result['loading_scores'].tolist(),
                notes=json.dumps({
                    'model': 'CCA', 
                    'n_phenotypes': result['n_phenotypes'],
                    'n_components': result['n_components'],
                    'canonical_correlations': result['canonical_correlations']
                }, ensure_ascii=False)
            )
            
            db.session.add(multipheno_result)
            db.session.flush()
            
            for snp_data in significant_snps:
                snp = SignificantSNP(
                    multiphenotype_result_id=multipheno_result.id,
                    snp_id=snp_data['id'],
                    chromosome=snp_data['chr'],
                    position=snp_data['pos'],
                    ref_allele=snp_data.get('ref', ''),
                    alt_allele=snp_data.get('alt', ''),
                    p_value=snp_data['p_value'],
                    log10_p=-np.log10(max(snp_data['p_value'], 1e-300)),
                    effect_size=snp_data.get('effect_size'),
                    maf=snp_data.get('maf'),
                    gene=snp_data.get('gene'),
                    annotation=snp_data.get('annotation')
                )
                db.session.add(snp)
            
            progress_callback(0.98, '生成可视化文件')
            vis_service = VisualizationService()
            result_dir = os.path.join(Config.RESULTS_FOLDER, task.user_id, task_id)
            os.makedirs(result_dir, exist_ok=True)
            
            manhattan_path = os.path.join(result_dir, 'manhattan.png')
            vis_service.create_manhattan_plot(manhattan_data, manhattan_path)
            db.session.add(VisualizationFile(
                multiphenotype_result_id=multipheno_result.id,
                file_type='manhattan',
                file_path=manhattan_path,
                width=1200,
                height=600
            ))
            
            qq_path = os.path.join(result_dir, 'qq.png')
            vis_service.create_qq_plot(qq_data, qq_path)
            db.session.add(VisualizationFile(
                multiphenotype_result_id=multipheno_result.id,
                file_type='qq',
                file_path=qq_path,
                width=600,
                height=600
            ))
            
            task.status = 'completed'
            task.progress = 1.0
            task.current_stage = 'CCA多表型分析完成'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {'status': 'success', 'task_id': task_id}
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
            raise
