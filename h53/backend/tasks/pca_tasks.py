from celery import current_app as celery_app
from datetime import datetime
import os
import numpy as np

from .celery_app import make_celery
from ..models.models import db, AnalysisTask
from ..services.vcf_parser import VCFParser
from ..services.pca_service import PCAService
from ..services.visualization_service import VisualizationService

celery = make_celery()

def update_task_progress(task_id, progress, stage):
    task = AnalysisTask.query.get(task_id)
    if task:
        task.progress = progress
        task.current_stage = stage
        db.session.commit()

@celery.task(bind=True, name='pca.calculate')
def calculate_pca(self, task_id, vcf_path, n_components=10):
    try:
        task = AnalysisTask.query.get(task_id)
        if not task or task.status == 'cancelled':
            return
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        def progress_callback(progress, stage, *args):
            msg = stage.format(*args) if args else stage
            update_task_progress(task_id, progress, msg)
        
        progress_callback(0.1, '解析VCF文件')
        vcf_parser = VCFParser(vcf_path)
        vcf_parser.parse_header()
        
        progress_callback(0.3, '执行PCA分析')
        pca_service = PCAService()
        pca_result = pca_service.calculate_pca_from_vcf(
            vcf_parser,
            n_components=n_components,
            update_progress=progress_callback
        )
        
        progress_callback(0.9, '生成PCA图')
        result_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'results', str(task.user_id), task_id)
        os.makedirs(result_dir, exist_ok=True)
        
        vis_service = VisualizationService()
        pca_plot_path = os.path.join(result_dir, 'pca_plot.png')
        
        pc_data_with_ids = []
        for i, sample in enumerate(pca_result['samples']):
            pc_dict = {'sampleId': sample}
            for j in range(min(n_components, pca_result['pc_scores'].shape[1])):
                pc_dict[f'PC{j+1}'] = float(pca_result['pc_scores'][i, j])
            pc_data_with_ids.append(pc_dict)
        
        vis_service.create_pca_plot(pc_data_with_ids, pca_plot_path)
        
        task.parameters['pca_result'] = {
            'explained_variance_ratio': pca_result['explained_variance_ratio'],
            'pc_data': pc_data_with_ids,
            'samples': pca_result['samples']
        }
        
        task.status = 'completed'
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'status': 'success',
            'task_id': task_id,
            'explained_variance_ratio': pca_result['explained_variance_ratio'],
            'n_components': len(pca_result['explained_variance_ratio'])
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
