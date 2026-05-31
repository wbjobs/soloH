from celery import shared_task
from datetime import datetime
import json
import numpy as np
import os

from .. import create_app
from ..models.models import db, AnalysisTask, EnrichmentResult, VisualizationFile, GWASResult, SignificantSNP, ReferenceGenome
from ..services.enrichment_service import EnrichmentService
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
def run_enrichment_go(self, task_id):
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
            result_task_id = params['result_task_id']
            p_value_threshold = params.get('p_value_threshold', 0.05)
            window_size = params.get('window_size', 50000)
            reference_genome_id = params.get('reference_genome', 'B73_v5')
            
            def progress_callback(progress, stage, *args):
                update_task_progress(task_id, progress, stage, *args)
            
            progress_callback(0.1, '获取GWAS分析结果')
            gwas_result = GWASResult.query.filter_by(task_id=result_task_id).first()
            if not gwas_result:
                raise ValueError('GWAS结果不存在')
            
            significant_snps = SignificantSNP.query.filter_by(
                result_id=gwas_result.id
            ).order_by(SignificantSNP.p_value).all()
            
            snp_list = [snp.to_dict() for snp in significant_snps]
            
            genome = ReferenceGenome.query.get(reference_genome_id)
            if not genome:
                genome = ReferenceGenome.query.first()
            
            progress_callback(0.2, f'定位候选基因，窗口大小 {window_size//1000}kb')
            enrichment_service = EnrichmentService()
            gene_mapping = enrichment_service.get_genes_for_snps(
                snp_list, genome, window_size=window_size
            )
            
            candidate_genes = gene_mapping['candidate_genes']
            snp_gene_mapping = gene_mapping['snp_gene_mapping']
            
            progress_callback(0.3, f'执行GO富集分析，{len(candidate_genes)}个候选基因')
            background_genes = []
            for go_term in enrichment_service.go_terms.values():
                background_genes.extend(go_term['genes'])
            background_genes = list(set(background_genes))
            
            go_result = enrichment_service.run_go_enrichment(
                candidate_genes,
                background_genes=background_genes,
                p_value_threshold=p_value_threshold,
                update_progress=progress_callback
            )
            
            progress_callback(0.9, '准备可视化数据')
            barplot_data = enrichment_service.prepare_enrichment_barplot_data(
                go_result['enrichment_results']
            )
            network_data = enrichment_service.prepare_gene_concept_network(
                go_result['enrichment_results']
            )
            
            progress_callback(0.95, '保存结果到数据库')
            enrichment_result = EnrichmentResult(
                task_id=task_id,
                enrichment_type='GO',
                total_terms_analyzed=go_result['total_terms_analyzed'],
                significant_terms_count=go_result['significant_terms_count'],
                enrichment_data=go_result['enrichment_results'],
                barplot_data=barplot_data,
                network_data=network_data,
                snp_gene_mapping=snp_gene_mapping,
                candidate_genes=candidate_genes,
                notes=json.dumps({
                    'source_task_id': result_task_id,
                    'window_size': window_size,
                    'p_value_threshold': p_value_threshold,
                    'candidate_gene_count': len(candidate_genes)
                }, ensure_ascii=False)
            )
            
            db.session.add(enrichment_result)
            db.session.flush()
            
            progress_callback(0.98, '生成可视化文件')
            vis_service = VisualizationService()
            result_dir = os.path.join(Config.RESULTS_FOLDER, task.user_id, task_id)
            os.makedirs(result_dir, exist_ok=True)
            
            if barplot_data:
                barplot_path = os.path.join(result_dir, 'go_enrichment_barplot.png')
                vis_service.create_enrichment_barplot(barplot_data, barplot_path, 'GO Enrichment')
                db.session.add(VisualizationFile(
                    enrichment_result_id=enrichment_result.id,
                    file_type='enrichment_barplot',
                    file_path=barplot_path,
                    width=1000,
                    height=600
                ))
            
            task.status = 'completed'
            task.progress = 1.0
            task.current_stage = f'GO富集分析完成，发现{go_result["significant_terms_count"]}个显著富集术语'
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
def run_enrichment_kegg(self, task_id):
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
            result_task_id = params['result_task_id']
            p_value_threshold = params.get('p_value_threshold', 0.05)
            window_size = params.get('window_size', 50000)
            reference_genome_id = params.get('reference_genome', 'B73_v5')
            
            def progress_callback(progress, stage, *args):
                update_task_progress(task_id, progress, stage, *args)
            
            progress_callback(0.1, '获取GWAS分析结果')
            gwas_result = GWASResult.query.filter_by(task_id=result_task_id).first()
            if not gwas_result:
                raise ValueError('GWAS结果不存在')
            
            significant_snps = SignificantSNP.query.filter_by(
                result_id=gwas_result.id
            ).order_by(SignificantSNP.p_value).all()
            
            snp_list = [snp.to_dict() for snp in significant_snps]
            
            genome = ReferenceGenome.query.get(reference_genome_id)
            if not genome:
                genome = ReferenceGenome.query.first()
            
            progress_callback(0.2, f'定位候选基因，窗口大小 {window_size//1000}kb')
            enrichment_service = EnrichmentService()
            gene_mapping = enrichment_service.get_genes_for_snps(
                snp_list, genome, window_size=window_size
            )
            
            candidate_genes = gene_mapping['candidate_genes']
            snp_gene_mapping = gene_mapping['snp_gene_mapping']
            
            progress_callback(0.3, f'执行KEGG通路富集分析，{len(candidate_genes)}个候选基因')
            background_genes = []
            for pathway in enrichment_service.kegg_pathways.values():
                background_genes.extend(pathway['genes'])
            background_genes = list(set(background_genes))
            
            kegg_result = enrichment_service.run_kegg_enrichment(
                candidate_genes,
                background_genes=background_genes,
                p_value_threshold=p_value_threshold,
                update_progress=progress_callback
            )
            
            progress_callback(0.9, '准备可视化数据')
            barplot_data = enrichment_service.prepare_enrichment_barplot_data(
                kegg_result['enrichment_results']
            )
            network_data = enrichment_service.prepare_gene_concept_network(
                kegg_result['enrichment_results']
            )
            
            progress_callback(0.95, '保存结果到数据库')
            enrichment_result = EnrichmentResult(
                task_id=task_id,
                enrichment_type='KEGG',
                total_terms_analyzed=kegg_result['total_pathways_analyzed'],
                significant_terms_count=kegg_result['significant_pathways_count'],
                enrichment_data=kegg_result['enrichment_results'],
                barplot_data=barplot_data,
                network_data=network_data,
                snp_gene_mapping=snp_gene_mapping,
                candidate_genes=candidate_genes,
                notes=json.dumps({
                    'source_task_id': result_task_id,
                    'window_size': window_size,
                    'p_value_threshold': p_value_threshold,
                    'candidate_gene_count': len(candidate_genes)
                }, ensure_ascii=False)
            )
            
            db.session.add(enrichment_result)
            db.session.flush()
            
            progress_callback(0.98, '生成可视化文件')
            vis_service = VisualizationService()
            result_dir = os.path.join(Config.RESULTS_FOLDER, task.user_id, task_id)
            os.makedirs(result_dir, exist_ok=True)
            
            if barplot_data:
                barplot_path = os.path.join(result_dir, 'kegg_enrichment_barplot.png')
                vis_service.create_enrichment_barplot(barplot_data, barplot_path, 'KEGG Pathway Enrichment')
                db.session.add(VisualizationFile(
                    enrichment_result_id=enrichment_result.id,
                    file_type='enrichment_barplot',
                    file_path=barplot_path,
                    width=1000,
                    height=600
                ))
            
            task.status = 'completed'
            task.progress = 1.0
            task.current_stage = f'KEGG通路富集分析完成，发现{kegg_result["significant_pathways_count"]}个显著富集通路'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {'status': 'success', 'task_id': task_id}
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
            raise
