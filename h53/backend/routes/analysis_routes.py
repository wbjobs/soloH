from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models.models import db, UploadFile, AnalysisTask
from ..services.sample_matcher import SampleMatcher
from ..services.pca_service import PCAService
from ..tasks.gwas_tasks import run_gwas_glm, run_gwas_mlm
from ..tasks.pca_tasks import calculate_pca
from ..tasks.multiphenotype_tasks import run_multiphenotype_manova, run_multiphenotype_cca
from ..tasks.enrichment_tasks import run_enrichment_go, run_enrichment_kegg
from ..tasks.finemapping_tasks import run_finemapping

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/match-samples', methods=['POST'])
@jwt_required()
def match_samples():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'vcfFileId' not in data or 'phenotypeFileId' not in data:
        return jsonify({'error': '缺少必要参数'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    phenotype_file = UploadFile.query.filter_by(id=data['phenotypeFileId'], user_id=user_id).first()
    
    if not vcf_file or not phenotype_file:
        return jsonify({'error': '文件不存在或无权限访问'}), 404
    
    try:
        matcher = SampleMatcher()
        result = matcher.match(vcf_file, phenotype_file)
        
        return jsonify({
            'matchedSamples': result['matched'],
            'vcfOnlySamples': result['vcf_only'],
            'phenotypeOnlySamples': result['phenotype_only'],
            'matchCount': len(result['matched']),
            'vcfTotal': len(result['vcf_samples']),
            'phenotypeTotal': len(result['phenotype_samples'])
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'样本匹配失败: {str(e)}'}), 400

@analysis_bp.route('/pca', methods=['POST'])
@jwt_required()
def run_pca():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'vcfFileId' not in data:
        return jsonify({'error': '缺少必要参数'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    
    if not vcf_file:
        return jsonify({'error': 'VCF文件不存在或无权限访问'}), 404
    
    n_components = data.get('nComponents', 10)
    
    task = AnalysisTask(
        user_id=user_id,
        task_type='pca',
        status='queued',
        parameters={
            'vcf_file_id': data['vcfFileId'],
            'n_components': n_components
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    calculate_pca.delay(task.id, vcf_file.storage_path, n_components)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'createdAt': task.created_at.isoformat()
    }), 202

@analysis_bp.route('/gwas', methods=['POST'])
@jwt_required()
def run_gwas():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['vcfFileId', 'phenotypeFileId', 'phenotypeName', 'model']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    phenotype_file = UploadFile.query.filter_by(id=data['phenotypeFileId'], user_id=user_id).first()
    
    if not vcf_file or not phenotype_file:
        return jsonify({'error': '文件不存在或无权限访问'}), 404
    
    model = data.get('model', 'GLM').upper()
    if model not in ['GLM', 'MLM']:
        return jsonify({'error': '不支持的模型类型，请选择GLM或MLM'}), 400
    
    covariates = data.get('covariates', {})
    custom_cov_file_id = covariates.get('customCovariateFileId')
    
    if custom_cov_file_id:
        cov_file = UploadFile.query.filter_by(id=custom_cov_file_id, user_id=user_id).first()
        if not cov_file:
            return jsonify({'error': '协变量文件不存在或无权限访问'}), 404
    
    task = AnalysisTask(
        user_id=user_id,
        task_type=f'gwas_{model.lower()}',
        status='queued',
        parameters={
            'vcf_file_id': data['vcfFileId'],
            'phenotype_file_id': data['phenotypeFileId'],
            'phenotype_name': data['phenotypeName'],
            'model': model,
            'covariates': covariates,
            'significance_threshold': data.get('significanceThreshold', 5e-8),
            'reference_genome': data.get('referenceGenome', 'B73_v5'),
            'vcf_path': vcf_file.storage_path,
            'phenotype_path': phenotype_file.storage_path,
            'covariate_path': cov_file.storage_path if custom_cov_file_id else None
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    if model == 'GLM':
        run_gwas_glm.delay(task.id)
    else:
        run_gwas_mlm.delay(task.id)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'model': model,
        'createdAt': task.created_at.isoformat()
    }), 202

@analysis_bp.route('/ld-heatmap', methods=['POST'])
@jwt_required()
def calculate_ld_heatmap():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['vcfFileId', 'chr', 'start', 'end']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    
    if not vcf_file:
        return jsonify({'error': 'VCF文件不存在或无权限访问'}), 404
    
    from ..tasks.ld_tasks import calculate_ld_heatmap as ld_task
    
    task = AnalysisTask(
        user_id=user_id,
        task_type='ld_heatmap',
        status='queued',
        parameters={
            'vcf_file_id': data['vcfFileId'],
            'vcf_path': vcf_file.storage_path,
            'chr': data['chr'],
            'start': data['start'],
            'end': data['end']
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    ld_task.delay(task.id)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'createdAt': task.created_at.isoformat()
    }), 202

@analysis_bp.route('/multiphenotype', methods=['POST'])
@jwt_required()
def run_multiphenotype():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['vcfFileId', 'phenotypeFileId', 'phenotypeNames', 'method']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    method = data.get('method', 'MANOVA').upper()
    if method not in ['MANOVA', 'CCA']:
        return jsonify({'error': '不支持的方法，请选择MANOVA或CCA'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    phenotype_file = UploadFile.query.filter_by(id=data['phenotypeFileId'], user_id=user_id).first()
    
    if not vcf_file or not phenotype_file:
        return jsonify({'error': '文件不存在或无权限访问'}), 404
    
    covariates = data.get('covariates', {})
    custom_cov_file_id = covariates.get('customCovariateFileId')
    
    if custom_cov_file_id:
        cov_file = UploadFile.query.filter_by(id=custom_cov_file_id, user_id=user_id).first()
        if not cov_file:
            return jsonify({'error': '协变量文件不存在或无权限访问'}), 404
    
    task = AnalysisTask(
        user_id=user_id,
        task_type=f'multiphenotype_{method.lower()}',
        status='queued',
        parameters={
            'vcf_file_id': data['vcfFileId'],
            'phenotype_file_id': data['phenotypeFileId'],
            'phenotype_names': data['phenotypeNames'],
            'method': method,
            'covariates': covariates,
            'significance_threshold': data.get('significanceThreshold', 5e-8),
            'reference_genome': data.get('referenceGenome', 'B73_v5'),
            'n_components': data.get('nComponents', 3),
            'vcf_path': vcf_file.storage_path,
            'phenotype_path': phenotype_file.storage_path,
            'covariate_path': cov_file.storage_path if custom_cov_file_id else None
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    if method == 'MANOVA':
        run_multiphenotype_manova.delay(task.id)
    else:
        run_multiphenotype_cca.delay(task.id)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'method': method,
        'phenotypeCount': len(data['phenotypeNames']),
        'createdAt': task.created_at.isoformat()
    }), 202

@analysis_bp.route('/enrichment', methods=['POST'])
@jwt_required()
def run_enrichment():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['resultTaskId', 'type']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    enrichment_type = data.get('type', 'GO').upper()
    if enrichment_type not in ['GO', 'KEGG']:
        return jsonify({'error': '不支持的富集类型，请选择GO或KEGG'}), 400
    
    result_task = AnalysisTask.query.filter_by(id=data['resultTaskId'], user_id=user_id).first()
    if not result_task:
        return jsonify({'error': '结果任务不存在或无权限访问'}), 404
    
    task = AnalysisTask(
        user_id=user_id,
        task_type=f'enrichment_{enrichment_type.lower()}',
        status='queued',
        parameters={
            'result_task_id': data['resultTaskId'],
            'type': enrichment_type,
            'p_value_threshold': data.get('pValueThreshold', 0.05),
            'window_size': data.get('windowSize', 50000),
            'reference_genome': data.get('referenceGenome', 'B73_v5')
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    if enrichment_type == 'GO':
        run_enrichment_go.delay(task.id)
    else:
        run_enrichment_kegg.delay(task.id)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'type': enrichment_type,
        'createdAt': task.created_at.isoformat()
    }), 202

@analysis_bp.route('/finemapping', methods=['POST'])
@jwt_required()
def run_finemapping_route():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['vcfFileId', 'resultTaskId', 'chr', 'start', 'end']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': '缺少必要参数'}), 400
    
    vcf_file = UploadFile.query.filter_by(id=data['vcfFileId'], user_id=user_id).first()
    result_task = AnalysisTask.query.filter_by(id=data['resultTaskId'], user_id=user_id).first()
    
    if not vcf_file or not result_task:
        return jsonify({'error': '文件或任务不存在或无权限访问'}), 404
    
    task = AnalysisTask(
        user_id=user_id,
        task_type='finemapping',
        status='queued',
        parameters={
            'vcf_file_id': data['vcfFileId'],
            'result_task_id': data['resultTaskId'],
            'vcf_path': vcf_file.storage_path,
            'chr': data['chr'],
            'start': data['start'],
            'end': data['end'],
            'num_causal_config': data.get('numCausalConfig', [1, 2, 3]),
            'prior_causal': data.get('priorCausal', 1e-4),
            'credible_level': data.get('credibleLevel', 0.95),
            'window_size': data.get('windowSize', 100000)
        }
    )
    
    db.session.add(task)
    db.session.commit()
    
    run_finemapping.delay(task.id)
    
    return jsonify({
        'taskId': task.id,
        'status': task.status,
        'region': {
            'chr': data['chr'],
            'start': data['start'],
            'end': data['end']
        },
        'createdAt': task.created_at.isoformat()
    }), 202
