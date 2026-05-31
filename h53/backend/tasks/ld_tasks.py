from celery import current_app as celery_app
from datetime import datetime
import os
import numpy as np

from .celery_app import make_celery
from ..models.models import db, AnalysisTask
from ..services.vcf_parser import VCFParser
from ..services.ld_service import LDService
from ..services.visualization_service import VisualizationService

celery = make_celery()

def update_task_progress(task_id, progress, stage):
    task = AnalysisTask.query.get(task_id)
    if task:
        task.progress = progress
        task.current_stage = stage
        db.session.commit()

@celery.task(bind=True, name='ld.calculate_heatmap')
def calculate_ld_heatmap(self, task_id):
    try:
        task = AnalysisTask.query.get(task_id)
        if not task or task.status == 'cancelled':
            return
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        params = task.parameters
        vcf_path = params['vcf_path']
        chrom = params['chr']
        start = params['start']
        end = params['end']
        
        def progress_callback(progress, stage, *args):
            msg = stage.format(*args) if args else stage
            update_task_progress(task_id, progress, msg)
        
        progress_callback(0.1, '解析VCF文件')
        vcf_parser = VCFParser(vcf_path)
        vcf_parser.parse_header()
        
        progress_callback(0.3, '计算LD矩阵')
        ld_service = LDService()
        ld_result = ld_service.calculate_ld_from_vcf(
            vcf_parser,
            chrom,
            start,
            end,
            update_progress=progress_callback
        )
        
        progress_callback(0.9, '生成LD热图')
        result_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'results', str(task.user_id), task_id)
        os.makedirs(result_dir, exist_ok=True)
        
        vis_service = VisualizationService()
        ld_heatmap_path = os.path.join(result_dir, f'ld_heatmap_{chrom}_{start}_{end}.png')
        
        vis_service.create_ld_heatmap(
            ld_result['ldMatrix'],
            ld_result['snpNames'],
            ld_result['positions'],
            ld_heatmap_path,
            ld_result.get('hapBlocks')
        )
        
        task.parameters['ld_result'] = {
            'snpNames': ld_result['snpNames'],
            'positions': ld_result['positions'],
            'ldMatrix': ld_result['ldMatrix'],
            'hapBlocks': ld_result.get('hapBlocks', []),
            'heatmap_path': ld_heatmap_path
        }
        
        task.status = 'completed'
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'status': 'success',
            'task_id': task_id,
            'n_snps': len(ld_result['snpNames']),
            'n_hap_blocks': len(ld_result.get('hapBlocks', []))
        }
        
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
