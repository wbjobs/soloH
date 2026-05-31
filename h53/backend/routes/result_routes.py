import os
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import io
import csv

from ..models.models import db, AnalysisTask, GWASResult, SignificantSNP, VisualizationFile, \
    MultiPhenotypeResult, EnrichmentResult, FineMappingResult
from ..services.visualization_service import VisualizationService

result_bp = Blueprint('result', __name__)

@result_bp.route('/<task_id>', methods=['GET'])
@jwt_required()
def get_result(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    if task.status != 'completed':
        return jsonify({
            'taskId': task_id,
            'status': task.status,
            'message': '任务尚未完成'
        }), 202
    
    if task.task_type in ['gwas_glm', 'gwas_mlm']:
        return get_gwas_result(task_id, task)
    elif task.task_type in ['multiphenotype_manova', 'multiphenotype_cca']:
        return get_multiphenotype_result(task_id, task)
    elif task.task_type in ['enrichment_go', 'enrichment_kegg']:
        return get_enrichment_result(task_id, task)
    elif task.task_type == 'finemapping':
        return get_finemapping_result(task_id, task)
    else:
        return jsonify({'error': '不支持的任务类型'}), 400

def get_gwas_result(task_id, task):
    gwas_result = GWASResult.query.filter_by(task_id=task_id).first()
    
    if not gwas_result:
        return jsonify({'error': '结果不存在'}), 404
    
    significant_snps = SignificantSNP.query.filter_by(result_id=gwas_result.id) \
                                            .order_by(SignificantSNP.p_value) \
                                            .all()
    
    vis_files = VisualizationFile.query.filter_by(result_id=gwas_result.id).all()
    
    result_data = {
        'taskId': task_id,
        'taskType': task.task_type,
        'resultType': 'gwas',
        'model': gwas_result.model_type,
        'phenotype': gwas_result.phenotype,
        'inflationFactor': gwas_result.inflation_factor,
        'significantSNPCount': gwas_result.significant_snp_count,
        'manhattanData': gwas_result.manhattan_data,
        'qqData': gwas_result.qq_data,
        'significantSNPs': [snp.to_dict() for snp in significant_snps],
        'visualizationFiles': [vf.to_dict() for vf in vis_files],
        'createdAt': gwas_result.created_at.isoformat() if gwas_result.created_at else None
    }
    
    if gwas_result.notes:
        result_data['notes'] = gwas_result.notes
        if isinstance(gwas_result.notes, dict):
            result_data['mlmFailed'] = gwas_result.notes.get('mlm_failed', False)
            result_data['warnings'] = gwas_result.notes.get('warnings')
            result_data['originalModel'] = gwas_result.notes.get('original_model')
    
    return jsonify(result_data), 200

def get_multiphenotype_result(task_id, task):
    result = MultiPhenotypeResult.query.filter_by(task_id=task_id).first()
    
    if not result:
        return jsonify({'error': '结果不存在'}), 404
    
    significant_snps = SignificantSNP.query.filter_by(multiphenotype_result_id=result.id) \
                                            .order_by(SignificantSNP.p_value) \
                                            .all()
    
    vis_files = VisualizationFile.query.filter_by(multiphenotype_result_id=result.id).all()
    
    result_data = {
        'taskId': task_id,
        'taskType': task.task_type,
        'resultType': 'multiphenotype',
        'method': result.method,
        'phenotypes': result.phenotypes,
        'nPhenotypes': result.n_phenotypes,
        'inflationFactor': result.inflation_factor,
        'significantSNPCount': result.significant_snp_count,
        'manhattanData': result.manhattan_data,
        'qqData': result.qq_data,
        'canonicalCorrelations': result.canonical_correlations,
        'canonicalWeights': result.canonical_weights,
        'loadingScores': result.loading_scores,
        'fStatistics': result.f_statistics,
        'wilksLambda': result.wilks_lambda,
        'significantSNPs': [snp.to_dict() for snp in significant_snps],
        'visualizationFiles': [vf.to_dict() for vf in vis_files],
        'notes': result.notes,
        'createdAt': result.created_at.isoformat() if result.created_at else None
    }
    
    return jsonify(result_data), 200

def get_enrichment_result(task_id, task):
    result = EnrichmentResult.query.filter_by(task_id=task_id).first()
    
    if not result:
        return jsonify({'error': '结果不存在'}), 404
    
    vis_files = VisualizationFile.query.filter_by(enrichment_result_id=result.id).all()
    
    result_data = {
        'taskId': task_id,
        'taskType': task.task_type,
        'resultType': 'enrichment',
        'type': result.enrichment_type,
        'totalTermsAnalyzed': result.total_terms_analyzed,
        'significantTermsCount': result.significant_terms_count,
        'enrichmentData': result.enrichment_data,
        'barplotData': result.barplot_data,
        'networkData': result.network_data,
        'snpGeneMapping': result.snp_gene_mapping,
        'candidateGenes': result.candidate_genes,
        'visualizationFiles': [vf.to_dict() for vf in vis_files],
        'notes': result.notes,
        'createdAt': result.created_at.isoformat() if result.created_at else None
    }
    
    return jsonify(result_data), 200

def get_finemapping_result(task_id, task):
    result = FineMappingResult.query.filter_by(task_id=task_id).first()
    
    if not result:
        return jsonify({'error': '结果不存在'}), 404
    
    vis_files = VisualizationFile.query.filter_by(finemapping_result_id=result.id).all()
    
    result_data = {
        'taskId': task_id,
        'taskType': task.task_type,
        'resultType': 'finemapping',
        'regionChromosome': result.region_chromosome,
        'regionStart': result.region_start,
        'regionEnd': result.region_end,
        'nVariants': result.n_variants,
        'leadVariant': result.lead_variant,
        'credibleSets': result.credible_sets,
        'posteriorInclusionProbs': result.posterior_inclusion_probs,
        'modelPosteriors': result.model_posteriors,
        'ldMatrix': result.ld_matrix,
        'zScores': result.z_scores,
        'functionalScores': result.functional_scores,
        'manhattanData': result.manhattan_data,
        'credibleSetTable': result.credible_set_table,
        'visualizationFiles': [vf.to_dict() for vf in vis_files],
        'notes': result.notes,
        'createdAt': result.created_at.isoformat() if result.created_at else None
    }
    
    return jsonify(result_data), 200

@result_bp.route('/<task_id>/snps', methods=['GET'])
@jwt_required()
def get_significant_snps(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    gwas_result = GWASResult.query.filter_by(task_id=task_id).first()
    
    if not gwas_result:
        return jsonify({'error': '结果不存在'}), 404
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    chromosome = request.args.get('chr', None)
    min_log10p = request.args.get('minLog10P', None, type=float)
    
    query = SignificantSNP.query.filter_by(result_id=gwas_result.id)
    
    if chromosome:
        query = query.filter_by(chromosome=chromosome)
    if min_log10p:
        query = query.filter(SignificantSNP.log10_p >= min_log10p)
    
    total = query.count()
    snps = query.order_by(SignificantSNP.p_value) \
                .offset((page - 1) * page_size) \
                .limit(page_size) \
                .all()
    
    return jsonify({
        'total': total,
        'page': page,
        'pageSize': page_size,
        'snps': [snp.to_dict() for snp in snps]
    }), 200

@result_bp.route('/<task_id>/download/manhattan.png', methods=['GET'])
@jwt_required()
def download_manhattan(task_id):
    return _download_visualization(task_id, 'manhattan')

@result_bp.route('/<task_id>/download/qq.png', methods=['GET'])
@jwt_required()
def download_qq(task_id):
    return _download_visualization(task_id, 'qq')

@result_bp.route('/<task_id>/download/ld-heatmap.png', methods=['GET'])
@jwt_required()
def download_ld_heatmap(task_id):
    return _download_visualization(task_id, 'ld_heatmap')

def _download_visualization(task_id, file_type):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    gwas_result = GWASResult.query.filter_by(task_id=task_id).first()
    
    if not gwas_result:
        return jsonify({'error': '结果不存在'}), 404
    
    vis_file = VisualizationFile.query.filter_by(
        result_id=gwas_result.id,
        file_type=file_type
    ).first()
    
    if not vis_file or not os.path.exists(vis_file.file_path):
        from ..services.visualization_service import VisualizationService
        vis_service = VisualizationService()
        
        result_dir = os.path.join(os.path.dirname(vis_file.file_path), task_id) if vis_file else \
                     os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'results', user_id, task_id)
        os.makedirs(result_dir, exist_ok=True)
        
        if file_type == 'manhattan':
            file_path = os.path.join(result_dir, 'manhattan.png')
            vis_service.create_manhattan_plot(gwas_result.manhattan_data, file_path)
        elif file_type == 'qq':
            file_path = os.path.join(result_dir, 'qq.png')
            vis_service.create_qq_plot(gwas_result.qq_data, file_path)
        else:
            return jsonify({'error': '图片文件不存在'}), 404
    else:
        file_path = vis_file.file_path
    
    return send_file(
        file_path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'{task_id}_{file_type}.png'
    )

@result_bp.route('/<task_id>/download/snps.csv', methods=['GET'])
@jwt_required()
def download_snps_csv(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    gwas_result = GWASResult.query.filter_by(task_id=task_id).first()
    
    if not gwas_result:
        return jsonify({'error': '结果不存在'}), 404
    
    snps = SignificantSNP.query.filter_by(result_id=gwas_result.id) \
                                .order_by(SignificantSNP.p_value) \
                                .all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SNP', 'Chromosome', 'Position', 'Ref', 'Alt', 'P-value', '-log10(P)', 'Effect Size', 'MAF', 'Gene', 'Annotation'])
    
    for snp in snps:
        writer.writerow([
            snp.snp_id,
            snp.chromosome,
            snp.position,
            snp.ref_allele,
            snp.alt_allele,
            snp.p_value,
            snp.log10_p,
            snp.effect_size if snp.effect_size else '',
            snp.maf if snp.maf else '',
            snp.gene if snp.gene else '',
            snp.annotation if snp.annotation else ''
        ])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{task_id}_significant_snps.csv'
    )

@result_bp.route('/<task_id>/download/report.pdf', methods=['GET'])
@jwt_required()
def download_report(task_id):
    user_id = get_jwt_identity()
    task = AnalysisTask.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    gwas_result = GWASResult.query.filter_by(task_id=task_id).first()
    
    if not gwas_result:
        return jsonify({'error': '结果不存在'}), 404
    
    try:
        from ..services.report_service import ReportService
        report_service = ReportService()
        report_path = report_service.generate_pdf_report(task_id, gwas_result)
        
        return send_file(
            report_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{task_id}_gwas_report.pdf'
        )
    except Exception as e:
        return jsonify({'error': f'报告生成失败: {str(e)}'}), 500
