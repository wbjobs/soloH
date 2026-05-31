import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import uuid

from ..models.models import db, UploadFile
from ..services.vcf_parser import VCFParser
from ..services.file_service import FileService

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/vcf', methods=['POST'])
@jwt_required()
def upload_vcf():
    user_id = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名不能为空'}), 400
    
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in current_app.config['ALLOWED_VCF_EXTENSIONS']:
        return jsonify({'error': '不支持的文件格式，请上传VCF或VCF.GZ文件'}), 400
    
    user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], user_id, 'vcf')
    os.makedirs(user_upload_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    storage_filename = f"{file_id}_{filename}"
    storage_path = os.path.join(user_upload_dir, storage_filename)
    
    file.save(storage_path)
    file_size = os.path.getsize(storage_path)
    
    try:
        parser = VCFParser(storage_path)
        metadata = parser.parse_header()
        
        upload_file = UploadFile(
            id=file_id,
            user_id=user_id,
            file_name=filename,
            file_type='vcf',
            storage_path=storage_path,
            file_size=file_size,
            metadata=metadata
        )
        
        db.session.add(upload_file)
        db.session.commit()
        
        return jsonify({
            'fileId': file_id,
            'fileName': filename,
            'fileType': 'vcf',
            'sampleCount': metadata.get('sample_count', 0),
            'variantCount': metadata.get('variant_count', 0),
            'uploadTime': upload_file.uploaded_at.isoformat(),
            'chromosomes': metadata.get('chromosomes', [])
        }), 201
        
    except Exception as e:
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return jsonify({'error': f'VCF文件解析失败: {str(e)}'}), 400

@upload_bp.route('/phenotype', methods=['POST'])
@jwt_required()
def upload_phenotype():
    user_id = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名不能为空'}), 400
    
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in current_app.config['ALLOWED_CSV_EXTENSIONS']:
        return jsonify({'error': '不支持的文件格式，请上传CSV文件'}), 400
    
    user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], user_id, 'phenotype')
    os.makedirs(user_upload_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    storage_filename = f"{file_id}_{filename}"
    storage_path = os.path.join(user_upload_dir, storage_filename)
    
    file.save(storage_path)
    file_size = os.path.getsize(storage_path)
    
    try:
        file_service = FileService()
        metadata = file_service.parse_phenotype_csv(storage_path)
        
        upload_file = UploadFile(
            id=file_id,
            user_id=user_id,
            file_name=filename,
            file_type='phenotype',
            storage_path=storage_path,
            file_size=file_size,
            metadata=metadata
        )
        
        db.session.add(upload_file)
        db.session.commit()
        
        return jsonify({
            'fileId': file_id,
            'fileName': filename,
            'fileType': 'phenotype',
            'sampleCount': metadata.get('sample_count', 0),
            'phenotypeNames': metadata.get('phenotype_names', []),
            'uploadTime': upload_file.uploaded_at.isoformat()
        }), 201
        
    except Exception as e:
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return jsonify({'error': f'表型文件解析失败: {str(e)}'}), 400

@upload_bp.route('/covariate', methods=['POST'])
@jwt_required()
def upload_covariate():
    user_id = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名不能为空'}), 400
    
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in current_app.config['ALLOWED_CSV_EXTENSIONS']:
        return jsonify({'error': '不支持的文件格式，请上传CSV文件'}), 400
    
    user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], user_id, 'covariate')
    os.makedirs(user_upload_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    storage_filename = f"{file_id}_{filename}"
    storage_path = os.path.join(user_upload_dir, storage_filename)
    
    file.save(storage_path)
    file_size = os.path.getsize(storage_path)
    
    try:
        file_service = FileService()
        metadata = file_service.parse_covariate_csv(storage_path)
        
        upload_file = UploadFile(
            id=file_id,
            user_id=user_id,
            file_name=filename,
            file_type='covariate',
            storage_path=storage_path,
            file_size=file_size,
            metadata=metadata
        )
        
        db.session.add(upload_file)
        db.session.commit()
        
        return jsonify({
            'fileId': file_id,
            'fileName': filename,
            'fileType': 'covariate',
            'sampleCount': metadata.get('sample_count', 0),
            'covariateNames': metadata.get('covariate_names', []),
            'uploadTime': upload_file.uploaded_at.isoformat()
        }), 201
        
    except Exception as e:
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return jsonify({'error': f'协变量文件解析失败: {str(e)}'}), 400

@upload_bp.route('/preview/<file_id>', methods=['GET'])
@jwt_required()
def preview_file(file_id):
    user_id = get_jwt_identity()
    upload_file = UploadFile.query.filter_by(id=file_id, user_id=user_id).first()
    
    if not upload_file:
        return jsonify({'error': '文件不存在'}), 404
    
    limit = request.args.get('limit', 10, type=int)
    
    try:
        if upload_file.file_type == 'vcf':
            parser = VCFParser(upload_file.storage_path)
            preview_data = parser.get_preview(limit)
        else:
            file_service = FileService()
            preview_data = file_service.get_csv_preview(upload_file.storage_path, limit)
        
        return jsonify({
            'fileId': file_id,
            'fileType': upload_file.file_type,
            'preview': preview_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'文件预览失败: {str(e)}'}), 400

@upload_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    user_id = get_jwt_identity()
    file_type = request.args.get('type', None)
    
    query = UploadFile.query.filter_by(user_id=user_id)
    if file_type:
        query = query.filter_by(file_type=file_type)
    
    files = query.order_by(UploadFile.uploaded_at.desc()).all()
    
    return jsonify([{
        'fileId': f.id,
        'fileName': f.file_name,
        'fileType': f.file_type,
        'fileSize': f.file_size,
        'uploadTime': f.uploaded_at.isoformat() if f.uploaded_at else None,
        'metadata': f.metadata
    } for f in files]), 200

@upload_bp.route('/<file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    user_id = get_jwt_identity()
    upload_file = UploadFile.query.filter_by(id=file_id, user_id=user_id).first()
    
    if not upload_file:
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        if os.path.exists(upload_file.storage_path):
            os.remove(upload_file.storage_path)
        
        db.session.delete(upload_file)
        db.session.commit()
        
        return jsonify({'message': '文件删除成功'}), 200
        
    except Exception as e:
        return jsonify({'error': f'文件删除失败: {str(e)}'}), 500
