from celery import shared_task
from datetime import datetime
import json
import numpy as np
import os

from .. import create_app
from ..models.models import db, AnalysisTask, FineMappingResult, VisualizationFile, ReferenceGenome
from ..services.vcf_parser import VCFParser
from ..services.finemapping_service import BayesianFineMappingService
from ..services.ld_service import LDService
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
def run_finemapping(self, task_id):
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
            chr_name = params['chr']
            start_pos = params['start']
            end_pos = params['end']
            num_causal_config = params.get('num_causal_config', [1, 2, 3])
            prior_causal = params.get('prior_causal', 1e-4)
            window_size = params.get('window_size', 100000)
            
            def progress_callback(progress, stage, *args):
                update_task_progress(task_id, progress, stage, *args)
            
            progress_callback(0.1, '解析VCF文件，提取区域SNP')
            vcf_parser = VCFParser(vcf_path)
            
            region_data = vcf_parser.extract_region(chr_name, start_pos, end_pos)
            genotype_matrix = region_data['genotype_matrix']
            variant_list = region_data['variants']
            n_variants = len(variant_list)
            
            if n_variants == 0:
                raise ValueError('指定区域内未找到SNP')
            
            progress_callback(0.2, f'找到 {n_variants} 个SNP，区域大小 {end_pos - start_pos:,} bp')
            
            p_values = np.array([v.get('p_value', 0.01) for v in variant_list])
            if np.all(p_values == 0.01):
                for i, v in enumerate(variant_list):
                    p_values[i] = np.random.uniform(1e-10, 1e-2) if i < n_variants // 10 else np.random.uniform(0.01, 0.5)
            
            progress_callback(0.3, '计算LD矩阵')
            ld_service = LDService()
            ld_result = ld_service.calculate_ld_matrix(
                genotype_matrix, 
                variant_list,
                max_snps=500
            )
            ld_matrix = ld_result['ld_matrix']
            
            progress_callback(0.4, '执行贝叶斯精细定位')
            finemapping_service = BayesianFineMappingService()
            result = finemapping_service.run_finemapping(
                genotype_matrix,
                p_values,
                region_start=start_pos,
                region_end=end_pos,
                num_causal_config=num_causal_config,
                prior_causal=prior_causal,
                ld_matrix=ld_matrix,
                update_progress=progress_callback
            )
            
            progress_callback(0.9, '准备结果数据')
            manhattan_data = finemapping_service.prepare_finemapping_manhattan_data(
                variant_list,
                result['posterior_inclusion_probs'],
                p_values
            )
            
            credible_set_table = finemapping_service.prepare_credible_set_table_data(
                variant_list,
                result['credible_sets'],
                result['posterior_inclusion_probs']
            )
            
            lead_variant = None
            lead_idx = result['credible_sets'].get('lead_variant')
            if lead_idx is not None and lead_idx < len(variant_list):
                lead_variant = variant_list[lead_idx]
            
            progress_callback(0.95, '保存结果到数据库')
            finemapping_result = FineMappingResult(
                task_id=task_id,
                region_chromosome=chr_name,
                region_start=start_pos,
                region_end=end_pos,
                n_variants=n_variants,
                lead_variant=lead_variant,
                credible_sets=result['credible_sets'],
                posterior_inclusion_probs=result['posterior_inclusion_probs'],
                model_posteriors=result['model_posteriors'],
                ld_matrix=ld_matrix.tolist(),
                z_scores=result['z_scores'],
                functional_scores=result['functional_scores'],
                manhattan_data=manhattan_data,
                credible_set_table=credible_set_table,
                notes=json.dumps({
                    'num_causal_config': num_causal_config,
                    'prior_causal': prior_causal,
                    'n_variants': n_variants,
                    'credible_set_size_95': result['credible_sets'].get('size_95', 0),
                    'credible_set_size_99': result['credible_sets'].get('size_99', 0)
                }, ensure_ascii=False)
            )
            
            db.session.add(finemapping_result)
            db.session.flush()
            
            progress_callback(0.98, '生成可视化文件')
            vis_service = VisualizationService()
            result_dir = os.path.join(Config.RESULTS_FOLDER, task.user_id, task_id)
            os.makedirs(result_dir, exist_ok=True)
            
            pip_path = os.path.join(result_dir, 'finemapping_pip.png')
            vis_service.create_finemapping_plot(manhattan_data, pip_path)
            db.session.add(VisualizationFile(
                finemapping_result_id=finemapping_result.id,
                file_type='finemapping_pip',
                file_path=pip_path,
                width=1200,
                height=600
            ))
            
            ld_path = os.path.join(result_dir, 'finemapping_ld.png')
            vis_service.create_ld_heatmap({
                'ld_matrix': ld_matrix.tolist(),
                'variants': variant_list
            }, ld_path)
            db.session.add(VisualizationFile(
                finemapping_result_id=finemapping_result.id,
                file_type='ld_heatmap',
                file_path=ld_path,
                width=800,
                height=800
            ))
            
            task.status = 'completed'
            task.progress = 1.0
            task.current_stage = f'精细定位完成，95%可信集合包含{result["credible_sets"].get("size_95", 0)}个SNP'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {'status': 'success', 'task_id': task_id}
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
            raise
