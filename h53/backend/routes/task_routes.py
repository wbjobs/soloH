from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from ..models.models import db, AnalysisTask

task_bp = Blueprint('task', __name__)

@task_bp.route('', methods=['GET'])
@jwt_required()
def list_tasks():
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status', None)
    task_type = request.args.get('type', None)
    
    query = AnalysisTask.query.filter_by(user_id=user_id)
    
    if status:
        query = query.filter_by(status=status)
    if task_type:
        query = query.filter_by(task_type=task_type)
    
    total = query.count()
    tasks = query.order_by(AnalysisTask.created_at.desc()) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()
    
    return jsonify({
        'total': total,
        'page': page,
        'pageSize': page_size,
        'tasks': [task.to_dict() for task in tasks]
    }), 200

@task_bp.route('/<task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(task.to_dict()), 200

@task_bp.route('/<task_id>', methods=['DELETE'])
@jwt_required()
def cancel_task(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    if task.status in ['queued', 'running']:
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.session.commit()
        
        from celery import current_app as celery_app
        try:
            celery_app.control.revoke(task_id, terminate=True)
        except:
            pass
        
        return jsonify({'message': '任务已取消', 'task': task.to_dict()}), 200
    else:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': '任务已删除'}), 200

@task_bp.route('/<task_id>/restart', methods=['POST'])
@jwt_required()
def restart_task(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    new_task = AnalysisTask(
        user_id=user_id,
        task_type=task.task_type,
        status='queued',
        parameters=task.parameters,
        progress=0.0
    )
    
    db.session.add(new_task)
    db.session.commit()
    
    from ..tasks.gwas_tasks import run_gwas_glm, run_gwas_mlm
    from ..tasks.pca_tasks import calculate_pca
    from ..tasks.ld_tasks import calculate_ld_heatmap
    
    if task.task_type == 'gwas_glm':
        run_gwas_glm.delay(new_task.id)
    elif task.task_type == 'gwas_mlm':
        run_gwas_mlm.delay(new_task.id)
    elif task.task_type == 'pca':
        calculate_pca.delay(
            new_task.id,
            task.parameters.get('vcf_path'),
            task.parameters.get('n_components', 10)
        )
    elif task.task_type == 'ld_heatmap':
        calculate_ld_heatmap.delay(new_task.id)
    
    return jsonify({
        'message': '任务已重新提交',
        'taskId': new_task.id,
        'task': new_task.to_dict()
    }), 201

@task_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_task_stats():
    user_id = get_jwt_identity()
    
    stats = {
        'total': AnalysisTask.query.filter_by(user_id=user_id).count(),
        'queued': AnalysisTask.query.filter_by(user_id=user_id, status='queued').count(),
        'running': AnalysisTask.query.filter_by(user_id=user_id, status='running').count(),
        'completed': AnalysisTask.query.filter_by(user_id=user_id, status='completed').count(),
        'failed': AnalysisTask.query.filter_by(user_id=user_id, status='failed').count(),
        'cancelled': AnalysisTask.query.filter_by(user_id=user_id, status='cancelled').count()
    }
    
    return jsonify(stats), 200
