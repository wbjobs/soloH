import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from ..models.models import db, ReferenceGenome, GeneAnnotation

reference_bp = Blueprint('reference', __name__)

@reference_bp.route('/genomes', methods=['GET'])
@jwt_required()
def list_genomes():
    species = request.args.get('species', None)
    
    query = ReferenceGenome.query
    if species:
        query = query.filter_by(species=species)
    
    genomes = query.all()
    
    return jsonify([genome.to_dict() for genome in genomes]), 200

@reference_bp.route('/genomes/<genome_id>', methods=['GET'])
@jwt_required()
def get_genome(genome_id):
    genome = ReferenceGenome.query.get(genome_id)
    
    if not genome:
        return jsonify({'error': '参考基因组不存在'}), 404
    
    return jsonify(genome.to_dict()), 200

@reference_bp.route('/genomes/<genome_id>/genes', methods=['GET'])
@jwt_required()
def get_genes(genome_id):
    genome = ReferenceGenome.query.get(genome_id)
    
    if not genome:
        return jsonify({'error': '参考基因组不存在'}), 404
    
    chromosome = request.args.get('chr', None)
    start = request.args.get('start', None, type=int)
    end = request.args.get('end', None, type=int)
    gene_name = request.args.get('geneName', None)
    
    query = GeneAnnotation.query.filter_by(genome_id=genome_id)
    
    if chromosome:
        query = query.filter_by(chromosome=chromosome)
    if start and end:
        query = query.filter(
            (GeneAnnotation.start_pos <= end) & 
            (GeneAnnotation.end_pos >= start)
        )
    if gene_name:
        query = query.filter(GeneAnnotation.gene_name.like(f'%{gene_name}%'))
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    
    total = query.count()
    genes = query.order_by(GeneAnnotation.chromosome, GeneAnnotation.start_pos) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()
    
    return jsonify({
        'total': total,
        'page': page,
        'pageSize': page_size,
        'genes': [gene.to_dict() for gene in genes]
    }), 200

@reference_bp.route('/genomes/<genome_id>/annotate', methods=['POST'])
@jwt_required()
def annotate_snps(genome_id):
    genome = ReferenceGenome.query.get(genome_id)
    
    if not genome:
        return jsonify({'error': '参考基因组不存在'}), 404
    
    data = request.get_json()
    snps = data.get('snps', [])
    
    if not snps:
        return jsonify({'error': '未提供SNP数据'}), 400
    
    from ..services.annotation_service import AnnotationService
    annotation_service = AnnotationService()
    
    annotated_snps = annotation_service.annotate_snps(genome, snps)
    
    return jsonify({
        'genomeId': genome_id,
        'annotatedSNPs': annotated_snps
    }), 200

@reference_bp.route('/maize/inbred-lines', methods=['GET'])
@jwt_required()
def get_maize_inbred_lines():
    maize_genomes = ReferenceGenome.query.filter_by(species='Zea mays').all()
    
    inbred_lines = [
        {
            'id': 'B73_v5',
            'name': 'B73',
            'version': 'v5',
            'description': '玉米标准参考基因组，最广泛使用的自交系',
            'chromosomeCount': 10,
            'genomeSize': '2.3 Gb',
            'annotationVersion': 'AGPv5'
        },
        {
            'id': 'Mo17_v1',
            'name': 'Mo17',
            'version': 'v1',
            'description': '重要的玉米自交系，与B73杂交产生著名杂交种',
            'chromosomeCount': 10,
            'genomeSize': '2.2 Gb',
            'annotationVersion': 'v1.0'
        },
        {
            'id': 'W22_v2',
            'name': 'W22',
            'version': 'v2',
            'description': '常用的实验品系，遗传背景清晰',
            'chromosomeCount': 10,
            'genomeSize': '2.3 Gb',
            'annotationVersion': 'v2.0'
        },
        {
            'id': 'PH207_v1',
            'name': 'PH207',
            'version': 'v1',
            'description': '玉米父本系，重要的育种材料',
            'chromosomeCount': 10,
            'genomeSize': '2.1 Gb',
            'annotationVersion': 'v1.0'
        },
        {
            'id': 'B97_v1',
            'name': 'B97',
            'version': 'v1',
            'description': '耐旱自交系，抗逆性研究的重要材料',
            'chromosomeCount': 10,
            'genomeSize': '2.2 Gb',
            'annotationVersion': 'v1.0'
        }
    ]
    
    return jsonify(inbred_lines), 200
